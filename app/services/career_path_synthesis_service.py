"""
Career Path Synthesis Service
Uses Perplexity AI for web-grounded, thoroughly researched career plans with real data
Includes schema validation and JSON repair
"""
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
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
from app.services.gateway import get_gateway

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
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            # Use GPT-4.1-mini for career plans
            self.model = "gpt-4.1-mini"

    def _compute_intake_variables(self, intake: IntakeRequest) -> Dict[str, Any]:
        """Compute derived variables from intake for prompt engineering"""
        # Total hours available
        timeline_weeks = {"3months": 13, "6months": 26, "12months": 52}.get(intake.timeline, 26)
        total_hours = timeline_weeks * intake.time_per_week

        # Experience tier
        yrs = intake.years_experience
        if yrs <= 3:
            experience_tier = "early-career"
        elif yrs <= 10:
            experience_tier = "mid-career"
        elif yrs <= 20:
            experience_tier = "experienced"
        else:
            experience_tier = "senior"

        # Budget tier
        budget = (intake.training_budget or "").lower()
        if "employer" in budget:
            budget_tier = "flexible"
        elif "5k" in budget or "5K" in budget:
            budget_tier = "comfortable"
        elif "2k" in budget or "2K" in budget:
            budget_tier = "moderate"
        elif "500" in budget or not budget:
            budget_tier = "shoestring"
        else:
            budget_tier = "moderate"

        # Head start detection
        has_head_start = intake.already_started and bool(intake.steps_already_taken and intake.steps_already_taken.strip())

        return {
            "total_hours": total_hours,
            "timeline_weeks": timeline_weeks,
            "experience_tier": experience_tier,
            "budget_tier": budget_tier,
            "has_head_start": has_head_start,
        }

    def _validate_plan_quality(self, plan_data: Dict[str, Any], intake: IntakeRequest, computed: Dict[str, Any]) -> None:
        """
        Advisory-only quality checks — logged warnings, never blocks response.
        Checks that the AI output respects user context (dream role, hours, certs, concern, tools, head-start).
        """
        warnings = []

        try:
            # 1. Dream role should be target_roles[0] with highest match_score
            target_roles = plan_data.get("target_roles", [])
            dream = intake.target_role_interest or ""
            if target_roles and dream:
                first_role = target_roles[0].get("role_title", "") if isinstance(target_roles[0], dict) else ""
                if dream.lower() not in first_role.lower() and first_role.lower() not in dream.lower():
                    warnings.append(f"Dream role '{dream}' is not first in target_roles (got '{first_role}')")

            # 2. Weekly hours in 12-week plan shouldn't exceed time_per_week
            twelve_week = plan_data.get("twelve_week_action_plan", [])
            for week in twelve_week:
                hours = week.get("hours_this_week", 0) if isinstance(week, dict) else 0
                if hours > intake.time_per_week * 1.5:  # Allow 50% buffer
                    warnings.append(f"Week {week.get('week', '?')} has {hours}hrs, exceeds {intake.time_per_week}hrs/week budget")
                    break  # Only warn once

            # 3. No cert in certification_path should duplicate existing_certifications
            existing = [c.lower().strip() for c in (intake.existing_certifications or [])]
            if existing:
                cert_path = plan_data.get("certification_path", [])
                for cert in cert_path:
                    cert_name = (cert.get("name", "") if isinstance(cert, dict) else "").lower()
                    for ec in existing:
                        if ec in cert_name or cert_name in ec:
                            warnings.append(f"Cert '{cert.get('name', '')}' may duplicate existing cert '{ec}'")

            # 4. Skills guidance should reference at least 2 of user's tools
            tools = intake.tools or []
            if len(tools) >= 2:
                plan_text = json.dumps(plan_data.get("skills_guidance", {})).lower()
                referenced = sum(1 for t in tools if t.lower() in plan_text)
                if referenced < 2:
                    warnings.append(f"Skills guidance references only {referenced} of {len(tools)} user tools")

            # 5. Biggest concern keywords should appear in plan
            concern = intake.biggest_concern or ""
            if concern:
                concern_words = [w.lower() for w in concern.split() if len(w) > 4]
                plan_text_full = json.dumps(plan_data).lower()
                found = sum(1 for w in concern_words if w in plan_text_full)
                if found == 0 and concern_words:
                    warnings.append(f"Biggest concern '{concern}' keywords not found in plan text")

            # 6. If has_head_start, Week 1 shouldn't repeat steps already taken
            if computed.get("has_head_start") and twelve_week:
                steps = (intake.steps_already_taken or "").lower()
                week1 = twelve_week[0] if twelve_week else {}
                week1_text = json.dumps(week1).lower()
                step_words = [w for w in steps.split() if len(w) > 5]
                overlap = sum(1 for w in step_words[:10] if w in week1_text)
                if overlap > 3:
                    warnings.append(f"Week 1 may repeat steps already taken ({overlap} keyword overlaps)")

        except Exception as e:
            warnings.append(f"Quality validation error: {e}")

        # Log warnings (advisory only)
        if warnings:
            print(f"⚠ Plan quality warnings ({len(warnings)}):")
            for w in warnings:
                print(f"  - {w}")
        else:
            print("✓ Plan passed all quality checks")

    async def generate_career_plan(
        self,
        intake: IntakeRequest,
        research_data: Dict[str, Any],
        job_details: Optional[Dict[str, Any]] = None
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

        # Compute derived variables
        computed = self._compute_intake_variables(intake)

        # Build synthesis prompt
        prompt = self._build_synthesis_prompt(intake, research_data, job_details=job_details, computed=computed)

        try:
            # Call OpenAI with JSON mode for guaranteed valid JSON
            response = await get_gateway().execute(
                "openai",
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(intake=intake, computed=computed)
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},  # Ensures valid JSON
                temperature=0.75,
                max_tokens=32000  # GPT-4.1 supports up to 32K output tokens for maximum detail
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

            # Apply deterministic type coercions before Pydantic validation
            plan_data = self._pre_validate_coerce(plan_data)

            validation_result = self._validate_plan(plan_data)

            if validation_result.valid:
                print("✓ Plan passed schema validation")
                # Advisory quality checks (never blocks response)
                self._validate_plan_quality(plan_data, intake, computed)
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
                self._validate_plan_quality(repaired.get("plan", {}), intake, computed)
                return repaired
            else:
                # Repair failed — return the original plan anyway (non-blocking validation)
                # The frontend handles missing/incomplete data gracefully
                print("⚠ Repair failed, returning plan with validation warnings (non-blocking)")
                print(f"⚠ Validation errors ({len(validation_result.errors)} total):")
                for i, e in enumerate(validation_result.errors[:10]):
                    print(f"  {i+1}. Field: {e.field}")
                    print(f"      Error: {e.error}")

                # Advisory quality checks (never blocks response)
                self._validate_plan_quality(plan_data, intake, computed)
                return {
                    "success": True,
                    "plan": plan_data,
                    "validation": validation_result,
                    "validation_warnings": [
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

    def _build_job_posting_section(self, job_details: Optional[Dict[str, Any]]) -> str:
        """Build the job posting section for the prompt if job_details are available"""
        if not job_details:
            return ""

        skills = job_details.get('skills_required', [])
        skills_str = ', '.join(skills) if skills else 'Not specified'
        description = job_details.get('description', '')
        if len(description) > 3000:
            description = description[:3000] + '...'

        return f"""# TARGET JOB POSTING (TAILOR THE PLAN TO THIS SPECIFIC JOB)
- Company: {job_details.get('company', 'Unknown')}
- Job Title: {job_details.get('title', 'Unknown')}
- Location: {job_details.get('location', 'Not specified')}
- Salary: {job_details.get('salary', 'Not specified')}
- Experience Level: {job_details.get('experience_level', 'Not specified')}
- Required Skills: {skills_str}
- Job Description: {description}

IMPORTANT: Since the user is targeting THIS specific job:
1. Make the PRIMARY target role match this job title
2. Analyze skills gaps against THIS job's requirements
3. Prioritize certs/training that THIS job lists or implies
4. Tailor resume assets for THIS role at THIS company
5. Timeline should focus on becoming qualified for THIS position

"""

    def _format_salary_insights(self, salary_insights: Dict[str, Any]) -> str:
        """Format Perplexity salary insights for inclusion in prompt"""
        if not salary_insights:
            return "No real-time salary data available. Use industry knowledge for estimates."

        formatted = []
        for role, data in salary_insights.items():
            if isinstance(data, dict) and "salary_range" in data:
                formatted.append(f"- {role}: {data['salary_range']}")
                if data.get("market_insights"):
                    # Extract first 200 chars of insights
                    insights = data["market_insights"][:200]
                    formatted.append(f"  Market: {insights}...")

        if not formatted:
            return "Salary research completed but no data extracted. Use industry knowledge."

        result = "\n".join(formatted)
        result += "\n\n**IMPORTANT**: Use the exact salary ranges above for target_roles. These are web-grounded, real-time data from Perplexity."
        return result

    def _build_synthesis_prompt(
        self,
        intake: IntakeRequest,
        research_data: Dict[str, Any],
        job_details: Optional[Dict[str, Any]] = None,
        computed: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build comprehensive prompt for OpenAI synthesis with enhanced context
        """

        # Compute if not provided
        if computed is None:
            computed = self._compute_intake_variables(intake)

        # Extract research data
        certs = research_data.get("certifications", [])
        edu_options = research_data.get("education_options", [])
        events = research_data.get("events", [])
        sources = research_data.get("research_sources", [])

        # Extract raw Perplexity research content for direct prompt injection
        # Truncate each to 3000 chars to prevent prompt overflow that causes truncated JSON
        raw_cert_content = research_data.get("raw_certification_content", "")[:3000]
        raw_edu_content = research_data.get("raw_education_content", "")[:3000]
        raw_events_content = research_data.get("raw_events_content", "")[:3000]
        if research_data.get("raw_certification_content", "") and len(research_data.get("raw_certification_content", "")) > 3000:
            raw_cert_content += "\n[...truncated for length, use key facts above...]"
        if research_data.get("raw_education_content", "") and len(research_data.get("raw_education_content", "")) > 3000:
            raw_edu_content += "\n[...truncated for length, use key facts above...]"
        if research_data.get("raw_events_content", "") and len(research_data.get("raw_events_content", "")) > 3000:
            raw_events_content += "\n[...truncated for length, use key facts above...]"
        cert_citation_urls = research_data.get("cert_citation_urls", [])
        edu_citation_urls = research_data.get("edu_citation_urls", [])

        # Build enhanced user profile
        existing_certs_str = ", ".join(intake.existing_certifications) if intake.existing_certifications else "None"
        tools_str = ", ".join(intake.tools[:10]) if intake.tools else "Not specified"
        dislikes_str = ", ".join(intake.dislikes[:5]) if intake.dislikes else "None listed"
        likes_str = ", ".join(intake.likes[:5]) if intake.likes else "Not specified"
        companies_str = ", ".join(intake.specific_companies[:5]) if intake.specific_companies else "None"
        platforms_str = ", ".join(intake.preferred_platforms[:5]) if intake.preferred_platforms else "Not specified"
        tech_interests_str = ", ".join(intake.specific_technologies_interest[:5]) if intake.specific_technologies_interest else "Not specified"
        cert_interests_str = ", ".join(intake.certification_areas_interest[:5]) if intake.certification_areas_interest else "Not specified"

        # Build conditional instructions
        conditional_instructions = ""

        if intake.biggest_concern:
            conditional_instructions += f"""
## CONCERN THREADING
The user's biggest concern is: "{intake.biggest_concern}"
You MUST address this concern in at least 3 places:
1. In the profile_summary or skills_guidance strategy
2. In at least one timeline task or milestone
3. In the resume_assets section (how to position despite this concern)
Do NOT add a generic "don't worry" paragraph. Instead, give concrete steps that directly mitigate this concern.
"""

        if computed["has_head_start"]:
            conditional_instructions += f"""
## HEAD-START AWARENESS
The user has already started their transition and completed: "{intake.steps_already_taken}"
- Week 1 of the timeline must NOT repeat what they already did
- Acknowledge their progress in the profile_summary
- Skip recommending certifications they already hold: {existing_certs_str}
- Build on their momentum - suggest NEXT steps, not starting-from-scratch steps
"""

        if intake.existing_certifications:
            conditional_instructions += f"""
## CERT DEDUPLICATION
The user already holds: {existing_certs_str}
Do NOT recommend any of these certifications again. Recommend the NEXT level up or complementary certs.
"""

        if computed["budget_tier"] == "shoestring":
            conditional_instructions += """
## BUDGET GUARDRAILS (SHOESTRING)
User has very limited budget. Prioritize:
- Free resources (YouTube, official documentation, free tier cloud accounts)
- Low-cost options (Udemy sales, Coursera financial aid, free community events)
- Do NOT recommend expensive bootcamps ($5K+) or premium certifications as first steps
"""

        prompt = f"""Generate a comprehensive career transition plan for this professional.

## COMPUTED CONTEXT
- Total Available Hours: {computed['total_hours']} hours ({intake.time_per_week} hrs/week x {computed['timeline_weeks']} weeks)
- Experience Tier: {computed['experience_tier']}
- Budget Tier: {computed['budget_tier']}
- Has Head Start: {computed['has_head_start']}

## USER PROFILE
- Current Role: {intake.current_role_title}
- Industry: {intake.current_industry}
- Years Experience: {intake.years_experience}
- Top Tasks: {', '.join(intake.top_tasks[:5])}
- Tools/Technologies: {tools_str}
- Strengths: {', '.join(intake.strengths[:5])}
- Likes: {likes_str}
- Dislikes: {dislikes_str}
- Current Salary: {intake.current_salary_range or 'Not disclosed'}
- Existing Certifications: {existing_certs_str}
- Training Budget: {intake.training_budget or 'Not specified'}
- Biggest Concern: {intake.biggest_concern or 'Not stated'}
- Already Started: {'Yes' if computed['has_head_start'] else 'No'}
{f'- Steps Taken: {intake.steps_already_taken}' if computed['has_head_start'] else ''}

## TARGET
- Dream Role (USER'S STATED GOAL): {intake.target_role_interest or "To be determined - suggest 3-6 aligned roles"}
- Target Companies: {companies_str}
- Education Level: {intake.education_level}
- Location: {intake.location}
- Time Available: {intake.time_per_week} hours/week
- Timeline: {intake.timeline}
- Format Preference: {intake.in_person_vs_remote}
- Preferred Platforms: {platforms_str}
- Tech Interests: {tech_interests_str}
- Cert Area Interests: {cert_interests_str}
- Motivation: {', '.join(intake.transition_motivation)}

{self._build_job_posting_section(job_details)}# WEB-GROUNDED RESEARCH DATA (USE THESE VERIFIED FACTS)
## CERTIFICATION RESEARCH (from Perplexity web search):
{raw_cert_content if raw_cert_content else "No certification research available. Use your knowledge of industry certifications."}

Source URLs for certifications: {json.dumps(cert_citation_urls[:10]) if cert_citation_urls else "[]"}

## EDUCATION RESEARCH (from Perplexity web search):
{raw_edu_content if raw_edu_content else "No education research available. Use your knowledge of education programs."}

Source URLs for education: {json.dumps(edu_citation_urls[:10]) if edu_citation_urls else "[]"}

## EVENTS RESEARCH (from Perplexity web search):
{raw_events_content if raw_events_content else "No events research available. Use your knowledge of industry events."}

Source URLs for events: {json.dumps(research_data.get("events_citation_urls", [])[:10]) if research_data.get("events_citation_urls") else "[]"}

## Source Citations ({len(sources)} sources):
{json.dumps(sources[:10], indent=2) if sources else "None"}

## Salary Data (Real-time Perplexity Research):
{self._format_salary_insights(research_data.get("salary_insights", {}))}

{conditional_instructions}

# YOUR TASK

Generate a complete career plan JSON object based on:
1. The user's background, tools, existing certs, and concerns above
2. Current industry best practices and trends
3. Your knowledge of typical requirements for target roles
4. The research data provided above (if any)
5. The computed context (time budget, experience tier, budget tier)

Match this EXACT schema:

{{
  "generated_at": "2026-01-16T12:00:00Z",
  "version": "1.0",
  "profile_summary": "150-500 char summary of user's background and transition goals",

  "target_roles": [
    // FIRST target role MUST be the user's exact dream role: "{intake.target_role_interest}"
    // Additional roles (2-3 more) can be related alternatives
    {{
      "title": "MUST be '{intake.target_role_interest}' for the first entry - use the user's exact dream role title",
      "why_aligned": "How user's background maps to this role based on typical requirements",
      "growth_outlook": "Industry growth trends and demand, e.g., '23% growth 2024-2034 per BLS, strong demand in market'",
      "salary_range": "USE THE EXACT PERPLEXITY SALARY DATA PROVIDED ABOVE. If not available, provide typical range like '$95,000 - $135,000 for {intake.location} market'",
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

  "skills_guidance": {{
    "soft_skills": [
      {{
        "skill_name": "Name of a critical soft skill for the target role",
        "why_needed": "Detailed explanation (100+ chars) of why this soft skill is critical for the target role, connecting it to specific responsibilities and team dynamics",
        "how_to_improve": "Specific actionable steps (150+ chars) to develop this soft skill, including concrete exercises, courses, mentorship approaches, and practice opportunities the user can start immediately",
        "importance": "critical|high|medium",
        "estimated_time": "e.g., '3-6 months' or '1-2 years'",
        "resources": ["Specific course or book title", "Another resource"],
        "real_world_application": "Detailed description (100+ chars) of how this soft skill is used in day-to-day work in the target role, with specific scenarios and examples"
      }}
      // Minimum 3 soft skills, maximum 8. Include at least: communication, leadership, and one domain-specific soft skill.
    ],
    "hard_skills": [
      {{
        "skill_name": "Name of a critical technical/hard skill for the target role",
        "why_needed": "Detailed explanation (100+ chars) of why this hard skill is essential, referencing industry standards, job requirements, and technical demands of the role",
        "how_to_improve": "Specific actionable steps (150+ chars) to build this hard skill, including courses with exact names, hands-on projects to build, certifications to pursue, and tools to practice with",
        "importance": "critical|high|medium",
        "estimated_time": "e.g., '3-6 months' or '1-2 years'",
        "resources": ["Specific course or platform", "Another resource"],
        "real_world_application": "Detailed description (100+ chars) of how this hard skill is applied in actual work situations, including tools used, problems solved, and deliverables produced"
      }}
      // Minimum 3 hard skills, maximum 10. Prioritize skills mentioned in the target role requirements.
    ],
    "skill_development_strategy": "Comprehensive strategy (200+ chars minimum) for how the user should approach building all these skills in parallel. Include prioritization advice, time allocation recommendations, how to balance skill development with current responsibilities, and milestones to track progress. Reference the user's stated learning preferences and available time per week."
  }},

  "certification_journey_summary": "2-4 sentence overview of the complete certification journey from beginner to expert. E.g., 'Start with CompTIA Security+ to build foundational knowledge, then advance to AWS Solutions Architect for cloud expertise. Complete with CISSP to unlock senior leadership roles. This 12-18 month journey will qualify you for 90%+ of job postings in your target roles.'",

  "certification_path": [
    {{
      "name": "EXACT certification name from official body (from research above)",
      "certifying_body": "e.g., CompTIA, AWS, Microsoft, ISC2, Google, etc.",
      "level": "foundation|intermediate|advanced",
      "journey_order": 1,  // Sequential order in the journey (1 = first cert to pursue, 2 = second, etc.)
      "tier": "foundation|intermediate|advanced",  // Tier grouping for UI display
      "unlocks_next": "Name of the NEXT cert in the journey (null for the last cert)",
      "beginner_entry_point": true,  // Set to true on EXACTLY ONE cert (the starting point)
      "prerequisites": ["List any prerequisite certs or experience"],
      "est_study_weeks": 12,
      "est_cost_range": "$XXX-$YYY (from research data or official pricing)",
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
        {{"week": "Week 1", "focus": "Module 1: Fundamentals", "resources": "Official course chapters 1-3", "practice": "Quiz 1"}},
        {{"week": "Week 2", "focus": "Module 2: Core concepts", "resources": "Video course sections 4-6", "practice": "Hands-on lab 1"}},
        {{"week": "Week 12", "focus": "Final review and exam", "resources": "Practice exams", "practice": "Full mock exam"}}
      ],
      "source_citations": ["All URLs where you found this data"]
    }}
  ],

  "education_recommendation": "2-3 sentence recommendation of the BEST education option for this user based on their budget, timeline, and learning style. E.g., 'Given your $2K budget and preference for online learning, the Google Cybersecurity Certificate on Coursera is your best starting point at $49/month. For deeper expertise, supplement with TryHackMe labs ($14/month) for hands-on practice.'",

  "education_options": [
    {{
      "type": "degree|bootcamp|self-study|online-course",
      "name": "EXACT program name from research (e.g., 'Google Cybersecurity Certificate on Coursera')",
      "duration": "X weeks/months",
      "cost_range": "$X-$Y (exact price from research)",
      "format": "online|in-person|hybrid",
      "official_link": "VERIFIED enrollment URL from research data",
      "description": "100-300 word description of what the program covers, learning outcomes, and why it's valuable for career changers",
      "who_its_best_for": "Describe the ideal student for this program (e.g., 'Complete beginners with no tech background who want structured learning')",
      "financing_options": "Payment plans, scholarships, ISAs, employer reimbursement, financial aid options",
      "employment_outcomes": "Job placement rate, average salary after completion, employer partnerships if available",
      "time_commitment_weekly": "X hours per week",
      "comparison_rank": 1,  // 1 = best overall fit for this user, 2 = second best, etc.
      "pros": ["pro1", "pro2", "pro3", "pro4"],
      "cons": ["con1", "con2", "con3"],
      "source_citations": ["url from research"]
    }}
  ],

  "experience_plan": [
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
    }}
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
0. **RESPECT THE USER'S DREAM ROLE**: The FIRST entry in target_roles MUST use the user's exact stated dream role title from the "Dream Role" field above. Do NOT substitute, modify, or replace it with a different role. Build the entire plan around achieving THIS specific role. Additional target_roles can suggest alternatives.
1. **COMPLETE ALL FIELDS**: Provide comprehensive career guidance based on your knowledge of industry practices. Use placeholders for URLs if needed.
2. **Study Materials**: Each certification should have 2-3 study materials with descriptions (50-150 words each)
3. **Tech Stack Details**: Each project should have 3-5 key technologies, each with a brief "why_this_tech" explanation
4. **Event Details**: Each event should have organizer, scope, attendee_count, target_audience, key_topics, and "why_attend" explanation
5. **Resume Guidance**: Provide practical resume guidance including headlines, summaries, and bullet point strategies.
6. **MINIMUM ITEMS REQUIRED (validate before submitting)**:
   - target_roles: At least 1
   - skills_analysis.already_have: At least 1
   - skills_analysis.need_to_build: At least 1
   - certification_path: At least 4 certifications with journey_order, tier, unlocks_next, beginner_entry_point fields
   - certification_journey_summary: Required (2-4 sentence overview of the journey)
   - education_options: At least 4 options across price points with description, who_its_best_for, comparison_rank, official_link
   - education_recommendation: Required (2-3 sentence recommendation)
   - experience_plan: EXACTLY 5 projects (2 beginner, 2 intermediate, 1 advanced)
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

## QUALITY CHECKLIST (verify before returning)
- [ ] Dream role "{intake.target_role_interest}" is target_roles[0] with highest relevance
- [ ] Total study hours across all certs and courses fit within {computed['total_hours']} available hours
- [ ] No certification in certification_path duplicates existing certs: {existing_certs_str}
- [ ] Skills guidance references at least 2 of user's tools: {tools_str}
- [ ] If biggest concern was stated, it's addressed in at least 2 sections
- [ ] If user already started, Week 1 builds on their progress
- [ ] Salary ranges reflect career-changer expectations, not established professional median

IMPORTANT: Your response must be ONLY a JSON object. Do not include:
- Markdown code blocks (no ```json or ```)
- Explanatory text before or after the JSON
- Comments or notes
- Just the raw JSON starting with {{ and ending with }}

Generate the plan now:"""

        return prompt

    def _get_system_prompt(self, intake: IntakeRequest = None, computed: Dict[str, Any] = None) -> str:
        """Enhanced system prompt with reasoning architecture and personalization"""

        # Build client profile section if intake available
        client_profile = ""
        if intake and computed:
            existing_certs = ", ".join(intake.existing_certifications) if intake.existing_certifications else "None listed"
            tools_list = ", ".join(intake.tools[:10]) if intake.tools else "None listed"
            dislikes_list = ", ".join(intake.dislikes[:5]) if intake.dislikes else "None listed"
            companies_list = ", ".join(intake.specific_companies[:5]) if intake.specific_companies else "None"

            client_profile = f"""
## CLIENT PROFILE (use for all reasoning)
- Current: {intake.current_role_title} in {intake.current_industry} ({intake.years_experience} yrs)
- Target: {intake.target_role_interest or 'TBD'}
- Experience Tier: {computed['experience_tier']}
- Tools they use: {tools_list}
- Existing certifications: {existing_certs}
- Budget tier: {computed['budget_tier']} (stated: {intake.training_budget or 'not specified'})
- Current salary: {intake.current_salary_range or 'not disclosed'}
- Time budget: {intake.time_per_week} hrs/week x {computed['timeline_weeks']} weeks = {computed['total_hours']} total hours
- Biggest concern: {intake.biggest_concern or 'not stated'}
- Already started: {computed['has_head_start']}
- Dislikes: {dislikes_list}
- Target companies: {companies_list}
"""

        return f"""You are an elite career transition strategist with 20+ years experience and 10,000+ clients coached through successful career pivots. You produce EXHAUSTIVELY DETAILED, deeply personalized career plans that read like a $5,000 professional consulting deliverable — not a generic AI summary.
{client_profile}
## YOUR MANDATE: EXTREME DEPTH AND DETAIL

You MUST produce the most comprehensive, granular, actionable career plan possible. Every section should be PACKED with specific, useful content. Think of this as a 30-page consulting report compressed into structured JSON.

### DEPTH REQUIREMENTS (NON-NEGOTIABLE):
- **profile_summary**: 400-500 characters minimum. Weave in transferable skills, career narrative, and positioning strategy.
- **target_roles**: 3-5 roles minimum. Each with 200+ word why_aligned, real growth data, 4-6 typical_requirements, 2-3 bridge_roles with detailed gap analysis.
- **skills_analysis.already_have**: 5-8 skills with 2-3 resume bullets EACH. Bullets must be specific achievement statements with metrics, not generic descriptions.
- **skills_analysis.can_reframe**: 3-5 skills showing exactly HOW to reposition current experience. Include before/after resume bullet examples.
- **skills_analysis.need_to_build**: 4-8 gap skills, each with specific learning path (exact course names, practice projects, timeline).
- **skills_guidance.soft_skills**: 4-6 skills, each with 150+ word how_to_improve including specific exercises, books by title, courses by name.
- **skills_guidance.hard_skills**: 5-8 skills, each with 150+ word how_to_improve referencing exact tools, platforms, tutorials, and hands-on practice.
- **skill_development_strategy**: 300+ words covering week-by-week prioritization, parallel learning tracks, and measurement milestones.
- **certification_path**: 4-6 certifications as a SEQUENTIAL JOURNEY (foundation → intermediate → advanced). Set journey_order (1-N), tier labels, unlocks_next chain, and beginner_entry_point=true on exactly ONE cert. Each cert must have 3-5 study materials with descriptions AND a week-by-week study plan. Generate certification_journey_summary.
- **education_options**: 4-5 options across price points: 1 FREE, 1-2 MID-RANGE ($100-$2K), 1-2 PREMIUM ($5K+). EVERY option MUST have official_link from research data. Set comparison_rank (1=best fit). Include description, who_its_best_for, financing_options. Generate education_recommendation.
- **experience_plan**: EXACTLY 5 projects: 2 beginner, 2 intermediate, 1 advanced. Each with FULL technical architecture breakdowns, 8-15 technologies each with why_this_tech explanations, detailed step-by-step guides (8-12 WEEK-LEVEL tasks with deliverables), and interview talking points.
- **events**: 8-15 events mixing conferences, meetups, virtual events, and career fairs. Each with 100+ word why_attend and specific networking strategies.
- **timeline.twelve_week_plan**: 12 detailed weeks with 3-5 specific tasks per week, clear milestones, and checkpoint assessments.
- **timeline.six_month_plan**: 6 monthly phases with 3-4 goals and 2-3 deliverables per month.
- **resume_assets**: THIS IS CRITICAL. Provide:
  - headline + 150+ word explanation of keyword strategy
  - summary + 300+ word sentence-by-sentence breakdown
  - 6-10 achievement bullets using CAR/STAR with metrics, each with 100+ word analysis
  - 3-5 skill groups with strategic ordering rationale
  - 200+ word reframing guide with before/after examples
  - 10-15 ATS keywords with placement strategy
  - Full LinkedIn optimization (headline, about section, content strategy)
  - Cover letter template with 200+ word customization guide

### CONTENT QUALITY STANDARDS:
- Every recommendation must pass the "WHAT DO I DO MONDAY MORNING?" test
- Not "learn cloud computing" → "Go to aws.training, create a free account, start the Cloud Practitioner Essentials course (6 hours), complete modules 1-3 this week"
- Not "improve leadership skills" → "Read 'The First 90 Days' by Michael Watkins (ch. 1-4), join your company's ERG leadership committee, volunteer to lead the next sprint retrospective"
- Every skill explanation must reference SPECIFIC tools, courses, books, or platforms by name
- Every resume bullet must include a quantified metric (percentage, dollar amount, team size, timeline)
- Every project must have enough technical detail that someone could actually build it

## CRITICAL RULES

1. **RESPECT THE DREAM ROLE**: FIRST entry in target_roles MUST be the user's exact stated dream role. Build the ENTIRE plan around achieving THIS role.

2. **SKILLS GAP ANALYSIS WITH TOOL BRIDGING**: Map the user's actual tools to target role equivalents with specific bridging strategies.

3. **TIME-BUDGET CONSTRAINED**: Total available hours ({computed['total_hours'] if computed else 'N/A'}) is a HARD constraint. Plan must fit within this budget.

4. **BUDGET CONSTRAINED**: Filter by training budget. Don't recommend $15K bootcamps to a $500 budget.

5. **EXPERIENCE-LEVEL CALIBRATION**: Calibrate to {computed['experience_tier'] if computed else 'mid-career'} professional. No beginner content for veterans.

6. **HONEST SALARY EXPECTATIONS**: Career changers start 10-20% below established median. Show first-role vs. 2-3 year salary trajectory.

7. **ADDRESS CONCERNS THROUGHOUT**: Weave biggest concern into skills guidance, timeline milestones, and resume strategy — not as a throwaway paragraph.

8. **BUILD ON EXISTING PROGRESS**: If already started, Week 1 picks up where they left off. Never repeat completed steps.

9. **AVOID WHAT THEY HATE**: Thread dislikes through role recommendations and skill guidance.

10. **TARGET COMPANY INTELLIGENCE**: Tailor certs and networking to specific companies' known tech stacks and hiring patterns.

11. **MOTIVATION-AWARE FRAMING**: Lead with ROI for "better-pay", passion for "follow-passion", flexibility for "work-life-balance".

## STRUCTURAL MINIMUMS (HARD REQUIREMENTS):
- target_roles: 3+
- skills_analysis.already_have: 5+
- skills_analysis.can_reframe: 3+
- skills_analysis.need_to_build: 4+
- skills_guidance.soft_skills: 4+
- skills_guidance.hard_skills: 5+
- certification_path: 4+ with journey_order, tier, unlocks_next, beginner_entry_point, study materials, AND week-by-week study plans
- certification_journey_summary: required (2-4 sentence overview)
- education_options: 4+ across price points (free, mid-range, premium) with description, who_its_best_for, comparison_rank
- education_recommendation: required (2-3 sentence recommendation)
- experience_plan: EXACTLY 5 projects (2 beginner, 2 intermediate, 1 advanced)
- events: 8+
- timeline.twelve_week_plan: EXACTLY 12 weekly entries with 3-5 tasks each
- timeline.six_month_plan: EXACTLY 6 monthly entries with 3+ goals each
- resume_assets.target_role_bullets: 6+
- resume_assets.skills_grouped: 3+
- research_sources: 3+

## ANTI-HALLUCINATION RULES
- URLs: ONLY from provided research data or well-known official domains (aws.amazon.com, coursera.org, etc.)
- Prices: Use "check current pricing" if unsure
- Dates: Use "check website for dates" if unsure
- Salary figures: Use Perplexity data when provided, otherwise state "estimated range based on market data"

## OUTPUT FORMAT
Return ONLY a valid JSON object starting with {{ and ending with }}. No markdown, no explanation text. MAXIMIZE detail in every field — treat empty space as wasted opportunity."""

    def _pre_validate_coerce(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deterministically fix common GPT type mismatches before Pydantic validation.
        These are predictable errors that can be fixed without a second LLM call.
        """
        try:
            # 1. study_plan_weeks: all dict values must be strings (List[Dict[str, str]])
            for cert in plan_data.get("certification_path", []):
                if isinstance(cert, dict) and "study_plan_weeks" in cert:
                    fixed_weeks = []
                    for week_entry in cert["study_plan_weeks"]:
                        if isinstance(week_entry, dict):
                            fixed_entry = {k: str(v) for k, v in week_entry.items()}
                            fixed_weeks.append(fixed_entry)
                        else:
                            fixed_weeks.append(week_entry)
                    cert["study_plan_weeks"] = fixed_weeks

            # 2. beginner_entry_point: must be bool, not string "true"/"false"
            for cert in plan_data.get("certification_path", []):
                if isinstance(cert, dict) and "beginner_entry_point" in cert:
                    val = cert["beginner_entry_point"]
                    if isinstance(val, str):
                        cert["beginner_entry_point"] = val.lower() == "true"

            # 3. journey_order: must be int (ge=1, le=20)
            for cert in plan_data.get("certification_path", []):
                if isinstance(cert, dict) and "journey_order" in cert:
                    val = cert["journey_order"]
                    if isinstance(val, str):
                        try:
                            cert["journey_order"] = int(val)
                        except (ValueError, TypeError):
                            cert["journey_order"] = None

            # 4. comparison_rank in education_options: must be int (ge=1, le=10)
            for edu in plan_data.get("education_options", []):
                if isinstance(edu, dict) and "comparison_rank" in edu:
                    val = edu["comparison_rank"]
                    if isinstance(val, str):
                        try:
                            edu["comparison_rank"] = int(val)
                        except (ValueError, TypeError):
                            edu["comparison_rank"] = None

            # 5. what_to_emphasize in resume bullets: must be string, not list
            resume_assets = plan_data.get("resume_assets", {})
            if isinstance(resume_assets, dict):
                for bullet in resume_assets.get("target_role_bullets", []):
                    if isinstance(bullet, dict) and "what_to_emphasize" in bullet:
                        val = bullet["what_to_emphasize"]
                        if isinstance(val, list):
                            bullet["what_to_emphasize"] = "; ".join(str(v) for v in val)

            # 6. recommended_order in study_materials: must be int (ge=1, le=20)
            for cert in plan_data.get("certification_path", []):
                if isinstance(cert, dict):
                    for material in cert.get("study_materials", []):
                        if isinstance(material, dict) and "recommended_order" in material:
                            val = material["recommended_order"]
                            if isinstance(val, str):
                                try:
                                    material["recommended_order"] = int(val)
                                except (ValueError, TypeError):
                                    material["recommended_order"] = 1

            # 7. week_number in twelve_week_plan: must be int (ge=1, le=52)
            timeline = plan_data.get("timeline", {})
            if isinstance(timeline, dict):
                for week in timeline.get("twelve_week_plan", []):
                    if isinstance(week, dict) and "week_number" in week:
                        val = week["week_number"]
                        if isinstance(val, str):
                            # Handle "Week 1" format
                            try:
                                week["week_number"] = int(str(val).replace("Week ", "").replace("week ", "").strip())
                            except (ValueError, TypeError):
                                pass

                # 8. month_number in six_month_plan: must be int (ge=1, le=12)
                for month in timeline.get("six_month_plan", []):
                    if isinstance(month, dict) and "month_number" in month:
                        val = month["month_number"]
                        if isinstance(val, str):
                            try:
                                month["month_number"] = int(str(val).replace("Month ", "").replace("month ", "").strip())
                            except (ValueError, TypeError):
                                pass

            # 9. profile_summary: truncate if over 1000 chars (schema max)
            if isinstance(plan_data.get("profile_summary"), str) and len(plan_data["profile_summary"]) > 1000:
                plan_data["profile_summary"] = plan_data["profile_summary"][:997] + "..."

            # 10. est_study_weeks: must be int (ge=1, le=104)
            for cert in plan_data.get("certification_path", []):
                if isinstance(cert, dict) and "est_study_weeks" in cert:
                    val = cert["est_study_weeks"]
                    if isinstance(val, str):
                        try:
                            cert["est_study_weeks"] = int(val)
                        except (ValueError, TypeError):
                            cert["est_study_weeks"] = 8  # default fallback

            # 11. Ensure skills_analysis.can_reframe exists (optional list but Pydantic expects it)
            sa = plan_data.get("skills_analysis")
            if isinstance(sa, dict):
                if "can_reframe" not in sa:
                    sa["can_reframe"] = []
                if "already_have" not in sa:
                    sa["already_have"] = []
                if "need_to_build" not in sa:
                    sa["need_to_build"] = []

            # 12. Booleans in events: beginner_friendly, recurring, virtual_option_available
            for event in plan_data.get("events", []):
                if isinstance(event, dict):
                    for bool_field in ["beginner_friendly", "recurring", "virtual_option_available"]:
                        if bool_field in event and isinstance(event[bool_field], str):
                            event[bool_field] = event[bool_field].lower() in ("true", "yes", "1")

            # 13. exam_details numeric fields: duration_minutes, num_questions as int
            for cert in plan_data.get("certification_path", []):
                if isinstance(cert, dict):
                    ed = cert.get("exam_details")
                    if isinstance(ed, dict):
                        for int_field in ["duration_minutes", "num_questions"]:
                            if int_field in ed and isinstance(ed[int_field], str):
                                try:
                                    ed[int_field] = int(ed[int_field].replace(",", ""))
                                except (ValueError, TypeError):
                                    pass

            # 14. Ensure certifying_body exists on certs (required field)
            for cert in plan_data.get("certification_path", []):
                if isinstance(cert, dict) and not cert.get("certifying_body"):
                    cert["certifying_body"] = "Industry Certification Body"

            # 15. Ensure source_citations is a list with at least 1 item where required
            for cert in plan_data.get("certification_path", []):
                if isinstance(cert, dict):
                    if not cert.get("source_citations"):
                        cert["source_citations"] = ["Industry research and certification body data"]
                    if not cert.get("official_links"):
                        cert["official_links"] = ["https://www.example.com/certification"]
                    # Ensure study_materials exists and has at least 1
                    if not cert.get("study_materials"):
                        cert["study_materials"] = [{
                            "type": "official-course",
                            "title": f"{cert.get('name', 'Certification')} Study Guide",
                            "provider": cert.get("certifying_body", "Official"),
                            "url": "https://www.example.com/study-guide",
                            "cost": "Varies",
                            "duration": "Self-paced",
                            "description": f"Official study materials for {cert.get('name', 'this certification')}",
                            "recommended_order": 1
                        }]

            for event in plan_data.get("events", []):
                if isinstance(event, dict) and not event.get("source_citations"):
                    event["source_citations"] = ["Industry event data"]

            # 16. Ensure research_sources exists at root level
            if not plan_data.get("research_sources"):
                plan_data["research_sources"] = ["Industry research and market data"]

            # 17. Ensure skills_guidance exists with required structure
            sg = plan_data.get("skills_guidance")
            if not isinstance(sg, dict):
                plan_data["skills_guidance"] = {
                    "soft_skills": [],
                    "hard_skills": [],
                    "skill_development_strategy": "Focus on building core skills progressively, starting with fundamentals."
                }

            # 18. attendee_count: must be string or None, not int
            for event in plan_data.get("events", []):
                if isinstance(event, dict) and "attendee_count" in event:
                    val = event["attendee_count"]
                    if isinstance(val, (int, float)):
                        event["attendee_count"] = str(int(val))

            print("✓ Pre-validation type coercions applied (18 rules)")

        except Exception as e:
            print(f"⚠ Pre-validation coercion error (non-fatal): {e}")

        return plan_data

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

        # Limit the plan JSON sent to repair to avoid exceeding repair max_tokens
        plan_json_str = json.dumps(invalid_plan, indent=2)
        if len(plan_json_str) > 40000:
            plan_json_str = plan_json_str[:40000] + "\n... [truncated]"

        repair_prompt = f"""The following JSON failed schema validation with these errors:

{error_summary}

INVALID JSON:
{plan_json_str}

Fix ALL validation errors and return a corrected JSON object that passes validation.

Requirements:
1. Keep all existing data where possible
2. Fix missing required fields by adding realistic values
3. Fix type mismatches (e.g., string vs array)
4. Ensure array minimum/maximum item constraints are met
5. Ensure string length constraints are met (profile_summary max 1000 chars)
6. FIELD TYPE FIXES REQUIRED:
   - study_plan_weeks entries: all dict values must be strings, e.g. {{"week": "Week 1", "focus": "...", "resources": "..."}}
   - beginner_entry_point: must be boolean true/false, not string "true"/"false"
   - journey_order: must be an integer, not a string
   - comparison_rank: must be an integer 1-10, not a string
   - what_to_emphasize in resume bullets: must be a single string, NOT a list/array
   - week_number in twelve_week_plan: must be an integer 1-52
   - month_number in six_month_plan: must be an integer 1-12
   - recommended_order in study_materials: must be an integer 1-20
   - est_study_weeks: must be an integer 1-104
7. REQUIRED ROOT-LEVEL FIELDS: certification_journey_summary (string) and education_recommendation (string) must be at the top level of the JSON object
8. Return ONLY the corrected JSON - no explanations

Return the fixed JSON now:"""

        try:
            response = await get_gateway().execute(
                "openai",
                self.client.chat.completions.create,
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
                max_tokens=16000,
                response_format={"type": "json_object"}
            )

            repaired_json = response.choices[0].message.content
            repaired_data = json.loads(repaired_json)

            # Apply deterministic coercions to repaired data too
            repaired_data = self._pre_validate_coerce(repaired_data)

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
