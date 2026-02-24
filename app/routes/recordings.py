from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text
from app.database import get_db
from app.services.storage_service import (
    generate_presigned_upload_url,
    generate_presigned_download_url,
    delete_object,
)
from app.utils.logger import logger

router = APIRouter(prefix="/api/recordings", tags=["Recordings"])


class PresignedUploadRequest(BaseModel):
    file_name: str
    content_type: str
    question_context: str  # e.g. "behavioral_3", "common_q2", "star_story_45"


class PresignedDownloadRequest(BaseModel):
    s3_key: str


class DeleteRecordingRequest(BaseModel):
    s3_key: str
    question_context: str


@router.post("/presigned-upload-url")
async def get_presigned_upload_url(
    req: PresignedUploadRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    allowed_types = [
        "video/webm",
        "video/mp4",
        "audio/webm",
        "audio/ogg",
        "audio/mp4",
    ]
    if req.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Content type must be one of: {', '.join(allowed_types)}",
        )

    try:
        result = await generate_presigned_upload_url(
            user_id=x_user_id,
            question_context=req.question_context,
            content_type=req.content_type,
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Failed to generate upload URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate upload URL")


@router.post("/presigned-download-url")
async def get_presigned_download_url(
    req: PresignedDownloadRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    # Verify the s3_key belongs to this user
    if f"/{x_user_id}/" not in req.s3_key:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        url = await generate_presigned_download_url(req.s3_key)
        return {"success": True, "download_url": url}
    except Exception as e:
        logger.error(f"Failed to generate download URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate download URL")


@router.delete("/delete")
async def delete_recording(
    req: DeleteRecordingRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
):
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    # Verify the s3_key belongs to this user
    if f"/{x_user_id}/" not in req.s3_key:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        # Delete from storage
        await delete_object(req.s3_key)

        # Clear URL in database based on question_context prefix
        if req.question_context.startswith("star_story_"):
            story_id = req.question_context.replace("star_story_", "")
            await db.execute(
                text(
                    "UPDATE star_stories SET video_recording_url = NULL WHERE id = :id AND session_user_id = :uid"
                ),
                {"id": int(story_id), "uid": x_user_id},
            )
            await db.commit()
        else:
            # For practice_question_responses, clear by matching question context
            await db.execute(
                text(
                    "UPDATE practice_question_responses SET video_recording_url = NULL "
                    "WHERE session_user_id = :uid AND question_id = :qid"
                ),
                {"uid": x_user_id, "qid": req.question_context},
            )
            await db.commit()

        logger.info(
            f"Deleted recording for user {x_user_id}, context: {req.question_context}"
        )
        return {"success": True, "message": "Recording deleted"}

    except Exception as e:
        logger.error(f"Failed to delete recording: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete recording")
