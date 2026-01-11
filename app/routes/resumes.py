from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.resume import BaseResume
from app.models.user import User
from app.middleware.auth import get_current_user, get_current_user_optional
from app.services.resume_parser import ResumeParser
from app.utils.file_handler import FileHandler
import json

router = APIRouter()
file_handler = FileHandler()
resume_parser = ResumeParser()

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """Upload and parse resume (optional authentication)"""

    try:
        print(f"=== UPLOAD START ===")
        print(f"Received file: {file.filename}")
        print(f"Content type: {file.content_type}")
        print(f"File size: {file.size if hasattr(file, 'size') else 'unknown'}")

        # Save file
        print(f"Step 1: Saving file...")
        try:
            file_info = await file_handler.save_upload(file, category="resumes")
            print(f"File saved successfully: {file_info['file_path']}")
        except Exception as e:
            print(f"ERROR in file saving: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")

        # Parse resume
        print(f"Step 2: Parsing resume...")
        try:
            parsed_data = resume_parser.parse_file(file_info['file_path'])
            print(f"Resume parsed: {len(parsed_data.get('skills', []))} skills, {len(parsed_data.get('experience', []))} jobs")
        except Exception as e:
            print(f"ERROR in parsing: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Cleanup file if parsing fails
            file_handler.delete_file(file_info['file_path'])
            raise HTTPException(status_code=500, detail=f"Resume parsing failed: {str(e)}")

        # Save to database
        print(f"Step 3: Saving to database...")
        try:
            resume = BaseResume(
                user_id=current_user.id if current_user else None,
                filename=file_info['filename'],
                file_path=file_info['file_path'],
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

            print(f"Resume saved to database with ID: {resume.id}")
        except Exception as e:
            print(f"ERROR in database save: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Cleanup file if database save fails
            file_handler.delete_file(file_info['file_path'])
            raise HTTPException(status_code=500, detail=f"Database save failed: {str(e)}")

        print(f"=== UPLOAD SUCCESS ===")
        return {
            "success": True,
            "resume_id": resume.id,
            "filename": resume.filename,
            "parsed_data": parsed_data
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch any unexpected errors
        print(f"UNEXPECTED ERROR in upload_resume: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.get("/list")
async def list_resumes(
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """List resumes (optionally filtered by user)"""
    # If authenticated, only show user's resumes
    if current_user:
        result = await db.execute(
            select(BaseResume)
            .where(BaseResume.user_id == current_user.id)
            .order_by(BaseResume.uploaded_at.desc())
        )
    else:
        # No auth - show all resumes (backward compatibility)
        result = await db.execute(select(BaseResume).order_by(BaseResume.uploaded_at.desc()))

    resumes = result.scalars().all()

    return {
        "resumes": [
            {
                "id": r.id,
                "filename": r.filename,
                "summary": r.summary[:200] + "..." if len(r.summary) > 200 else r.summary,
                "skills_count": len(json.loads(r.skills)) if r.skills else 0,
                "uploaded_at": r.uploaded_at.isoformat()
            }
            for r in resumes
        ]
    }

@router.get("/{resume_id}")
async def get_resume(resume_id: int, db: AsyncSession = Depends(get_db)):
    """Get resume details"""
    result = await db.execute(select(BaseResume).where(BaseResume.id == resume_id))
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    return {
        "id": resume.id,
        "filename": resume.filename,
        "candidate_name": resume.candidate_name,
        "candidate_email": resume.candidate_email,
        "candidate_phone": resume.candidate_phone,
        "candidate_location": resume.candidate_location,
        "candidate_linkedin": resume.candidate_linkedin,
        "summary": resume.summary,
        "skills": json.loads(resume.skills) if resume.skills else [],
        "experience": json.loads(resume.experience) if resume.experience else [],
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

    # If authenticated, validate ownership
    if current_user and resume.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't have permission to delete this resume")

    # If resume has a user_id but no current_user, require auth
    if resume.user_id and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required to delete this resume")

    print(f"=== DELETING RESUME ID {resume_id} ===")
    print(f"Base resume file: {resume.file_path}")

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
                print(f"Deleted tailored DOCX: {tailored.docx_path}")
            else:
                print(f"WARNING: Failed to delete {tailored.docx_path}")

        # Delete PDF file if exists
        if tailored.pdf_path:
            if file_handler.delete_file(tailored.pdf_path):
                deleted_files.append(tailored.pdf_path)
                print(f"Deleted tailored PDF: {tailored.pdf_path}")
            else:
                print(f"WARNING: Failed to delete {tailored.pdf_path}")

    print(f"Deleted {len(deleted_files)} tailored resume files")

    # Step 2: Delete base resume file from disk
    if file_handler.delete_file(resume.file_path):
        print(f"Deleted base resume file: {resume.file_path}")
    else:
        print(f"WARNING: Failed to delete base resume: {resume.file_path}")

    # Step 3: Delete from database (CASCADE will handle tailored_resumes)
    await db.delete(resume)
    await db.commit()

    print(f"=== RESUME DELETED ===")

    return {
        "success": True,
        "message": f"Resume and {len(tailored_resumes)} tailored versions deleted",
        "deleted_files": len(deleted_files) + 1
    }
