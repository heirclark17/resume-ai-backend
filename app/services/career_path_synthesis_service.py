"""
Career Path Synthesis Service
Uses OpenAI with STRICT structured outputs to generate complete career plans
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


class CareerPathSynthesisService:
    """
    Synthesizes complete career plans using OpenAI with strict schema validation
    """

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # Use gpt-4-turbo-preview for JSON mode support (or set CAREER_PATH_MODEL env var)
        self.model = os.getenv("CAREER_PATH_MODEL", os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"))

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

        # Build synthesis prompt
        prompt = self._build_synthesis_prompt(intake, research_data)

        try:
            # Call OpenAI with strict structured output
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
                max_tokens=4000,
                response_format={"type": "json_object"}  # Enforce JSON output
            )

            raw_json = response.choices[0].message.content
            print(f"✓ OpenAI returned {len(raw_json)} characters of JSON")

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
Generate a complete career plan JSON object matching this EXACT schema:

{{
  "generated_at": "2026-01-16T12:00:00Z",
  "version": "1.0",
  "profile_summary": "150-500 char summary of user's background and transition goals",

  "target_roles": [
    {{
      "title": "Specific Job Title",
      "why_aligned": "How user's background maps to this role",
      "growth_outlook": "Job market data",
      "salary_range": "$XX,XXX - $XX,XXX",
      "typical_requirements": ["req1", "req2", "req3"],
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
2. Ensure every array has minimum items (target_roles: 1+, already_have skills: 3+, etc.)
3. Make timeline realistic given {intake.time_per_week} hours/week
4. Sequence certifications logically with clear prerequisites
5. Resume bullets must be achievement-focused with measurable outcomes
6. Profile summary must be 150-500 characters
7. Resume summary must be 100-1000 characters
8. Timeline must have 10-14 weekly tasks and 5-7 monthly phases (typically 12 weeks and 6 months)
9. If target_role_interest is empty, suggest 3-6 aligned roles based on user background
10. Return ONLY valid JSON - no markdown, no extra text

Generate the plan now:"""

        return prompt

    def _get_system_prompt(self) -> str:
        """System prompt for OpenAI"""

        return """You are an expert career transition coach and strategist.
You help professionals successfully transition to new career paths by:
- Analyzing transferable skills from their current background
- Identifying gaps and creating realistic learning plans
- Recommending certifications, education, and hands-on experience
- Building timelines that fit their constraints
- Crafting resume assets aligned to their target role

You ALWAYS return valid JSON matching the exact schema provided.
You NEVER invent URLs - only use URLs from verified research data.
You prioritize practical, actionable advice over theoretical concepts.
You ensure all recommendations are realistic given the user's time and budget constraints."""

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
                max_tokens=4000,
                response_format={"type": "json_object"}
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
