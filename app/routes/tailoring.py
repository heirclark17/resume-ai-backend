from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.database import get_db
from app.models.resume import BaseResume, TailoredResume
from app.models.job import Job
from app.models.company import CompanyResearch
from app.services.perplexity_client import PerplexityClient
from app.services.openai_tailor import OpenAITailor
from app.services.docx_generator import DOCXGenerator
from app.services.firecrawl_client import FirecrawlClient
from app.utils.url_validator import URLValidator
from app.utils.quality_scorer import QualityScorer
from app.middleware.auth import get_user_id
from app.config import get_settings
import json
from datetime import datetime

settings = get_settings()

router = APIRouter()

# Rate limiter for expensive AI operations
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)


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

@router.post("/tailor")
@limiter.limit("10/hour")  # Rate limit: 10 tailoring operations per hour per IP
async def tailor_resume(
    request: Request,
    tailor_request: TailorRequest,
    user_id: str = Depends(get_user_id),
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

        # Verify ownership via session user ID
        if base_resume.session_user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied: You don't own this resume")

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
        if tailor_request.job_url:
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
                is_active=True
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)

        print(f"Job record: {job.company} - {job.title}")

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
            "alignment_statement": tailored_content.get('alignment_statement', '')
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
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Get a tailored resume by ID (requires ownership, excludes deleted resumes)"""
    result = await db.execute(
        select(TailoredResume).where(TailoredResume.id == tailored_id)
    )
    tailored = result.scalar_one_or_none()

    if not tailored:
        raise HTTPException(status_code=404, detail="Tailored resume not found")

    # Check if deleted
    if tailored.is_deleted:
        raise HTTPException(status_code=404, detail="Tailored resume has been deleted")

    # Verify ownership via session user ID
    if tailored.session_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied: You don't own this tailored resume")

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
        "created_at": tailored.created_at.isoformat()
    }


@router.put("/tailored/{tailored_id}")
async def update_tailored_resume(
    tailored_id: int,
    update_request: UpdateTailoredResumeRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Update a tailored resume's content (requires ownership)"""
    result = await db.execute(
        select(TailoredResume).where(TailoredResume.id == tailored_id)
    )
    tailored = result.scalar_one_or_none()

    if not tailored:
        raise HTTPException(status_code=404, detail="Tailored resume not found")

    # Check if deleted
    if tailored.is_deleted:
        raise HTTPException(status_code=404, detail="Tailored resume has been deleted")

    # Verify ownership via session user ID
    if tailored.session_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied: You don't own this tailored resume")

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
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    """List tailored resumes (requires session user ID, excludes deleted resumes)"""
    result = await db.execute(
        select(TailoredResume)
        .where(
            TailoredResume.is_deleted == False,
            TailoredResume.session_user_id == user_id  # Filter by session user ID
        )
        .order_by(TailoredResume.created_at.desc())
    )
    tailored_resumes = result.scalars().all()

    return {
        "tailored_resumes": [
            {
                "id": tr.id,
                "base_resume_id": tr.base_resume_id,
                "job_id": tr.job_id,
                "summary": tr.tailored_summary[:200] + "..." if tr.tailored_summary and len(tr.tailored_summary) > 200 else tr.tailored_summary,
                "docx_path": tr.docx_path,
                "quality_score": tr.quality_score,
                "created_at": tr.created_at.isoformat()
            }
            for tr in tailored_resumes
        ]
    }


@router.get("/download/{tailored_id}")
async def download_tailored_resume(
    tailored_id: int,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Download a tailored resume DOCX file (requires ownership)"""
    result = await db.execute(
        select(TailoredResume).where(TailoredResume.id == tailored_id)
    )
    tailored = result.scalar_one_or_none()

    if not tailored:
        raise HTTPException(status_code=404, detail="Tailored resume not found")

    # Check if deleted
    if tailored.is_deleted:
        raise HTTPException(status_code=404, detail="Tailored resume has been deleted")

    # Verify ownership via session user ID
    if tailored.session_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied: You don't own this tailored resume")

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


@router.post("/tailor/batch")
@limiter.limit("2/hour")  # Rate limit: 2 batch operations per hour per IP (very expensive)
async def tailor_resume_batch(
    request: Request,
    batch_request: BatchTailorRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Tailor a resume for multiple jobs (up to 10)

    Rate limited to 2 batch operations per hour per IP (can process up to 10 jobs each).

    Returns results for each job URL with success/failure status
    """
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

    # Verify ownership via session user ID
    if base_resume.session_user_id != user_id:
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

            # Call single tailor endpoint (pass request and user_id for rate limiting and ownership)
            result = await tailor_resume(request, tailor_req, user_id, db)

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
