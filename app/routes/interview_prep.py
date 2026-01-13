from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.interview_prep import InterviewPrep
from app.models.resume import TailoredResume
from app.models.job import Job
from app.models.company import CompanyResearch
from app.services.openai_interview_prep import OpenAIInterviewPrep
from datetime import datetime

router = APIRouter(prefix="/api/interview-prep", tags=["interview_prep"])

@router.post("/generate/{tailored_resume_id}")
async def generate_interview_prep(
    tailored_resume_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate interview prep for a tailored resume.

    This endpoint:
    1. Fetches the tailored resume and associated job + company research
    2. Calls OpenAI to generate structured interview prep data
    3. Stores the result in the database
    4. Returns the interview prep data
    """

    # Fetch tailored resume
    result = await db.execute(
        select(TailoredResume).where(
            TailoredResume.id == tailored_resume_id,
            TailoredResume.is_deleted == False
        )
    )
    tailored_resume = result.scalar_one_or_none()

    if not tailored_resume:
        raise HTTPException(status_code=404, detail="Tailored resume not found")

    # Fetch associated job
    result = await db.execute(
        select(Job).where(Job.id == tailored_resume.job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Fetch company research
    result = await db.execute(
        select(CompanyResearch).where(CompanyResearch.job_id == job.id)
    )
    company_research = result.scalar_one_or_none()

    if not company_research:
        raise HTTPException(
            status_code=404,
            detail="Company research not found. Please generate a tailored resume first."
        )

    # Check if interview prep already exists
    result = await db.execute(
        select(InterviewPrep).where(
            InterviewPrep.tailored_resume_id == tailored_resume_id,
            InterviewPrep.is_deleted == False
        )
    )
    existing_prep = result.scalar_one_or_none()

    if existing_prep:
        # Return existing prep
        print(f"✓ Returning existing interview prep for tailored resume {tailored_resume_id}")
        return {
            "success": True,
            "interview_prep_id": existing_prep.id,
            "prep_data": existing_prep.prep_data,
            "created_at": existing_prep.created_at.isoformat(),
            "cached": True
        }

    # Generate new interview prep using OpenAI
    try:
        ai_service = OpenAIInterviewPrep()

        # Build job description text
        job_description = f"""
Job Title: {job.title}
Company: {job.company}
Location: {job.location or 'Not specified'}
Posted: {job.posted_date or 'Unknown'}
Salary: {job.salary or 'Not specified'}

Job Description:
{job.description or 'No description available'}

Requirements:
{job.requirements or 'No requirements listed'}
"""

        # Build company research dict
        company_data = {
            'industry': company_research.industry or 'Unknown',
            'mission_values': company_research.mission_values or '',
            'initiatives': company_research.initiatives or '',
            'team_culture': company_research.team_culture or '',
            'compliance': company_research.compliance or '',
            'tech_stack': company_research.tech_stack or '',
            'sources': company_research.sources or []
        }

        print(f"Generating interview prep for job: {job.company} - {job.title}")
        prep_data = await ai_service.generate_interview_prep(
            job_description=job_description,
            company_research=company_data
        )

        # Save to database
        interview_prep = InterviewPrep(
            tailored_resume_id=tailored_resume_id,
            prep_data=prep_data,
            created_at=datetime.utcnow()
        )

        db.add(interview_prep)
        await db.commit()
        await db.refresh(interview_prep)

        print(f"✓ Interview prep generated and saved with ID {interview_prep.id}")

        return {
            "success": True,
            "interview_prep_id": interview_prep.id,
            "prep_data": prep_data,
            "created_at": interview_prep.created_at.isoformat(),
            "cached": False
        }

    except Exception as e:
        print(f"Failed to generate interview prep: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate interview prep: {str(e)}"
        )


@router.get("/{tailored_resume_id}")
async def get_interview_prep(
    tailored_resume_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get existing interview prep for a tailored resume.
    Returns 404 if no prep exists yet.
    """

    result = await db.execute(
        select(InterviewPrep).where(
            InterviewPrep.tailored_resume_id == tailored_resume_id,
            InterviewPrep.is_deleted == False
        )
    )
    interview_prep = result.scalar_one_or_none()

    if not interview_prep:
        raise HTTPException(
            status_code=404,
            detail="Interview prep not found. Generate it first using POST /generate/{tailored_resume_id}"
        )

    return {
        "success": True,
        "interview_prep_id": interview_prep.id,
        "prep_data": interview_prep.prep_data,
        "created_at": interview_prep.created_at.isoformat()
    }


@router.delete("/{interview_prep_id}")
async def delete_interview_prep(
    interview_prep_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Soft delete an interview prep record.
    """

    result = await db.execute(
        select(InterviewPrep).where(InterviewPrep.id == interview_prep_id)
    )
    interview_prep = result.scalar_one_or_none()

    if not interview_prep:
        raise HTTPException(status_code=404, detail="Interview prep not found")

    # Soft delete
    interview_prep.is_deleted = True
    interview_prep.deleted_at = datetime.utcnow()

    await db.commit()

    return {
        "success": True,
        "message": "Interview prep deleted successfully"
    }
