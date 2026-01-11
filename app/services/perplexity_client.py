from openai import OpenAI
from app.config import get_settings

settings = get_settings()

class PerplexityClient:
    """Client for Perplexity AI company research"""

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.perplexity_api_key,
            base_url="https://api.perplexity.ai"
        )

    async def research_company(self, company_name: str, job_title: str = "") -> dict:
        """
        Research company using Perplexity AI

        Returns:
            {
                "mission": str,
                "values": list,
                "initiatives": list,
                "industry": str,
                "culture": str,
                "recent_news": list
            }
        """

        # TEST MODE: Return mock data
        if settings.test_mode:
            print(f"[TEST MODE] Simulating Perplexity research for {company_name}")
            return {
                "company": company_name,
                "research": f"""
{company_name} Company Research

MISSION: {company_name}'s mission is to deliver innovative solutions that empower businesses and individuals through cutting-edge technology and exceptional service.

CORE VALUES:
- Innovation and Excellence
- Customer-Centric Approach
- Integrity and Transparency
- Collaboration and Teamwork
- Continuous Improvement

RECENT INITIATIVES (Last 12 Months):
- Launched new cloud security platform with AI-driven threat detection
- Expanded cybersecurity operations to support Fortune 500 clients
- Invested $500M in digital transformation and modernization programs
- Achieved ISO 27001 and SOC 2 Type II certifications
- Established Cybersecurity Center of Excellence

INDUSTRY FOCUS:
{company_name} operates in the technology and cybersecurity sector, serving clients across financial services, healthcare, and enterprise technology markets.

COMPANY CULTURE:
Known for fostering a collaborative environment that values innovation, professional growth, and work-life balance. Strong emphasis on continuous learning and certification support for cybersecurity professionals.

RECENT NEWS:
- Named a Leader in Gartner Magic Quadrant for Security Services
- Recognized as Top Employer for Cybersecurity Professionals
- Announced strategic partnership with leading cloud providers
""",
                "raw_response": f"[TEST MODE] Mock research for {company_name}"
            }

        # Build research prompt
        prompt = f"""Research {company_name} and provide:

1. Company mission statement (exact wording)
2. Core values (3-5 key principles)
3. Major recent initiatives or programs (last 12 months)
4. Industry focus and business areas
5. Company culture and work environment
6. Recent news or significant announcements

Format the response as a detailed analysis focusing on information relevant for tailoring a cybersecurity/technology resume{' for a ' + job_title + ' position' if job_title else ''}.
"""

        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-sonar-large-128k-online",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a research assistant helping with resume customization. Provide detailed, factual information about companies."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=2000
            )

            research_text = response.choices[0].message.content

            # Parse the research into structured data
            # For now, return as unstructured text
            # TODO: Parse into structured format
            return {
                "company": company_name,
                "research": research_text,
                "raw_response": research_text
            }

        except Exception as e:
            print(f"Perplexity API error: {str(e)}")
            # Return fallback data
            return {
                "company": company_name,
                "research": f"Unable to research {company_name} at this time.",
                "error": str(e)
            }

    async def analyze_job_posting(self, job_url: str = None, job_description: str = None) -> dict:
        """
        Analyze a job posting to extract key requirements

        Returns:
            {
                "title": str,
                "company": str,
                "key_skills": list,
                "required_frameworks": list,
                "experience_level": str,
                "salary_range": str
            }
        """

        if job_url:
            prompt = f"Analyze the job posting at {job_url} and extract the job title, company, key required skills, frameworks/certifications mentioned, and experience level requirements."
        elif job_description:
            prompt = f"Analyze this job description and extract key requirements:\n\n{job_description}"
        else:
            return {"error": "No job URL or description provided"}

        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-sonar-large-128k-online",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a job posting analyzer. Extract structured information from job postings."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=1500
            )

            analysis = response.choices[0].message.content

            return {
                "analysis": analysis,
                "raw_response": analysis
            }

        except Exception as e:
            print(f"Perplexity API error: {str(e)}")
            return {"error": str(e)}
