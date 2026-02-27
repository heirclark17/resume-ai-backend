"""Cover Letter Generation Routes"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db, AsyncSessionLocal
from app.models.cover_letter import CoverLetter
from app.middleware.auth import get_user_id, ownership_filter
from app.services.cover_letter_service import generate_cover_letter_content
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger()


class GenerateRequest(BaseModel):
    job_title: str
    company_name: str
    job_description: Optional[str] = None
    job_url: Optional[str] = None
    tone: str = "professional"
    length: str = "standard"
    focus: str = "program_management"
    tailored_resume_id: Optional[int] = None
    base_resume_id: Optional[int] = None


class UpdateRequest(BaseModel):
    content: Optional[str] = None
    tone: Optional[str] = None


@router.get("/")
async def list_cover_letters(
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CoverLetter)
        .where(ownership_filter(CoverLetter.session_user_id, user_id), CoverLetter.is_deleted == False)
        .order_by(CoverLetter.created_at.desc())
    )
    letters = result.scalars().all()
    return {"cover_letters": [l.to_dict() for l in letters]}


def detect_company_from_url(url: str) -> Optional[str]:
    """Detect company name from URL domain"""
    url_lower = url.lower()
    company_mapping = {
        'jpmc': 'JPMorgan Chase',
        'jpmorganchase': 'JPMorgan Chase',
        'oracle': 'Oracle',
        'microsoft': 'Microsoft',
        'google': 'Google',
        'amazon': 'Amazon',
        'apple': 'Apple',
        'meta': 'Meta',
        'facebook': 'Meta',
    }

    for key, company in company_mapping.items():
        if key in url_lower:
            return company
    return None


async def extract_job_from_url(url: str) -> str:
    """Extract job description from URL using Playwright"""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, timeout=30000)
                await page.wait_for_timeout(5000)  # Wait for JavaScript

                # Try to wait for job description content
                try:
                    await page.wait_for_selector('article, .job-description, .description', timeout=5000)
                except:
                    pass

                # Extract page text
                text = await page.inner_text('body')
                await browser.close()
                return text

            except Exception as e:
                await browser.close()
                raise Exception(f"Failed to extract from URL: {str(e)}")

    except Exception as e:
        logger.error(f"URL extraction error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to extract job from URL: {str(e)}")


@router.post("/generate")
async def generate_cover_letter(
    data: GenerateRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    valid_tones = ("professional", "enthusiastic", "conversational", "strategic", "technical")
    if data.tone not in valid_tones:
        raise HTTPException(status_code=400, detail=f"Invalid tone. Must be one of: {', '.join(valid_tones)}")

    try:
        from app.models.resume import TailoredResume, BaseResume
        from app.models.job import Job

        # Normalize job_url: discard any non-HTTP placeholder values (e.g. manual_ IDs
        # stored by the tailoring route when no real URL was provided). Only treat it
        # as a real URL if it starts with http:// or https://.
        effective_job_url = data.job_url
        if effective_job_url and not (effective_job_url.startswith('http://') or effective_job_url.startswith('https://')):
            logger.info(f"Ignoring non-HTTP job_url value '{effective_job_url}' - treating as no URL")
            effective_job_url = None

        # Resolve job_description from tailored resume's Job if not provided directly.
        # Run this whenever job_description is missing, regardless of whether a URL was
        # also sent - the URL may be a manual_ placeholder that provides no description.
        job_description = data.job_description
        if not job_description and data.tailored_resume_id:
            tr_result = await db.execute(
                select(TailoredResume).where(TailoredResume.id == data.tailored_resume_id)
            )
            tr = tr_result.scalar_one_or_none()
            if tr and tr.job_id:
                job_result = await db.execute(
                    select(Job).where(Job.id == tr.job_id)
                )
                job = job_result.scalar_one_or_none()
                if job and job.description:
                    job_description = job.description
                    logger.info(f"Resolved job description from tailored resume {data.tailored_resume_id}, job {tr.job_id}")

        # Validate that we have a job description from some source
        if not job_description and not effective_job_url:
            raise HTTPException(status_code=400, detail="Either job_description or job_url must be provided")

        # Extract job description from URL if provided and we don't already have one
        if effective_job_url and not job_description:
            logger.info(f"Extracting job from URL: {effective_job_url}")
            job_description = await extract_job_from_url(effective_job_url)

            # Auto-detect company from URL if company_name is generic or empty
            if not data.company_name or data.company_name.lower() in ['company', 'target company']:
                detected_company = detect_company_from_url(effective_job_url)
                if detected_company:
                    data.company_name = detected_company
                    logger.info(f"Detected company from URL: {detected_company}")

        if not job_description:
            raise HTTPException(status_code=400, detail="No job description could be extracted")

        # Fetch resume data if linked
        resume_context = None
        resolved_base_resume_id = None

        if data.tailored_resume_id:
            # Path 1: From a tailored resume (existing behavior)
            tr_result = await db.execute(
                select(TailoredResume).where(TailoredResume.id == data.tailored_resume_id)
            )
            tr = tr_result.scalar_one_or_none()
            if tr:
                resolved_base_resume_id = tr.base_resume_id
                br_result = await db.execute(
                    select(BaseResume).where(BaseResume.id == tr.base_resume_id)
                )
                br = br_result.scalar_one_or_none()
                if br:
                    resume_context = {
                        "summary": tr.tailored_summary or br.summary,
                        "experience": tr.tailored_experience or br.experience,
                        "skills": tr.tailored_skills or br.skills,
                        "name": br.candidate_name,
                    }
        elif data.base_resume_id:
            # Path 2: From a base (uploaded) resume directly
            resolved_base_resume_id = data.base_resume_id
            br_result = await db.execute(
                select(BaseResume).where(BaseResume.id == data.base_resume_id)
            )
            br = br_result.scalar_one_or_none()
            if br:
                resume_context = {
                    "summary": br.summary or "",
                    "experience": br.experience or "",
                    "skills": br.skills or "",
                    "name": br.candidate_name,
                }

        # Research company with Perplexity
        company_research = None
        try:
            from app.services.perplexity_client import PerplexityClient
            perplexity = PerplexityClient()
            company_research = await perplexity.research_company(
                company_name=data.company_name,
                job_title=data.job_title
            )
            logger.info(f"Perplexity research completed for {data.company_name}")
        except Exception as e:
            logger.warning(f"Perplexity research failed for {data.company_name}: {e}")
            company_research = None

        content = await generate_cover_letter_content(
            job_title=data.job_title,
            company_name=data.company_name,
            job_description=job_description,
            tone=data.tone,
            length=data.length,
            focus=data.focus,
            resume_context=resume_context,
            company_research=company_research,
        )

        letter = CoverLetter(
            session_user_id=user_id,
            tailored_resume_id=data.tailored_resume_id,
            base_resume_id=resolved_base_resume_id,
            job_title=data.job_title,
            company_name=data.company_name,
            job_description=job_description,
            tone=data.tone,
            content=content,
        )
        db.add(letter)
        await db.commit()
        await db.refresh(letter)

        return {"success": True, "cover_letter": letter.to_dict()}

    except Exception as e:
        logger.error(f"Cover letter generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.put("/{letter_id}")
async def update_cover_letter(
    letter_id: int,
    data: UpdateRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CoverLetter).where(CoverLetter.id == letter_id, ownership_filter(CoverLetter.session_user_id, user_id))
    )
    letter = result.scalar_one_or_none()
    if not letter or letter.is_deleted:
        raise HTTPException(status_code=404, detail="Cover letter not found")

    if data.content is not None:
        letter.content = data.content
    if data.tone is not None:
        letter.tone = data.tone
    letter.updated_at = datetime.utcnow()
    await db.commit()
    return {"success": True, "cover_letter": letter.to_dict()}


@router.delete("/{letter_id}")
async def delete_cover_letter(
    letter_id: int,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CoverLetter).where(CoverLetter.id == letter_id, ownership_filter(CoverLetter.session_user_id, user_id))
    )
    letter = result.scalar_one_or_none()
    if not letter:
        raise HTTPException(status_code=404, detail="Cover letter not found")

    letter.is_deleted = True
    await db.commit()
    return {"success": True, "message": "Cover letter deleted"}


@router.get("/{letter_id}/export")
async def export_cover_letter(
    letter_id: int,
    format: str = "docx",
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    from fastapi.responses import Response
    from docx import Document
    from io import BytesIO

    result = await db.execute(
        select(CoverLetter).where(CoverLetter.id == letter_id, ownership_filter(CoverLetter.session_user_id, user_id))
    )
    letter = result.scalar_one_or_none()
    if not letter or letter.is_deleted:
        raise HTTPException(status_code=404, detail="Cover letter not found")

    doc = Document()
    for paragraph in letter.content.split('\n'):
        if paragraph.strip():
            doc.add_paragraph(paragraph.strip())

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    filename = f"cover_letter_{letter.company_name}_{letter.job_title}.docx".replace(' ', '_')
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Async cover letter generation (non-blocking, polls for result)
# ---------------------------------------------------------------------------

@router.post("/generate-async")
async def generate_cover_letter_async(
    data: GenerateRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Start cover letter generation asynchronously.

    Returns a job_id immediately. Client polls GET /api/cover-letters/job/{job_id}
    for progress and final result.
    """
    from app.services import job_manager

    job_id = await job_manager.enqueue_job(
        db=db,
        job_type="cover_letter",
        user_id=user_id,
        input_data={
            "job_title": data.job_title,
            "company_name": data.company_name,
            "job_description": data.job_description,
            "job_url": data.job_url,
            "tone": data.tone,
            "length": data.length,
            "focus": data.focus,
            "tailored_resume_id": data.tailored_resume_id,
            "base_resume_id": data.base_resume_id,
        },
    )

    background_tasks.add_task(_process_cover_letter_job, job_id, data, user_id)

    return {"success": True, "job_id": job_id, "message": "Poll /api/cover-letters/job/{job_id}"}


@router.get("/job/{job_id}")
async def get_cover_letter_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get status of an async cover letter generation job."""
    from app.services import job_manager

    status = await job_manager.get_job_status(db, job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


async def _process_cover_letter_job(job_id: str, data: GenerateRequest, user_id: str):
    """Background task that runs the full cover letter generation pipeline."""
    from app.services import job_manager
    from app.models.resume import TailoredResume, BaseResume
    from app.models.job import Job

    async with AsyncSessionLocal() as db:
        try:
            await job_manager.update_progress(db, job_id, 10, "Preparing job details...")

            # Normalize job_url
            effective_job_url = data.job_url
            if effective_job_url and not (effective_job_url.startswith('http://') or effective_job_url.startswith('https://')):
                effective_job_url = None

            # Resolve job_description from tailored resume if not provided
            job_description = data.job_description
            if not job_description and data.tailored_resume_id:
                tr_result = await db.execute(
                    select(TailoredResume).where(TailoredResume.id == data.tailored_resume_id)
                )
                tr = tr_result.scalar_one_or_none()
                if tr and tr.job_id:
                    job_result = await db.execute(select(Job).where(Job.id == tr.job_id))
                    job = job_result.scalar_one_or_none()
                    if job and job.description:
                        job_description = job.description

            if not job_description and not effective_job_url:
                await job_manager.fail_job(db, job_id, "Either job_description or job_url must be provided")
                return

            # Extract from URL if needed
            if effective_job_url and not job_description:
                await job_manager.update_progress(db, job_id, 20, "Extracting job from URL...")
                job_description = await extract_job_from_url(effective_job_url)

            if not job_description:
                await job_manager.fail_job(db, job_id, "No job description could be extracted")
                return

            await job_manager.update_progress(db, job_id, 30, "Fetching resume context...")

            # Fetch resume context
            resume_context = None
            resolved_base_resume_id = None

            if data.tailored_resume_id:
                tr_result = await db.execute(
                    select(TailoredResume).where(TailoredResume.id == data.tailored_resume_id)
                )
                tr = tr_result.scalar_one_or_none()
                if tr:
                    resolved_base_resume_id = tr.base_resume_id
                    br_result = await db.execute(select(BaseResume).where(BaseResume.id == tr.base_resume_id))
                    br = br_result.scalar_one_or_none()
                    if br:
                        resume_context = {
                            "summary": tr.tailored_summary or br.summary,
                            "experience": tr.tailored_experience or br.experience,
                            "skills": tr.tailored_skills or br.skills,
                            "name": br.candidate_name,
                        }
            elif data.base_resume_id:
                resolved_base_resume_id = data.base_resume_id
                br_result = await db.execute(select(BaseResume).where(BaseResume.id == data.base_resume_id))
                br = br_result.scalar_one_or_none()
                if br:
                    resume_context = {
                        "summary": br.summary or "",
                        "experience": br.experience or "",
                        "skills": br.skills or "",
                        "name": br.candidate_name,
                    }

            await job_manager.update_progress(db, job_id, 50, "Researching company...")

            # Research company
            company_research = None
            try:
                from app.services.perplexity_client import PerplexityClient
                perplexity = PerplexityClient()
                company_research = await perplexity.research_company(
                    company_name=data.company_name, job_title=data.job_title
                )
            except Exception as e:
                logger.warning(f"Perplexity research failed: {e}")

            await job_manager.update_progress(db, job_id, 70, "Generating cover letter...")

            content = await generate_cover_letter_content(
                job_title=data.job_title,
                company_name=data.company_name,
                job_description=job_description,
                tone=data.tone,
                length=data.length,
                focus=data.focus,
                resume_context=resume_context,
                company_research=company_research,
            )

            await job_manager.update_progress(db, job_id, 90, "Saving...")

            letter = CoverLetter(
                session_user_id=user_id,
                tailored_resume_id=data.tailored_resume_id,
                base_resume_id=resolved_base_resume_id,
                job_title=data.job_title,
                company_name=data.company_name,
                job_description=job_description,
                tone=data.tone,
                content=content,
            )
            db.add(letter)
            await db.commit()
            await db.refresh(letter)

            await job_manager.complete_job(db, job_id, {
                "cover_letter_id": letter.id,
                "company_name": letter.company_name,
                "job_title": letter.job_title,
            })

        except Exception as exc:
            import traceback
            traceback.print_exc()
            await job_manager.fail_job(db, job_id, str(exc))
