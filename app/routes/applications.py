"""
Application Tracking API Routes

Endpoints for:
- Creating job applications
- Listing applications with filtering by status
- Updating application details and status
- Deleting applications
- Getting application statistics
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date

from app.database import get_db
from app.models.application import Application

router = APIRouter()

# Request/Response models
class CreateApplicationRequest(BaseModel):
    job_title: str
    company_name: str
    job_url: Optional[str] = None
    status: str = 'saved'  # Default to 'saved'
    location: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    applied_date: Optional[date] = None
    next_follow_up: Optional[date] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None
    tailored_resume_id: Optional[int] = None

class UpdateApplicationRequest(BaseModel):
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    job_url: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    applied_date: Optional[date] = None
    next_follow_up: Optional[date] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None
    tailored_resume_id: Optional[int] = None

class ApplicationResponse(BaseModel):
    id: int
    job_title: str
    company_name: str
    job_url: Optional[str]
    status: str
    location: Optional[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    applied_date: Optional[date]
    next_follow_up: Optional[date]
    contact_name: Optional[str]
    contact_email: Optional[str]
    notes: Optional[str]
    tailored_resume_id: Optional[int]
    created_at: datetime
    updated_at: datetime

class ApplicationListResponse(BaseModel):
    applications: List[ApplicationResponse]
    total: int

class ApplicationStatsResponse(BaseModel):
    stats: dict  # { 'saved': 5, 'applied': 10, 'screening': 3, ... }
    total: int


# Validation constants
VALID_STATUSES = [
    'saved',
    'applied',
    'screening',
    'interviewing',
    'offer',
    'accepted',
    'rejected',
    'withdrawn',
    'no_response'
]


@router.post("/", response_model=ApplicationResponse)
async def create_application(
    request: CreateApplicationRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new job application
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Validate status
    if request.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"
        )

    # Create application
    application = Application(
        user_id=x_user_id,
        job_title=request.job_title,
        company_name=request.company_name,
        job_url=request.job_url,
        status=request.status,
        location=request.location,
        salary_min=request.salary_min,
        salary_max=request.salary_max,
        applied_date=request.applied_date,
        next_follow_up=request.next_follow_up,
        contact_name=request.contact_name,
        contact_email=request.contact_email,
        notes=request.notes,
        tailored_resume_id=request.tailored_resume_id
    )

    db.add(application)
    await db.commit()
    await db.refresh(application)

    return ApplicationResponse(
        id=application.id,
        job_title=application.job_title,
        company_name=application.company_name,
        job_url=application.job_url,
        status=application.status,
        location=application.location,
        salary_min=application.salary_min,
        salary_max=application.salary_max,
        applied_date=application.applied_date,
        next_follow_up=application.next_follow_up,
        contact_name=application.contact_name,
        contact_email=application.contact_email,
        notes=application.notes,
        tailored_resume_id=application.tailored_resume_id,
        created_at=application.created_at,
        updated_at=application.updated_at
    )


@router.get("/", response_model=ApplicationListResponse)
async def list_applications(
    status: Optional[str] = Query(None, description="Filter by status"),
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    List all applications for the user, optionally filtered by status
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Build query
    query = select(Application).filter(Application.user_id == x_user_id)

    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"
            )
        query = query.filter(Application.status == status)

    # Order by most recent first
    query = query.order_by(Application.created_at.desc())

    result = await db.execute(query)
    applications = result.scalars().all()

    # Convert to response models
    application_list = [
        ApplicationResponse(
            id=app.id,
            job_title=app.job_title,
            company_name=app.company_name,
            job_url=app.job_url,
            status=app.status,
            location=app.location,
            salary_min=app.salary_min,
            salary_max=app.salary_max,
            applied_date=app.applied_date,
            next_follow_up=app.next_follow_up,
            contact_name=app.contact_name,
            contact_email=app.contact_email,
            notes=app.notes,
            tailored_resume_id=app.tailored_resume_id,
            created_at=app.created_at,
            updated_at=app.updated_at
        )
        for app in applications
    ]

    return ApplicationListResponse(
        applications=application_list,
        total=len(application_list)
    )


@router.get("/stats", response_model=ApplicationStatsResponse)
async def get_application_stats(
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get application statistics grouped by status
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Query to get counts grouped by status
    result = await db.execute(
        select(
            Application.status,
            func.count(Application.id).label('count')
        )
        .filter(Application.user_id == x_user_id)
        .group_by(Application.status)
    )

    rows = result.all()

    # Build stats dictionary
    stats = {status: 0 for status in VALID_STATUSES}  # Initialize all statuses to 0
    total = 0

    for status, count in rows:
        stats[status] = count
        total += count

    return ApplicationStatsResponse(
        stats=stats,
        total=total
    )


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific application by ID
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    result = await db.execute(
        select(Application).filter(
            and_(
                Application.id == application_id,
                Application.user_id == x_user_id
            )
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found or access denied")

    return ApplicationResponse(
        id=application.id,
        job_title=application.job_title,
        company_name=application.company_name,
        job_url=application.job_url,
        status=application.status,
        location=application.location,
        salary_min=application.salary_min,
        salary_max=application.salary_max,
        applied_date=application.applied_date,
        next_follow_up=application.next_follow_up,
        contact_name=application.contact_name,
        contact_email=application.contact_email,
        notes=application.notes,
        tailored_resume_id=application.tailored_resume_id,
        created_at=application.created_at,
        updated_at=application.updated_at
    )


@router.put("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: int,
    request: UpdateApplicationRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Update an application
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Get application
    result = await db.execute(
        select(Application).filter(
            and_(
                Application.id == application_id,
                Application.user_id == x_user_id
            )
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found or access denied")

    # Validate status if provided
    if request.status and request.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"
        )

    # Update fields
    if request.job_title is not None:
        application.job_title = request.job_title
    if request.company_name is not None:
        application.company_name = request.company_name
    if request.job_url is not None:
        application.job_url = request.job_url
    if request.status is not None:
        application.status = request.status
    if request.location is not None:
        application.location = request.location
    if request.salary_min is not None:
        application.salary_min = request.salary_min
    if request.salary_max is not None:
        application.salary_max = request.salary_max
    if request.applied_date is not None:
        application.applied_date = request.applied_date
    if request.next_follow_up is not None:
        application.next_follow_up = request.next_follow_up
    if request.contact_name is not None:
        application.contact_name = request.contact_name
    if request.contact_email is not None:
        application.contact_email = request.contact_email
    if request.notes is not None:
        application.notes = request.notes
    if request.tailored_resume_id is not None:
        application.tailored_resume_id = request.tailored_resume_id

    application.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(application)

    return ApplicationResponse(
        id=application.id,
        job_title=application.job_title,
        company_name=application.company_name,
        job_url=application.job_url,
        status=application.status,
        location=application.location,
        salary_min=application.salary_min,
        salary_max=application.salary_max,
        applied_date=application.applied_date,
        next_follow_up=application.next_follow_up,
        contact_name=application.contact_name,
        contact_email=application.contact_email,
        notes=application.notes,
        tailored_resume_id=application.tailored_resume_id,
        created_at=application.created_at,
        updated_at=application.updated_at
    )


@router.delete("/{application_id}")
async def delete_application(
    application_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete an application
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Get application
    result = await db.execute(
        select(Application).filter(
            and_(
                Application.id == application_id,
                Application.user_id == x_user_id
            )
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found or access denied")

    await db.delete(application)
    await db.commit()

    return {"success": True, "message": "Application deleted successfully"}
