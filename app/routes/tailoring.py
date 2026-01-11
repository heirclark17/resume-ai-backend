from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from backend.app.database import get_db
from backend.app.models.resume import BaseResume, TailoredResume
from backend.app.models.job import Job
from backend.app.models.company import CompanyResearch
from backend.app.services.perplexity_client import PerplexityClient
from backend.app.services.claude_tailor import ClaudeTailor
from backend.app.services.docx_generator import DOCXGenerator
from backend.app.config import get_settings
import json
from datetime import datetime

settings = get_settings()

router = APIRouter()

class TailorRequest(BaseModel):
    base_resume_id: int
    job_url: str = None
    company: str = None
    job_title: str = None
    job_description: str = None

@router.post("/tailor")
async def tailor_resume(
    request: TailorRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Tailor a resume for a specific job

    Process:
    1. Fetch base resume from database
    2. Research company with Perplexity
    3. Tailor resume with Claude
    4. Generate DOCX file
    5. Save to database
    """

    try:
        print(f"=== TAILORING START ===")
        print(f"TEST MODE: {settings.test_mode} (type: {type(settings.test_mode).__name__})")
        print(f"Base Resume ID: {request.base_resume_id}")
        print(f"Company: {request.company}")
        print(f"Job Title: {request.job_title}")
        print(f"Job URL: {request.job_url}")

        # Step 1: Fetch base resume
        print("Step 1: Fetching base resume...")
        result = await db.execute(
            select(BaseResume).where(BaseResume.id == request.base_resume_id)
        )
        base_resume = result.scalar_one_or_none()

        if not base_resume:
            raise HTTPException(status_code=404, detail="Base resume not found")

        # Parse base resume data
        base_resume_data = {
            "summary": base_resume.summary or "",
            "skills": json.loads(base_resume.skills) if base_resume.skills else [],
            "experience": json.loads(base_resume.experience) if base_resume.experience else [],
            "education": base_resume.education or "",
            "certifications": base_resume.certifications or ""
        }

        print(f"Base resume loaded: {base_resume.filename}")

        # Step 2: Create or fetch job record
        print("Step 2: Processing job details...")
        job = None

        if request.job_url:
            # Check if job already exists
            result = await db.execute(
                select(Job).where(Job.url == request.job_url)
            )
            job = result.scalar_one_or_none()

        if not job:
            # Create new job record
            job = Job(
                url=request.job_url or f"manual_{datetime.utcnow().timestamp()}",
                company=request.company or "Unknown Company",
                title=request.job_title or "Unknown Position",
                is_active=True
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)

        print(f"Job record: {job.company} - {job.title}")

        # Step 3: Research company with Perplexity
        print("Step 3: Researching company with Perplexity...")
        perplexity = PerplexityClient()

        try:
            company_research = await perplexity.research_company(
                company_name=job.company,
                job_title=job.title
            )
            print(f"Company research completed: {len(company_research.get('research', ''))} characters")
        except Exception as e:
            print(f"Perplexity research failed: {e}")
            company_research = {
                "company": job.company,
                "research": "Unable to perform company research at this time."
            }

        # Step 4: Tailor resume with Claude
        print("Step 4: Tailoring resume with Claude...")
        claude = ClaudeTailor()

        job_details = {
            "company": job.company,
            "title": job.title,
            "url": job.url,
            "description": request.job_description or ""
        }

        try:
            tailored_content = await claude.tailor_resume(
                base_resume=base_resume_data,
                company_research=company_research,
                job_details=job_details
            )
            print(f"Resume tailored: {len(tailored_content.get('competencies', []))} competencies")
        except Exception as e:
            print(f"Claude tailoring failed: {e}")
            raise HTTPException(status_code=500, detail=f"Resume tailoring failed: {str(e)}")

        # Step 5: Generate DOCX
        print("Step 5: Generating DOCX file...")
        docx_gen = DOCXGenerator()

        # Extract candidate info from base resume
        candidate_name = "Justin Washington"  # TODO: Extract from resume or settings
        contact_info = {
            "email": "justinwashington@gmail.com",
            "phone": "(555) 123-4567",
            "location": "Houston, TX",
            "linkedin": "linkedin.com/in/justintwashington"
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{job.company.replace(' ', '_')}_{job.title.replace(' ', '_')}.docx"

        try:
            docx_path = docx_gen.create_tailored_resume(
                candidate_name=candidate_name,
                contact_info=contact_info,
                job_details=job_details,
                tailored_content=tailored_content,
                base_resume_data=base_resume_data,
                output_filename=filename
            )
            print(f"DOCX created: {docx_path}")
        except Exception as e:
            print(f"DOCX generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Document generation failed: {str(e)}")

        # Step 6: Save tailored resume to database
        print("Step 6: Saving to database...")
        tailored_resume = TailoredResume(
            base_resume_id=base_resume.id,
            job_id=job.id,
            tailored_summary=tailored_content.get('summary', ''),
            tailored_skills=json.dumps(tailored_content.get('competencies', [])),
            tailored_experience=json.dumps(tailored_content.get('experience', [])),
            alignment_statement=tailored_content.get('alignment_statement', ''),
            docx_path=docx_path,
            quality_score=85.0,  # TODO: Calculate actual quality score
            changes_count=len(tailored_content.get('competencies', []))
        )

        db.add(tailored_resume)
        await db.commit()
        await db.refresh(tailored_resume)

        print(f"=== TAILORING COMPLETE ===")
        print(f"Tailored Resume ID: {tailored_resume.id}")

        return {
            "success": True,
            "tailored_resume_id": tailored_resume.id,
            "job_id": job.id,
            "company": job.company,
            "title": job.title,
            "docx_path": docx_path,
            "summary": tailored_content.get('summary', ''),
            "competencies": tailored_content.get('competencies', []),
            "alignment_statement": tailored_content.get('alignment_statement', '')
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"UNEXPECTED ERROR in tailoring: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Tailoring failed: {str(e)}")


@router.get("/tailored/{tailored_id}")
async def get_tailored_resume(tailored_id: int, db: AsyncSession = Depends(get_db)):
    """Get a tailored resume by ID"""
    result = await db.execute(
        select(TailoredResume).where(TailoredResume.id == tailored_id)
    )
    tailored = result.scalar_one_or_none()

    if not tailored:
        raise HTTPException(status_code=404, detail="Tailored resume not found")

    return {
        "id": tailored.id,
        "base_resume_id": tailored.base_resume_id,
        "job_id": tailored.job_id,
        "summary": tailored.tailored_summary,
        "competencies": json.loads(tailored.tailored_skills) if tailored.tailored_skills else [],
        "experience": json.loads(tailored.tailored_experience) if tailored.tailored_experience else [],
        "alignment_statement": tailored.alignment_statement,
        "docx_path": tailored.docx_path,
        "quality_score": tailored.quality_score,
        "created_at": tailored.created_at.isoformat()
    }


@router.get("/list")
async def list_tailored_resumes(db: AsyncSession = Depends(get_db)):
    """List all tailored resumes"""
    result = await db.execute(
        select(TailoredResume).order_by(TailoredResume.created_at.desc())
    )
    tailored_resumes = result.scalars().all()

    return {
        "tailored_resumes": [
            {
                "id": tr.id,
                "base_resume_id": tr.base_resume_id,
                "job_id": tr.job_id,
                "summary": tr.tailored_summary[:200] + "..." if tr.tailored_summary and len(tr.tailored_summary) > 200 else tr.tailored_summary,
                "docx_path": tr.docx_path,
                "quality_score": tr.quality_score,
                "created_at": tr.created_at.isoformat()
            }
            for tr in tailored_resumes
        ]
    }
