"""
Job Details API Routes

Endpoints for extracting job information from URLs
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app.services.firecrawl_client import FirecrawlClient
from app.utils.url_validator import URLValidator

router = APIRouter()

# Rate limiter
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)


class ExtractJobRequest(BaseModel):
    job_url: str


@router.post("/extract")
@limiter.limit("20/minute")  # Rate limit: 20 extractions per minute per IP
async def extract_job_details(
    request: Request,
    extract_request: ExtractJobRequest
):
    """
    Extract job details (company, title, description) from a job URL

    This endpoint is used by the frontend to pre-populate job fields
    before actually tailoring the resume.

    Rate limited to 20 requests per minute per IP.
    """

    try:
        print(f"=== JOB EXTRACTION START ===")
        print(f"URL: {extract_request.job_url}")

        # Validate job URL for SSRF protection
        print("Validating job URL for SSRF protection...")
        validated_url = URLValidator.validate_job_url(extract_request.job_url)
        print(f"✓ URL validated successfully")

        # Extract job details with Firecrawl
        print("Extracting job details with Firecrawl...")
        firecrawl = FirecrawlClient()

        try:
            extracted_data = await firecrawl.extract_job_details(validated_url)

            print(f"✓ Job extracted: {extracted_data.get('company', 'N/A')} - {extracted_data.get('title', 'N/A')}")
            print(f"=== EXTRACTION SUCCESS ===")

            return {
                "success": True,
                "company": extracted_data.get('company', ''),
                "job_title": extracted_data.get('title', ''),
                "description": extracted_data.get('description', ''),
                "location": extracted_data.get('location', ''),
                "salary": extracted_data.get('salary', '')
            }

        except Exception as e:
            print(f"WARNING: Firecrawl extraction failed: {e}")
            print(f"=== EXTRACTION FAILED ===")

            # Return empty fields instead of error - frontend will show manual input
            return {
                "success": False,
                "error": str(e),
                "company": '',
                "job_title": '',
                "description": '',
                "location": '',
                "salary": ''
            }

    except HTTPException:
        # Re-raise HTTP exceptions from URL validation
        raise
    except Exception as e:
        print(f"UNEXPECTED ERROR in extract_job_details: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

        # Return failure response instead of throwing error
        return {
            "success": False,
            "error": str(e),
            "company": '',
            "job_title": '',
            "description": '',
            "location": '',
            "salary": ''
        }
