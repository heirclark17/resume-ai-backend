from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.models.interview_prep import InterviewPrep
from app.models.resume import TailoredResume, BaseResume
from app.models.job import Job
from app.models.company import CompanyResearch
from app.services.openai_interview_prep import OpenAIInterviewPrep
from app.services.company_research_service import CompanyResearchService
from app.services.news_aggregator_service import NewsAggregatorService
from app.services.interview_questions_scraper import InterviewQuestionsScraperService
from datetime import datetime
import json

router = APIRouter(prefix="/api/interview-prep", tags=["interview_prep"])

@router.post("/generate/{tailored_resume_id}")
async def generate_interview_prep(
    tailored_resume_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate interview prep for a tailored resume.

    This endpoint:
    1. Fetches the tailored resume and associated job + company research
    2. Calls OpenAI to generate structured interview prep data
    3. Stores the result in the database
    4. Returns the interview prep data
    """

    # Fetch tailored resume
    result = await db.execute(
        select(TailoredResume).where(
            TailoredResume.id == tailored_resume_id,
            TailoredResume.is_deleted == False
        )
    )
    tailored_resume = result.scalar_one_or_none()

    if not tailored_resume:
        raise HTTPException(status_code=404, detail="Tailored resume not found")

    # Fetch associated job
    result = await db.execute(
        select(Job).where(Job.id == tailored_resume.job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Fetch company research
    result = await db.execute(
        select(CompanyResearch).where(CompanyResearch.job_id == job.id)
    )
    company_research = result.scalar_one_or_none()

    if not company_research:
        raise HTTPException(
            status_code=404,
            detail="Company research not found. Please generate a tailored resume first."
        )

    # Check if interview prep already exists
    result = await db.execute(
        select(InterviewPrep).where(
            InterviewPrep.tailored_resume_id == tailored_resume_id,
            InterviewPrep.is_deleted == False
        )
    )
    existing_prep = result.scalar_one_or_none()

    if existing_prep:
        # Return existing prep
        print(f"✓ Returning existing interview prep for tailored resume {tailored_resume_id}")
        return {
            "success": True,
            "interview_prep_id": existing_prep.id,
            "prep_data": existing_prep.prep_data,
            "created_at": existing_prep.created_at.isoformat(),
            "cached": True
        }

    # Generate new interview prep using OpenAI
    try:
        ai_service = OpenAIInterviewPrep()

        # Build job description text
        job_description = f"""
Job Title: {job.title}
Company: {job.company}
Location: {job.location or 'Not specified'}
Posted: {job.posted_date or 'Unknown'}
Salary: {job.salary or 'Not specified'}

Job Description:
{job.description or 'No description available'}

Requirements:
{job.requirements or 'No requirements listed'}
"""

        # Build company research dict
        company_data = {
            'industry': company_research.industry or 'Unknown',
            'mission_values': company_research.mission_values or '',
            'initiatives': company_research.initiatives or '',
            'team_culture': company_research.team_culture or '',
            'compliance': company_research.compliance or '',
            'tech_stack': company_research.tech_stack or '',
            'sources': company_research.sources or []
        }

        print(f"Generating interview prep for job: {job.company} - {job.title}")
        prep_data = await ai_service.generate_interview_prep(
            job_description=job_description,
            company_research=company_data
        )

        # Save to database
        interview_prep = InterviewPrep(
            tailored_resume_id=tailored_resume_id,
            prep_data=prep_data,
            created_at=datetime.utcnow()
        )

        db.add(interview_prep)
        await db.commit()
        await db.refresh(interview_prep)

        print(f"✓ Interview prep generated and saved with ID {interview_prep.id}")

        return {
            "success": True,
            "interview_prep_id": interview_prep.id,
            "prep_data": prep_data,
            "created_at": interview_prep.created_at.isoformat(),
            "cached": False
        }

    except Exception as e:
        print(f"Failed to generate interview prep: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate interview prep: {str(e)}"
        )


@router.get("/{tailored_resume_id}")
async def get_interview_prep(
    tailored_resume_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get existing interview prep for a tailored resume.
    Returns 404 if no prep exists yet.
    """

    result = await db.execute(
        select(InterviewPrep).where(
            InterviewPrep.tailored_resume_id == tailored_resume_id,
            InterviewPrep.is_deleted == False
        )
    )
    interview_prep = result.scalar_one_or_none()

    if not interview_prep:
        raise HTTPException(
            status_code=404,
            detail="Interview prep not found. Generate it first using POST /generate/{tailored_resume_id}"
        )

    return {
        "success": True,
        "interview_prep_id": interview_prep.id,
        "prep_data": interview_prep.prep_data,
        "created_at": interview_prep.created_at.isoformat()
    }


@router.delete("/{interview_prep_id}")
async def delete_interview_prep(
    interview_prep_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Soft delete an interview prep record.
    """

    result = await db.execute(
        select(InterviewPrep).where(InterviewPrep.id == interview_prep_id)
    )
    interview_prep = result.scalar_one_or_none()

    if not interview_prep:
        raise HTTPException(status_code=404, detail="Interview prep not found")

    # Soft delete
    interview_prep.is_deleted = True
    interview_prep.deleted_at = datetime.utcnow()

    await db.commit()

    return {
        "success": True,
        "message": "Interview prep deleted successfully"
    }


@router.get("/list")
async def list_interview_preps(
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    List all interview preps for the current user (non-deleted).
    Returns basic metadata + company/job info for each prep.
    """

    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    # Fetch all interview preps for this user via TailoredResume relationship
    result = await db.execute(
        select(InterviewPrep, TailoredResume, Job)
        .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
        .join(Job, TailoredResume.job_id == Job.id)
        .where(
            and_(
                TailoredResume.session_user_id == x_user_id,
                InterviewPrep.is_deleted == False,
                TailoredResume.is_deleted == False
            )
        )
        .order_by(InterviewPrep.created_at.desc())
    )

    rows = result.all()

    prep_list = []
    for interview_prep, tailored_resume, job in rows:
        # Extract key info from prep_data
        prep_data = interview_prep.prep_data
        company_name = prep_data.get("company_profile", {}).get("name", job.company)
        job_title = prep_data.get("role_analysis", {}).get("job_title", job.title)

        prep_list.append({
            "id": interview_prep.id,
            "tailored_resume_id": tailored_resume.id,
            "company_name": company_name,
            "job_title": job_title,
            "job_location": job.location,
            "created_at": interview_prep.created_at.isoformat(),
            "updated_at": interview_prep.updated_at.isoformat() if interview_prep.updated_at else None
        })

    return {
        "success": True,
        "count": len(prep_list),
        "interview_preps": prep_list
    }


class STARStoryRequest(BaseModel):
    tailored_resume_id: int
    experience_indices: List[int]  # Indices from resume experience array
    story_theme: str  # e.g., "Handling ambiguity", "Delivering under pressure"
    company_context: Optional[str] = None


@router.post("/generate-star-story")
async def generate_star_story(
    request: STARStoryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a detailed STAR story from selected resume experiences.

    This combines the user's actual experiences with AI to create
    a compelling interview story tailored to the company/role.
    """
    try:
        # Fetch tailored resume
        result = await db.execute(
            select(TailoredResume).where(
                TailoredResume.id == request.tailored_resume_id,
                TailoredResume.is_deleted == False
            )
        )
        tailored_resume = result.scalar_one_or_none()

        if not tailored_resume:
            raise HTTPException(status_code=404, detail="Tailored resume not found")

        # Fetch base resume to get original experiences
        result = await db.execute(
            select(BaseResume).where(BaseResume.id == tailored_resume.base_resume_id)
        )
        base_resume = result.scalar_one_or_none()

        if not base_resume:
            raise HTTPException(status_code=404, detail="Base resume not found")

        # Parse experiences
        try:
            experiences = json.loads(base_resume.experience) if isinstance(base_resume.experience, str) else base_resume.experience
        except:
            experiences = []

        # Get selected experiences
        selected_experiences = []
        for idx in request.experience_indices:
            if 0 <= idx < len(experiences):
                selected_experiences.append(experiences[idx])

        if not selected_experiences:
            raise HTTPException(status_code=400, detail="No valid experiences selected")

        # Fetch job context
        result = await db.execute(
            select(Job).where(Job.id == tailored_resume.job_id)
        )
        job = result.scalar_one_or_none()

        company_context = request.company_context or (f"{job.company} - {job.title}" if job else "")

        # Generate STAR story using OpenAI
        ai_service = OpenAIInterviewPrep()

        # Build prompt for STAR story generation
        experiences_text = "\n\n".join([
            f"Experience {i+1}:\nRole: {exp.get('header', exp.get('title', 'Position'))}\n" +
            "Achievements:\n" + "\n".join([f"- {bullet}" for bullet in exp.get('bullets', [])])
            for i, exp in enumerate(selected_experiences)
        ])

        prompt = f"""Generate a detailed STAR (Situation, Task, Action, Result) interview story based on these actual experiences:

{experiences_text}

Story Theme: {request.story_theme}
Company Context: {company_context}

Create a compelling, authentic story that:
1. Combines elements from the provided experiences naturally
2. Addresses the theme "{request.story_theme}"
3. Shows relevance to {company_context}
4. Includes specific metrics and outcomes
5. Demonstrates leadership and impact

Format as JSON with this structure:
{{
  "title": "Brief story title (5-8 words)",
  "situation": "2-3 sentences setting the context",
  "task": "1-2 sentences describing what needed to be done",
  "action": "3-4 sentences detailing specific actions taken",
  "result": "2-3 sentences with quantifiable outcomes",
  "key_themes": ["theme1", "theme2", "theme3"],
  "talking_points": ["point1", "point2", "point3"]
}}"""

        # Use OpenAI to generate the story
        import openai
        from app.config import get_settings
        settings = get_settings()

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are an expert career coach helping candidates prepare compelling interview stories. Generate authentic, detailed STAR stories based on real experiences."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        story_data = json.loads(response.choices[0].message.content)

        return {
            "success": True,
            "story": story_data,
            "experiences_used": len(selected_experiences)
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to generate STAR story: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate STAR story: {str(e)}"
        )


class CompanyResearchRequest(BaseModel):
    company_name: str
    industry: Optional[str] = None
    job_title: Optional[str] = None


@router.post("/company-research")
async def get_company_research(request: CompanyResearchRequest):
    """
    Fetch real company strategies and initiatives from multiple sources.

    Sources:
    - Company press releases and newsroom
    - Investor relations and annual reports
    - Company blogs and engineering blogs
    - Perplexity research with citations

    Returns strategic initiatives, recent developments, technology focus with source URLs.
    """
    try:
        service = CompanyResearchService()

        research_data = await service.research_company_strategies(
            company_name=request.company_name,
            industry=request.industry,
            job_title=request.job_title
        )

        return {
            "success": True,
            "data": research_data
        }

    except Exception as e:
        print(f"Failed to fetch company research: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch company research: {str(e)}"
        )


class NewsAggregationRequest(BaseModel):
    company_name: str
    industry: Optional[str] = None
    job_title: Optional[str] = None
    days_back: int = 90


@router.post("/company-news")
async def get_company_news(request: NewsAggregationRequest):
    """
    Aggregate recent company news from multiple sources.

    Sources:
    - Company newsroom and blog
    - Major news outlets (Bloomberg, Reuters, TechCrunch, etc.)
    - Industry publications
    - Perplexity search with date filtering

    Returns news articles with:
    - Headlines and summaries
    - Publication dates and sources
    - Source URLs for verification
    - Relevance scores based on job role
    - Impact summaries showing why news matters for the role
    """
    try:
        service = NewsAggregatorService()

        news_data = await service.aggregate_company_news(
            company_name=request.company_name,
            industry=request.industry,
            job_title=request.job_title,
            days_back=request.days_back
        )

        return {
            "success": True,
            "data": news_data
        }

    except Exception as e:
        print(f"Failed to fetch company news: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch company news: {str(e)}"
        )


class InterviewQuestionsRequest(BaseModel):
    company_name: str
    job_title: Optional[str] = None
    role_category: Optional[str] = None
    max_questions: int = 30


@router.post("/interview-questions")
async def get_interview_questions(request: InterviewQuestionsRequest):
    """
    Scrape real interview questions from multiple sources.

    Sources:
    - Glassdoor interview experiences
    - Reddit (r/cscareerquestions, r/ExperiencedDevs, r/cybersecurity)
    - Blind company discussions
    - Interview prep sites

    Returns questions with:
    - Question text and type (behavioral, technical, situational)
    - Difficulty ratings (easy, medium, hard)
    - Frequency indicators (how often asked)
    - Source URLs for verification
    - Interview tips and context from candidates
    - Relevance scores based on job role

    Note: Respects robots.txt and implements rate limiting for ethical scraping.
    """
    try:
        service = InterviewQuestionsScraperService()

        questions_data = await service.scrape_interview_questions(
            company_name=request.company_name,
            job_title=request.job_title,
            role_category=request.role_category,
            max_questions=request.max_questions
        )

        return {
            "success": True,
            "data": questions_data
        }

    except Exception as e:
        print(f"Failed to fetch interview questions: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch interview questions: {str(e)}"
        )
