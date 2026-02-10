"""Follow-Up Reminder Routes"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.follow_up_reminder import FollowUpReminder
from app.middleware.auth import get_user_id
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger()


class ReminderCreate(BaseModel):
    application_id: Optional[int] = None
    reminder_date: str
    email: str
    subject: Optional[str] = None
    message: Optional[str] = None


class ReminderUpdate(BaseModel):
    reminder_date: Optional[str] = None
    email: Optional[str] = None
    subject: Optional[str] = None
    message: Optional[str] = None


@router.get("/")
async def list_reminders(
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FollowUpReminder)
        .where(FollowUpReminder.session_user_id == user_id)
        .order_by(FollowUpReminder.reminder_date.asc())
    )
    reminders = result.scalars().all()
    return {"reminders": [r.to_dict() for r in reminders]}


@router.post("/")
async def create_reminder(
    data: ReminderCreate,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    reminder = FollowUpReminder(
        session_user_id=user_id,
        application_id=data.application_id,
        reminder_date=datetime.fromisoformat(data.reminder_date),
        email=data.email,
        subject=data.subject,
        message=data.message,
    )
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    return {"success": True, "reminder": reminder.to_dict()}


@router.delete("/{reminder_id}")
async def delete_reminder(
    reminder_id: int,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FollowUpReminder).where(
            FollowUpReminder.id == reminder_id,
            FollowUpReminder.session_user_id == user_id,
        )
    )
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    await db.delete(reminder)
    await db.commit()
    return {"success": True, "message": "Reminder deleted"}
