from openai import OpenAI
from app.config import get_settings
import json
import os
import re

settings = get_settings()

class OpenAITailor:
    """AI service for resume tailoring using OpenAI GPT-4o"""

    def __init__(self):
        openai_api_key = os.getenv('OPENAI_API_KEY') or settings.openai_api_key

        if not openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Please set it in Railway environment variables, "
                "or set TEST_MODE=true to use mock data. "
                "Railway dashboard -> Variables -> Add Variable -> OPENAI_API_KEY"
            )

        try:
            self.client = OpenAI(api_key=openai_api_key)
        except Exception as e:
            raise ValueError(
                f"Failed to initialize OpenAI client: {str(e)}. "
                "Check that your OPENAI_API_KEY is valid and has access to GPT-4o."
            )

    async def tailor_resume(
        self,
        base_resume: dict,
        company_research: dict,
        job_details: dict
    ) -> dict:
        """
        Tailor resume using OpenAI GPT-4o

        Args:
            base_resume: {summary, skills, experience, education, certifications}
            company_research: {company, research, ...}
            job_details: {company, title, url, description}

        Returns:
            {
                "summary": str,
                "skills": list,
                "experience": list,
                "competencies": list,
                "alignment_statement": str
            }
        """

        # TEST MODE: Return mock tailored content
        if settings.test_mode:
            print(f"[TEST MODE] Simulating AI tailoring for {job_details.get('company')}")
            return {
                "summary": f"Senior Cybersecurity Program Manager with 10+ years driving security initiatives for {job_details.get('company')}. Expertise in breaking down complex security objectives into executable strategies while managing cross-functional stakeholders and delivering resilient solutions aligned with {job_details.get('company')}'s mission. Track record of reducing operational risk, accelerating secure delivery, and building governance structures that enable business growth. Experienced in NIST, ISO 27001, and enterprise-scale security program management.",
                "experience": base_resume.get('experience', []),  # Keep original experience
                "competencies": [
                    "Cybersecurity Program Leadership",
                    "Risk & Control Frameworks (NIST, ISO 27001)",
                    "Stakeholder & Executive Communication",
                    f"{job_details.get('company')} Security Standards",
                    "Technology Risk Governance",
                    "Cloud Security & AI Controls",
                    "Threat & Vulnerability Management",
                    "Cross-Functional Team Leadership",
                    "Agile Program Delivery",
                    "Security Architecture & Resiliency",
                    "Compliance & Audit Management",
                    "Incident Response Coordination"
                ],
                "alignment_statement": f"Committed to {job_details.get('company')}'s mission to deliver innovative solutions through cutting-edge technology and exceptional service. Aligned with core values of innovation, customer-centricity, and integrity. Ready to contribute to {job_details.get('company')}'s cybersecurity initiatives by delivering scalable security solutions that enable business growth while maintaining the highest standards of operational excellence."
            }

        # Build tailoring prompt
        prompt = f"""You are a professional resume writer specializing in cybersecurity and technology roles.

TASK: Tailor the provided base resume for a specific job opportunity.

BASE RESUME:
Summary: {base_resume.get('summary', '')}

Skills: {json.dumps(base_resume.get('skills', []), indent=2)}

Experience: {json.dumps(base_resume.get('experience', []), indent=2)}

Education: {base_resume.get('education', '')}

Certifications: {base_resume.get('certifications', '')}

---

JOB DETAILS:
Company: {job_details.get('company', 'Unknown')}
Title: {job_details.get('title', 'Unknown')}
Description: {job_details.get('description', 'N/A')}
URL: {job_details.get('url', 'N/A')}

---

COMPANY RESEARCH:
{company_research.get('research', 'No research available')}

---

CRITICAL INSTRUCTIONS:

1. **ANALYZE JOB DESCRIPTION FIRST**
   - Identify the key responsibilities, required skills, and qualifications
   - Note the specific terminology, frameworks, and technologies mentioned
   - Understand what type of role this is (technical, managerial, strategic, etc.)

2. **REFRAME JOB TITLES**
   - Change each original job title to better reflect the TARGET role
   - If applying for "Cybersecurity Program Manager", reframe past titles like:
     * "Project Manager" → "Cybersecurity Implementation Project Manager"
     * "Operations Manager" → "Security Operations Program Manager"
   - Keep company names and dates exactly as they are
   - Format: "[Reframed Title] – [Original Company]"

3. **REWRITE ALL EXPERIENCE BULLETS TO MATCH JOB DESCRIPTION**
   - **ONLY include experience relevant to this specific job**
   - If job is for cybersecurity, DO NOT mention sales, customer service, or unrelated work
   - Frame EVERY bullet to emphasize skills from the job description
   - Example transformations:
     * Sales experience → "Stakeholder engagement and requirements gathering"
     * Customer service → "User security awareness and incident response coordination"
     * General project management → Specific security/technical program management
   - Add measurable outcomes (%, numbers, scale)
   - Use terminology from the job description

4. **TAILOR PROFESSIONAL SUMMARY**
   - Lead with years of experience in the TARGET field
   - Mention specific skills from job description
   - Reference company's mission or recent initiatives
   - Keep to 3-4 sentences maximum

5. **CREATE 12 CORE COMPETENCIES**
   - Pull directly from job description requirements
   - Match exact terminology when possible
   - Include frameworks/tools mentioned in job posting
   - Mix technical skills and leadership/soft skills

6. **ALIGNMENT STATEMENT**
   - Connect candidate's experience to company's mission
   - Reference specific company initiatives or values
   - Show understanding of company's industry challenges

7. **PRESERVE EDUCATION & CERTIFICATIONS**
   - Return education text exactly as provided
   - Return certifications text exactly as provided
   - Do NOT modify these sections

Return ONLY a valid JSON object with this structure:
{{
  "summary": "tailored professional summary (3-4 sentences)",
  "experience": [
    {{
      "header": "[Reframed Title] – [Company] | [Location] | [Dates]",
      "bullets": [
        "Bullet rewritten to match job requirements with measurable outcome",
        "Another bullet emphasizing relevant skills from job description",
        "..."
      ]
    }}
  ],
  "competencies": ["competency 1", "competency 2", ... (12 total matching job description)],
  "alignment_statement": "statement connecting candidate to company mission",
  "education": "{base_resume.get('education', '')}",
  "certifications": "{base_resume.get('certifications', '')}"
}}
"""

        try:
            # Use gpt-4.1-mini (user has API key for this model)
            models_to_try = ["gpt-4.1-mini"]

            response = None
            for model_name in models_to_try:
                try:
                    print(f"Attempting to use model: {model_name}")
                    response = self.client.chat.completions.create(
                        model=model_name,
                        max_tokens=4000,
                        temperature=0.7,
                        response_format={"type": "json_object"},  # Force JSON response
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a professional resume writer specializing in cybersecurity and technology roles. Return only valid JSON."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    )
                    print(f"✓ Successfully used model: {model_name}")
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
                # With response_format="json_object", OpenAI returns clean JSON
                tailored = json.loads(content)

                # Ensure required fields exist
                tailored.setdefault('summary', base_resume.get('summary', ''))
                tailored.setdefault('experience', base_resume.get('experience', []))
                tailored.setdefault('competencies', [])
                tailored.setdefault('alignment_statement', '')
                tailored.setdefault('education', base_resume.get('education', ''))
                tailored.setdefault('certifications', base_resume.get('certifications', ''))

                # Clean up experience bullets - remove separator characters
                for exp in tailored.get('experience', []):
                    if 'bullets' in exp and isinstance(exp['bullets'], list):
                        # Filter out empty bullets and bullets containing only separators/whitespace
                        # This regex catches any combination of whitespace and separator characters
                        exp['bullets'] = [
                            bullet for bullet in exp['bullets']
                            if bullet and bullet.strip() and not re.match(r'^[\s\|\/•\-–—]+$', bullet.strip())
                        ]

                return tailored

            except (json.JSONDecodeError, ValueError) as e:
                print(f"Failed to parse OpenAI response as JSON: {e}")
                print(f"Response: {content}")

                # Return base resume as fallback
                cleaned_experience = []
                for exp in base_resume.get('experience', []):
                    if isinstance(exp, dict) and 'bullets' in exp:
                        cleaned_exp = exp.copy()
                        # Filter out empty bullets and bullets containing only separators/whitespace
                        cleaned_exp['bullets'] = [
                            bullet for bullet in exp.get('bullets', [])
                            if bullet and bullet.strip() and not re.match(r'^[\s\|\/•\-–—]+$', bullet.strip())
                        ]
                        cleaned_experience.append(cleaned_exp)
                    else:
                        cleaned_experience.append(exp)

                return {
                    "summary": base_resume.get('summary', ''),
                    "experience": cleaned_experience,
                    "competencies": [],
                    "alignment_statement": f"Tailored for {job_details.get('company', 'this company')}",
                    "education": base_resume.get('education', ''),
                    "certifications": base_resume.get('certifications', ''),
                    "error": "Failed to parse tailored resume",
                    "raw_response": content
                }

        except Exception as e:
            print(f"OpenAI API error: {str(e)}")
            import traceback
            traceback.print_exc()
            # Return base resume as fallback
            return {
                "summary": base_resume.get('summary', ''),
                "experience": base_resume.get('experience', []),
                "competencies": [],
                "alignment_statement": "",
                "error": str(e)
            }
