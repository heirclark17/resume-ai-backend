"""Application Tracking Routes"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json

from app.database import get_db
from app.models.application import Application
from app.models.resume import TailoredResume
from app.models.job import Job
from app.middleware.auth import get_user_id
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger()


class ApplicationCreate(BaseModel):
    job_title: str
    company_name: str
    job_url: Optional[str] = None
    status: str = "saved"
    applied_date: Optional[str] = None
    notes: Optional[str] = None
    tailored_resume_id: Optional[int] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    location: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    next_follow_up: Optional[str] = None


class ApplicationUpdate(BaseModel):
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    job_url: Optional[str] = None
    status: Optional[str] = None
    applied_date: Optional[str] = None
    notes: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    location: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    next_follow_up: Optional[str] = None


VALID_STATUSES = {'saved', 'applied', 'screening', 'interviewing', 'offer', 'accepted', 'rejected', 'withdrawn', 'no_response'}


@router.get("/")
async def list_applications(
    status: Optional[str] = None,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    query = select(Application).where(
        Application.session_user_id == user_id,
        Application.is_deleted == False,
    )
    if status and status in VALID_STATUSES:
        query = query.where(Application.status == status)
    query = query.order_by(Application.updated_at.desc())
    result = await db.execute(query)
    apps = result.scalars().all()

    # Enrich applications with job salary data
    enriched_apps = []
    for app in apps:
        app_dict = app.to_dict()

        # If application has a tailored resume, fetch job salary data
        if app.tailored_resume_id:
            try:
                # Fetch tailored resume
                resume_result = await db.execute(
                    select(TailoredResume).where(TailoredResume.id == app.tailored_resume_id)
                )
                tailored_resume = resume_result.scalar_one_or_none()

                # If resume has a job, fetch salary insights
                if tailored_resume and tailored_resume.job_id:
                    job_result = await db.execute(
                        select(Job).where(Job.id == tailored_resume.job_id)
                    )
                    job = job_result.scalar_one_or_none()

                    if job:
                        # Add salary insights to application data
                        app_dict["salaryInsights"] = {
                            "salary_range": job.salary,
                            "median_salary": job.median_salary,
                            "market_insights": job.salary_insights,
                            "sources": json.loads(job.salary_sources) if job.salary_sources else [],
                            "last_updated": job.salary_last_updated.isoformat() if job.salary_last_updated else None
                        }
            except Exception as e:
                logger.error(f"Error fetching salary data for application {app.id}: {e}")
                # Continue without salary insights if there's an error
                pass

        enriched_apps.append(app_dict)

    return {"applications": enriched_apps}


@router.get("/stats")
async def get_stats(
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Application.status, func.count(Application.id))
        .where(Application.session_user_id == user_id, Application.is_deleted == False)
        .group_by(Application.status)
    )
    result = await db.execute(query)
    stats = {row[0]: row[1] for row in result.all()}
    return {"stats": stats}


@router.post("/")
async def create_application(
    data: ApplicationCreate,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    if data.status and data.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {data.status}")

    app = Application(
        session_user_id=user_id,
        job_title=data.job_title,
        company_name=data.company_name,
        job_url=data.job_url,
        status=data.status,
        applied_date=datetime.fromisoformat(data.applied_date) if data.applied_date else None,
        notes=data.notes,
        tailored_resume_id=data.tailored_resume_id,
        salary_min=data.salary_min,
        salary_max=data.salary_max,
        location=data.location,
        contact_name=data.contact_name,
        contact_email=data.contact_email,
        next_follow_up=datetime.fromisoformat(data.next_follow_up) if data.next_follow_up else None,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return {"success": True, "application": app.to_dict()}


@router.put("/{app_id}")
async def update_application(
    app_id: int,
    data: ApplicationUpdate,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Application).where(Application.id == app_id, Application.session_user_id == user_id)
    )
    app = result.scalar_one_or_none()
    if not app or app.is_deleted:
        raise HTTPException(status_code=404, detail="Application not found")

    update_data = data.model_dump(exclude_unset=True)
    if 'status' in update_data and update_data['status'] not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {update_data['status']}")

    for field, value in update_data.items():
        if field in ('applied_date', 'next_follow_up') and value:
            value = datetime.fromisoformat(value)
        setattr(app, field, value)

    app.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(app)
    return {"success": True, "application": app.to_dict()}


@router.delete("/{app_id}")
async def delete_application(
    app_id: int,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Application).where(Application.id == app_id, Application.session_user_id == user_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    app.is_deleted = True
    await db.commit()
    return {"success": True, "message": "Application deleted"}
