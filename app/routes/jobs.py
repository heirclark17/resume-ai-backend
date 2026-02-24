"""
Job Details API Routes

Endpoints for extracting job information from URLs and managing saved jobs
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.services.firecrawl_client import FirecrawlClient
from app.services.perplexity_client import PerplexityClient
from app.utils.url_validator import URLValidator
from app.database import get_db
from app.models.job import Job
from app.middleware.auth import get_user_id, ownership_filter

router = APIRouter()

# Rate limiter
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)


class ExtractJobRequest(BaseModel):
    job_url: str


class SaveJobRequest(BaseModel):
    url: str
    company: str
    title: str
    location: Optional[str] = None
    salary: Optional[str] = None
    description: Optional[str] = None


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

            # Enhance salary data with Perplexity real-time research
            job_title = extracted_data.get('title', '')
            location = extracted_data.get('location', '')
            extracted_salary = extracted_data.get('salary', '')

            salary_data = {
                "salary_range": extracted_salary or "Not specified",
                "market_insights": None,
                "sources": []
            }

            if job_title:
                print(f"Researching salary data with Perplexity for {job_title}...")
                try:
                    perplexity = PerplexityClient()
                    perplexity_salary = perplexity.research_salary_insights(
                        job_title=job_title,
                        location=location if location else None
                    )

                    # Use Perplexity data if available, otherwise keep extracted
                    if perplexity_salary and not perplexity_salary.get('error'):
                        salary_data = {
                            "salary_range": perplexity_salary.get('salary_range', extracted_salary or "Not specified"),
                            "median_salary": perplexity_salary.get('median_salary'),
                            "market_insights": perplexity_salary.get('market_insights'),
                            "sources": perplexity_salary.get('sources', []),
                            "last_updated": perplexity_salary.get('last_updated')
                        }
                        print(f"✓ Perplexity salary: {salary_data['salary_range']}")
                    else:
                        print(f"⚠ Perplexity salary unavailable, using extracted: {extracted_salary}")

                except Exception as e:
                    print(f"⚠ Perplexity salary research failed: {e}")
                    # Keep extracted salary as fallback

            print(f"=== EXTRACTION SUCCESS ===")

            return {
                "success": True,
                "company": extracted_data.get('company', ''),
                "job_title": job_title,
                "description": extracted_data.get('description', ''),
                "location": location,
                "salary": salary_data['salary_range'],
                "salary_data": salary_data  # Full salary insights for modal display
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


# ─── Saved Jobs CRUD ───────────────────────────────────────────────

@router.get("/saved")
async def get_saved_jobs(
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Get all saved jobs for the current user, newest first"""
    result = await db.execute(
        select(Job)
        .where(ownership_filter(Job.session_user_id, user_id))
        .where(Job.is_active == True)
        .order_by(desc(Job.created_at))
    )
    jobs = result.scalars().all()

    return {
        "success": True,
        "jobs": [
            {
                "id": job.id,
                "url": job.url,
                "company": job.company,
                "title": job.title,
                "location": job.location or "",
                "salary": job.salary or "",
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
            for job in jobs
        ]
    }


@router.post("/save")
async def save_job(
    req: SaveJobRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Save a job URL for later reuse. Upserts by URL."""
    # Check if job with this URL already exists
    result = await db.execute(
        select(Job).where(Job.url == req.url)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update ownership if not already owned by this user
        existing.session_user_id = user_id
        existing.company = req.company or existing.company
        existing.title = req.title or existing.title
        existing.location = req.location or existing.location
        existing.salary = req.salary or existing.salary
        existing.description = req.description or existing.description
        existing.is_active = True
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        job = existing
    else:
        job = Job(
            url=req.url,
            company=req.company,
            title=req.title,
            location=req.location or "",
            salary=req.salary or "",
            description=req.description or "",
            session_user_id=user_id,
            is_active=True,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

    return {
        "success": True,
        "job": {
            "id": job.id,
            "url": job.url,
            "company": job.company,
            "title": job.title,
            "location": job.location or "",
            "salary": job.salary or "",
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }
    }


@router.delete("/saved/{job_id}")
async def delete_saved_job(
    job_id: int,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Delete a saved job (soft delete by setting is_active=False)"""
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id)
        .where(ownership_filter(Job.session_user_id, user_id))
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.is_active = False
    db.add(job)
    await db.commit()

    return {"success": True}
