"""
PostgreSQL-backed async job queue manager.
Replaces in-memory JobStore with durable, crash-safe job management.

Usage:
    job_id = await job_manager.enqueue_job(db, "tailor_resume", user_id, {...})
    status = await job_manager.get_job_status(db, job_id)
    await job_manager.update_progress(db, job_id, 50, "Researching company...")
    await job_manager.complete_job(db, job_id, result_data)
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, text
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import uuid

from app.models.async_job import AsyncJob
from app.utils.logger import logger


async def enqueue_job(
    db: AsyncSession,
    job_type: str,
    user_id: str,
    input_data: Optional[Dict[str, Any]] = None,
    max_attempts: int = 3,
) -> str:
    """Create a new job and return its ID"""
    job_id = str(uuid.uuid4())
    job = AsyncJob(
        id=job_id,
        user_id=user_id,
        job_type=job_type,
        status="pending",
        progress=0,
        message="Queued",
        input_data=input_data or {},
        max_attempts=max_attempts,
    )
    db.add(job)
    await db.commit()
    logger.info(f"job.enqueued", extra={"job_id": job_id, "job_type": job_type, "user_id": user_id})
    return job_id


async def get_job_status(db: AsyncSession, job_id: str) -> Optional[Dict[str, Any]]:
    """Get job status, progress, and result"""
    result = await db.execute(select(AsyncJob).where(AsyncJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        return None

    response = {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }

    if job.status == "completed" and job.result_data:
        response["result"] = job.result_data
    if job.status == "failed" and job.error_message:
        response["error"] = job.error_message

    return response


async def get_job(db: AsyncSession, job_id: str) -> Optional[AsyncJob]:
    """Get the raw AsyncJob ORM object"""
    result = await db.execute(select(AsyncJob).where(AsyncJob.id == job_id))
    return result.scalar_one_or_none()


async def update_progress(
    db: AsyncSession,
    job_id: str,
    progress: int,
    message: str = "",
) -> None:
    """Update job progress (0-100) and status message"""
    await db.execute(
        update(AsyncJob)
        .where(AsyncJob.id == job_id)
        .values(
            progress=min(progress, 100),
            message=message,
            status="processing",
            updated_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()


async def complete_job(
    db: AsyncSession,
    job_id: str,
    result_data: Dict[str, Any],
) -> None:
    """Mark job as completed with result data"""
    now = datetime.now(timezone.utc)
    await db.execute(
        update(AsyncJob)
        .where(AsyncJob.id == job_id)
        .values(
            status="completed",
            progress=100,
            message="Completed",
            result_data=result_data,
            completed_at=now,
            updated_at=now,
        )
    )
    await db.commit()
    logger.info("job.completed", extra={"job_id": job_id})


async def fail_job(
    db: AsyncSession,
    job_id: str,
    error: str,
) -> None:
    """Mark job as failed with error message"""
    now = datetime.now(timezone.utc)
    await db.execute(
        update(AsyncJob)
        .where(AsyncJob.id == job_id)
        .values(
            status="failed",
            message="Failed",
            error_message=error,
            completed_at=now,
            updated_at=now,
        )
    )
    await db.commit()
    logger.error("job.failed", extra={"job_id": job_id, "error": error})


async def claim_next_job(
    db: AsyncSession,
    job_type: Optional[str] = None,
) -> Optional[AsyncJob]:
    """
    Atomically claim the next pending job for processing.
    Uses SELECT ... FOR UPDATE SKIP LOCKED for safe concurrent access.
    """
    query = (
        select(AsyncJob)
        .where(
            and_(
                AsyncJob.status == "pending",
                AsyncJob.attempts < AsyncJob.max_attempts,
            )
        )
        .order_by(AsyncJob.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )

    if job_type:
        query = query.where(AsyncJob.job_type == job_type)

    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if job:
        job.status = "processing"
        job.attempts += 1
        job.updated_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("job.claimed", extra={"job_id": job.id, "job_type": job.job_type, "attempt": job.attempts})

    return job


async def cleanup_old_jobs(
    db: AsyncSession,
    max_age_hours: int = 72,
) -> int:
    """Delete completed/failed jobs older than max_age_hours. Returns count deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    result = await db.execute(
        text(
            "DELETE FROM async_jobs WHERE status IN ('completed', 'failed') AND created_at < :cutoff"
        ),
        {"cutoff": cutoff},
    )
    await db.commit()
    count = result.rowcount
    if count > 0:
        logger.info("job.cleanup", extra={"deleted": count, "max_age_hours": max_age_hours})
    return count
