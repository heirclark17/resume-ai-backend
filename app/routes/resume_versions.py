"""Resume Version History Routes"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
import json

from app.database import get_db
from app.models.resume_version import ResumeVersion
from app.models.resume import TailoredResume
from app.middleware.auth import get_user_id, ownership_filter
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger()


@router.get("/{tailored_resume_id}/versions")
async def list_versions(
    tailored_resume_id: int,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership
    tr_result = await db.execute(
        select(TailoredResume).where(
            TailoredResume.id == tailored_resume_id,
            ownership_filter(TailoredResume.session_user_id, user_id),
        )
    )
    tr = tr_result.scalar_one_or_none()
    if not tr:
        raise HTTPException(status_code=404, detail="Tailored resume not found")

    result = await db.execute(
        select(ResumeVersion)
        .where(ResumeVersion.tailored_resume_id == tailored_resume_id)
        .order_by(ResumeVersion.version_number.desc())
    )
    versions = result.scalars().all()
    return {"versions": [v.to_dict() for v in versions]}


@router.get("/{tailored_resume_id}/versions/{version_id}")
async def get_version(
    tailored_resume_id: int,
    version_id: int,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ResumeVersion).where(
            ResumeVersion.id == version_id,
            ResumeVersion.tailored_resume_id == tailored_resume_id,
            ownership_filter(ResumeVersion.session_user_id, user_id),
        )
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    return {
        **version.to_dict(),
        "snapshotJson": version.snapshot_json,
    }


@router.post("/{tailored_resume_id}/versions/restore/{version_id}")
async def restore_version(
    tailored_resume_id: int,
    version_id: int,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Get the version to restore
    ver_result = await db.execute(
        select(ResumeVersion).where(
            ResumeVersion.id == version_id,
            ResumeVersion.tailored_resume_id == tailored_resume_id,
            ownership_filter(ResumeVersion.session_user_id, user_id),
        )
    )
    version = ver_result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    # Get the tailored resume
    tr_result = await db.execute(
        select(TailoredResume).where(TailoredResume.id == tailored_resume_id)
    )
    tr = tr_result.scalar_one_or_none()
    if not tr:
        raise HTTPException(status_code=404, detail="Tailored resume not found")

    # Snapshot current state before restoring
    current_snapshot = {
        "tailored_summary": tr.tailored_summary,
        "tailored_skills": tr.tailored_skills,
        "tailored_experience": tr.tailored_experience,
        "alignment_statement": tr.alignment_statement,
    }

    # Get next version number
    max_ver_result = await db.execute(
        select(func.max(ResumeVersion.version_number))
        .where(ResumeVersion.tailored_resume_id == tailored_resume_id)
    )
    max_ver = max_ver_result.scalar() or 0

    # Save current as new version (before overwriting)
    backup_version = ResumeVersion(
        tailored_resume_id=tailored_resume_id,
        session_user_id=user_id,
        version_number=max_ver + 1,
        snapshot_json=current_snapshot,
        change_summary=f"Auto-saved before restoring to version {version.version_number}",
    )
    db.add(backup_version)

    # Restore from snapshot
    snapshot = version.snapshot_json
    tr.tailored_summary = snapshot.get("tailored_summary")
    tr.tailored_skills = snapshot.get("tailored_skills")
    tr.tailored_experience = snapshot.get("tailored_experience")
    tr.alignment_statement = snapshot.get("alignment_statement")

    await db.commit()

    return {
        "success": True,
        "message": f"Restored to version {version.version_number}",
        "backup_version": max_ver + 1,
    }
