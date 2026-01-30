from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.resume import BaseResume
from app.models.user import User
from app.middleware.auth import get_current_user, get_current_user_optional, get_user_id
from app.services.resume_parser import ResumeParser
from app.utils.file_handler import FileHandler
from app.utils.logger import logger
from pydantic import BaseModel
import json
import os
from openai import AsyncOpenAI


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

# Pydantic models for request validation
class AnalyzeResumeRequest(BaseModel):
    resume_id: int

@router.post("/upload")
@limiter.limit("5/minute")  # Rate limit: 5 uploads per minute per IP
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Upload and parse resume (requires session user ID)

    Rate limited to 5 uploads per minute per IP address to prevent abuse.
    Resumes are isolated by session user ID.
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
            # Handle education field - AI sometimes returns list instead of string
            education_data = parsed_data.get('education', '')
            if isinstance(education_data, list):
                education_str = '\n'.join(education_data)
                logger.info(f"Converted education list to string: {len(education_data)} entries")
            else:
                education_str = education_data

            # Handle certifications field - same issue
            cert_data = parsed_data.get('certifications', '')
            if isinstance(cert_data, list):
                cert_str = '\n'.join(cert_data)
                logger.info(f"Converted certifications list to string: {len(cert_data)} entries")
            else:
                cert_str = cert_data

            resume = BaseResume(
                session_user_id=user_id,  # Store session user ID for data isolation
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
                education=education_str,
                certifications=cert_str
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
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    """List resumes (requires session user ID, excludes deleted resumes)"""
    # Filter by session user ID for data isolation
    query = select(BaseResume).where(
        BaseResume.is_deleted == False,
        BaseResume.session_user_id == user_id
    )

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
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Get resume details (requires session user ID, excludes deleted resumes)"""
    result = await db.execute(select(BaseResume).where(BaseResume.id == resume_id))
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Check if resume is deleted
    if resume.is_deleted:
        raise HTTPException(status_code=404, detail="Resume has been deleted")

    # Ownership verification via session user ID
    if resume.session_user_id != user_id:
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
    user_id: str = Depends(get_user_id),
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

    # Validate ownership via session user ID
    if resume.session_user_id != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to delete this resume")

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
    resume.deleted_by = None  # Session-based users don't have user_id for audit

    # Mark all tailored resumes as deleted too
    for tailored in tailored_resumes:
        tailored.is_deleted = True
        tailored.deleted_at = datetime.utcnow()
        tailored.deleted_by = None  # Session-based users don't have user_id for audit

    db.add(resume)
    for tailored in tailored_resumes:
        db.add(tailored)
    await db.commit()

    # Audit log
    logger.info(f"=== RESUME SOFT-DELETED ===")
    logger.info(f"Deleted by: Session User ID {user_id}")
    logger.info(f"Deleted at: {resume.deleted_at.isoformat()}")
    logger.info(f"Base resume ID: {resume.id}, Tailored resumes: {len(tailored_resumes)}")

    return {
        "success": True,
        "message": f"Resume and {len(tailored_resumes)} tailored versions deleted",
        "deleted_files": len(deleted_files) + 1,
        "audit": {
            "deleted_by": None,
            "deleted_at": resume.deleted_at.isoformat(),
            "resume_id": resume.id,
            "tailored_count": len(tailored_resumes)
        }
    }

@router.post("/analyze")
@limiter.limit("10/minute")  # Rate limit: 10 analyses per minute per IP
async def analyze_resume(
    request: Request,
    analyze_request: AnalyzeResumeRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze a base resume for strengths, weaknesses, ATS compatibility, and improvement recommendations.

    This endpoint provides AI-powered analysis of resume quality, keyword optimization,
    and actionable suggestions for improvement.
    """
    try:
        # Fetch the resume
        result = await db.execute(
            select(BaseResume).where(BaseResume.id == analyze_request.resume_id)
        )
        resume = result.scalar_one_or_none()

        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")

        # Check if resume is deleted
        if resume.is_deleted:
            raise HTTPException(status_code=404, detail="Resume has been deleted")

        # Verify ownership
        if resume.session_user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied: You don't own this resume")

        # Prepare resume content for analysis
        resume_content = {
            "name": resume.candidate_name,
            "email": resume.candidate_email,
            "phone": resume.candidate_phone,
            "location": resume.candidate_location,
            "linkedin": resume.candidate_linkedin,
            "summary": resume.summary,
            "skills": safe_json_loads(resume.skills, []),
            "experience": safe_json_loads(resume.experience, []),
            "education": resume.education,
            "certifications": resume.certifications
        }

        # Initialize OpenAI client
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Construct prompt for analysis
        system_prompt = """You are an expert resume analyst and career coach with deep knowledge of:
- ATS (Applicant Tracking System) optimization
- Modern hiring practices and recruiter preferences
- Industry-specific resume best practices
- Professional branding and personal marketing
- Quantifiable achievement writing

Your task is to provide comprehensive, actionable analysis of resumes."""

        user_prompt = f"""Analyze this resume and provide detailed feedback in the following categories:

RESUME CONTENT:
Name: {resume_content['name']}
Email: {resume_content['email']}
Location: {resume_content['location']}
LinkedIn: {resume_content['linkedin']}

Professional Summary:
{resume_content['summary']}

Skills: {', '.join(resume_content['skills'])}

Experience:
{json.dumps(resume_content['experience'], indent=2)}

Education:
{resume_content['education']}

Certifications:
{resume_content['certifications']}

Provide analysis in this JSON format:
{{
  "overall_score": <number 1-100>,
  "strengths": [
    "Strength 1 with specific example from resume",
    "Strength 2 with specific example",
    "Strength 3 with specific example"
  ],
  "weaknesses": [
    "Weakness 1 with specific issue",
    "Weakness 2 with specific issue",
    "Weakness 3 with specific issue"
  ],
  "keyword_optimization": {{
    "score": <number 1-100>,
    "missing_keywords": ["keyword1", "keyword2", "keyword3"],
    "suggestions": "Detailed suggestions for improving keyword usage and placement"
  }},
  "ats_compatibility": {{
    "score": <number 1-100>,
    "issues": ["Issue 1", "Issue 2"],
    "recommendations": "Specific recommendations for ATS optimization"
  }},
  "improvement_recommendations": [
    {{
      "category": "Professional Summary",
      "priority": "high",
      "recommendation": "Specific actionable recommendation",
      "example": "Example of how to implement this"
    }},
    {{
      "category": "Experience",
      "priority": "medium",
      "recommendation": "Another specific recommendation",
      "example": "Example implementation"
    }},
    {{
      "category": "Skills",
      "priority": "high",
      "recommendation": "Skills-related recommendation",
      "example": "Example implementation"
    }}
  ]
}}

Focus on:
1. Quantifiable achievements vs. responsibilities
2. Action verbs and power words
3. Industry-relevant keywords
4. ATS-friendly formatting
5. Professional branding and personal value proposition
6. Gaps or missing critical information
7. Length and conciseness
8. Specificity and relevance"""

        # Call OpenAI API
        logger.info(f"Analyzing resume ID {analyze_request.resume_id} for user {user_id}")

        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        # Parse AI response
        analysis_text = response.choices[0].message.content
        analysis = json.loads(analysis_text)

        logger.info(f"Resume analysis completed. Overall score: {analysis.get('overall_score', 'N/A')}")

        return {
            "success": True,
            "analysis": analysis,
            "resume_id": analyze_request.resume_id,
            "filename": resume.filename
        }

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse analysis results")
    except Exception as e:
        logger.error(f"Error analyzing resume: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze resume: {str(e)}")
