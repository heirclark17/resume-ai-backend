from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.resume import BaseResume
from app.models.user import User
from app.middleware.auth import get_current_user, get_current_user_optional
from app.services.resume_parser import ResumeParser
from app.utils.file_handler import FileHandler
from app.utils.logger import logger
import json


def safe_json_loads(json_str: str, default=None):
    """Safely parse JSON string with error handling"""
    if not json_str:
        return default if default is not None else []
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning(f"JSON deserialization failed: {e}. Returning default value.")
        return default if default is not None else []

router = APIRouter()
file_handler = FileHandler()
resume_parser = ResumeParser()

# Get limiter from main app (set in app.state.limiter)
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)

@router.post("/upload")
@limiter.limit("5/minute")  # Rate limit: 5 uploads per minute per IP
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """Upload and parse resume (optional authentication)

    Rate limited to 5 uploads per minute per IP address to prevent abuse.
    """

    try:
        logger.info("=== UPLOAD START ===")
        logger.info(f"Received file: {file.filename}, Content-Type: {file.content_type}, Size: {file.size if hasattr(file, 'size') else 'unknown'}")

        # Save file
        logger.info("Step 1: Saving file...")
        try:
            file_info = await file_handler.save_upload(file, category="resumes")
            logger.info(f"File saved successfully: {file_info['file_path']}")
        except Exception as e:
            logger.error(f"File save failed: {type(e).__name__}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")

        # Parse resume
        logger.info("Step 2: Parsing resume...")
        try:
            parsed_data = resume_parser.parse_file(file_info['file_path'])
            logger.info(f"Resume parsed: {len(parsed_data.get('skills', []))} skills, {len(parsed_data.get('experience', []))} jobs")
        except Exception as e:
            logger.error(f"Parsing failed: {type(e).__name__}: {str(e)}", exc_info=True)
            # Cleanup file if parsing fails
            file_handler.delete_file(file_info['file_path'])
            raise HTTPException(status_code=500, detail=f"Resume parsing failed: {str(e)}")

        # Save to database
        logger.info("Step 3: Saving to database...")
        try:
            resume = BaseResume(
                user_id=current_user.id if current_user else None,
                filename=file_info['filename'],
                file_path=file_info['file_path'],
                file_signature=file_info.get('signature', ''),  # HMAC signature for integrity
                candidate_name=parsed_data.get('candidate_name', ''),
                candidate_email=parsed_data.get('candidate_email', ''),
                candidate_phone=parsed_data.get('candidate_phone', ''),
                candidate_location=parsed_data.get('candidate_location', ''),
                candidate_linkedin=parsed_data.get('candidate_linkedin', ''),
                summary=parsed_data.get('summary', ''),
                skills=json.dumps(parsed_data.get('skills', [])),
                experience=json.dumps(parsed_data.get('experience', [])),
                education=parsed_data.get('education', ''),
                certifications=parsed_data.get('certifications', '')
            )

            db.add(resume)
            await db.commit()
            await db.refresh(resume)

            logger.info(f"Resume saved to database with ID: {resume.id}")
        except Exception as e:
            logger.error(f"Database save failed: {type(e).__name__}: {str(e)}", exc_info=True)
            # Cleanup file if database save fails
            file_handler.delete_file(file_info['file_path'])
            raise HTTPException(status_code=500, detail=f"Database save failed: {str(e)}")

        logger.info("=== UPLOAD SUCCESS ===")

        # Check for parsing warnings
        response = {
            "success": True,
            "resume_id": resume.id,
            "filename": resume.filename,
            "parsed_data": parsed_data
        }

        # Include parsing warnings at top level if present
        parsing_warnings = parsed_data.get('parsing_warnings', [])
        if parsing_warnings:
            response['warnings'] = parsing_warnings
            response['parsing_method'] = parsed_data.get('parsing_method', 'unknown')
            logger.warning(f"Parsing warnings detected: {len(parsing_warnings)} warnings")
            for warning in parsing_warnings:
                logger.warning(f"  - {warning}")

        return response

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch any unexpected errors
        logger.critical(f"UNEXPECTED ERROR in upload_resume: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.get("/list")
async def list_resumes(
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """List resumes (authentication optional, excludes deleted resumes)"""
    # If authenticated, show only user's resumes; otherwise show all non-deleted resumes
    query = select(BaseResume).where(BaseResume.is_deleted == False)

    if current_user:
        query = query.where(BaseResume.user_id == current_user.id)

    result = await db.execute(query.order_by(BaseResume.uploaded_at.desc()))

    resumes = result.scalars().all()

    return {
        "resumes": [
            {
                "id": r.id,
                "filename": r.filename,
                "summary": r.summary[:200] + "..." if len(r.summary) > 200 else r.summary,
                "skills_count": len(safe_json_loads(r.skills, [])),
                "uploaded_at": r.uploaded_at.isoformat()
            }
            for r in resumes
        ]
    }

@router.get("/{resume_id}")
async def get_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """Get resume details (authentication optional, excludes deleted resumes)"""
    result = await db.execute(select(BaseResume).where(BaseResume.id == resume_id))
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Check if resume is deleted
    if resume.is_deleted:
        raise HTTPException(status_code=404, detail="Resume has been deleted")

    # Ownership verification (only if both have user_id)
    if current_user and resume.user_id and resume.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied: You don't own this resume")

    return {
        "id": resume.id,
        "filename": resume.filename,
        "candidate_name": resume.candidate_name,
        "candidate_email": resume.candidate_email,
        "candidate_phone": resume.candidate_phone,
        "candidate_location": resume.candidate_location,
        "candidate_linkedin": resume.candidate_linkedin,
        "summary": resume.summary,
        "skills": safe_json_loads(resume.skills, []),
        "experience": safe_json_loads(resume.experience, []),
        "education": resume.education,
        "certifications": resume.certifications,
        "uploaded_at": resume.uploaded_at.isoformat()
    }

@router.post("/{resume_id}/delete")
async def delete_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """Delete resume and all associated tailored resumes and files (requires ownership)"""
    from app.models.resume import TailoredResume

    result = await db.execute(select(BaseResume).where(BaseResume.id == resume_id))
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Check if already deleted
    if resume.is_deleted:
        raise HTTPException(status_code=400, detail="Resume is already deleted")

    # If authenticated, validate ownership
    if current_user and resume.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't have permission to delete this resume")

    # If resume has a user_id but no current_user, require auth
    if resume.user_id and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required to delete this resume")

    logger.info(f"=== DELETING RESUME ID {resume_id} ===")
    logger.info(f"Base resume file: {resume.file_path}")

    # Step 1: Find and delete all tailored resume files
    tailored_result = await db.execute(
        select(TailoredResume).where(TailoredResume.base_resume_id == resume_id)
    )
    tailored_resumes = tailored_result.scalars().all()

    deleted_files = []
    for tailored in tailored_resumes:
        # Delete DOCX file if exists
        if tailored.docx_path:
            if file_handler.delete_file(tailored.docx_path):
                deleted_files.append(tailored.docx_path)
                logger.debug(f"Deleted tailored DOCX: {tailored.docx_path}")
            else:
                logger.warning(f"Failed to delete {tailored.docx_path}")

        # Delete PDF file if exists
        if tailored.pdf_path:
            if file_handler.delete_file(tailored.pdf_path):
                deleted_files.append(tailored.pdf_path)
                logger.debug(f"Deleted tailored PDF: {tailored.pdf_path}")
            else:
                logger.warning(f"Failed to delete {tailored.pdf_path}")

    logger.info(f"Deleted {len(deleted_files)} tailored resume files")

    # Step 2: Delete base resume file from disk
    if file_handler.delete_file(resume.file_path):
        logger.info(f"Deleted base resume file: {resume.file_path}")
    else:
        logger.warning(f"Failed to delete base resume: {resume.file_path}")

    # Step 3: Mark as deleted in database (soft delete with audit trail)
    from datetime import datetime
    resume.is_deleted = True
    resume.deleted_at = datetime.utcnow()
    resume.deleted_by = current_user.id if current_user else None

    # Mark all tailored resumes as deleted too
    for tailored in tailored_resumes:
        tailored.is_deleted = True
        tailored.deleted_at = datetime.utcnow()
        tailored.deleted_by = current_user.id if current_user else None

    db.add(resume)
    for tailored in tailored_resumes:
        db.add(tailored)
    await db.commit()

    # Audit log
    logger.info(f"=== RESUME SOFT-DELETED ===")
    logger.info(f"Deleted by: User ID {current_user.id if current_user else 'Anonymous'}")
    logger.info(f"Deleted at: {resume.deleted_at.isoformat()}")
    logger.info(f"Base resume ID: {resume.id}, Tailored resumes: {len(tailored_resumes)}")

    return {
        "success": True,
        "message": f"Resume and {len(tailored_resumes)} tailored versions deleted",
        "deleted_files": len(deleted_files) + 1,
        "audit": {
            "deleted_by": current_user.id if current_user else None,
            "deleted_at": resume.deleted_at.isoformat(),
            "resume_id": resume.id,
            "tailored_count": len(tailored_resumes)
        }
    }
