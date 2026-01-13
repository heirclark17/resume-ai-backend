from openai import OpenAI
from app.config import get_settings
import json
import os

settings = get_settings()

class OpenAIInterviewPrep:
    """AI service for interview prep generation using OpenAI GPT-4o"""

    def __init__(self):
        openai_api_key = os.getenv('OPENAI_API_KEY') or settings.openai_api_key

        if not openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Please set it in Railway environment variables."
            )

        try:
            self.client = OpenAI(api_key=openai_api_key)
        except Exception as e:
            raise ValueError(
                f"Failed to initialize OpenAI client: {str(e)}. "
                "Check that your OPENAI_API_KEY is valid and has access to GPT-4o."
            )

    async def generate_interview_prep(
        self,
        job_description: str,
        company_research: dict
    ) -> dict:
        """
        Generate interview prep data using OpenAI GPT-4o

        Args:
            job_description: Full job description text
            company_research: {mission_values, initiatives, team_culture, compliance, tech_stack, industry, sources}

        Returns:
            Complete interview prep JSON matching the schema
        """

        # Build company information text
        company_info = f"""
Company Industry: {company_research.get('industry', 'Unknown')}

Mission & Values:
{company_research.get('mission_values', 'No information available')}

Recent Initiatives & Programs:
{company_research.get('initiatives', 'No information available')}

Team Culture & Security Philosophy:
{company_research.get('team_culture', 'No information available')}

Compliance & Regulatory Environment:
{company_research.get('compliance', 'No information available')}

Technology Stack:
{company_research.get('tech_stack', 'No information available')}

Sources:
{json.dumps(company_research.get('sources', []), indent=2)}
"""

        # System prompt for interview prep generation
        system_prompt = """You are an AI assistant for a tailored resume web application.

In this app, a user first generates a tailored resume for a specific job.
From that screen, the user presses a button labeled something like
"View Interview Prep," which navigates them to a dedicated Interview Prep
page for that job and company.

Your ONLY task is to generate the structured data that will populate this
Interview Prep page.

You will be given:
- A job description (JD) for a specific role.
- Company information (may be unstructured research text with multiple sections).

CRITICAL: The company information may contain UNSTRUCTURED TEXT from research.
You MUST actively extract and structure this information:

1. **Values & Culture:** Search for company values, mission statements, cultural principles.
   - Look for keywords like "values", "mission", "culture", "principles", "what we believe"
   - Extract each value as a separate item with name and description
   - If sources/URLs are mentioned, include them
   - If no explicit values found, infer from company description

2. **Strategy & News:** Search for recent events, announcements, initiatives, strategic themes.
   - Look for dates (2024, 2025, 2026, "last year", "recently")
   - Look for keywords like "launched", "announced", "partnership", "acquisition", "expansion"
   - Extract specific events with dates and impact
   - Identify strategic themes and rationale
   - If no dates found, use "Recent" or "2025-2026"

3. **Handle Redundancy:** The company information may repeat the same text in multiple sections.
   - Read through ALL sections to find relevant information
   - Deduplicate and organize findings
   - Don't skip extraction just because text appears multiple times

You must:
- Analyze the JD and company information.
- **ACTIVELY EXTRACT** structured data from unstructured text.
- Produce a single valid JSON object that matches the JSON schema below.
- Write all content so it can be rendered directly on the Interview Prep page.

Important rules:
- Respond with JSON only, no markdown, no comments, no prose.
- Do not add or remove top-level keys.
- **DO NOT leave values_and_culture or strategy_and_news empty unless there is truly zero information.**
- For values: Extract at least 2-5 company values from the research text.
- For news: Extract at least 1-3 recent events or strategic themes from the research text.
- Be concise and avoid repetition; write in clear, plain language optimized for on-screen scanning.
- Use qualitative descriptors like "mid-sized", "fast-growing", "recent" when exact numbers aren't available.
- Focus on actionable, interview-oriented information.

JSON schema (structure and key names MUST be followed exactly):

{
  "company_profile": {
    "name": "string",
    "industry": "string",
    "locations": ["string"],
    "size_estimate": "string",
    "overview_paragraph": "string"
  },
  "values_and_culture": {
    "stated_values": [
      {
        "name": "string",
        "source_snippet": "string",
        "url": "string"
      }
    ],
    "practical_implications": [
      "string"
    ]
  },
  "strategy_and_news": {
    "recent_events": [
      {
        "date": "string",
        "title": "string",
        "impact_summary": "string"
      }
    ],
    "strategic_themes": [
      {
        "theme": "string",
        "rationale": "string"
      }
    ]
  },
  "role_analysis": {
    "job_title": "string",
    "seniority_level": "string",
    "core_responsibilities": [
      "string"
    ],
    "must_have_skills": [
      "string"
    ],
    "nice_to_have_skills": [
      "string"
    ],
    "success_signals_6_12_months": "string"
  },
  "interview_preparation": {
    "research_tasks": [
      "string"
    ],
    "practice_questions_for_candidate": [
      "string"
    ],
    "day_of_checklist": [
      "string"
    ]
  },
  "candidate_positioning": {
    "resume_focus_areas": [
      "string"
    ],
    "story_prompts": [
      {
        "title": "string",
        "description": "string",
        "star_hint": {
          "situation": "string",
          "task": "string",
          "action": "string",
          "result": "string"
        }
      }
    ],
    "keyword_map": [
      {
        "company_term": "string",
        "candidate_equivalent": "string",
        "context": "string"
      }
    ]
  },
  "questions_to_ask_interviewer": {
    "product": [
      "string"
    ],
    "team": [
      "string"
    ],
    "culture": [
      "string"
    ],
    "performance": [
      "string"
    ],
    "strategy": [
      "string"
    ]
  }
}

Return ONLY a single valid JSON object. Do not include any explanations or extra text."""

        user_prompt = f"""Here is the job description (JD):

{job_description}

Here is the company information (about page, careers/values, recent news, etc.):

{company_info}

Using ONLY the information above plus your general knowledge of interview
preparation and the STAR method, fill out the JSON schema defined in the
system prompt. The JSON will populate a dedicated Interview Prep page
that the user opened by pressing an "Interview Prep" button from their
tailored resume screen.

Return ONLY a single valid JSON object. Do not include any explanations
or extra text."""

        try:
            # Try multiple models in order of preference
            models_to_try = ["gpt-4o", "gpt-4o-mini"]

            response = None
            for model_name in models_to_try:
                try:
                    print(f"Attempting to generate interview prep with model: {model_name}")
                    response = self.client.chat.completions.create(
                        model=model_name,
                        max_tokens=4000,
                        temperature=0.7,
                        response_format={"type": "json_object"},  # Force JSON response
                        messages=[
                            {
                                "role": "system",
                                "content": system_prompt
                            },
                            {
                                "role": "user",
                                "content": user_prompt
                            }
                        ]
                    )
                    print(f"✓ Successfully generated interview prep with model: {model_name}")
                    break  # Success! Exit the loop
                except Exception as model_error:
                    print(f"✗ Model {model_name} failed: {str(model_error)}")
                    if model_name == models_to_try[-1]:
                        # This was the last model, re-raise the error
                        print(f"All models failed. Last error: {str(model_error)}")
                        raise
                    # Otherwise continue to next model
                    continue

            # Extract the response content
            content = response.choices[0].message.content

            # Try to parse as JSON
            try:
                prep_data = json.loads(content)
                return prep_data

            except (json.JSONDecodeError, ValueError) as e:
                print(f"Failed to parse OpenAI response as JSON: {e}")
                print(f"Response: {content}")
                raise ValueError(f"Failed to parse interview prep response: {e}")

        except Exception as e:
            print(f"OpenAI API error: {str(e)}")
            import traceback
            traceback.print_exc()
            raise ValueError(f"Failed to generate interview prep: {str(e)}")
