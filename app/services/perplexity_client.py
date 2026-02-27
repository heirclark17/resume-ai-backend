from openai import AsyncOpenAI
from app.config import get_settings
from app.services.gateway import get_gateway

settings = get_settings()

class PerplexityClient:
    """Client for Perplexity AI company research (async)"""

    def __init__(self):
        if not settings.perplexity_api_key:
            raise ValueError(
                "PERPLEXITY_API_KEY not found. Please set it in Railway environment variables, "
                "or set TEST_MODE=true to use mock data. "
                "Railway dashboard -> Variables -> Add Variable -> PERPLEXITY_API_KEY"
            )

        try:
            self.client = AsyncOpenAI(
                api_key=settings.perplexity_api_key,
                base_url="https://api.perplexity.ai"
            )
        except Exception as e:
            raise ValueError(
                f"Failed to initialize Perplexity client: {str(e)}. "
                "Check that your PERPLEXITY_API_KEY is valid."
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

        # Build comprehensive research prompt for interview prep
        job_context = f" for a {job_title} position" if job_title else ""
        prompt = f"""Research {company_name} thoroughly and provide detailed information for interview preparation{job_context}. Include:

1. **Company Profile:**
   - Industry sector and business model
   - Company size (revenue, employees, market position)
   - Headquarters and office locations
   - Brief company overview (2-3 sentences)

2. **Mission & Values:**
   - Official mission statement (exact wording with source URL if available)
   - Core company values (list each with brief explanation and source)
   - Cultural principles and work environment
   - What the company prioritizes or emphasizes

3. **Recent News & Strategy (Last 12 Months):**
   - Major announcements, product launches, or acquisitions (with dates)
   - Strategic initiatives and business priorities
   - Leadership changes or organizational shifts
   - Financial performance, funding, or growth news
   - Industry recognition or awards

4. **Industry Position:**
   - Market position and competitive landscape
   - Key differentiators or unique strengths
   - Strategic partnerships or major clients/customers
   - Technology stack or platforms they use

5. **Work Culture & Employee Experience:**
   - Work-life balance and employee benefits
   - Career development and growth opportunities
   - Diversity, equity, and inclusion initiatives
   - Employee reviews or glassdoor ratings if available
   - Recognition as a top employer

6. **For Job Candidates:**
   - What this company values most in candidates
   - Key skills or experiences they prioritize
   - Interview process insights if available
   - Growth opportunities in this field/role

Format your response with clear section headers and bullet points. Include specific facts, numbers, dates, and URLs where available. Provide enough detail for someone preparing for an interview."""


        try:
            response = await get_gateway().execute("perplexity", self.client.chat.completions.create,
                model="sonar",
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

    async def research_with_citations(self, query: str) -> dict:
        """
        Research a topic using Perplexity AI with citations

        This is the PRIMARY method for getting real company data.
        Returns web-sourced research with actual URLs, dates, and sources.

        Args:
            query: Research question or prompt

        Returns:
            {
                "content": str,  # Research findings
                "citations": [   # Real articles with URLs
                    {
                        "title": "Article title",
                        "url": "https://...",
                        "text": "Excerpt from source"
                    }
                ],
                "timestamp": str
            }
        """

        # TEST MODE: Return mock citations
        if settings.test_mode:
            print(f"[TEST MODE] Simulating Perplexity research with citations")
            return {
                "content": f"Research findings for: {query[:100]}...\n\nMock research results with citations.",
                "citations": [
                    {
                        "title": "Example Article 1",
                        "url": "https://example.com/article1",
                        "text": "Sample citation text"
                    }
                ],
                "timestamp": "2026-01-16T00:00:00Z"
            }

        try:
            # Use Perplexity's sonar model for web search with citations
            # Note: Perplexity automatically returns citations in the response
            # Model updated to latest: https://docs.perplexity.ai/guides/model-cards
            response = await get_gateway().execute("perplexity", self.client.chat.completions.create,
                model="sonar",  # Latest Perplexity model with web search
                messages=[
                    {
                        "role": "system",
                        "content": "You are a research assistant. Provide detailed, factual information with specific sources and dates. Always cite your sources."
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                temperature=0.2,
                max_tokens=2000
            )

            content = response.choices[0].message.content

            # Extract citations from Perplexity response
            # Perplexity's sonar model returns citations as URLs in the response
            citations = []

            # Check for citations in various possible locations
            if hasattr(response, 'citations') and response.citations:
                # Citations might be a list of URLs (strings) or dictionaries
                for citation in response.citations:
                    if isinstance(citation, str):
                        # Citation is just a URL string
                        citations.append({
                            "title": "Source",
                            "url": citation,
                            "text": ""
                        })
                    elif isinstance(citation, dict):
                        # Citation is a dictionary
                        citations.append({
                            "title": citation.get("title", "Source"),
                            "url": citation.get("url", citation.get("link", "")),
                            "text": citation.get("text", citation.get("snippet", ""))
                        })

            # Also check for sources/references in message metadata
            if hasattr(response.choices[0].message, 'metadata'):
                metadata = response.choices[0].message.metadata
                if isinstance(metadata, dict) and 'citations' in metadata:
                    for citation in metadata.get('citations', []):
                        if isinstance(citation, str):
                            citations.append({
                                "title": "Source",
                                "url": citation,
                                "text": ""
                            })

            print(f"✓ Perplexity research completed: {len(citations)} citations found")

            return {
                "content": content,
                "citations": citations,
                "timestamp": response.created if hasattr(response, 'created') else None
            }

        except Exception as e:
            print(f"Perplexity research_with_citations error: {str(e)}")
            return {
                "content": "",
                "citations": [],
                "timestamp": None,
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
            response = await get_gateway().execute("perplexity", self.client.chat.completions.create,
                model="sonar",
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

    async def research_salary_insights(
        self,
        job_title: str,
        location: str = None,
        experience_level: str = None,
        skills: list = None
    ) -> dict:
        """
        Research real-time salary data for a specific job title and location.

        Args:
            job_title: The job title to research (e.g., "Senior Software Engineer")
            location: Location for salary research (e.g., "San Francisco, CA", "Remote")
            experience_level: Experience level (e.g., "Senior", "Mid-level", "Entry-level")
            skills: List of key skills that may affect salary

        Returns:
            {
                "salary_range": str,  # e.g., "$120,000 - $180,000"
                "median_salary": str,  # e.g., "$150,000"
                "percentile_25": str,  # 25th percentile
                "percentile_75": str,  # 75th percentile
                "market_insights": str,  # Growth trends, demand, etc.
                "sources": list,  # Citations from web sources
                "last_updated": str  # When the data was retrieved
            }
        """

        # Build comprehensive prompt
        location_str = f" in {location}" if location else ""
        experience_str = f" at the {experience_level} level" if experience_level else ""
        skills_str = f" with skills in {', '.join(skills[:5])}" if skills else ""

        prompt = f"""Research current salary data for {job_title}{location_str}{experience_str}{skills_str}.

Please provide:
1. Current salary range (minimum to maximum)
2. Median/average salary
3. 25th percentile salary (lower quartile)
4. 75th percentile salary (upper quartile)
5. Market insights including:
   - Current demand and hiring trends
   - Year-over-year salary growth
   - Industry-specific factors affecting compensation
   - Remote vs in-office salary differences (if applicable)
6. Data sources and when they were published

Focus on data from 2024-2025. Include citations from sources like Glassdoor, Levels.fyi, Bureau of Labor Statistics, Payscale, LinkedIn Salary, or company-specific data."""

        try:
            response = await get_gateway().execute("perplexity", self.client.chat.completions.create,
                model="sonar",  # Sonar model has real-time web access
                messages=[
                    {
                        "role": "system",
                        "content": "You are a compensation research analyst with access to real-time salary data from multiple sources. Provide accurate, web-grounded salary insights with proper citations."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,  # Low temperature for factual accuracy
                max_tokens=2000
            )

            raw_content = response.choices[0].message.content
            citations = getattr(response, 'citations', []) if hasattr(response, 'citations') else []

            # Parse the response to extract structured data
            import re
            from datetime import datetime

            # Extract salary range
            salary_range_match = re.search(r'\$[\d,]+\s*[-–]\s*\$[\d,]+', raw_content)
            salary_range = salary_range_match.group(0) if salary_range_match else "Data not available"

            # Extract median/average
            median_match = re.search(r'(?:median|average)[:\s]+\$[\d,]+', raw_content, re.IGNORECASE)
            median_salary = median_match.group(0).split('$')[-1] if median_match else "Data not available"
            if median_salary != "Data not available":
                median_salary = f"${median_salary}"

            return {
                "salary_range": salary_range,
                "median_salary": median_salary,
                "market_insights": raw_content,
                "sources": citations,
                "last_updated": datetime.now().isoformat(),
                "raw_response": raw_content
            }

        except Exception as e:
            print(f"Perplexity salary research error: {str(e)}")
            return {
                "error": str(e),
                "salary_range": "Data unavailable",
                "median_salary": "Data unavailable",
                "market_insights": f"Unable to retrieve salary data: {str(e)}",
                "sources": [],
                "last_updated": None
            }
