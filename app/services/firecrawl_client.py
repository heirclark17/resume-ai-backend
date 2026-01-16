"""
Firecrawl client for extracting job posting details from URLs
"""
import os
import asyncio
from typing import Dict, Any, Optional, List
from functools import partial
from app.config import get_settings

settings = get_settings()


class FirecrawlClient:
    """Client for extracting job details from job posting URLs using Firecrawl"""

    def __init__(self):
        """Initialize Firecrawl client"""
        # Firecrawl is available via MCP, no initialization needed
        pass

    async def extract_job_details(self, job_url: str) -> Dict[str, Any]:
        """
        Extract structured job details from a job posting URL

        Args:
            job_url: URL to job posting (LinkedIn, Indeed, company site, etc.)

        Returns:
            Dictionary with extracted job details:
            {
                "company": str,
                "title": str,
                "description": str,
                "location": str,
                "salary": str,
                "posted_date": str,
                "employment_type": str,
                "experience_level": str,
                "skills_required": list[str],
                "raw_text": str
            }
        """
        print(f"Extracting job details from URL: {job_url}")

        # TEST MODE: Return mock data
        if settings.test_mode:
            print("[TEST MODE] Returning mock job extraction data")
            return {
                "company": "Microsoft",
                "title": "Senior Cybersecurity Program Manager",
                "description": "We are seeking an experienced Cybersecurity Program Manager to lead security initiatives across cloud infrastructure, AI systems, and enterprise applications. The ideal candidate will have 8+ years of experience in security program management, risk frameworks (NIST, ISO 27001), and stakeholder communication. Responsibilities include driving security roadmaps, managing cross-functional teams, implementing security controls, and reporting to executive leadership on cyber risk posture.",
                "location": "Redmond, WA (Hybrid)",
                "salary": "$150,000 - $200,000",
                "posted_date": "2 days ago",
                "employment_type": "Full-time",
                "experience_level": "Senior",
                "skills_required": [
                    "Cybersecurity Program Management",
                    "NIST Cybersecurity Framework",
                    "ISO 27001",
                    "Risk Assessment",
                    "Cloud Security (Azure, AWS)",
                    "Security Architecture",
                    "Stakeholder Management",
                    "Incident Response",
                    "Compliance & Audit"
                ],
                "raw_text": job_url
            }

        try:
            # Use Firecrawl to scrape the job page content first
            # We'll scrape to get clean markdown, then extract structured data from it
            from firecrawl import FirecrawlApp

            firecrawl_api_key = os.getenv('FIRECRAWL_API_KEY', '')

            if not firecrawl_api_key:
                raise ValueError(
                    "FIRECRAWL_API_KEY not found. Please set it in Railway environment variables, "
                    "or set TEST_MODE=true to use mock data."
                )

            app = FirecrawlApp(api_key=firecrawl_api_key)

            print("Scraping job page with Firecrawl...")

            # Run synchronous Firecrawl operations in thread pool
            # Scrape the page to get clean content (v2 API uses scrape() with keyword args)
            scrape_result = await asyncio.to_thread(
                app.scrape,
                job_url,
                formats=['markdown'],
                only_main_content=True  # Focus on main content, skip headers/footers
            )

            # v2 SDK returns a Document object (Pydantic model), access attributes directly
            if not scrape_result or not hasattr(scrape_result, 'markdown') or not scrape_result.markdown:
                raise ValueError("Failed to scrape job page - no content returned")

            markdown_content = scrape_result.markdown
            print(f"Job page scraped: {len(markdown_content)} characters")

            # Now use Firecrawl's extract feature to get structured data (v2 API uses scrape with JSON format)
            print("Extracting structured job data...")

            extract_result = await asyncio.to_thread(
                app.scrape,
                job_url,
                formats=[{
                    'type': 'json',
                    'prompt': 'Extract all job posting details including company name, job title, full job description, location, salary range, posted date, employment type (full-time/part-time/contract), experience level, and required skills.',
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'company': {
                                'type': 'string',
                                'description': 'Company name'
                            },
                            'title': {
                                'type': 'string',
                                'description': 'Job title/position name'
                            },
                            'description': {
                                'type': 'string',
                                'description': 'Full job description including responsibilities, requirements, and qualifications'
                            },
                            'location': {
                                'type': 'string',
                                'description': 'Job location (city, state, country, or remote)'
                            },
                            'salary': {
                                'type': 'string',
                                'description': 'Salary range or compensation details if mentioned'
                            },
                            'posted_date': {
                                'type': 'string',
                                'description': 'When the job was posted (e.g., "2 days ago", "January 10, 2026")'
                            },
                            'employment_type': {
                                'type': 'string',
                                'description': 'Full-time, Part-time, Contract, Temporary, etc.'
                            },
                            'experience_level': {
                                'type': 'string',
                                'description': 'Entry level, Mid-level, Senior, Lead, etc.'
                            },
                            'skills_required': {
                                'type': 'array',
                                'items': {'type': 'string'},
                                'description': 'List of required skills, technologies, or qualifications'
                            }
                        },
                        'required': ['company', 'title', 'description']
                    }
                }],
                only_main_content=False,
                timeout=120000
            )

            # Check if extraction succeeded (v2 SDK returns Document object with json attribute)
            extracted_data = None
            if extract_result and hasattr(extract_result, 'json') and extract_result.json:
                # The json attribute might be a Pydantic model or dict - convert to dict if needed
                json_data = extract_result.json
                if hasattr(json_data, 'model_dump'):
                    extracted_data = json_data.model_dump()
                elif hasattr(json_data, 'dict'):
                    extracted_data = json_data.dict()
                elif isinstance(json_data, dict):
                    extracted_data = json_data
                else:
                    extracted_data = dict(json_data) if json_data else None
                print(f"Firecrawl extraction succeeded")
            else:
                print("Firecrawl extraction returned no data, will use OpenAI fallback")

            # If Firecrawl extraction failed or returned Unknown values, use OpenAI as fallback
            company = extracted_data.get('company', '') if extracted_data else ''
            title = extracted_data.get('title', '') if extracted_data else ''

            # Check if we got actual data or just defaults
            if not company or company == 'Unknown Company' or not title or title == 'Unknown Position':
                print("Company or title missing, using OpenAI to extract from markdown content...")

                # Use OpenAI to extract company and title from the scraped markdown
                from openai import OpenAI
                openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

                extraction_prompt = f"""Extract the company name and job title from this job posting.

Job Posting Content:
{markdown_content[:3000]}

Return ONLY a JSON object with this structure:
{{
  "company": "exact company name",
  "title": "exact job title"
}}

Do not include any other text, only the JSON."""

                try:
                    ai_response = await asyncio.to_thread(
                        openai_client.chat.completions.create,
                        model="gpt-4.1-mini",
                        messages=[
                            {"role": "system", "content": "You are a job posting analyzer. Extract company name and job title accurately."},
                            {"role": "user", "content": extraction_prompt}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.1
                    )

                    import json
                    ai_extracted = json.loads(ai_response.choices[0].message.content)
                    company = ai_extracted.get('company', company)
                    title = ai_extracted.get('title', title)
                    print(f"✓ OpenAI extracted: {company} - {title}")

                except Exception as ai_error:
                    print(f"WARNING: OpenAI extraction also failed: {ai_error}")
                    # If both fail, we'll use what we have or raise error below

            # Final validation - don't allow Unknown values
            if not company or company == 'Unknown Company':
                raise ValueError(
                    "Could not extract company name from job URL. "
                    "Please provide the company name manually using the 'company' field."
                )

            if not title or title == 'Unknown Position':
                raise ValueError(
                    "Could not extract job title from job URL. "
                    "Please provide the job title manually using the 'jobTitle' field."
                )

            # Combine extracted data with raw markdown
            result = {
                "company": company,
                "title": title,
                "description": extracted_data.get('description', '') if extracted_data else markdown_content[:2000],
                "location": extracted_data.get('location', '') if extracted_data else '',
                "salary": extracted_data.get('salary', '') if extracted_data else '',
                "posted_date": extracted_data.get('posted_date', '') if extracted_data else '',
                "employment_type": extracted_data.get('employment_type', '') if extracted_data else '',
                "experience_level": extracted_data.get('experience_level', '') if extracted_data else '',
                "skills_required": extracted_data.get('skills_required', []) if extracted_data else [],
                "raw_text": markdown_content
            }

            print(f"✓ Final extracted data: {result['company']} - {result['title']}")
            return await self.validate_extraction_result(result, job_url)

        except ImportError:
            print("WARNING: Firecrawl package not installed. Install with: pip install firecrawl-py")
            raise ValueError(
                "Firecrawl not available. Please install: pip install firecrawl-py, "
                "or set TEST_MODE=true to use mock data."
            )
        except Exception as e:
            print(f"Firecrawl extraction error: {str(e)}")

            # Try Playwright as fallback for sites that block Firecrawl
            try:
                print("Attempting Playwright fallback extraction...")
                from app.services.playwright_extractor import PlaywrightJobExtractor

                extractor = PlaywrightJobExtractor()
                playwright_result = await extractor.extract_job_details(job_url)

                print(f"✓ Playwright extraction succeeded: {playwright_result['company']} - {playwright_result['title']}")
                return await self.validate_extraction_result(playwright_result, job_url)

            except Exception as playwright_error:
                print(f"Playwright extraction also failed: {playwright_error}")

                # Try GPT-4 Vision + Screenshot API as final fallback
                try:
                    print("Attempting GPT-4 Vision + Screenshot API fallback...")
                    from app.services.vision_extractor import VisionJobExtractor

                    vision_extractor = VisionJobExtractor()
                    vision_result = await vision_extractor.extract_from_url(job_url)

                    print(f"✓ Vision extraction succeeded: {vision_result['company']} - {vision_result['title']}")
                    return await self.validate_extraction_result(vision_result, job_url)

                except Exception as vision_error:
                    print(f"Vision extraction also failed: {vision_error}")
                    # All methods failed
                    raise ValueError(
                        f"Failed to extract job details from URL. "
                        f"Firecrawl failed: {str(e)}. "
                        f"Playwright failed: {str(playwright_error)}. "
                        f"Vision extraction failed: {str(vision_error)}. "
                        f"Please provide company name and job title manually."
                    )

    async def scrape_page(self, url: str, formats: List[str] = None) -> str:
        """
        Scrape a page using Firecrawl and return content in requested format

        Args:
            url: URL to scrape
            formats: List of formats to return (e.g., ["markdown", "html"])

        Returns:
            Scraped content as string (markdown by default)
        """
        if formats is None:
            formats = ["markdown"]

        try:
            from firecrawl import FirecrawlApp
            import os
            import asyncio

            firecrawl_api_key = os.getenv('FIRECRAWL_API_KEY', '')

            if not firecrawl_api_key:
                raise ValueError("FIRECRAWL_API_KEY not found")

            app = FirecrawlApp(api_key=firecrawl_api_key)

            print(f"Scraping page: {url}")

            # Use Firecrawl v2 scrape API
            scrape_result = await asyncio.to_thread(
                app.scrape,
                url,
                formats=formats,
                only_main_content=True,
                timeout=30000
            )

            # Extract content based on requested format
            if "markdown" in formats and hasattr(scrape_result, 'markdown'):
                return scrape_result.markdown or ""
            elif "html" in formats and hasattr(scrape_result, 'html'):
                return scrape_result.html or ""
            else:
                # Try to get any available content
                if hasattr(scrape_result, 'markdown'):
                    return scrape_result.markdown or ""
                elif hasattr(scrape_result, 'html'):
                    return scrape_result.html or ""
                else:
                    return ""

        except Exception as e:
            print(f"Failed to scrape {url}: {e}")
            return ""

    # CRITICAL VALIDATION: Apply to ALL extraction paths (Firecrawl, Playwright, Vision)
    # This validation must happen AFTER all fallback methods complete
    async def validate_extraction_result(self, result: Dict[str, str], job_url: str) -> Dict[str, str]:
        """
        Validate that required fields (company, title) are present in extraction result
        Applies to all extraction methods: Firecrawl, Playwright, Vision

        Args:
            result: Extraction result dict
            job_url: Original job URL (for error messages)

        Returns:
            Validated result dict

        Raises:
            ValueError: If company or title is missing/invalid
        """
        company = result.get('company', '').strip()
        title = result.get('title', '').strip()

        # Validate company
        if not company or company == 'Unknown Company':
            raise ValueError(
                f"Could not extract company name from job URL: {job_url}. "
                "Please provide the company name manually using the 'company' field."
            )

        # Validate title
        if not title or title == 'Unknown Position':
            raise ValueError(
                f"Could not extract job title from job URL: {job_url}. "
                "Please provide the job title manually using the 'jobTitle' field."
            )

        return result
