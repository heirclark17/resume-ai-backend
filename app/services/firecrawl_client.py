"""
Firecrawl client for extracting job posting details from URLs
"""
import os
import asyncio
from typing import Dict, Any, Optional
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
            # Scrape the page to get clean content
            scrape_result = await asyncio.to_thread(
                app.scrape_url,
                job_url,
                params={
                    'formats': ['markdown'],
                    'onlyMainContent': True  # Focus on main content, skip headers/footers
                }
            )

            if not scrape_result or not scrape_result.get('markdown'):
                raise ValueError("Failed to scrape job page - no content returned")

            markdown_content = scrape_result['markdown']
            print(f"Job page scraped: {len(markdown_content)} characters")

            # Now use Firecrawl's extract feature to get structured data
            print("Extracting structured job data...")

            extract_result = await asyncio.to_thread(
                app.extract,
                urls=[job_url],
                params={
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
                }
            )

            if not extract_result or not extract_result.get('data'):
                raise ValueError("Failed to extract structured data from job page")

            extracted_data = extract_result['data']
            print(f"Job details extracted successfully")

            # Combine extracted data with raw markdown
            result = {
                "company": extracted_data.get('company', 'Unknown Company'),
                "title": extracted_data.get('title', 'Unknown Position'),
                "description": extracted_data.get('description', ''),
                "location": extracted_data.get('location', ''),
                "salary": extracted_data.get('salary', ''),
                "posted_date": extracted_data.get('posted_date', ''),
                "employment_type": extracted_data.get('employment_type', ''),
                "experience_level": extracted_data.get('experience_level', ''),
                "skills_required": extracted_data.get('skills_required', []),
                "raw_text": markdown_content
            }

            print(f"Extracted: {result['company']} - {result['title']}")
            return result

        except ImportError:
            print("WARNING: Firecrawl package not installed. Install with: pip install firecrawl-py")
            raise ValueError(
                "Firecrawl not available. Please install: pip install firecrawl-py, "
                "or set TEST_MODE=true to use mock data."
            )
        except Exception as e:
            print(f"Firecrawl extraction error: {str(e)}")
            raise ValueError(f"Failed to extract job details: {str(e)}")
