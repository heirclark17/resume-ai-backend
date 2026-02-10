"""Cover Letter Generation Routes"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.cover_letter import CoverLetter
from app.middleware.auth import get_user_id
from app.services.cover_letter_service import generate_cover_letter_content
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger()


class GenerateRequest(BaseModel):
    job_title: str
    company_name: str
    job_description: str
    tone: str = "professional"
    tailored_resume_id: Optional[int] = None


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
        .where(CoverLetter.session_user_id == user_id, CoverLetter.is_deleted == False)
        .order_by(CoverLetter.created_at.desc())
    )
    letters = result.scalars().all()
    return {"cover_letters": [l.to_dict() for l in letters]}


@router.post("/generate")
async def generate_cover_letter(
    data: GenerateRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    if data.tone not in ("professional", "enthusiastic", "conversational"):
        raise HTTPException(status_code=400, detail="Invalid tone")

    try:
        # Fetch resume data if linked
        resume_context = None
        if data.tailored_resume_id:
            from app.models.resume import TailoredResume, BaseResume
            tr_result = await db.execute(
                select(TailoredResume).where(TailoredResume.id == data.tailored_resume_id)
            )
            tr = tr_result.scalar_one_or_none()
            if tr:
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

        content = await generate_cover_letter_content(
            job_title=data.job_title,
            company_name=data.company_name,
            job_description=data.job_description,
            tone=data.tone,
            resume_context=resume_context,
        )

        letter = CoverLetter(
            session_user_id=user_id,
            tailored_resume_id=data.tailored_resume_id,
            job_title=data.job_title,
            company_name=data.company_name,
            job_description=data.job_description,
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
        select(CoverLetter).where(CoverLetter.id == letter_id, CoverLetter.session_user_id == user_id)
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
        select(CoverLetter).where(CoverLetter.id == letter_id, CoverLetter.session_user_id == user_id)
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
        select(CoverLetter).where(CoverLetter.id == letter_id, CoverLetter.session_user_id == user_id)
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
