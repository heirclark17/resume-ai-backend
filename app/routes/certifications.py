"""
Certifications API Routes

Endpoint for generating personalized certification recommendations
for interview prep
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List

from app.database import get_db
from app.models import InterviewPrep, Job, TailoredResume
from app.services.certification_service import CertificationService

router = APIRouter()
cert_service = CertificationService()

class RecommendCertificationsRequest(BaseModel):
    interview_prep_id: int


@router.post("/recommend")
async def recommend_certifications(
    request: RecommendCertificationsRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate personalized certification recommendations
    based on interview prep data and target role
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Get interview prep with user validation through TailoredResume
    result = await db.execute(
        select(InterviewPrep, Job, TailoredResume)
        .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
        .join(Job, TailoredResume.job_id == Job.id)
        .filter(
            InterviewPrep.id == request.interview_prep_id,
            TailoredResume.session_user_id == x_user_id
        )
    )
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Interview prep not found or access denied")

    interview_prep, job, tailored_resume = row

    # Extract current skills from prep data
    prep_data = interview_prep.prep_data or {}
    current_skills = []

    # Try to get skills from various possible locations in prep_data
    if isinstance(prep_data, dict):
        # Look for skills in common locations
        if 'key_skills' in prep_data:
            current_skills = prep_data['key_skills']
        elif 'skills' in prep_data:
            current_skills = prep_data['skills']
        elif 'technical_skills' in prep_data:
            current_skills = prep_data['technical_skills']

    # If no skills found, use placeholder
    if not current_skills:
        current_skills = ["Program Management", "Cybersecurity", "Risk Management"]

    # Determine experience level (default to mid)
    experience_level = "mid"

    # Determine industry from job or company
    industry = job.company or "Technology"

    # Generate recommendations
    try:
        recommendations = await cert_service.recommend_certifications(
            job_title=job.title,
            company_name=job.company or "Target Company",
            industry=industry,
            job_description=job.description,
            current_skills=current_skills,
            experience_level=experience_level
        )

        return {
            "success": True,
            "certifications": recommendations
        }

    except Exception as e:
        print(f"Error generating certification recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
