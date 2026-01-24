from openai import OpenAI
from app.config import get_settings
from app.services.company_research_service import CompanyResearchService
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
            self.company_research_service = CompanyResearchService()
        except Exception as e:
            raise ValueError(
                f"Failed to initialize OpenAI client: {str(e)}. "
                "Check that your OPENAI_API_KEY is valid and has access to GPT-4o."
            )

    async def generate_interview_prep(
        self,
        job_description: str,
        company_research: dict,
        company_name: str = None,
        job_title: str = None
    ) -> dict:
        """
        Generate interview prep data using OpenAI GPT-4o with Perplexity-powered values research

        Args:
            job_description: Full job description text
            company_research: {mission_values, initiatives, team_culture, compliance, tech_stack, industry, sources}
            company_name: Company name for Perplexity research
            job_title: Job title for context

        Returns:
            Complete interview prep JSON matching the schema
        """

        # STEP 1: Fetch REAL company values using Perplexity
        perplexity_values = None
        if company_name:
            try:
                print(f"🔍 Fetching real company values from Perplexity for: {company_name}")
                perplexity_values = await self.company_research_service.research_company_values_culture(
                    company_name=company_name,
                    industry=company_research.get('industry'),
                    job_title=job_title
                )
                print(f"✓ Perplexity returned {len(perplexity_values.get('stated_values', []))} real values")
            except Exception as e:
                print(f"⚠️ Perplexity values research failed: {e}, will use GPT inference")
                perplexity_values = None

        # Build real values section if Perplexity data available
        real_values_section = ""
        if perplexity_values and perplexity_values.get('stated_values'):
            real_values_section = "\n\n=== REAL COMPANY VALUES (FROM PERPLEXITY WEB RESEARCH) ===\n"
            real_values_section += "USE THESE EXACT VALUES - DO NOT INFER OR MAKE UP VALUES:\n\n"

            for value in perplexity_values.get('stated_values', []):
                real_values_section += f"- {value.get('name', 'Unknown')}: {value.get('description', value.get('source_snippet', ''))}\n"
                if value.get('url'):
                    real_values_section += f"  Source: {value.get('url')}\n"

            if perplexity_values.get('cultural_priorities'):
                real_values_section += f"\nCultural Priorities: {', '.join(perplexity_values.get('cultural_priorities', []))}\n"

            if perplexity_values.get('work_environment'):
                real_values_section += f"\nWork Environment: {perplexity_values.get('work_environment')}\n"

            real_values_section += "\n=== END REAL VALUES ===\n"

        # Build company information text
        company_info = f"""
Company Industry: {company_research.get('industry', 'Unknown')}
{real_values_section}
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
- **REAL COMPANY VALUES** from Perplexity web research (if available, marked with === REAL COMPANY VALUES ===)

CRITICAL INSTRUCTIONS FOR VALUES & CULTURE:

**IF "=== REAL COMPANY VALUES (FROM PERPLEXITY WEB RESEARCH) ===" IS PROVIDED:**
- You MUST use ONLY those values in the values_and_culture.stated_values section
- DO NOT infer, guess, or make up additional values
- Copy the value names and descriptions exactly as provided
- Include the source URLs provided
- These are REAL values from the company's official website

**IF NO REAL VALUES ARE PROVIDED:**
- Then you may infer values from the company research text
- Look for keywords like "values", "mission", "culture", "principles"

For OTHER sections (Strategy & News, Role Analysis, etc.):

1. **Strategy & News:** AGGRESSIVELY search for recent events, announcements, initiatives, strategic themes.
   - Look for dates (2024, 2025, 2026, "last year", "recently", "Q1", "Q2", "Q3", "Q4")
   - Look for keywords like "launched", "announced", "partnership", "acquisition", "expansion", "raised", "funding", "growth", "transformation", "initiative"
   - Look for financial news ($X million, revenue, investment, valuation)
   - Look for product launches, new markets, executive changes, strategic pivots
   - Extract specific events with dates and impact
   - Identify strategic themes and rationale
   - **MINIMUM: Extract at least 3-5 recent events or strategic themes**
   - If specific dates not found, use "2025", "Recent", or "Last 12 months"
   - Infer strategic direction from job description if company info is limited
   - Use industry trends if company-specific news is unavailable

2. **Handle Redundancy:** The company information may repeat the same text in multiple sections.
   - Read through ALL sections to find relevant information
   - Deduplicate and organize findings
   - Don't skip extraction just because text appears multiple times

You must:
- Analyze the JD and company information.
- **USE REAL VALUES** from Perplexity when provided (don't infer if real values exist).
- Produce a single valid JSON object that matches the JSON schema below.
- Write all content so it can be rendered directly on the Interview Prep page.

Important rules:
- Respond with JSON only, no markdown, no comments, no prose.
- Do not add or remove top-level keys.
- **For values_and_culture.stated_values: USE REAL VALUES if provided. Only infer if no real values given.**
- **For strategy_and_news.recent_events: MINIMUM 3-5 events. Extract from text or infer from job description/industry trends.**
- **For strategy_and_news.strategic_themes: MINIMUM 2-4 themes. Identify patterns from available information.**
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

Using the information above, fill out the JSON schema defined in the
system prompt. The JSON will populate a dedicated Interview Prep page.

**CRITICAL REQUIREMENTS FOR VALUES & CULTURE:**
- If "=== REAL COMPANY VALUES (FROM PERPLEXITY WEB RESEARCH) ===" section is present above:
  - Use ONLY those exact values in values_and_culture.stated_values
  - Include the source URLs provided
  - DO NOT add or infer additional values
- If NO real values section is present:
  - Then infer 3-5 values from the company research text

**CRITICAL REQUIREMENTS FOR OTHER SECTIONS:**
1. strategy_and_news.recent_events: MUST have 3-5 items (extract or infer)
2. strategy_and_news.strategic_themes: MUST have 2-4 items (extract or infer)

If company information is limited for strategy/news:
- Infer recent events from industry trends (e.g., "AI adoption", "Cloud migration", "Security investment")
- Infer strategic themes from job requirements and market position

**DO NOT return empty arrays for these critical sections.**

Return ONLY a single valid JSON object. Do not include any explanations
or extra text."""

        try:
            # Use gpt-4.1-mini (user has API key for this model)
            models_to_try = ["gpt-4.1-mini"]

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
