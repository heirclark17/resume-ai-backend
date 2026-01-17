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
        # Use Perplexity AI for web-grounded research and real data
        if not settings.perplexity_api_key:
            if not settings.test_mode:
                raise ValueError(
                    "PERPLEXITY_API_KEY not found. Please set it in Railway environment variables, "
                    "or set TEST_MODE=true to use mock data. "
                    "Railway dashboard -> Variables -> Add Variable -> PERPLEXITY_API_KEY"
                )
            else:
                # TEST MODE: Don't initialize client, will use mock data
                self.client = None
                self.model = "test"
                print("[TEST MODE] CareerPathSynthesisService using mock data")
        else:
            self.client = OpenAI(
                api_key=settings.perplexity_api_key,
                base_url="https://api.perplexity.ai"
            )
            # Use sonar model - Perplexity's research-focused model with web search
            self.model = "sonar"

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
            # Call Perplexity with web search for real data
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
                temperature=0.7,
                max_tokens=16000  # Perplexity doesn't support response_format parameter
            )

            raw_json = response.choices[0].message.content
            print(f"✓ Perplexity returned {len(raw_json)} characters")

            # Clean up markdown code blocks if present (Perplexity sometimes adds these)
            if raw_json.strip().startswith("```"):
                # Remove markdown code blocks
                raw_json = raw_json.strip()
                if raw_json.startswith("```json"):
                    raw_json = raw_json[7:]  # Remove ```json
                elif raw_json.startswith("```"):
                    raw_json = raw_json[3:]  # Remove ```
                if raw_json.endswith("```"):
                    raw_json = raw_json[:-3]  # Remove trailing ```
                raw_json = raw_json.strip()
                print(f"✓ Cleaned markdown code blocks, {len(raw_json)} characters remain")

            # Parse and validate
            plan_data = json.loads(raw_json)
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
                print(f"  Error {i+1}: {e.field} - {e.error} (expected: {e.expected}, got: {e.received})")
            print("🔧 Attempting JSON repair...")

            repaired = await self._repair_plan(plan_data, validation_result)

            if repaired["success"]:
                print("✓ Plan successfully repaired")
                return repaired
            else:
                print("✗ Repair failed")
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
- Budget: {intake.budget}
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

STEP 1: RESEARCH THE WEB
Before generating the plan, search the web for:
1. Current job market data for {intake.target_role_interest or "the suggested roles"}
2. Real salary ranges from job postings in {intake.location} (check LinkedIn, Indeed, Glassdoor)
3. Actual skills required in recent job postings (last 30 days)
4. Real companies actively hiring for these roles
5. Current industry trends and demand (BLS data, tech blogs, industry reports)
6. Actual bridge roles that companies use as stepping stones
7. Real networking events in {intake.location} happening in 2025-2026

STEP 2: USE REAL DATA IN YOUR RESPONSE
Generate a complete career plan JSON object using ACTUAL data from your web search.
Match this EXACT schema:

{{
  "generated_at": "2026-01-16T12:00:00Z",
  "version": "1.0",
  "profile_summary": "150-500 char summary of user's background and transition goals",

  "target_roles": [
    {{
      "title": "Specific Job Title (from real job postings)",
      "why_aligned": "How user's background maps to this role based on actual requirements",
      "growth_outlook": "REAL DATA: e.g., '23% growth 2024-2034 per BLS, 15,000+ current openings on LinkedIn'",
      "salary_range": "ACTUAL RANGE: e.g., '$95,000 - $135,000 based on 50+ {intake.location} postings on Indeed/Glassdoor'",
      "typical_requirements": ["Real skill from job postings", "Another actual requirement", "Certification companies mention"],
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
    USE THE VERIFIED CERT DATA FROM RESEARCH.
    Sequence them logically (foundation -> intermediate -> advanced).
    Include prerequisites, cost, study time, official links.
    {{
      "name": "Exact cert name",
      "level": "foundation|intermediate|advanced",
      "prerequisites": [],
      "est_study_weeks": 12,
      "est_cost_range": "$300-$600",
      "official_links": ["USE VERIFIED URLs from research"],
      "what_it_unlocks": "What this enables",
      "alternatives": [],
      "source_citations": ["url"]
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
    Portfolio projects, volunteer work, labs, side projects.
    Minimum 2, maximum 10.
    {{
      "type": "portfolio|volunteer|lab|side-project|freelance",
      "title": "Project title",
      "description": "What to build/do",
      "skills_demonstrated": ["skill1", "skill2"],
      "time_commitment": "X hours/week for Y weeks",
      "how_to_showcase": "How to present on resume/LinkedIn",
      "example_resources": ["url1", "url2"]
    }}
  ],

  "events": [
    USE VERIFIED EVENTS FROM RESEARCH.
    Include conferences, meetups, virtual events, career fairs.
    {{
      "name": "Event name",
      "type": "conference|meetup|virtual|career-fair|workshop",
      "date_or_season": "Date or season",
      "location": "City or Virtual",
      "price_range": "$0-$500 or Free",
      "beginner_friendly": true|false,
      "why_attend": "Specific value",
      "registration_link": "VERIFIED URL from research",
      "source_citations": ["url"]
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
    "headline": "LinkedIn headline aligned to target role",
    "summary": "100-1000 char professional summary for resume",
    "skills_section": ["skill1", "skill2", ...],  // 8-20 skills
    "target_role_bullets": [
      "Achievement bullet 1 with metrics",
      "Achievement bullet 2 with metrics",
      // ...6-10 bullets total
    ],
    "keywords_for_ats": ["keyword1", "keyword2", ...]  // 10+ keywords
  }},

  "research_sources": {json.dumps(sources[:20], indent=2)}
}}

# CRITICAL REQUIREMENTS
1. ONLY use URLs that appear in the research data - NEVER invent URLs
2. Ensure every array has minimum items (target_roles: 1+, already_have skills: 1+, events: 1+, experience: 1+)
3. Make timeline realistic given {intake.time_per_week} hours/week
4. Sequence certifications logically with clear prerequisites
5. Resume bullets must be achievement-focused with measurable outcomes (minimum 3 bullets)
6. Profile summary must be 50-500 characters
7. Resume summary must be 50-1000 characters
8. Timeline must have 10-14 weekly tasks and 5-7 monthly phases (typically 12 weeks and 6 months)
9. If target_role_interest is empty, suggest 3-6 aligned roles based on user background
10. Return ONLY valid JSON - no markdown, no extra text

IMPORTANT: Your response must be ONLY a JSON object. Do not include:
- Markdown code blocks (no ```json or ```)
- Explanatory text before or after the JSON
- Comments or notes
- Just the raw JSON starting with {{ and ending with }}

Generate the plan now:"""

        return prompt

    def _get_system_prompt(self) -> str:
        """System prompt for Perplexity AI"""

        return """You are an expert career transition research analyst with real-time web access.

CRITICAL REQUIREMENTS:
1. SEARCH THE WEB for current, factual data about job markets, salaries, skills, and career paths
2. Use ACTUAL job postings, salary data, and labor market statistics from 2025-2026
3. Cite REAL sources - include URLs from authoritative websites (LinkedIn, Glassdoor, BLS, Indeed, company career pages)
4. Provide SPECIFIC numbers: actual salary ranges, real job growth percentages, current market demand
5. Reference REAL certifications with current costs and official links
6. Find ACTUAL companies hiring for these roles with real requirements

You help professionals successfully transition by providing:
- Web-researched analysis of transferable skills based on current job market
- Gap analysis using real job posting requirements from major employers
- Current certifications that employers are actually requiring (with official URLs)
- Real education programs and bootcamps with current pricing
- Actual networking events and conferences happening in 2025-2026
- Realistic timelines based on current market data

You MUST:
- Return ONLY valid JSON - no markdown, no explanations, no extra text before or after
- Match the exact schema provided (use proper JSON syntax with quotes, commas, brackets)
- Use ONLY real URLs from your web search (no invented links)
- Include current market data (salary ranges from 2025-2026, not outdated info)
- Base recommendations on ACTUAL job postings and employer requirements
- Provide thorough, well-researched answers grounded in real-world data

CRITICAL: Your entire response must be a single valid JSON object. Start with {{ and end with }}. No other text."""

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
                        "skill": skill,
                        "how_it_transfers": f"Your {skill} experience applies directly to {target_role}",
                        "evidence_from_background": f"Demonstrated through {intake.years_experience or 5}+ years in field"
                    }
                    for skill in (intake.skills_have[:3] if intake.skills_have else ["Problem Solving", "Communication", "Leadership"])
                ],
                "need_to_build": [
                    {
                        "skill": "Advanced Technical Skills",
                        "why_important": "Required for senior-level responsibilities",
                        "how_to_acquire": "Take online courses and earn certifications",
                        "timeline_weeks": 12
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
                    "skills_demonstrated": intake.skills_have[:3] if intake.skills_have else ["Leadership", "Technical Skills"],
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
                "skills_section": intake.skills_have[:8] if intake.skills_have else ["Leadership", "Communication", "Problem Solving", "Technical Skills", "Project Management"],
                "target_role_bullets": [
                    f"[TEST MODE] Led {intake.current_role_title or 'professional'} initiatives",
                    "[TEST MODE] Achieved measurable results through strategic planning",
                    "[TEST MODE] Collaborated with cross-functional teams"
                ],
                "keywords_for_ats": [target_role] + (intake.skills_have[:5] if intake.skills_have else ["Leadership", "Management", "Strategy"])
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
