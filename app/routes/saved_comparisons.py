"""
Saved Comparisons API Routes

Endpoints for:
- Saving resume comparisons for later viewing
- Retrieving saved comparisons list
- Viewing a specific saved comparison
- Managing user edits to tailored resumes
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import json

from app.database import get_db
from app.models import SavedComparison, TailoredResumeEdit, TailoredResume, BaseResume, Job

router = APIRouter()

# Request/Response models
class SaveComparisonRequest(BaseModel):
    tailored_resume_id: int
    title: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    analysis_data: Optional[dict] = None  # AI change analysis
    keywords_data: Optional[dict] = None  # Keyword extraction results
    match_score_data: Optional[dict] = None  # Match score breakdown

class SaveComparisonResponse(BaseModel):
    id: int
    tailored_resume_id: int
    title: Optional[str]
    saved_at: datetime

class SavedComparisonListItem(BaseModel):
    id: int
    tailored_resume_id: int
    title: Optional[str]
    company: str
    position: str
    saved_at: datetime
    last_viewed_at: Optional[datetime]
    is_pinned: bool
    tags: Optional[List[str]]

class EditResumeRequest(BaseModel):
    tailored_resume_id: int
    section_name: str  # "summary", "skills", "experience", "alignment_statement"
    section_index: Optional[int] = None  # For array sections
    edited_content: str

class UpdateComparisonRequest(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    is_pinned: Optional[bool] = None


@router.post("/save", response_model=SaveComparisonResponse)
async def save_comparison(
    request: SaveComparisonRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Save a resume comparison for later viewing
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Verify tailored resume exists and belongs to user
    result = await db.execute(
        select(TailoredResume, Job)
        .join(Job, TailoredResume.job_id == Job.id)
        .filter(
            TailoredResume.id == request.tailored_resume_id,
            TailoredResume.session_user_id == x_user_id
        )
    )
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Tailored resume not found or access denied")

    tailored_resume, job = row

    # Check if already saved
    existing = await db.execute(
        select(SavedComparison).filter(
            and_(
                SavedComparison.tailored_resume_id == request.tailored_resume_id,
                SavedComparison.session_user_id == x_user_id,
                SavedComparison.is_deleted == False
            )
        )
    )
    existing_comparison = existing.scalar_one_or_none()

    if existing_comparison:
        # Update existing
        if request.title is not None:
            existing_comparison.title = request.title
        if request.notes is not None:
            existing_comparison.notes = request.notes
        if request.tags is not None:
            existing_comparison.tags = json.dumps(request.tags)
        if request.analysis_data is not None:
            existing_comparison.analysis_data = json.dumps(request.analysis_data)
        if request.keywords_data is not None:
            existing_comparison.keywords_data = json.dumps(request.keywords_data)
        if request.match_score_data is not None:
            existing_comparison.match_score_data = json.dumps(request.match_score_data)

        await db.commit()
        await db.refresh(existing_comparison)

        return SaveComparisonResponse(
            id=existing_comparison.id,
            tailored_resume_id=existing_comparison.tailored_resume_id,
            title=existing_comparison.title,
            saved_at=existing_comparison.saved_at
        )

    # Create new saved comparison
    saved_comparison = SavedComparison(
        tailored_resume_id=request.tailored_resume_id,
        session_user_id=x_user_id,
        title=request.title or f"{job.company} - {job.title}",
        notes=request.notes,
        tags=json.dumps(request.tags) if request.tags else None,
        analysis_data=json.dumps(request.analysis_data) if request.analysis_data else None,
        keywords_data=json.dumps(request.keywords_data) if request.keywords_data else None,
        match_score_data=json.dumps(request.match_score_data) if request.match_score_data else None
    )

    db.add(saved_comparison)
    await db.commit()
    await db.refresh(saved_comparison)

    return SaveComparisonResponse(
        id=saved_comparison.id,
        tailored_resume_id=saved_comparison.tailored_resume_id,
        title=saved_comparison.title,
        saved_at=saved_comparison.saved_at
    )


@router.get("/list", response_model=List[SavedComparisonListItem])
async def get_saved_comparisons(
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of all saved comparisons for the user
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    result = await db.execute(
        select(SavedComparison, TailoredResume, Job)
        .join(TailoredResume, SavedComparison.tailored_resume_id == TailoredResume.id)
        .join(Job, TailoredResume.job_id == Job.id)
        .filter(
            SavedComparison.session_user_id == x_user_id,
            SavedComparison.is_deleted == False
        )
        .order_by(
            SavedComparison.is_pinned.desc(),
            SavedComparison.saved_at.desc()
        )
    )

    comparisons = []
    for saved_comp, tailored_resume, job in result:
        comparisons.append(SavedComparisonListItem(
            id=saved_comp.id,
            tailored_resume_id=saved_comp.tailored_resume_id,
            title=saved_comp.title,
            company=job.company,
            position=job.title,
            saved_at=saved_comp.saved_at,
            last_viewed_at=saved_comp.last_viewed_at,
            is_pinned=saved_comp.is_pinned,
            tags=json.loads(saved_comp.tags) if saved_comp.tags else None
        ))

    return comparisons


@router.get("/{comparison_id}")
async def get_saved_comparison(
    comparison_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific saved comparison with full resume data
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Get saved comparison
    result = await db.execute(
        select(SavedComparison, TailoredResume, BaseResume, Job)
        .join(TailoredResume, SavedComparison.tailored_resume_id == TailoredResume.id)
        .join(BaseResume, TailoredResume.base_resume_id == BaseResume.id)
        .join(Job, TailoredResume.job_id == Job.id)
        .filter(
            SavedComparison.id == comparison_id,
            SavedComparison.session_user_id == x_user_id,
            SavedComparison.is_deleted == False
        )
    )
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Saved comparison not found or access denied")

    saved_comp, tailored_resume, base_resume, job = row

    # Update last_viewed_at
    saved_comp.last_viewed_at = datetime.utcnow()
    await db.commit()

    # Get any user edits
    edits_result = await db.execute(
        select(TailoredResumeEdit).filter(
            TailoredResumeEdit.tailored_resume_id == tailored_resume.id,
            TailoredResumeEdit.is_deleted == False
        ).order_by(TailoredResumeEdit.edited_at.desc())
    )
    edits = edits_result.scalars().all()

    # Build response with edited content and AI analysis
    response = {
        "comparison_id": saved_comp.id,
        "title": saved_comp.title,
        "notes": saved_comp.notes,
        "tags": json.loads(saved_comp.tags) if saved_comp.tags else [],
        "is_pinned": saved_comp.is_pinned,
        "saved_at": saved_comp.saved_at,
        "job": {
            "company": job.company,
            "title": job.title,
            "url": job.url,
            "description": job.description
        },
        "base_resume": {
            "summary": base_resume.summary,
            "skills": json.loads(base_resume.skills) if base_resume.skills else [],
            "experience": json.loads(base_resume.experience) if base_resume.experience else [],
            "education": base_resume.education,
            "certifications": base_resume.certifications
        },
        "tailored_resume": {
            "summary": tailored_resume.tailored_summary,
            "skills": json.loads(tailored_resume.tailored_skills) if tailored_resume.tailored_skills else [],
            "experience": json.loads(tailored_resume.tailored_experience) if tailored_resume.tailored_experience else [],
            "education": base_resume.education,
            "certifications": base_resume.certifications,
            "alignment_statement": tailored_resume.alignment_statement
        },
        "edits": [
            {
                "id": edit.id,
                "section_name": edit.section_name,
                "section_index": edit.section_index,
                "edited_content": edit.edited_content,
                "edited_at": edit.edited_at,
                "edit_type": edit.edit_type
            }
            for edit in edits
        ],
        # AI Analysis Data (persisted from when comparison was saved)
        "analysis": json.loads(saved_comp.analysis_data) if saved_comp.analysis_data else None,
        "keywords": json.loads(saved_comp.keywords_data) if saved_comp.keywords_data else None,
        "match_score": json.loads(saved_comp.match_score_data) if saved_comp.match_score_data else None
    }

    return response


@router.put("/{comparison_id}")
async def update_saved_comparison(
    comparison_id: int,
    request: UpdateComparisonRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Update saved comparison metadata (title, notes, tags, pinned status)
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    result = await db.execute(
        select(SavedComparison).filter(
            SavedComparison.id == comparison_id,
            SavedComparison.session_user_id == x_user_id,
            SavedComparison.is_deleted == False
        )
    )
    saved_comp = result.scalar_one_or_none()

    if not saved_comp:
        raise HTTPException(status_code=404, detail="Saved comparison not found")

    # Update fields
    if request.title is not None:
        saved_comp.title = request.title
    if request.notes is not None:
        saved_comp.notes = request.notes
    if request.tags is not None:
        saved_comp.tags = json.dumps(request.tags)
    if request.is_pinned is not None:
        saved_comp.is_pinned = request.is_pinned

    await db.commit()

    return {"success": True, "message": "Comparison updated"}


@router.delete("/{comparison_id}")
async def delete_saved_comparison(
    comparison_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Soft delete a saved comparison
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    result = await db.execute(
        select(SavedComparison).filter(
            SavedComparison.id == comparison_id,
            SavedComparison.session_user_id == x_user_id,
            SavedComparison.is_deleted == False
        )
    )
    saved_comp = result.scalar_one_or_none()

    if not saved_comp:
        raise HTTPException(status_code=404, detail="Saved comparison not found")

    saved_comp.is_deleted = True
    saved_comp.deleted_at = datetime.utcnow()
    await db.commit()

    return {"success": True, "message": "Comparison deleted"}


@router.post("/edit")
async def save_resume_edit(
    request: EditResumeRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Save user edit to a tailored resume section
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Verify tailored resume exists and belongs to user
    result = await db.execute(
        select(TailoredResume).filter(
            TailoredResume.id == request.tailored_resume_id,
            TailoredResume.session_user_id == x_user_id
        )
    )
    tailored_resume = result.scalar_one_or_none()

    if not tailored_resume:
        raise HTTPException(status_code=404, detail="Tailored resume not found or access denied")

    # Get original content
    original_content = None
    if request.section_name == "summary":
        original_content = tailored_resume.tailored_summary
    elif request.section_name == "alignment_statement":
        original_content = tailored_resume.alignment_statement
    elif request.section_name == "skills" and request.section_index is not None:
        skills = json.loads(tailored_resume.tailored_skills) if tailored_resume.tailored_skills else []
        if request.section_index < len(skills):
            original_content = skills[request.section_index]
    elif request.section_name == "experience" and request.section_index is not None:
        experience = json.loads(tailored_resume.tailored_experience) if tailored_resume.tailored_experience else []
        if request.section_index < len(experience):
            original_content = json.dumps(experience[request.section_index])

    # Create edit record
    edit = TailoredResumeEdit(
        tailored_resume_id=request.tailored_resume_id,
        session_user_id=x_user_id,
        section_name=request.section_name,
        section_index=request.section_index,
        original_content=original_content,
        edited_content=request.edited_content,
        edit_type="modify"
    )

    db.add(edit)
    await db.commit()
    await db.refresh(edit)

    return {
        "success": True,
        "edit_id": edit.id,
        "message": "Edit saved"
    }
