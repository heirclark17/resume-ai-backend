"""
Career Path Synthesis Service
Uses Perplexity AI for web-grounded, thoroughly researched career plans with real data
Includes schema validation and JSON repair
"""
from typing import Dict, Any, Optional
from openai import OpenAI
from pydantic import ValidationError
import json
import os

from app.schemas.career_plan import (
    CareerPlan,
    IntakeRequest,
    ValidationResult,
    ValidationError as SchemaValidationError
)
from app.config import get_settings

settings = get_settings()


class CareerPathSynthesisService:
    """
    Synthesizes complete career plans using OpenAI with strict schema validation
    """

    def __init__(self):
        # Use OpenAI for reliable JSON generation
        if not settings.openai_api_key:
            if not settings.test_mode:
                raise ValueError(
                    "OPENAI_API_KEY not found. Please set it in Railway environment variables, "
                    "or set TEST_MODE=true to use mock data. "
                    "Railway dashboard -> Variables -> Add Variable -> OPENAI_API_KEY"
                )
            else:
                # TEST MODE: Don't initialize client, will use mock data
                self.client = None
                self.model = "test"
                print("[TEST MODE] CareerPathSynthesisService using mock data")
        else:
            self.client = OpenAI(api_key=settings.openai_api_key)
            # Use GPT-4.1-mini for fast, accurate career planning with 16K output limit
            self.model = "gpt-4.1-mini"

    async def generate_career_plan(
        self,
        intake: IntakeRequest,
        research_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate complete career plan with strict schema adherence

        Flow:
        1. Build comprehensive prompt with intake + research
        2. Call OpenAI with strict JSON schema
        3. Validate response against Pydantic schema
        4. If invalid, run repair pass
        5. Return validated plan or error
        """

        print(f"📝 Generating career plan for {intake.current_role_title} -> {intake.target_role_interest or 'TBD'}")

        # TEST MODE: Return mock career plan
        if settings.test_mode or self.client is None:
            print("[TEST MODE] Returning mock career plan")
            return await self._generate_mock_plan(intake)

        # Build synthesis prompt
        prompt = self._build_synthesis_prompt(intake, research_data)

        try:
            # Call OpenAI with JSON mode for guaranteed valid JSON
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},  # Ensures valid JSON
                temperature=0.7,
                max_tokens=16000  # GPT-4o-mini supports up to 16K output tokens
            )

            raw_json = response.choices[0].message.content
            print(f"✓ OpenAI returned {len(raw_json)} characters")

            # OpenAI JSON mode guarantees valid JSON - no cleaning needed
            plan_data = json.loads(raw_json)

            # Fix: Move research_sources to root level if OpenAI placed it inside resume_assets
            if "resume_assets" in plan_data and "research_sources" in plan_data.get("resume_assets", {}):
                if "research_sources" not in plan_data:
                    plan_data["research_sources"] = plan_data["resume_assets"]["research_sources"]
                    del plan_data["resume_assets"]["research_sources"]
                    print("✓ Moved research_sources from resume_assets to root level")

            validation_result = self._validate_plan(plan_data)

            if validation_result.valid:
                print("✓ Plan passed schema validation")
                return {
                    "success": True,
                    "plan": plan_data,
                    "validation": validation_result
                }

            # Validation failed - attempt repair
            print(f"⚠ Plan validation failed with {len(validation_result.errors)} errors")
            # Log first 5 errors for debugging
            for i, e in enumerate(validation_result.errors[:5]):
                print(f"  Error {i+1}: {e.field} - {e.error}")
                if hasattr(e, 'expected'):
                    print(f"      Expected: {e.expected}")
                if hasattr(e, 'received'):
                    print(f"      Received: {e.received}")
            print("🔧 Attempting JSON repair...")

            repaired = await self._repair_plan(plan_data, validation_result)

            if repaired["success"]:
                print("✓ Plan successfully repaired")
                return repaired
            else:
                print("✗ Repair failed")
                print(f"✗ Validation errors ({len(validation_result.errors)} total):")
                for i, e in enumerate(validation_result.errors[:10]):  # Show first 10
                    print(f"  {i+1}. Field: {e.field}")
                    print(f"      Error: {e.error}")
                    if hasattr(e, 'expected'):
                        print(f"      Expected: {e.expected}")
                    if hasattr(e, 'received'):
                        print(f"      Received: {e.received}")

                return {
                    "success": False,
                    "error": "Schema validation failed and repair unsuccessful",
                    "validation_errors": [
                        {"field": e.field, "error": e.error}
                        for e in validation_result.errors
                    ]
                }

        except json.JSONDecodeError as e:
            print(f"✗ JSON decode error: {e}")
            print(f"✗ Problematic JSON (first 500 chars):")
            print(raw_json[:500] if len(raw_json) > 500 else raw_json)
            print(f"✗ Problematic JSON (last 500 chars):")
            print(raw_json[-500:] if len(raw_json) > 500 else "")
            return {
                "success": False,
                "error": f"Invalid JSON from OpenAI: {str(e)}"
            }

        except Exception as e:
            print(f"✗ Synthesis error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    def _extract_and_clean_json(self, raw_text: str) -> str:
        """
        Extract and clean JSON from Perplexity response.
        Handles markdown code blocks, trailing commas, and other common issues.
        """
        import re

        # Step 1: Remove markdown code blocks
        text = raw_text.strip()
        if text.startswith("```"):
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # Step 2: Try to extract JSON object if embedded in other text
        # Find the first { and last }
        start_idx = text.find('{')
        end_idx = text.rfind('}')

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            text = text[start_idx:end_idx+1]

        # Step 3: Fix common JSON issues
        # Remove trailing commas before closing braces/brackets
        text = re.sub(r',(\s*[}\]])', r'\1', text)

        # Remove comments (// and /* */)
        text = re.sub(r'//.*?$', '', text, flags=re.MULTILINE)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

        # Step 4: Fix control characters in string values
        # JSON doesn't allow unescaped control characters (ASCII 0-31)
        # Replace common control characters with escaped versions
        control_char_fixes = {
            '\n': '\\n',
            '\r': '\\r',
            '\t': '\\t',
            '\b': '\\b',
            '\f': '\\f'
        }
        for char, escaped in control_char_fixes.items():
            text = text.replace(char, escaped)

        # Remove any remaining control characters (except those we escaped)
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)

        return text.strip()

    def _build_synthesis_prompt(
        self,
        intake: IntakeRequest,
        research_data: Dict[str, Any]
    ) -> str:
        """
        Build comprehensive prompt for OpenAI synthesis
        """

        # Extract research data
        certs = research_data.get("certifications", [])
        edu_options = research_data.get("education_options", [])
        events = research_data.get("events", [])
        sources = research_data.get("research_sources", [])

        prompt = f"""Generate a comprehensive career transition plan for this professional.

# USER PROFILE
- Current Role: {intake.current_role_title}
- Industry: {intake.current_industry}
- Years Experience: {intake.years_experience}
- Top 3 Tasks: {', '.join(intake.top_tasks[:3])}
- Tools/Technologies: {', '.join(intake.tools[:10])}
- Strengths: {', '.join(intake.strengths[:5])}
- Likes: {', '.join(intake.likes[:5])}
- Dislikes: {', '.join(intake.dislikes[:5])}

# TARGET
- Target Role Interest: {intake.target_role_interest or "To be determined - suggest 3-6 aligned roles"}
- Education Level: {intake.education_level}
- Location: {intake.location}
- Time Available: {intake.time_per_week} hours/week
- Timeline: {intake.timeline}
- Format Preference: {intake.in_person_vs_remote}

# WEB-GROUNDED RESEARCH DATA (USE THESE VERIFIED FACTS)
## Certifications Found ({len(certs)} options):
{json.dumps(certs[:5], indent=2) if certs else "None found"}

## Education Options Found ({len(edu_options)} options):
{json.dumps(edu_options[:3], indent=2) if edu_options else "None found"}

## Events Found ({len(events)} options):
{json.dumps(events[:5], indent=2) if events else "None found"}

## Source Citations ({len(sources)} sources):
{json.dumps(sources[:10], indent=2) if sources else "None"}

# YOUR TASK

Generate a complete career plan JSON object based on:
1. The user's background and goals above
2. Current industry best practices and trends
3. Your knowledge of typical requirements for target roles
4. The research data provided above (if any)

Match this EXACT schema:

{{
  "generated_at": "2026-01-16T12:00:00Z",
  "version": "1.0",
  "profile_summary": "150-500 char summary of user's background and transition goals",

  "target_roles": [
    {{
      "title": "Specific Job Title",
      "why_aligned": "How user's background maps to this role based on typical requirements",
      "growth_outlook": "Industry growth trends and demand, e.g., '23% growth 2024-2034 per BLS, strong demand in market'",
      "salary_range": "Typical salary range, e.g., '$95,000 - $135,000 for {intake.location} market'",
      "typical_requirements": ["Key skill for this role", "Another important skill", "Relevant certification or qualification"],
      "bridge_roles": [
        {{
          "title": "Bridge Role Title",
          "why_good_fit": "Why this is a stepping stone",
          "time_to_qualify": "3-6 months",
          "key_gaps_to_close": ["gap1", "gap2"]
        }}
      ],
      "source_citations": ["url1", "url2"]
    }}
  ],

  "skills_analysis": {{
    "already_have": [
      {{
        "skill_name": "Skill from user input",
        "evidence_from_input": "What in intake shows this",
        "target_role_mapping": "How this applies to target role",
        "resume_bullets": [
          "Achievement bullet demonstrating this skill",
          "Another bullet"
        ]
      }}
    ],
    "can_reframe": [
      {{
        "skill_name": "Skill to reposition",
        "current_context": "How user currently uses it",
        "target_context": "How target role uses it",
        "how_to_reframe": "Strategy for repositioning",
        "resume_bullets": ["Reframed bullet"]
      }}
    ],
    "need_to_build": [
      {{
        "skill_name": "Gap skill",
        "why_needed": "Why this matters for target role",
        "priority": "critical|high|medium",
        "how_to_build": "Learning strategy",
        "estimated_time": "X weeks/months"
      }}
    ]
  }},

  "certification_path": [
    Recommend relevant certifications for the target role.
    Sequence logically (foundation -> intermediate -> advanced).

    For EACH certification, provide:
    {{
      "name": "EXACT certification name from official body",
      "certifying_body": "e.g., CompTIA, AWS, Microsoft, ISC2, Google, etc.",
      "level": "foundation|intermediate|advanced",
      "prerequisites": ["List any prerequisite certs or experience"],
      "est_study_weeks": 12,
      "est_cost_range": "$XXX-$YYY (search official pricing)",
      "exam_details": {{
        "exam_code": "e.g., SAA-C03, 200-301, AZ-104",
        "passing_score": "e.g., 720/1000, 70%, 825/900",
        "duration_minutes": 130,
        "num_questions": 65,
        "question_types": "multiple choice, multiple response, etc."
      }},
      "official_links": ["Official cert page URL", "Exam registration URL"],
      "what_it_unlocks": "Specific career doors this opens",
      "alternatives": ["Alternative cert names that serve similar purpose"],
      "study_materials": [
        {{
          "type": "official-course|book|video-series|practice-exams|hands-on-labs",
          "title": "EXACT title from provider",
          "provider": "Official body, Udemy, Pluralsight, O'Reilly, A Cloud Guru, etc.",
          "url": "DIRECT link to resource (NO affiliate links)",
          "cost": "Free|$XX.XX|Included in subscription",
          "duration": "XX hours|XXX pages|XX practice exams",
          "description": "50-200 word description of what this resource covers and why it's valuable",
          "recommended_order": 1
        }},
        // Minimum 3-5 study materials per certification in recommended learning order:
        // 1. Official training (if available)
        // 2. Top-rated video course (Udemy, Pluralsight, etc.)
        // 3. Recommended book (O'Reilly, official study guide)
        // 4. Practice exams (Whizlabs, Tutorials Dojo, official practice tests)
        // 5. Hands-on labs (if applicable)
      ],
      "study_plan_weeks": [
        {{"week": 1, "focus": "Module 1: Fundamentals", "resources": "Official course chapters 1-3", "practice": "Quiz 1"}},
        {{"week": 2, "focus": "Module 2: Core concepts", "resources": "Video course sections 4-6", "practice": "Hands-on lab 1"}},
        // ...continue for est_study_weeks
        {{"week": 12, "focus": "Final review and exam", "resources": "Practice exams", "practice": "Full mock exam"}}
      ],
      "source_citations": ["All URLs where you found this data"]
    }}
  ],

  "education_options": [
    USE VERIFIED EDUCATION OPTIONS FROM RESEARCH.
    Include degrees, bootcamps, online courses, self-study.
    {{
      "type": "degree|bootcamp|self-study|online-course",
      "name": "Program name",
      "duration": "X weeks/months",
      "cost_range": "$X-$Y",
      "format": "online|in-person|hybrid",
      "official_link": "VERIFIED URL",
      "pros": ["pro1", "pro2", "pro3"],
      "cons": ["con1", "con2", "con3"],
      "source_citations": ["url"]
    }}
  ],

  "experience_plan": [
    Portfolio projects, volunteer work, labs, side projects with DETAILED TECH STACKS.
    Minimum 1, maximum 10. Provide 2-5 high-impact projects.

    For EACH project, provide EXTREME technical detail:
    {{
      "type": "portfolio|volunteer|lab|side-project|freelance",
      "title": "Clear, professional project title",
      "description": "100-300 words: What it does, why it's valuable for the target role, what problems it solves",
      "skills_demonstrated": ["skill1", "skill2", "skill3", "skill4", "skill5"],
      "detailed_tech_stack": [
        {{
          "name": "e.g., React 18, PostgreSQL, AWS Lambda",
          "category": "Frontend Framework|Backend|Database|Cloud Service|DevOps Tool|etc.",
          "why_this_tech": "50-150 words explaining WHY this specific technology is valuable for the target role. What employers look for with this tech. How it's used in production environments. Why it's industry-standard.",
          "learning_resources": [
            "Official documentation URL",
            "Top-rated course/tutorial URL",
            "Best practices guide URL",
            "Example GitHub repos"
          ]
        }},
        // Include 5-15 technologies covering:
        // - Frontend (if applicable)
        // - Backend/API
        // - Database
        // - Cloud/Infrastructure
        // - DevOps/CI-CD
        // - Testing
        // - Security
        // - Monitoring/Logging
      ],
      "architecture_overview": "100-200 words explaining the technical architecture: How components interact, data flow patterns, deployment architecture, why this architecture is industry-standard for this type of project",
      "difficulty_level": "beginner|intermediate|advanced",
      "step_by_step_guide": [
        "1. Set up development environment (specific tools needed)",
        "2. Create project structure and initial configuration",
        "3. Build core functionality (specific features)",
        "4. Implement authentication/authorization",
        "5. Add database and data persistence",
        "6. Create API endpoints or services",
        "7. Build UI/frontend (if applicable)",
        "8. Add testing (unit, integration)",
        "9. Deploy to cloud platform",
        "10. Set up CI/CD pipeline"
        // 5-10 high-level steps
      ],
      "time_commitment": "Realistic estimate: XX hours over X weeks (XX hrs/week)",
      "how_to_showcase": "How to present on resume (2-3 achievement bullets), LinkedIn project section template, what to include in GitHub README, how to discuss in interviews",
      "example_resources": ["Tutorial URLs", "Documentation", "Similar project examples"],
      "github_example_repos": [
        "https://github.com/user/similar-project-1",
        "https://github.com/user/similar-project-2",
        // 3-5 well-documented example repos
      ]
    }}
  ],

  "events": [
    Recommend relevant industry events and networking opportunities.
    Include: major conferences, regional events, local meetups, virtual options.
    Provide mix of local (in {intake.location}) and national events.

    For EACH event, provide details:
    {{
      "name": "Event name",
      "organizer": "Who runs this event (e.g., Linux Foundation, OWASP, local user group, company name)",
      "type": "conference|meetup|virtual|career-fair|workshop",
      "date_or_season": "Specific date if known, or recurring pattern (e.g., 'March 15-17, 2026', 'Every 2nd Thursday', 'Annual - Q2', 'Monthly meetup')",
      "location": "Specific city and venue for in-person, or 'Virtual', or 'Hybrid'",
      "scope": "local|regional|national|international",
      "price_range": "Typical pricing: Free|$50-$200|$500-$1500|etc.",
      "attendee_count": "Typical attendance: '5,000-8,000 attendees', 'Small group 20-30', '500-1000', etc.",
      "beginner_friendly": true|false,
      "target_audience": "Who this is for: 'Junior Developers', 'Security Professionals', 'Cloud Architects', 'Career Changers', etc.",
      "why_attend": "100-200 words: Specific networking opportunities (who attends - recruiters, hiring managers?), learning tracks, certifications/credits offered, hands-on labs, hiring/recruiting presence, speaker quality, why this specific event is valuable for career transition",
      "key_topics": ["Main topic 1", "Main topic 2", "Main topic 3", "Main topic 4", "Main topic 5"],
      "notable_speakers": ["Known speaker/company 1", "Known speaker/company 2"] or [] if not applicable,
      "registration_link": "https://example.com/event (use placeholder or omit if unavailable)",
      "recurring": true|false,
      "virtual_option_available": true|false,
      "source_citations": ["Event website URL", "Meetup.com URL", "etc."]
    }},

    // REQUIRED MIX:
    // - 2-3 major national/international conferences (even if expensive - good to know about)
    // - 3-5 regional or local in-person events in {intake.location}
    // - 5-10 virtual events (accessible from anywhere)
    // - Ongoing meetups (recurring community events)

    // RESEARCH SOURCES TO USE:
    // - Meetup.com for local groups in {intake.location}
    // - Eventbrite for workshops
    // - Conference websites (search: "[target role] conference 2026")
    // - Professional associations (ACM, IEEE, ISACA, etc.)
    // - LinkedIn Events for {intake.location}
    // - Tech company event calendars
  ],

  "timeline": {{
    "twelve_week_plan": [
      {{
        "week_number": 1,
        "tasks": ["task1", "task2", "task3"],
        "milestone": "Optional milestone",
        "checkpoint": "Optional apply-ready checkpoint"
      }}
      // ...weeks 2-12
    ],
    "six_month_plan": [
      {{
        "month_number": 1,
        "phase_name": "Foundation Phase",
        "goals": ["goal1", "goal2"],
        "deliverables": ["deliverable1"],
        "checkpoint": "Optional checkpoint"
      }}
      // ...months 2-6
    ],
    "apply_ready_checkpoint": "When user can start applying (e.g., 'After week 8')"
  }},

  "resume_assets": {{
    // PROVIDE EXTREME DETAIL AND GUIDANCE FOR RESUME TRANSFORMATION

    // === HEADLINE & SUMMARY ===
    "headline": "Optimized LinkedIn/resume headline for target role (max 200 chars)",
    "headline_explanation": "100-200 words: WHY this headline is effective. Explain keyword choices, positioning strategy, ATS optimization, what makes it stand out to recruiters. Reference job posting analysis.",

    "summary": "100-1000 char professional summary for resume following PROBLEM-SOLUTION-RESULT framework",
    "summary_breakdown": "200-400 words: Detailed sentence-by-sentence explanation of the summary. For EACH sentence explain: What it does, why it works, what keywords it includes, how it positions the candidate. Show the strategic intent behind each phrase.",
    "summary_strategy": "100-200 words: Overall strategy behind this summary. How does it address hiring manager concerns? What framework does it follow? How does it balance technical skills with business impact?",

    // === SKILLS SECTION ===
    "skills_grouped": [
      {{
        "category": "e.g., Cloud Platforms, Programming Languages, DevOps Tools",
        "skills": ["skill1", "skill2", "skill3", "skill4"],
        "why_group_these": "50-100 words: Why these skills are grouped together, how they relate to the target role, why this categorization is strategic",
        "priority": "core|important|supplementary"
      }},
      // Minimum 2-4 skill groups covering different technical areas
    ],
    "skills_ordering_rationale": "100-200 words: Explain the overall skills ordering strategy. Why are skills ordered this way? What's the logic (market demand, ATS optimization, career level signaling)? How does this maximize visibility?",

    // === ACHIEVEMENT BULLETS ===
    "target_role_bullets": [
      {{
        "bullet_text": "50-300 char achievement bullet following CAR/STAR method with specific metrics",
        "why_this_works": "50+ chars: Detailed explanation of why this bullet is effective. How does it demonstrate value? What makes the metrics credible? Why does this matter to hiring managers?",
        "what_to_emphasize": "When discussing this in interviews, emphasize: [specific talking points, complexity indicators, leadership aspects]",
        "keywords_included": ["keyword1", "keyword2", "keyword3"],
        "structure_explanation": "How this follows CAR/STAR method: Challenge/Situation → Action → Result. Break down each component."
      }},
      // Minimum 3, maximum 10 bullets. Provide 5-8 high-impact bullets.
      // Cover variety: technical execution, leadership, business impact, innovation
    ],
    "bullets_overall_strategy": "150-300 words: How do these bullets collectively position the candidate? What story do they tell? How do they progress from technical → leadership → business impact? What percentage of job description keywords do they hit?",

    // === EXPERIENCE REFRAMING ===
    "how_to_reframe_current_role": "200-400 words: DETAILED guide on repositioning current experience for target role. Explain title approach, which responsibilities to emphasize vs. de-emphasize, language shifts (engineer → architect), specific reframes for common scenarios. Provide before/after examples.",
    "experience_gaps_to_address": [
      "Gap 1: [description] - Strategy: [how to address this gap through positioning]",
      "Gap 2: [description] - Strategy: [how to spin this positively]",
      // Address 2-5 common gaps or concerns
    ],

    // === KEYWORDS & ATS ===
    "keywords_for_ats": ["keyword1", "keyword2", "keyword3", ...],  // 5-15 keywords
    "keyword_placement_strategy": "100-200 words: WHERE and HOW to naturally incorporate keywords. Which keywords in summary? Which in skills? How to avoid keyword stuffing while maximizing ATS matching? Long-tail vs. generic keywords strategy.",

    // === LINKEDIN OPTIMIZATION ===
    "linkedin_headline": "220-char optimized LinkedIn headline (different from resume, search-optimized)",
    "linkedin_about_section": "200-2000 char LinkedIn about section. Expanded version of resume summary with: opening hook, specialization paragraph, approach/philosophy, key achievements, current focus, call to action.",
    "linkedin_strategy": "100-200 words: How to optimize LinkedIn beyond the profile. Content strategy (posting frequency, topics), connection strategy, group participation, Open to Work settings, featured section optimization.",

    // === COVER LETTER ===
    "cover_letter_template": "500-1000 char customizable cover letter framework following PROBLEM-SOLUTION-FIT structure. Include [PLACEHOLDERS] for company-specific customization. Opening hook referencing company pain points, body paragraphs matching requirements, cultural fit statement, clear call to action.",
    "cover_letter_guidance": "200-400 words: How to adapt this template for different companies. Required research checklist (15 min before writing). Personalization points to customize. Tone adjustment by company type (startup vs. enterprise). Length optimization. What NOT to include."
  }},

  "research_sources": {json.dumps(sources[:20], indent=2)}
}}

# CRITICAL REQUIREMENTS
1. **COMPLETE ALL FIELDS**: Provide comprehensive career guidance based on your knowledge of industry practices. Use placeholders for URLs if needed.
2. **Study Materials**: Each certification should have 2-3 study materials with descriptions (50-150 words each)
3. **Tech Stack Details**: Each project should have 3-5 key technologies, each with a brief "why_this_tech" explanation
4. **Event Details**: Each event should have organizer, scope, attendee_count, target_audience, key_topics, and "why_attend" explanation
5. **Resume Guidance**: Provide practical resume guidance including headlines, summaries, and bullet point strategies.
6. **MINIMUM ITEMS REQUIRED (validate before submitting)**:
   - target_roles: At least 1
   - skills_analysis.already_have: At least 1
   - skills_analysis.need_to_build: At least 1
   - certification_path: At least 1 (with source_citations having at least 1 URL)
   - education_options: At least 1 (degree programs, bootcamps, or self-study paths)
   - experience_plan: At least 1
   - events: At least 1 (conferences, meetups, or networking opportunities)
   - timeline.twelve_week_plan: EXACTLY 12 weekly tasks (one per week, Week 1 through Week 12)
   - timeline.six_month_plan: EXACTLY 6 monthly phases (Month 1 through Month 6)
   - resume_assets.skills_grouped: At least 2 skill groups
   - research_sources: At least 1 source (can be placeholder like "Industry research and market data")
7. **FIELD TYPE REQUIREMENTS**:
   - Week fields (in study_plan_weeks): MUST be strings like "Week 1", "Week 2", NOT numbers
   - what_to_emphasize: MUST be a single string (NOT a list/array), e.g., "Technical leadership in cloud security"
   - profile_summary: 150-500 characters (MUST NOT EXCEED 500)
   - All URL fields: Can use placeholders like "https://example.com/..." if real URLs unavailable
8. **Timeline Requirements**: twelve_week_plan must have 12 weekly tasks (Week 1-12), six_month_plan must have 6 monthly phases (Month 1-6)
9. **Certification Sequencing**: Order foundation → intermediate → advanced with clear prerequisites
10. **JSON Only**: Return ONLY valid JSON - no markdown code blocks, no explanatory text before/after

IMPORTANT: Your response must be ONLY a JSON object. Do not include:
- Markdown code blocks (no ```json or ```)
- Explanatory text before or after the JSON
- Comments or notes
- Just the raw JSON starting with {{ and ending with }}

Generate the plan now:"""

        return prompt

    def _get_system_prompt(self) -> str:
        """System prompt for OpenAI career plan generation"""

        return """You are an EXPERT career transition advisor. You provide CONCISE, actionable career guidance based on industry best practices and current market trends.

CRITICAL REQUIREMENTS:
1. **COMPLETE RESPONSES**: Generate career plans with ALL required sections filled
2. **NO EMPTY LISTS**: Every list field (target_roles, skills, certifications, etc.) must have at least the minimum required items
3. **CONCISE EXPLANATIONS**: Be clear and specific but brief (20-100 words per explanation field, not per section)
4. **VALID JSON ONLY**: Return ONLY a valid JSON object - no markdown, no text before/after
5. **BREVITY**: Keep all text fields concise. Profile_summary under 400 characters.

YOU MUST PROVIDE:

**Target Roles (1-3 roles):**
- Specific job titles aligned with user's experience and interests
- Salary ranges based on current market data
- Growth outlook and demand trends
- Required qualifications and experience

**Skills Analysis:**
- Already Have: Identify 3-5 transferable skills from their background
- Need to Build: Identify 3-5 skills gaps for target roles
- Include evidence and how to build each skill

**Skills Guidance (REQUIRED - separate from Skills Analysis):**
- Soft Skills (3-8 items): Communication, leadership, problem-solving, collaboration, time management, etc.
  * For EACH soft skill: why_needed (100+ chars), how_to_improve (150+ chars), importance (critical/high/medium), estimated_time, resources (URLs), real_world_application (100+ chars)
- Hard Skills (3-10 items): Technical/domain-specific skills for target role
  * For EACH hard skill: Same detailed structure as soft skills
- skill_development_strategy: Overall strategy for building both soft and hard skills in parallel (200+ chars)

**Certifications (1-3 relevant certs):**
- Industry-recognized certifications for target role
- Cost estimates and study time (keep brief)

**Projects (2-3 portfolio projects):**
- Hands-on projects that demonstrate target role skills
- Key technologies (3-5 per project, keep descriptions under 30 words)

**Resume Guidance:**
- Concise headlines and bullet point examples
- Brief LinkedIn and cover letter tips

**Timeline (12-week plan with 12 weekly tasks):**
- Specific, actionable weekly tasks (keep descriptions under 50 words each)
- 6 monthly phases (keep descriptions under 50 words each)

YOU MUST:
- Return ONLY valid JSON (no markdown code blocks like ```json)
- Match the exact schema structure provided in the user prompt
- Fill ALL required fields - no empty lists or null values for required fields
- Keep profile_summary under 500 characters
- Provide at least the minimum number of items for each list field
- Use proper JSON syntax (double quotes, no trailing commas)

CRITICAL: Your response must be a single valid JSON object starting with { and ending with }. No other text."""

    def _validate_plan(self, plan_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate plan against Pydantic schema

        Returns ValidationResult with errors if invalid
        """

        try:
            # Attempt to parse with Pydantic
            CareerPlan(**plan_data)

            return ValidationResult(valid=True, errors=[])

        except ValidationError as e:
            # Extract validation errors
            errors = []
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                errors.append(SchemaValidationError(
                    field=field,
                    error=error["msg"],
                    expected=error["type"],
                    received=error.get("input", "unknown")
                ))

            return ValidationResult(
                valid=False,
                errors=errors,
                repaired=False
            )

        except Exception as e:
            return ValidationResult(
                valid=False,
                errors=[SchemaValidationError(
                    field="unknown",
                    error=str(e),
                    expected="valid data",
                    received="unknown"
                )],
                repaired=False
            )

    async def _repair_plan(
        self,
        invalid_plan: Dict[str, Any],
        validation_result: ValidationResult
    ) -> Dict[str, Any]:
        """
        Attempt to repair invalid JSON using OpenAI

        Sends the invalid JSON + validation errors to OpenAI
        and asks it to fix the issues
        """

        error_summary = "\n".join([
            f"- Field '{e.field}': {e.error} (expected: {e.expected}, got: {e.received})"
            for e in validation_result.errors[:25]  # Limit to top 25 errors for better repair
        ])

        repair_prompt = f"""The following JSON failed schema validation with these errors:

{error_summary}

INVALID JSON:
{json.dumps(invalid_plan, indent=2)}

Fix ALL validation errors and return a corrected JSON object that passes validation.

Requirements:
1. Keep all existing data where possible
2. Fix missing required fields by adding realistic values
3. Fix type mismatches (e.g., string vs array)
4. Ensure array minimum/maximum item constraints are met
5. Ensure string length constraints are met
6. Remove any invalid keys not in schema
7. Return ONLY the corrected JSON - no explanations

Return the fixed JSON now:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a JSON repair specialist. Fix validation errors precisely."
                    },
                    {
                        "role": "user",
                        "content": repair_prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for precise repairs
                max_tokens=16000  # Perplexity doesn't support response_format parameter
            )

            repaired_json = response.choices[0].message.content
            repaired_data = json.loads(repaired_json)

            # Validate repaired version
            validation = self._validate_plan(repaired_data)

            if validation.valid:
                return {
                    "success": True,
                    "plan": repaired_data,
                    "validation": validation,
                    "repaired": True
                }
            else:
                return {
                    "success": False,
                    "error": "Repair attempt failed validation",
                    "validation_errors": [
                        {"field": e.field, "error": e.error}
                        for e in validation.errors
                    ]
                }

        except Exception as e:
            print(f"✗ Repair failed: {e}")
            return {
                "success": False,
                "error": f"Repair exception: {str(e)}"
            }

    async def _generate_mock_plan(self, intake: IntakeRequest) -> Dict[str, Any]:
        """Generate a mock career plan for testing when Perplexity API is unavailable"""
        from datetime import datetime, timedelta

        target_role = intake.target_role_interest or "Senior Professional"
        location = intake.location or "Remote"

        mock_plan = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "version": "1.0",
            "profile_summary": f"Professional transitioning from {intake.current_role_title or 'current role'} to {target_role} with {intake.years_experience or 5}+ years of experience. This is TEST MODE data.",

            "target_roles": [
                {
                    "title": target_role,
                    "why_aligned": f"Your background in {intake.current_role_title or 'your field'} provides strong foundation for this role.",
                    "growth_outlook": "[TEST MODE] 15% projected growth through 2030 based on market analysis",
                    "salary_range": f"[TEST MODE] $85,000 - $135,000 in {location}",
                    "typical_requirements": [
                        f"{intake.years_experience or 5}+ years relevant experience",
                        "Strong communication skills",
                        "Industry certifications preferred"
                    ]
                }
            ],

            "skills_analysis": {
                "already_have": [
                    {
                        "skill_name": skill,
                        "evidence_from_input": f"Listed as strength in intake",
                        "target_role_mapping": f"Your {skill} experience applies directly to {target_role}",
                        "resume_bullets": [
                            f"Demonstrated {skill} through {intake.years_experience or 5}+ years of experience",
                            f"Applied {skill} to achieve measurable outcomes"
                        ]
                    }
                    for skill in (intake.strengths[:3] if intake.strengths else ["Problem Solving", "Communication", "Leadership"])
                ],
                "need_to_build": [
                    {
                        "skill_name": "Advanced Technical Skills",
                        "why_needed": "Required for senior-level responsibilities",
                        "priority": "high",
                        "how_to_build": "Take online courses and earn certifications",
                        "estimated_time": "12 weeks"
                    }
                ],
                "gaps_analysis": f"[TEST MODE] Based on your background in {intake.current_role_title or 'your field'}, focus on building advanced technical skills and industry-specific knowledge."
            },

            "certifications": [
                {
                    "name": "Industry-Standard Professional Certification",
                    "level": "intermediate",
                    "prerequisites": ["1-2 years experience"],
                    "est_study_weeks": 12,
                    "est_cost_range": "$300-$600",
                    "official_links": ["https://example.com/certification"],
                    "what_it_unlocks": "Industry credibility and career advancement",
                    "alternatives": []
                }
            ],

            "education_options": [
                {
                    "type": "online-course",
                    "name": "Professional Development Program",
                    "duration": "12-16 weeks",
                    "cost_range": "$500-$2000",
                    "format": "online",
                    "official_link": "https://example.com/program",
                    "pros": ["Flexible schedule", "Industry-recognized", "Practical skills"],
                    "cons": ["Requires self-discipline", "No degree credit"]
                }
            ],

            "experience_plan": [
                {
                    "project_type": "Professional Development Project",
                    "what_to_build": f"Build a project demonstrating {target_role} skills",
                    "skills_demonstrated": intake.strengths[:3] if intake.strengths else ["Leadership", "Technical Skills"],
                    "timeline_weeks": 8,
                    "portfolio_worthy": True,
                    "resume_bullet": f"[TEST MODE] Led professional development project demonstrating {target_role} competencies"
                }
            ],

            "bridge_roles": [
                {
                    "title": f"Mid-Level {target_role}",
                    "why_stepping_stone": "Provides pathway to senior role",
                    "typical_duration": "1-2 years",
                    "key_experiences_to_gain": ["Advanced technical skills", "Leadership experience"]
                }
            ],

            "events": [
                {
                    "name": "Industry Professional Conference",
                    "type": "conference",
                    "date_or_season": "Annual - Check website",
                    "location": location,
                    "price_range": "$200-$500",
                    "beginner_friendly": True,
                    "why_attend": "Network with industry professionals and learn latest trends",
                    "registration_link": "https://example.com/event"
                }
            ],

            "timeline": {
                "milestones": [
                    {
                        "phase": "Foundation Building",
                        "start_month": 1,
                        "end_month": 3,
                        "deliverables": ["Complete foundational certification", "Build initial portfolio project"]
                    },
                    {
                        "phase": "Skill Development",
                        "start_month": 4,
                        "end_month": 8,
                        "deliverables": ["Advanced training", "Professional networking"]
                    },
                    {
                        "phase": "Job Search",
                        "start_month": 9,
                        "end_month": 12,
                        "deliverables": ["Resume optimization", "Interview preparation", "Job applications"]
                    }
                ],
                "total_months": 12,
                "notes": "[TEST MODE] This is a mock timeline for testing purposes"
            },

            "resume_assets": {
                "summary": f"[TEST MODE] Experienced {intake.current_role_title or 'professional'} with {intake.years_experience or 5}+ years transitioning to {target_role}. Proven track record of success.",
                "skills_section": intake.strengths[:8] if intake.strengths else ["Leadership", "Communication", "Problem Solving", "Technical Skills", "Project Management"],
                "target_role_bullets": [
                    f"[TEST MODE] Led {intake.current_role_title or 'professional'} initiatives",
                    "[TEST MODE] Achieved measurable results through strategic planning",
                    "[TEST MODE] Collaborated with cross-functional teams"
                ],
                "keywords_for_ats": [target_role] + (intake.strengths[:5] if intake.strengths else ["Leadership", "Management", "Strategy"])
            },

            "research_sources": [
                "https://example.com/source1",
                "https://example.com/source2"
            ]
        }

        return {
            "success": True,
            "plan": mock_plan,
            "validation": ValidationResult(valid=True, errors=[]),
            "test_mode": True
        }
