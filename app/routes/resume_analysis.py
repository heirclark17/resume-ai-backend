"""
Resume Analysis API Routes

Endpoints for:
- Analyzing resume changes
- Keyword analysis
- Match score calculation
- Resume export (PDF/DOCX)
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json

from app.database import get_db
from app.models import TailoredResume, Job
from app.services.resume_analysis_service import ResumeAnalysisService
from app.services.resume_export_service import ResumeExportService

router = APIRouter()
analysis_service = ResumeAnalysisService()
export_service = ResumeExportService()

# Request models
class AnalyzeChangesRequest(BaseModel):
    tailored_resume_id: int

class AnalyzeKeywordsRequest(BaseModel):
    tailored_resume_id: int

class MatchScoreRequest(BaseModel):
    tailored_resume_id: int

class ExportResumeRequest(BaseModel):
    tailored_resume_id: int
    format: str  # "pdf" or "docx"


@router.post("/analyze-changes")
async def analyze_resume_changes(
    request: AnalyzeChangesRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze changes between original and tailored resume
    Returns detailed explanations for each section change
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Get tailored resume with user validation
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

    # Get original resume
    try:
        original_resume_data = json.loads(tailored_resume.original_resume) if tailored_resume.original_resume else {}
    except json.JSONDecodeError as e:
        print(f"Error parsing original_resume JSON: {e}")
        raise HTTPException(status_code=500, detail="Invalid original resume data format")

    try:
        tailored_resume_data = json.loads(tailored_resume.tailored_content) if tailored_resume.tailored_content else {}
    except json.JSONDecodeError as e:
        print(f"Error parsing tailored_content JSON: {e}")
        raise HTTPException(status_code=500, detail="Invalid tailored resume data format")

    # Analyze changes
    try:
        analysis = await analysis_service.analyze_resume_changes(
            original_resume=original_resume_data,
            tailored_resume=tailored_resume_data,
            job_description=job.description or "",
            job_title=job.title or "Unknown Position"
        )

        return {
            "success": True,
            "analysis": analysis
        }

    except Exception as e:
        print(f"Error in analyze_resume_changes: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"AI analysis error: {str(e)}")


@router.post("/analyze-keywords")
async def analyze_keywords(
    request: AnalyzeKeywordsRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Identify and categorize all new keywords added to tailored resume
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Get tailored resume with user validation
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

    # Get resumes with proper error handling
    try:
        original_resume_data = json.loads(tailored_resume.original_resume) if tailored_resume.original_resume else {}
    except json.JSONDecodeError as e:
        print(f"Error parsing original_resume JSON: {e}")
        raise HTTPException(status_code=500, detail="Invalid original resume data format")

    try:
        tailored_resume_data = json.loads(tailored_resume.tailored_content) if tailored_resume.tailored_content else {}
    except json.JSONDecodeError as e:
        print(f"Error parsing tailored_content JSON: {e}")
        raise HTTPException(status_code=500, detail="Invalid tailored resume data format")

    # Analyze keywords
    try:
        keyword_analysis = await analysis_service.analyze_keywords(
            original_resume=original_resume_data,
            tailored_resume=tailored_resume_data,
            job_description=job.description or ""
        )

        return {
            "success": True,
            "keywords": keyword_analysis
        }

    except Exception as e:
        print(f"Error in analyze_keywords: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"AI analysis error: {str(e)}")


@router.post("/match-score")
async def calculate_match_score(
    request: MatchScoreRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate 0-100 match score with detailed breakdown
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Get tailored resume with user validation
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

    # Get tailored resume data with proper error handling
    try:
        tailored_resume_data = json.loads(tailored_resume.tailored_content) if tailored_resume.tailored_content else {}
    except json.JSONDecodeError as e:
        print(f"Error parsing tailored_content JSON: {e}")
        raise HTTPException(status_code=500, detail="Invalid tailored resume data format")

    # Calculate match score
    try:
        match_score = await analysis_service.calculate_match_score(
            tailored_resume=tailored_resume_data,
            job_description=job.description or "",
            job_title=job.title or "Unknown Position"
        )

        return {
            "success": True,
            "match_score": match_score
        }

    except Exception as e:
        print(f"Error in calculate_match_score: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"AI analysis error: {str(e)}")


@router.post("/export")
async def export_resume(
    request: ExportResumeRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Export tailored resume as PDF or DOCX
    Returns file with proper filename: UserName_TargetRole_TailoredResume.ext
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Validate format
    if request.format not in ["pdf", "docx"]:
        raise HTTPException(status_code=400, detail="Format must be 'pdf' or 'docx'")

    # Get tailored resume with user validation
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

    # Get resume data
    resume_data = json.loads(tailored_resume.tailored_content)

    # Get user name from session_user_id (just use last 8 chars for filename)
    user_name = f"User{x_user_id[-8:]}"

    # Generate file
    try:
        if request.format == "pdf":
            file_buffer = export_service.generate_pdf(resume_data, user_name, job.title)
            media_type = "application/pdf"
        else:  # docx
            file_buffer = export_service.generate_docx(resume_data, user_name, job.title)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        # Generate filename
        filename = export_service.generate_filename(user_name, job.title, request.format)

        # Return file
        return StreamingResponse(
            file_buffer,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        print(f"Error exporting resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))
