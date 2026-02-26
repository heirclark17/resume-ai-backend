from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.database import get_db
from app.models.resume import BaseResume, TailoredResume
from app.models.job import Job
from app.models.company import CompanyResearch
from app.models.salary_cache import SalaryCache
from app.services.perplexity_client import PerplexityClient
from app.services.openai_tailor import OpenAITailor
from app.services.docx_generator import DOCXGenerator
from app.services.firecrawl_client import FirecrawlClient
from app.utils.url_validator import URLValidator
from app.utils.quality_scorer import QualityScorer
from app.middleware.auth import get_user_id, check_ownership, ownership_filter, get_current_user_unified
from app.config import get_settings
import json
from datetime import datetime

settings = get_settings()

router = APIRouter()

# Rate limiter for expensive AI operations
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)


async def get_or_fetch_salary_data(
    db: "AsyncSession",
    company: str,
    job_title: str,
    location: str = None,
) -> dict:
    """
    Cache-first salary lookup keyed on (company, job_title, location).

    Lookup order:
      1. salary_cache table: hit + younger than 30 days  -> return cached data
      2. salary_cache table: hit + expired               -> re-fetch from Perplexity, update row
      3. No row found                                     -> fetch from Perplexity, insert row

    Returns a dict with the same shape as PerplexityClient.research_salary_insights()
    plus two extra fields:
      - from_cache (bool)
      - days_old   (int)
    Returns None if the Perplexity call itself fails.
    """

    norm_company, norm_title, norm_location = SalaryCache.make_key(
        company, job_title, location
    )

    # --- 1. Check the cache -------------------------------------------------
    cache_result = await db.execute(
        select(SalaryCache).where(
            SalaryCache.company == norm_company,
            SalaryCache.job_title == norm_title,
            SalaryCache.location == norm_location,
        )
    )
    cached = cache_result.scalar_one_or_none()

    if cached and not cached.is_expired():
        print(
            f"[SalaryCache] HIT (company={norm_company!r}, title={norm_title!r}, "
            f"location={norm_location!r}, age={cached.days_old()}d) — skipping Perplexity"
        )
        return cached.to_salary_dict()

    # --- 2. Cache miss or expired: call Perplexity --------------------------
    if cached:
        print(
            f"[SalaryCache] EXPIRED (age={cached.days_old()}d) — refreshing from Perplexity"
        )
    else:
        print(
            f"[SalaryCache] MISS (company={norm_company!r}, title={norm_title!r}) "
            "— calling Perplexity"
        )

    try:
        perplexity = PerplexityClient()
        raw = perplexity.research_salary_insights(
            job_title=job_title,
            location=location if location else None,
        )
    except Exception as exc:
        print(f"[SalaryCache] Perplexity call failed: {exc}")
        # Return stale cache data rather than nothing if we have it
        if cached:
            print("[SalaryCache] Returning stale cache data as fallback")
            return cached.to_salary_dict()
        return None

    if not raw or raw.get("error"):
        print(f"[SalaryCache] Perplexity returned error: {raw}")
        if cached:
            return cached.to_salary_dict()
        return None

    # --- 3. Persist to salary_cache -----------------------------------------
    new_salary_range = raw.get("salary_range") or "Data not available"
    new_median = raw.get("median_salary") or "Data not available"
    new_insights = raw.get("market_insights") or ""
    new_sources = json.dumps(raw.get("sources") or [])
    now = datetime.utcnow()

    try:
        if cached:
            # Update existing stale row in place
            cached.median_salary = new_median
            cached.salary_range = new_salary_range
            cached.market_insights = new_insights
            cached.sources = new_sources
            cached.updated_at = now
            db.add(cached)
        else:
            # Insert brand-new cache row
            cached = SalaryCache(
                company=norm_company,
                job_title=norm_title,
                location=norm_location,
                median_salary=new_median,
                salary_range=new_salary_range,
                market_insights=new_insights,
                sources=new_sources,
                created_at=now,
                updated_at=now,
            )
            db.add(cached)

        await db.commit()
        await db.refresh(cached)
        print(
            f"[SalaryCache] Stored: median={new_median!r}, "
            f"range={new_salary_range!r}"
        )
    except Exception as exc:
        # Non-fatal: cache write failure should not abort the tailoring flow
        print(f"[SalaryCache] WARNING — failed to persist cache row: {exc}")
        await db.rollback()

    return {
        "salary_range": new_salary_range,
        "median_salary": new_median,
        "market_insights": new_insights,
        "sources": raw.get("sources") or [],
        "last_updated": now.isoformat(),
        "cache_updated_at": now.isoformat(),
        "days_old": 0,
        "from_cache": False,
    }


def safe_json_loads(json_str: str, default=None):
    """Safely parse JSON string with error handling"""
    if not json_str:
        return default if default is not None else []
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"JSON deserialization failed: {e}. Returning default value.")
        return default if default is not None else []

from typing import List

class TailorRequest(BaseModel):
    base_resume_id: int
    job_url: str = None
    company: str = None
    job_title: str = None
    job_description: str = None

class BatchTailorRequest(BaseModel):
    base_resume_id: int
    job_urls: List[str]  # Max 10 URLs

class UpdateTailoredResumeRequest(BaseModel):
    """Request model for updating tailored resume content"""
    summary: str = None
    competencies: List[str] = None
    experience: List[dict] = None
    alignment_statement: str = None

class BulkDeleteRequest(BaseModel):
    """Request model for bulk deleting tailored resumes"""
    ids: List[int]

@router.post("/tailor")
@limiter.limit("10/hour")  # Rate limit: 10 tailoring operations per hour per IP
async def tailor_resume(
    request: Request,
    tailor_request: TailorRequest,
    auth_result: tuple = Depends(get_current_user_unified),
    db: AsyncSession = Depends(get_db)
):
    """
    Tailor a resume for a specific job

    Rate limited to 10 tailoring operations per hour per IP (expensive AI operations).

    Process:
    1. Fetch base resume from database
    2. Research company with Perplexity
    3. Tailor resume with Claude
    4. Generate DOCX file
    5. Save to database
    """

    # Extract user and user_id from unified auth (handles both JWT and session-based auth)
    user, user_id = auth_result

    try:
        print(f"=== TAILORING START ===")
        print(f"TEST MODE: {settings.test_mode} (type: {type(settings.test_mode).__name__})")
        print(f"Base Resume ID: {tailor_request.base_resume_id}")
        print(f"Company: {tailor_request.company}")
        print(f"Job Title: {tailor_request.job_title}")
        print(f"Job URL: {tailor_request.job_url}")

        # Check API keys early (before any expensive operations)
        if not settings.test_mode:
            if not settings.openai_api_key:
                raise HTTPException(
                    status_code=503,
                    detail="AI service unavailable: OPENAI_API_KEY not configured. Please contact administrator or set TEST_MODE=true."
                )
            if not settings.perplexity_api_key:
                raise HTTPException(
                    status_code=503,
                    detail="Research service unavailable: PERPLEXITY_API_KEY not configured. Please contact administrator or set TEST_MODE=true."
                )

        # Validate job URL for SSRF protection
        if tailor_request.job_url:
            print(f"Validating job URL for SSRF protection...")
            tailor_request.job_url = URLValidator.validate_job_url(tailor_request.job_url)
            print(f"✓ URL validated successfully")

        # Step 1: Fetch base resume (verify ownership)
        print("Step 1: Fetching base resume...")
        result = await db.execute(
            select(BaseResume).where(BaseResume.id == tailor_request.base_resume_id)
        )
        base_resume = result.scalar_one_or_none()

        if not base_resume:
            raise HTTPException(status_code=404, detail="Base resume not found")

        # Verify ownership via session user ID (with auto-migration for supa_ users)
        if not check_ownership(base_resume.session_user_id, user_id):
            raise HTTPException(status_code=403, detail="Access denied: You don't own this resume")
        # Auto-migrate old user_ records to supa_ ID
        if base_resume.session_user_id != user_id:
            base_resume.session_user_id = user_id
            db.add(base_resume)
            await db.commit()
            await db.refresh(base_resume)

        # Parse base resume data
        base_resume_data = {
            "summary": base_resume.summary or "",
            "skills": safe_json_loads(base_resume.skills, []),
            "experience": safe_json_loads(base_resume.experience, []),
            "education": base_resume.education or "",
            "certifications": base_resume.certifications or ""
        }

        print(f"Base resume loaded: {base_resume.filename}")

        # Step 2: Extract job details from URL (if provided)
        print("Step 2: Processing job details...")

        extracted_job_data = None
        # Skip Firecrawl when company and title are already provided (saves 10-20s)
        needs_extraction = tailor_request.job_url and (not tailor_request.company or not tailor_request.job_title)
        if needs_extraction:
            print(f"Job URL provided: {tailor_request.job_url}")
            print("Extracting job details with Firecrawl...")

            try:
                firecrawl = FirecrawlClient()
                extracted_job_data = await firecrawl.extract_job_details(tailor_request.job_url)

                print(f"✓ Job extracted: {extracted_job_data['company']} - {extracted_job_data['title']}")

                # Use extracted data if manual fields not provided
                if not tailor_request.company:
                    tailor_request.company = extracted_job_data['company']
                if not tailor_request.job_title:
                    tailor_request.job_title = extracted_job_data['title']
                if not tailor_request.job_description:
                    tailor_request.job_description = extracted_job_data['description']

            except Exception as e:
                print(f"WARNING: Job extraction failed: {e}")
                # If extraction failed and no manual input provided, raise error
                if not tailor_request.company and not tailor_request.job_title:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Could not extract job details from URL: {str(e)}. Please provide at least company name or job title manually."
                    )
                print("Using manual input instead...")

                # Fill in missing fields with generic placeholders
                if not tailor_request.company:
                    tailor_request.company = "Company"
                if not tailor_request.job_title:
                    tailor_request.job_title = "Position"

        # Step 3: Create or fetch job record
        print("Step 3: Creating job record...")
        job = None

        if tailor_request.job_url:
            # Check if job already exists
            result = await db.execute(
                select(Job).where(Job.url == tailor_request.job_url)
            )
            job = result.scalar_one_or_none()

        if not job:
            # Create new job record with extracted or manual data
            job = Job(
                url=tailor_request.job_url or f"manual_{datetime.utcnow().timestamp()}",
                company=tailor_request.company or "Unknown Company",
                title=tailor_request.job_title or "Unknown Position",
                description=tailor_request.job_description or "",
                location=extracted_job_data.get('location', '') if extracted_job_data else '',
                salary=extracted_job_data.get('salary', '') if extracted_job_data else '',
                is_active=True,
                session_user_id=user_id,
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)
        elif not job.session_user_id:
            # Backfill ownership on existing jobs
            job.session_user_id = user_id
            db.add(job)
            await db.commit()

        print(f"Job record: {job.company} - {job.title}")

        # Step 3b: Research salary data using the cross-job SalaryCache
        # Cache key: (company, job_title, location) — not tied to URL.
        # First call for a given company+title: hits Perplexity and stores in
        # salary_cache.  Subsequent calls (any URL) hit the cache for 30 days.
        print("Step 3b: Fetching salary data (SalaryCache → Perplexity)...")

        perplexity_salary = None
        try:
            perplexity_salary = await get_or_fetch_salary_data(
                db=db,
                company=job.company,
                job_title=job.title,
                location=job.location if job.location else None,
            )
        except Exception as e:
            print(f"⚠ Salary cache/fetch failed: {e}")

        if perplexity_salary and not perplexity_salary.get("error"):
            # Mirror salary data onto the Job row for backwards-compat with
            # existing code that reads job.median_salary / job.salary_last_updated
            job.median_salary = perplexity_salary.get("median_salary", "Data unavailable")
            job.salary_insights = perplexity_salary.get("market_insights", "")
            job.salary_sources = json.dumps(perplexity_salary.get("sources", []))
            job.salary_last_updated = datetime.utcnow()

            if (
                perplexity_salary.get("salary_range")
                and perplexity_salary["salary_range"] != "Data not available"
            ):
                job.salary = perplexity_salary["salary_range"]

            db.add(job)
            await db.commit()
            await db.refresh(job)

            cache_source = "cache" if perplexity_salary.get("from_cache") else "Perplexity API"
            print(
                f"✓ Salary data from {cache_source}: {job.median_salary} "
                f"(age={perplexity_salary.get('days_old', 0)}d)"
            )
        else:
            print("⚠ Salary data unavailable")

        # Step 4: Research company with Perplexity
        print("Step 4: Researching company with Perplexity...")
        perplexity = PerplexityClient()

        try:
            company_research = await perplexity.research_company(
                company_name=job.company,
                job_title=job.title
            )
            print(f"Company research completed: {len(company_research.get('research', ''))} characters")
        except Exception as e:
            print(f"Perplexity research failed: {e}")
            company_research = {
                "company": job.company,
                "research": "Unable to perform company research at this time."
            }

        # Step 4b: Save company research to database for interview prep
        print("Step 4b: Saving company research to database...")

        # Check if company research already exists for this job
        result = await db.execute(
            select(CompanyResearch).where(CompanyResearch.job_id == job.id)
        )
        existing_research = result.scalar_one_or_none()

        if not existing_research:
            # Create new company research record
            # Store the unstructured research text from Perplexity in all fields
            # This is a temporary solution until we parse the research properly
            research_text = company_research.get('research', '')

            company_research_record = CompanyResearch(
                company_name=job.company,
                job_id=job.id,
                mission_values=research_text,  # Store full research in mission_values for now
                initiatives=research_text,      # Duplicate for interview prep access
                team_culture=research_text,     # Duplicate for interview prep access
                compliance='',                   # Will be parsed in future
                tech_stack='',                   # Will be parsed in future
                sources=[],                      # Will be added when we have citations
                industry=''                      # Will be extracted in future
            )
            db.add(company_research_record)
            await db.commit()
            await db.refresh(company_research_record)
            print(f"✓ Company research saved (ID: {company_research_record.id})")
        else:
            print(f"✓ Company research already exists (ID: {existing_research.id})")

        # Step 5: Tailor resume with OpenAI
        print("Step 5: Tailoring resume with OpenAI...")
        openai_tailor = OpenAITailor()

        job_details = {
            "company": job.company,
            "title": job.title,
            "url": job.url,
            "description": tailor_request.job_description or ""
        }

        try:
            tailored_content = await openai_tailor.tailor_resume(
                base_resume=base_resume_data,
                company_research=company_research,
                job_details=job_details
            )
            print(f"Resume tailored: {len(tailored_content.get('competencies', []))} competencies")
        except Exception as e:
            print(f"OpenAI tailoring failed: {e}")
            raise HTTPException(status_code=500, detail=f"Resume tailoring failed: {str(e)}")

        # Step 6: Generate DOCX
        print("Step 6: Generating DOCX file...")
        docx_gen = DOCXGenerator()

        # Extract candidate info from base resume
        candidate_name = base_resume.candidate_name or "Candidate Name"
        contact_info = {
            "email": base_resume.candidate_email or "",
            "phone": base_resume.candidate_phone or "",
            "location": base_resume.candidate_location or "",
            "linkedin": base_resume.candidate_linkedin or ""
        }

        print(f"Using candidate info: {candidate_name}, {contact_info.get('email', 'N/A')}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{job.company.replace(' ', '_')}_{job.title.replace(' ', '_')}.docx"

        try:
            docx_path = docx_gen.create_tailored_resume(
                candidate_name=candidate_name,
                contact_info=contact_info,
                job_details=job_details,
                tailored_content=tailored_content,
                base_resume_data=base_resume_data,
                output_filename=filename
            )
            print(f"DOCX created: {docx_path}")
        except Exception as e:
            print(f"DOCX generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Document generation failed: {str(e)}")

        # Step 7: Calculate quality score
        print("Step 7: Calculating quality score...")
        quality_score = QualityScorer.calculate_quality_score(
            base_resume_data=base_resume_data,
            tailored_content=tailored_content,
            company_research=company_research
        )

        # Validate quality score is in valid range
        if not isinstance(quality_score, (int, float)):
            raise ValueError(f"Quality score must be numeric, got {type(quality_score)}")
        if quality_score < 0 or quality_score > 100:
            raise ValueError(f"Quality score must be between 0-100, got {quality_score}")

        print(f"Quality score: {quality_score:.1f}/100")

        # Step 8: Save tailored resume to database
        print("Step 8: Saving to database...")
        tailored_resume = TailoredResume(
            base_resume_id=base_resume.id,
            job_id=job.id,
            session_user_id=user_id,  # Store session user ID for data isolation
            tailored_summary=tailored_content.get('summary', ''),
            tailored_skills=json.dumps(tailored_content.get('competencies', [])),
            tailored_experience=json.dumps(tailored_content.get('experience', [])),
            alignment_statement=tailored_content.get('alignment_statement', ''),
            docx_path=docx_path,
            quality_score=quality_score,
            changes_count=len(tailored_content.get('competencies', []))
        )

        db.add(tailored_resume)
        await db.commit()
        await db.refresh(tailored_resume)

        print(f"=== TAILORING COMPLETE ===")
        print(f"Tailored Resume ID: {tailored_resume.id}")

        # Build salary data payload for the frontend (SalaryInsights component)
        salary_payload = None
        if perplexity_salary and not perplexity_salary.get("error"):
            salary_payload = {
                "salary_range": perplexity_salary.get("salary_range", "Data not available"),
                "median_salary": perplexity_salary.get("median_salary", "Data not available"),
                "market_insights": perplexity_salary.get("market_insights", ""),
                "sources": perplexity_salary.get("sources", []),
                "last_updated": perplexity_salary.get("last_updated"),
                "cache_updated_at": perplexity_salary.get("cache_updated_at"),
                "days_old": perplexity_salary.get("days_old", 0),
                "from_cache": perplexity_salary.get("from_cache", False),
            }

        return {
            "success": True,
            "tailored_resume_id": tailored_resume.id,
            "job_id": job.id,
            "company": job.company,
            "title": job.title,
            "docx_path": docx_path,
            "summary": tailored_content.get('summary', ''),
            "competencies": tailored_content.get('competencies', []),
            "experience": tailored_content.get('experience', []),
            "education": tailored_content.get('education', ''),
            "certifications": tailored_content.get('certifications', ''),
            "alignment_statement": tailored_content.get('alignment_statement', ''),
            # Salary data — populated from SalaryCache (no extra API cost on cache hits)
            "salary_data": salary_payload,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"UNEXPECTED ERROR in tailoring: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Tailoring failed: {str(e)}")


@router.get("/tailored/{tailored_id}")
async def get_tailored_resume(
    tailored_id: int,
    auth_result: tuple = Depends(get_current_user_unified),
    db: AsyncSession = Depends(get_db)
):
    """Get a tailored resume by ID (requires ownership, excludes deleted resumes)"""
    # Extract user and user_id from unified auth (handles both JWT and session-based auth)
    user, user_id = auth_result

    # Fetch tailored resume with base resume joined
    result = await db.execute(
        select(TailoredResume, BaseResume)
        .join(BaseResume, TailoredResume.base_resume_id == BaseResume.id)
        .where(TailoredResume.id == tailored_id)
    )
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Tailored resume not found")

    tailored, base_resume = row

    # Check if deleted
    if tailored.is_deleted:
        raise HTTPException(status_code=404, detail="Tailored resume has been deleted")

    # Verify ownership (with auto-migration for supa_ users)
    if not check_ownership(tailored.session_user_id, user_id):
        raise HTTPException(status_code=403, detail="Access denied: You don't own this tailored resume")

    # Auto-migrate: update old user_ records to current supa_ ID
    if tailored.session_user_id != user_id and user_id.startswith('supa_') and (tailored.session_user_id.startswith('user_') or user_id == f"supa_{tailored.session_user_id}"):
        tailored.session_user_id = user_id
        db.add(tailored)
        await db.commit()
        await db.refresh(tailored)

    # Fetch associated job record for company/title
    job_data = {}
    if tailored.job_id:
        job_result = await db.execute(
            select(Job).where(Job.id == tailored.job_id)
        )
        job = job_result.scalar_one_or_none()
        if job:
            job_data = {
                "company": job.company,
                "title": job.title,
                "url": job.url,
            }

    return {
        "id": tailored.id,
        "base_resume_id": tailored.base_resume_id,
        "job_id": tailored.job_id,
        "summary": tailored.tailored_summary,
        "competencies": safe_json_loads(tailored.tailored_skills, []),
        "experience": safe_json_loads(tailored.tailored_experience, []),
        "alignment_statement": tailored.alignment_statement,
        "docx_path": tailored.docx_path,
        "quality_score": tailored.quality_score,
        "created_at": tailored.created_at.isoformat(),
        # Include education and certifications from base resume
        "education": base_resume.education,
        "certifications": base_resume.certifications,
        # Include contact info from base resume for template header
        "name": base_resume.candidate_name,
        "email": base_resume.candidate_email,
        "phone": base_resume.candidate_phone,
        "linkedin": base_resume.candidate_linkedin,
        "location": base_resume.candidate_location,
        **job_data,
    }


@router.put("/tailored/{tailored_id}")
async def update_tailored_resume(
    tailored_id: int,
    update_request: UpdateTailoredResumeRequest,
    auth_result: tuple = Depends(get_current_user_unified),
    db: AsyncSession = Depends(get_db)
):
    """Update a tailored resume's content (requires ownership)"""
    # Extract user and user_id from unified auth
    user, user_id = auth_result

    result = await db.execute(
        select(TailoredResume).where(TailoredResume.id == tailored_id)
    )
    tailored = result.scalar_one_or_none()

    if not tailored:
        raise HTTPException(status_code=404, detail="Tailored resume not found")

    # Check if deleted
    if tailored.is_deleted:
        raise HTTPException(status_code=404, detail="Tailored resume has been deleted")

    # Verify ownership (with auto-migration for supa_ users)
    if not check_ownership(tailored.session_user_id, user_id):
        raise HTTPException(status_code=403, detail="Access denied: You don't own this tailored resume")

    # Auto-migrate: update old user_ records to current supa_ ID
    if tailored.session_user_id != user_id and user_id.startswith('supa_') and (tailored.session_user_id.startswith('user_') or user_id == f"supa_{tailored.session_user_id}"):
        tailored.session_user_id = user_id

    # Update fields if provided
    if update_request.summary is not None:
        tailored.tailored_summary = update_request.summary

    if update_request.competencies is not None:
        tailored.tailored_skills = json.dumps(update_request.competencies)

    if update_request.experience is not None:
        tailored.tailored_experience = json.dumps(update_request.experience)

    if update_request.alignment_statement is not None:
        tailored.alignment_statement = update_request.alignment_statement

    await db.commit()
    await db.refresh(tailored)

    return {
        "success": True,
        "id": tailored.id,
        "summary": tailored.tailored_summary,
        "competencies": safe_json_loads(tailored.tailored_skills, []),
        "experience": safe_json_loads(tailored.tailored_experience, []),
        "alignment_statement": tailored.alignment_statement,
        "updated_at": datetime.utcnow().isoformat()
    }


@router.get("/list")
async def list_tailored_resumes(
    auth_result: tuple = Depends(get_current_user_unified),
    db: AsyncSession = Depends(get_db)
):
    """List tailored resumes with job details (requires authentication, excludes deleted resumes)"""
    # Extract user and user_id from unified auth
    user, user_id = auth_result

    # Join with Job table to get job title and company
    result = await db.execute(
        select(TailoredResume, Job)
        .join(Job, TailoredResume.job_id == Job.id, isouter=True)
        .where(
            TailoredResume.is_deleted == False,
            ownership_filter(TailoredResume.session_user_id, user_id)  # Filter by session user ID
        )
        .order_by(TailoredResume.created_at.desc())
    )
    rows = result.all()

    # Auto-migrate: update any old user_ or raw UUID records to current supa_ ID
    if user_id.startswith('supa_'):
        for tr, job in rows:
            if tr.session_user_id != user_id:
                tr.session_user_id = user_id
                db.add(tr)
        await db.commit()

    return {
        "tailored_resumes": [
            {
                "id": tr.id,
                "base_resume_id": tr.base_resume_id,
                "job_id": tr.job_id,
                "job_title": job.title if job else "Unknown Position",
                "company_name": job.company if job else None,
                "summary": tr.tailored_summary[:200] + "..." if tr.tailored_summary and len(tr.tailored_summary) > 200 else tr.tailored_summary,
                "docx_path": tr.docx_path,
                "quality_score": tr.quality_score,
                "created_at": tr.created_at.isoformat()
            }
            for tr, job in rows
        ]
    }


@router.get("/download/{tailored_id}")
async def download_tailored_resume(
    tailored_id: int,
    auth_result: tuple = Depends(get_current_user_unified),
    db: AsyncSession = Depends(get_db)
):
    """Download a tailored resume DOCX file (requires ownership)"""
    # Extract user and user_id from unified auth
    user, user_id = auth_result

    result = await db.execute(
        select(TailoredResume).where(TailoredResume.id == tailored_id)
    )
    tailored = result.scalar_one_or_none()

    if not tailored:
        raise HTTPException(status_code=404, detail="Tailored resume not found")

    # Check if deleted
    if tailored.is_deleted:
        raise HTTPException(status_code=404, detail="Tailored resume has been deleted")

    # Verify ownership (with auto-migration for supa_ users)
    if not check_ownership(tailored.session_user_id, user_id):
        raise HTTPException(status_code=403, detail="Access denied: You don't own this tailored resume")

    # Auto-migrate: update old user_ records to current supa_ ID
    if tailored.session_user_id != user_id and user_id.startswith('supa_') and (tailored.session_user_id.startswith('user_') or user_id == f"supa_{tailored.session_user_id}"):
        tailored.session_user_id = user_id
        db.add(tailored)
        await db.commit()
        await db.refresh(tailored)

    # Check if file exists
    import os

    # Convert relative path to absolute
    docx_path = tailored.docx_path
    if not os.path.isabs(docx_path):
        docx_path = os.path.abspath(docx_path)

    if not os.path.exists(docx_path):
        raise HTTPException(
            status_code=404,
            detail=f"Resume file not found. The file may have been cleaned up after deployment. Please regenerate the resume."
        )

    # Get filename from path
    filename = os.path.basename(docx_path)

    return FileResponse(
        path=docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename
    )


@router.delete("/tailored/{tailored_id}")
async def delete_tailored_resume(
    tailored_id: int,
    auth_result: tuple = Depends(get_current_user_unified),
    db: AsyncSession = Depends(get_db)
):
    """Soft-delete a tailored resume (requires ownership)"""
    user, user_id = auth_result

    result = await db.execute(
        select(TailoredResume).where(TailoredResume.id == tailored_id)
    )
    tailored = result.scalar_one_or_none()

    if not tailored:
        raise HTTPException(status_code=404, detail="Tailored resume not found")

    if tailored.is_deleted:
        raise HTTPException(status_code=404, detail="Tailored resume already deleted")

    if not check_ownership(tailored.session_user_id, user_id):
        raise HTTPException(status_code=403, detail="Access denied: You don't own this tailored resume")

    tailored.is_deleted = True
    tailored.deleted_at = datetime.utcnow()
    tailored.deleted_by = user_id
    db.add(tailored)
    await db.commit()

    return {"success": True, "message": "Tailored resume deleted"}


@router.post("/tailored/bulk-delete")
async def bulk_delete_tailored_resumes(
    bulk_request: BulkDeleteRequest,
    auth_result: tuple = Depends(get_current_user_unified),
    db: AsyncSession = Depends(get_db)
):
    """Soft-delete multiple tailored resumes (requires ownership of each)"""
    user, user_id = auth_result

    if not bulk_request.ids:
        raise HTTPException(status_code=400, detail="No IDs provided")

    if len(bulk_request.ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 IDs per request")

    result = await db.execute(
        select(TailoredResume).where(
            TailoredResume.id.in_(bulk_request.ids),
            TailoredResume.is_deleted == False,
            ownership_filter(TailoredResume.session_user_id, user_id)
        )
    )
    resumes = result.scalars().all()

    now = datetime.utcnow()
    deleted_count = 0
    for resume in resumes:
        resume.is_deleted = True
        resume.deleted_at = now
        resume.deleted_by = user_id
        db.add(resume)
        deleted_count += 1

    await db.commit()

    return {
        "success": True,
        "deleted_count": deleted_count,
        "requested_count": len(bulk_request.ids)
    }


@router.post("/tailor/batch")
@limiter.limit("2/hour")  # Rate limit: 2 batch operations per hour per IP (very expensive)
async def tailor_resume_batch(
    request: Request,
    batch_request: BatchTailorRequest,
    auth_result: tuple = Depends(get_current_user_unified),
    db: AsyncSession = Depends(get_db)
):
    """
    Tailor a resume for multiple jobs (up to 10)

    Rate limited to 2 batch operations per hour per IP (can process up to 10 jobs each).

    Returns results for each job URL with success/failure status
    """
    # Extract user and user_id from unified auth (handles both JWT and session-based auth)
    user, user_id = auth_result

    # Validate URL limit
    if len(batch_request.job_urls) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 job URLs allowed per batch"
        )

    if len(batch_request.job_urls) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least 1 job URL required"
        )

    print(f"=== BATCH TAILORING START ===")
    print(f"Base Resume ID: {batch_request.base_resume_id}")
    print(f"Job URLs: {len(batch_request.job_urls)}")

    # Validate all URLs for SSRF protection
    print("Validating all job URLs for SSRF protection...")
    validated_urls = []
    for idx, job_url in enumerate(batch_request.job_urls, 1):
        try:
            validated_url = URLValidator.validate_job_url(job_url)
            validated_urls.append(validated_url)
            print(f"  ✓ URL {idx}/{len(batch_request.job_urls)} validated")
        except HTTPException as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid URL #{idx}: {e.detail}"
            )

    batch_request.job_urls = validated_urls
    print(f"✓ All {len(validated_urls)} URLs validated successfully")

    # Verify base resume exists and user owns it
    result = await db.execute(
        select(BaseResume).where(BaseResume.id == batch_request.base_resume_id)
    )
    base_resume = result.scalar_one_or_none()

    if not base_resume:
        raise HTTPException(status_code=404, detail="Base resume not found")

    # Verify ownership (with auto-migration for supa_ users)
    if not check_ownership(base_resume.session_user_id, user_id):
        raise HTTPException(status_code=403, detail="Access denied: You don't own this resume")

    # Process each job URL
    results = []
    for idx, job_url in enumerate(batch_request.job_urls, 1):
        print(f"\n--- Processing Job {idx}/{len(batch_request.job_urls)} ---")
        print(f"URL: {job_url}")

        try:
            # Create individual tailor request
            tailor_req = TailorRequest(
                base_resume_id=batch_request.base_resume_id,
                job_url=job_url
            )

            # Call single tailor endpoint (pass request and auth_result for rate limiting and ownership)
            result = await tailor_resume(request, tailor_req, auth_result, db)

            results.append({
                "job_url": job_url,
                "success": True,
                "data": result
            })
            print(f"✓ Job {idx} completed successfully")

        except HTTPException as e:
            # HTTP exceptions from tailor_resume
            results.append({
                "job_url": job_url,
                "success": False,
                "error": e.detail,
                "error_code": e.status_code
            })
            print(f"✗ Job {idx} failed: {e.detail}")

        except Exception as e:
            # Unexpected exceptions
            results.append({
                "job_url": job_url,
                "success": False,
                "error": str(e)
            })
            print(f"✗ Job {idx} failed unexpectedly: {str(e)}")

    # Calculate summary
    succeeded = sum(1 for r in results if r["success"])
    failed = len(results) - succeeded

    print(f"\n=== BATCH TAILORING COMPLETE ===")
    print(f"Total: {len(results)} | Succeeded: {succeeded} | Failed: {failed}")

    return {
        "success": True,
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results
    }


@router.delete("/tailored/{tailored_id}")
async def delete_tailored_resume(
    tailored_id: int,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Soft-delete a single tailored resume (requires ownership)"""
    result = await db.execute(
        select(TailoredResume).where(TailoredResume.id == tailored_id)
    )
    tailored = result.scalar_one_or_none()

    if not tailored:
        raise HTTPException(status_code=404, detail="Tailored resume not found")

    if tailored.session_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if tailored.is_deleted:
        raise HTTPException(status_code=404, detail="Already deleted")

    tailored.is_deleted = True
    tailored.deleted_at = datetime.utcnow()
    tailored.deleted_by = None
    await db.commit()

    return {"success": True, "message": "Tailored resume deleted"}


class BulkDeleteRequest(BaseModel):
    ids: List[int]


@router.post("/tailored/bulk-delete")
async def bulk_delete_tailored_resumes(
    request: BulkDeleteRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Soft-delete multiple tailored resumes (requires ownership)"""
    if len(request.ids) == 0:
        raise HTTPException(status_code=400, detail="No IDs provided")

    if len(request.ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 IDs per request")

    result = await db.execute(
        select(TailoredResume).where(
            TailoredResume.id.in_(request.ids),
            TailoredResume.session_user_id == user_id,
            TailoredResume.is_deleted == False,
        )
    )
    resumes = result.scalars().all()

    deleted_count = 0
    for tailored in resumes:
        tailored.is_deleted = True
        tailored.deleted_at = datetime.utcnow()
        tailored.deleted_by = None
        deleted_count += 1

    await db.commit()

    return {
        "success": True,
        "deleted_count": deleted_count,
        "requested_count": len(request.ids)
    }
