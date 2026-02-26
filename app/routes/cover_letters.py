"""Cover Letter Generation Routes"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
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

        # Resolve job_description from tailored resume's Job if not provided directly
        job_description = data.job_description
        if not job_description and not data.job_url and data.tailored_resume_id:
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
        if not job_description and not data.job_url:
            raise HTTPException(status_code=400, detail="Either job_description or job_url must be provided")

        # Extract job description from URL if provided
        if data.job_url:
            logger.info(f"Extracting job from URL: {data.job_url}")
            job_description = await extract_job_from_url(data.job_url)

            # Auto-detect company from URL if company_name is generic or empty
            if not data.company_name or data.company_name.lower() in ['company', 'target company']:
                detected_company = detect_company_from_url(data.job_url)
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
