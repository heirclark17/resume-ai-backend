from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import List, Optional, Dict
from app.database import get_db
from app.models.interview_prep import InterviewPrep
from app.models.resume import TailoredResume, BaseResume
from app.models.job import Job
from app.models.company import CompanyResearch
from app.services.openai_interview_prep import OpenAIInterviewPrep
from app.services.openai_common_questions import OpenAICommonQuestions
from app.services.company_research_service import CompanyResearchService
from app.services.news_aggregator_service import NewsAggregatorService
from app.services.interview_questions_scraper import InterviewQuestionsScraperService
from app.services.interview_intelligence_service import InterviewIntelligenceService
from app.services.practice_questions_service import PracticeQuestionsService
from app.services.interview_questions_generator import InterviewQuestionsGenerator
from app.models.practice_question_response import PracticeQuestionResponse
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

    # Check if interview prep already exists (including soft-deleted)
    result = await db.execute(
        select(InterviewPrep).where(
            InterviewPrep.tailored_resume_id == tailored_resume_id
        )
    )
    existing_prep = result.scalar_one_or_none()

    if existing_prep and not existing_prep.is_deleted:
        # Return existing active prep
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
            company_research=company_data,
            company_name=job.company,
            job_title=job.title
        )

        # Save to database — reactivate soft-deleted row if one exists
        if existing_prep and existing_prep.is_deleted:
            existing_prep.prep_data = prep_data
            existing_prep.is_deleted = False
            existing_prep.deleted_at = None
            existing_prep.created_at = datetime.utcnow()
            existing_prep.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(existing_prep)
            interview_prep = existing_prep
        else:
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


@router.get("/{tailored_resume_id}")
async def get_interview_prep(
    tailored_resume_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get existing interview prep for a tailored resume.
    Returns 404 if no prep exists yet.
    Includes cached AI-generated data if available.
    Validates user ownership via TailoredResume.session_user_id.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    try:
        # Join with TailoredResume to validate user ownership
        result = await db.execute(
            select(InterviewPrep, TailoredResume)
            .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
            .where(
                InterviewPrep.tailored_resume_id == tailored_resume_id,
                InterviewPrep.is_deleted == False,
                TailoredResume.session_user_id == x_user_id,
                TailoredResume.is_deleted == False
            )
        )
        row = result.first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Interview prep not found or access denied"
            )

        interview_prep = row[0]

        # Safely get created_at
        created_at_str = interview_prep.created_at.isoformat() if interview_prep.created_at else None

        # Safely build cached_data (handle missing columns gracefully)
        cached_data = {}
        try:
            cached_data = {
                "company_research": getattr(interview_prep, 'company_research_data', None),
                "strategic_news": getattr(interview_prep, 'strategic_news_data', None),
                "values_alignment": getattr(interview_prep, 'values_alignment_data', None),
                "readiness_score": getattr(interview_prep, 'readiness_score_data', None),
                "competitive_intelligence": getattr(interview_prep, 'competitive_intelligence_data', None),
                "interview_strategy": getattr(interview_prep, 'interview_strategy_data', None),
                "behavioral_technical_questions": getattr(interview_prep, 'behavioral_technical_questions_data', None),
                "common_questions": getattr(interview_prep, 'common_questions_data', None),
                "certification_recommendations": getattr(interview_prep, 'certification_recommendations_data', None),
                "user_data": getattr(interview_prep, 'user_data', None),
            }
        except Exception as cache_error:
            print(f"Warning: Could not get cached data fields: {cache_error}")
            cached_data = {}

        return {
            "success": True,
            "interview_prep_id": interview_prep.id,
            "prep_data": interview_prep.prep_data,
            "created_at": created_at_str,
            "cached_data": cached_data
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_interview_prep: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get interview prep: {str(e)}"
        )


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


class CachedDataUpdate(BaseModel):
    """Request body for updating cached AI-generated data"""
    company_research: Optional[Dict] = None
    strategic_news: Optional[Dict] = None
    values_alignment: Optional[Dict] = None
    interview_questions: Optional[Dict] = None
    company_values: Optional[Dict] = None
    behavioral_technical_questions: Optional[Dict] = None
    common_questions: Optional[Dict] = None
    certification_recommendations: Optional[Dict] = None
    user_data: Optional[Dict] = None


@router.patch("/{interview_prep_id}/cache")
async def update_cached_data(
    interview_prep_id: int,
    data: CachedDataUpdate,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Save AI-generated data to the database for permanent caching.
    This prevents regeneration on subsequent page loads.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Get interview prep with user validation
    result = await db.execute(
        select(InterviewPrep, TailoredResume)
        .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
        .where(
            InterviewPrep.id == interview_prep_id,
            InterviewPrep.is_deleted == False,
            TailoredResume.session_user_id == x_user_id
        )
    )
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Interview prep not found or access denied")

    interview_prep = row[0]

    # Update cached fields if provided
    if data.company_research is not None:
        interview_prep.company_research_data = data.company_research
    if data.strategic_news is not None:
        interview_prep.strategic_news_data = data.strategic_news
    if data.values_alignment is not None:
        interview_prep.values_alignment_data = data.values_alignment
    if data.interview_questions is not None:
        # Store in competitive_intelligence_data (repurposed) or add new column
        interview_prep.competitive_intelligence_data = data.interview_questions
    if data.company_values is not None:
        # Store in interview_strategy_data (repurposed) or add new column
        interview_prep.interview_strategy_data = data.company_values
    if data.behavioral_technical_questions is not None:
        interview_prep.behavioral_technical_questions_data = data.behavioral_technical_questions
    if data.common_questions is not None:
        interview_prep.common_questions_data = data.common_questions
    if data.certification_recommendations is not None:
        interview_prep.certification_recommendations_data = data.certification_recommendations
    if data.user_data is not None:
        # Merge user_data so partial updates work (don't overwrite entire blob)
        existing = interview_prep.user_data or {}
        existing.update(data.user_data)
        interview_prep.user_data = existing

    await db.commit()

    return {
        "success": True,
        "message": "Cached data saved successfully"
    }


# =====================================================
# Enhanced Data GET Endpoints (Cached Persistence)
# These endpoints return cached AI-generated data.
# If data doesn't exist, they generate and cache it.
# =====================================================

@router.get("/{prep_id}/readiness-score")
async def get_readiness_score(
    prep_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get cached readiness score for interview prep.
    Returns cached data if available, otherwise generates and caches it.
    """
    result = await db.execute(
        select(InterviewPrep).where(
            InterviewPrep.id == prep_id,
            InterviewPrep.is_deleted == False
        )
    )
    interview_prep = result.scalar_one_or_none()

    if not interview_prep:
        raise HTTPException(status_code=404, detail="Interview prep not found")

    # Return cached data if available
    if interview_prep.readiness_score_data:
        return {
            "success": True,
            "data": interview_prep.readiness_score_data,
            "cached": True
        }

    # Generate and cache readiness score
    try:
        service = InterviewIntelligenceService()
        readiness_data = await service.calculate_interview_readiness(
            prep_data=interview_prep.prep_data,
            sections_completed=[]  # Default empty - user hasn't marked any sections
        )

        # Cache the result
        interview_prep.readiness_score_data = readiness_data
        interview_prep.updated_at = datetime.utcnow()
        await db.commit()

        return {
            "success": True,
            "data": readiness_data,
            "cached": False
        }
    except Exception as e:
        print(f"Failed to generate readiness score: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate readiness score: {str(e)}")


@router.get("/{prep_id}/values-alignment")
async def get_values_alignment(
    prep_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get cached values alignment data for interview prep.
    """
    result = await db.execute(
        select(InterviewPrep).where(
            InterviewPrep.id == prep_id,
            InterviewPrep.is_deleted == False
        )
    )
    interview_prep = result.scalar_one_or_none()

    if not interview_prep:
        raise HTTPException(status_code=404, detail="Interview prep not found")

    if interview_prep.values_alignment_data:
        return {
            "success": True,
            "data": interview_prep.values_alignment_data,
            "cached": True
        }

    # Generate and cache
    try:
        service = InterviewIntelligenceService()
        prep_data = interview_prep.prep_data or {}
        company_data = prep_data.get('company_profile', {})
        role_analysis = prep_data.get('role_analysis', {})

        # Build stated_values in the format the service expects
        stated_values = []
        for value in company_data.get('stated_values', []):
            if isinstance(value, dict):
                stated_values.append(value)
            else:
                stated_values.append({"value": str(value), "description": ""})

        # Build candidate background from prep data
        candidate_background = json.dumps({
            "skills": role_analysis.get('must_have_skills', []),
            "experience": role_analysis.get('key_responsibilities', [])
        })

        alignment_data = await service.generate_values_alignment_scorecard(
            stated_values=stated_values,
            candidate_background=candidate_background,
            job_description=json.dumps(role_analysis),
            company_name=company_data.get('company_name', 'Unknown')
        )

        interview_prep.values_alignment_data = alignment_data
        interview_prep.updated_at = datetime.utcnow()
        await db.commit()

        return {
            "success": True,
            "data": alignment_data,
            "cached": False
        }
    except Exception as e:
        print(f"Failed to generate values alignment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate values alignment: {str(e)}")


@router.get("/{prep_id}/company-research")
async def get_company_research_for_prep(
    prep_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get cached company research data for interview prep.
    """
    result = await db.execute(
        select(InterviewPrep).where(
            InterviewPrep.id == prep_id,
            InterviewPrep.is_deleted == False
        )
    )
    interview_prep = result.scalar_one_or_none()

    if not interview_prep:
        raise HTTPException(status_code=404, detail="Interview prep not found")

    if interview_prep.company_research_data:
        return {
            "success": True,
            "data": interview_prep.company_research_data,
            "cached": True
        }

    # Return prep_data company_profile as fallback
    prep_data = interview_prep.prep_data or {}
    company_profile = prep_data.get('company_profile', {})

    return {
        "success": True,
        "data": company_profile,
        "cached": True
    }


@router.get("/{prep_id}/strategic-news")
async def get_strategic_news(
    prep_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get cached strategic news data for interview prep.
    """
    result = await db.execute(
        select(InterviewPrep).where(
            InterviewPrep.id == prep_id,
            InterviewPrep.is_deleted == False
        )
    )
    interview_prep = result.scalar_one_or_none()

    if not interview_prep:
        raise HTTPException(status_code=404, detail="Interview prep not found")

    if interview_prep.strategic_news_data:
        return {
            "success": True,
            "data": interview_prep.strategic_news_data,
            "cached": True
        }

    # Generate and cache
    try:
        prep_data = interview_prep.prep_data or {}
        company_data = prep_data.get('company_profile', {})
        company_name = company_data.get('company_name', 'Unknown')

        service = NewsAggregatorService()
        news_data = await service.get_company_news(company_name=company_name, max_articles=10)

        interview_prep.strategic_news_data = news_data
        interview_prep.updated_at = datetime.utcnow()
        await db.commit()

        return {
            "success": True,
            "data": news_data,
            "cached": False
        }
    except Exception as e:
        print(f"Failed to fetch strategic news: {str(e)}")
        return {
            "success": True,
            "data": [],
            "cached": False,
            "error": str(e)
        }


@router.get("/{prep_id}/competitive-intelligence")
async def get_competitive_intelligence(
    prep_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get cached competitive intelligence data for interview prep.
    Returns prep_data strategy_news section as competitive context.
    """
    result = await db.execute(
        select(InterviewPrep).where(
            InterviewPrep.id == prep_id,
            InterviewPrep.is_deleted == False
        )
    )
    interview_prep = result.scalar_one_or_none()

    if not interview_prep:
        raise HTTPException(status_code=404, detail="Interview prep not found")

    if interview_prep.competitive_intelligence_data:
        return {
            "success": True,
            "data": interview_prep.competitive_intelligence_data,
            "cached": True
        }

    # Extract competitive context from prep_data
    prep_data = interview_prep.prep_data or {}
    company_data = prep_data.get('company_profile', {})
    strategy_news = prep_data.get('strategy_news', {})

    intel_data = {
        "company_name": company_data.get('company_name', 'Unknown'),
        "industry": company_data.get('industry', 'Technology'),
        "strategic_initiatives": strategy_news.get('strategic_initiatives', []),
        "technology_focus": strategy_news.get('technology_focus', []),
        "recent_events": strategy_news.get('recent_events', []),
        "market_position": company_data.get('size', 'Unknown')
    }

    # Cache for future requests
    interview_prep.competitive_intelligence_data = intel_data
    interview_prep.updated_at = datetime.utcnow()
    await db.commit()

    return {
        "success": True,
        "data": intel_data,
        "cached": False
    }


@router.get("/{prep_id}/interview-strategy")
async def get_interview_strategy(
    prep_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get cached interview strategy data for interview prep.
    Derives strategy from preparation_checklist and role_analysis.
    """
    result = await db.execute(
        select(InterviewPrep).where(
            InterviewPrep.id == prep_id,
            InterviewPrep.is_deleted == False
        )
    )
    interview_prep = result.scalar_one_or_none()

    if not interview_prep:
        raise HTTPException(status_code=404, detail="Interview prep not found")

    if interview_prep.interview_strategy_data:
        return {
            "success": True,
            "data": interview_prep.interview_strategy_data,
            "cached": True
        }

    # Extract strategy from prep_data
    prep_data = interview_prep.prep_data or {}
    prep_checklist = prep_data.get('preparation_checklist', {})
    role_analysis = prep_data.get('role_analysis', {})
    questions_to_ask = prep_data.get('questions_to_ask', {})

    strategy_data = {
        "research_tasks": prep_checklist.get('research_tasks', []),
        "day_of_checklist": prep_checklist.get('day_of_checklist', []),
        "key_responsibilities": role_analysis.get('key_responsibilities', []),
        "must_have_skills": role_analysis.get('must_have_skills', []),
        "nice_to_have_skills": role_analysis.get('nice_to_have_skills', []),
        "questions_by_category": questions_to_ask,
        "preparation_focus": [
            "Research the company's recent news and strategic initiatives",
            "Prepare STAR stories for behavioral questions",
            "Review technical concepts mentioned in job description",
            "Prepare thoughtful questions to ask the interviewer"
        ]
    }

    # Cache for future requests
    interview_prep.interview_strategy_data = strategy_data
    interview_prep.updated_at = datetime.utcnow()
    await db.commit()

    return {
        "success": True,
        "data": strategy_data,
        "cached": False
    }


@router.get("/{prep_id}/executive-insights")
async def get_executive_insights(
    prep_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get cached executive insights data for interview prep.
    Derives insights from company_profile and values_culture.
    """
    result = await db.execute(
        select(InterviewPrep).where(
            InterviewPrep.id == prep_id,
            InterviewPrep.is_deleted == False
        )
    )
    interview_prep = result.scalar_one_or_none()

    if not interview_prep:
        raise HTTPException(status_code=404, detail="Interview prep not found")

    if interview_prep.executive_insights_data:
        return {
            "success": True,
            "data": interview_prep.executive_insights_data,
            "cached": True
        }

    # Extract executive insights from prep_data
    prep_data = interview_prep.prep_data or {}
    company_data = prep_data.get('company_profile', {})
    values_culture = prep_data.get('values_culture', {})
    strategy_news = prep_data.get('strategy_news', {})

    insights_data = {
        "company_overview": company_data.get('overview', ''),
        "company_size": company_data.get('size', 'Unknown'),
        "industry": company_data.get('industry', 'Technology'),
        "stated_values": values_culture.get('stated_values', []),
        "culture_indicators": values_culture.get('practical_implications', []),
        "strategic_priorities": strategy_news.get('strategic_initiatives', []),
        "technology_investments": strategy_news.get('technology_focus', []),
        "leadership_focus": [
            "Understanding company mission and values",
            "Aligning your experience with strategic priorities",
            "Demonstrating cultural fit through specific examples"
        ]
    }

    # Cache for future requests
    interview_prep.executive_insights_data = insights_data
    interview_prep.updated_at = datetime.utcnow()
    await db.commit()

    return {
        "success": True,
        "data": insights_data,
        "cached": False
    }


# =====================================================
# End Enhanced Data GET Endpoints
# =====================================================


class STARStoryRequest(BaseModel):
    tailored_resume_id: int
    experience_indices: List[int]  # Indices from resume experience array
    story_theme: str  # e.g., "Handling ambiguity", "Delivering under pressure"
    tone: Optional[str] = "professional"  # Tone: professional, conversational, confident, technical, strategic
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

        # Fetch interview prep data to get values & culture and role analysis
        result = await db.execute(
            select(InterviewPrep).where(
                InterviewPrep.tailored_resume_id == request.tailored_resume_id,
                InterviewPrep.is_deleted == False
            )
        )
        interview_prep = result.scalar_one_or_none()

        # Extract values & culture and role analysis from prep data
        values_and_culture = None
        role_analysis = None
        if interview_prep and interview_prep.prep_data:
            values_and_culture = interview_prep.prep_data.get('values_and_culture', {})
            role_analysis = interview_prep.prep_data.get('role_analysis', {})

        company_context = request.company_context or (f"{job.company} - {job.title}" if job else "")

        # Generate STAR story using OpenAI
        ai_service = OpenAIInterviewPrep()

        # Build prompt for STAR story generation
        experiences_text = "\n\n".join([
            f"Experience {i+1}:\nRole: {exp.get('header', exp.get('title', 'Position'))}\n" +
            "Achievements:\n" + "\n".join([f"- {bullet}" for bullet in exp.get('bullets', [])])
            for i, exp in enumerate(selected_experiences)
        ])

        # Build company values and role analysis context
        values_context = ""
        if values_and_culture:
            core_values = values_and_culture.get('core_values', [])
            cultural_priorities = values_and_culture.get('cultural_priorities', [])
            values_context = f"""
COMPANY VALUES & CULTURE:
Core Values: {', '.join([v.get('value', '') for v in core_values]) if core_values else 'N/A'}
Cultural Priorities: {', '.join(cultural_priorities) if cultural_priorities else 'N/A'}
"""

        role_context = ""
        if role_analysis:
            core_responsibilities = role_analysis.get('core_responsibilities', [])
            must_have_skills = role_analysis.get('must_have_skills', [])
            seniority_level = role_analysis.get('seniority_level', '')
            role_context = f"""
ROLE REQUIREMENTS:
Position Level: {seniority_level}
Core Responsibilities: {', '.join(core_responsibilities[:5]) if core_responsibilities else 'N/A'}
Must-Have Skills: {', '.join(must_have_skills[:5]) if must_have_skills else 'N/A'}
"""

        # Tone descriptions
        tone_descriptions = {
            'professional': 'Use corporate, structured, polished language. Maintain formal business communication style.',
            'conversational': 'Use natural, approachable, genuine tone. Sound authentic and relatable while remaining professional.',
            'confident': 'Use strong, decisive, leadership-focused language. Emphasize assertiveness and clear decision-making.',
            'technical': 'Use precise, methodical language with technical depth. Focus on technical details and systematic approaches.',
            'strategic': 'Use big-picture, forward-thinking, executive-level language. Emphasize vision, strategy, and long-term impact.'
        }

        tone_instruction = tone_descriptions.get(request.tone, tone_descriptions['professional'])

        prompt = f"""Generate an EXTREMELY DETAILED STAR (Situation, Task, Action, Result) interview story based on these actual experiences:

{experiences_text}

Story Theme: {request.story_theme}
Company Context: {company_context}

{values_context}
{role_context}

TONE REQUIREMENT:
{tone_instruction}

CRITICAL REQUIREMENTS - Each section must be VERY DETAILED AND EXPLICITLY TIE TO COMPANY VALUES/ROLE:


SITUATION (150-250 words):
- Set the scene with rich context and background
- Describe the company/team environment and constraints
- Explain what was happening that led to this challenge
- Include relevant stakeholders, team composition, and organizational dynamics
- Describe any external pressures, market conditions, or competitive factors
- **EXPLICITLY mention how the situation relates to the company's values/culture (if provided)**
- Paint a vivid picture that helps the interviewer understand the full context

TASK (100-150 words):
- Clearly articulate what needed to be accomplished and why
- Explain the specific goals, objectives, and success criteria
- Describe the scope and scale of the challenge
- Detail any constraints (time, budget, resources, technical)
- Explain your specific role and responsibilities
- **EXPLICITLY align the task with the role's core responsibilities (if provided)**
- **Reference the must-have skills required for this role**
- Clarify what was at stake and why it mattered to the organization

ACTION (300-500 words) - THIS IS THE MOST IMPORTANT SECTION:
- Provide a step-by-step breakdown of what YOU specifically did
- Include specific methodologies, frameworks, or tools used
- Describe how you collaborated with others and led the effort
- Explain key decisions you made and why
- Detail any obstacles encountered and how you overcame them
- Include specific examples of technical work, analysis, or problem-solving
- Describe your communication and stakeholder management approach
- **EXPLICITLY demonstrate the company's core values through your actions (e.g., if they value "innovation", show innovative thinking)**
- **EXPLICITLY demonstrate the must-have skills from the role requirements**
- Show your thought process and strategic thinking
- Mention specific technologies, platforms, or systems you worked with
- **Connect your actions to the company's cultural priorities**
- Demonstrate both technical depth and leadership/soft skills matching the seniority level

RESULT (150-250 words):
- Provide specific, quantifiable outcomes with percentages, dollar amounts, or other metrics
- Describe both immediate and long-term impact
- Include business metrics (revenue, cost savings, efficiency gains)
- Include technical metrics (performance improvements, uptime, scalability)
- Include team/organizational impact (processes improved, knowledge shared, culture enhanced)
- **EXPLICITLY show how results align with company values (e.g., if they value "customer obsession", show customer impact)**
- **Demonstrate capabilities at the required seniority level**
- Mention any recognition, awards, or follow-on opportunities that resulted
- **Explain how this experience prepares you for the specific role responsibilities listed**
- Connect outcomes to what matters most to this company and role

KEY THEMES (5-7 items):
- List the main competencies demonstrated
- **MUST include at least 2-3 themes that directly match the role's must-have skills**
- **MUST include at least 1-2 themes that reflect the company's core values**
- Example format: "Innovation (company value: Innovation)", "Risk Management (role requirement)"

TALKING POINTS (6-10 items):
- Provide specific memorable details, numbers, or phrases to emphasize when telling this story
- **Include explicit callouts to company values** (e.g., "Emphasize how this demonstrates [Company Value]")
- **Include explicit callouts to role requirements** (e.g., "This shows proficiency in [Must-Have Skill]")
- Include potential follow-up question handlers
- Suggest how to pivot this story to address other competency questions
- Provide tips for connecting this story to the specific role and company

Format as JSON with this structure:
{{
  "title": "Compelling story title (6-10 words)",
  "situation": "VERY DETAILED 150-250 word paragraph",
  "task": "VERY DETAILED 100-150 word paragraph",
  "action": "EXTREMELY DETAILED 300-500 word paragraph with step-by-step breakdown",
  "result": "VERY DETAILED 150-250 word paragraph with specific metrics",
  "key_themes": ["theme1", "theme2", "theme3", "theme4", "theme5"],
  "talking_points": ["specific point 1", "specific point 2", "specific point 3", "specific point 4", "specific point 5", "specific point 6"]
}}

Remember: This story should take 3-5 minutes to tell verbally. Make it detailed, authentic, and compelling."""

        # Use OpenAI to generate the story
        import openai
        from app.config import get_settings
        settings = get_settings()

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are an expert career coach and interview preparation specialist. Your expertise is creating EXTREMELY DETAILED, compelling STAR (Situation, Task, Action, Result) interview stories that are EXPLICITLY TAILORED to the target company's values and role requirements. Generate authentic, comprehensive stories that take 3-5 minutes to tell. Focus on rich detail, specific examples, quantifiable metrics, and demonstrating both technical depth and leadership qualities. The ACTION section should be the longest and most detailed (300-500 words). CRITICAL: You MUST explicitly weave the company's core values and the role's required skills throughout the story. Every section should clearly demonstrate alignment with what this specific company and role needs. Use bold markers like 'This demonstrates [Company Value]' or 'This shows [Role Requirement]' in talking points. IMPORTANT: Strictly follow the tone requirements specified in the prompt - adjust your language, word choice, and communication style to match the requested tone (professional, conversational, confident, technical, or strategic)."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
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


class CompanyValuesRequest(BaseModel):
    company_name: str
    industry: Optional[str] = None
    job_title: Optional[str] = None


@router.post("/company-values")
async def get_company_values(request: CompanyValuesRequest):
    """
    Fetch real company values and culture from multiple sources.

    Sources:
    - Company careers and about pages
    - Employee review sites (Glassdoor, Built In)
    - Perplexity research with citations
    - Company culture articles and blog posts

    Returns company values with:
    - Value names and descriptions
    - Source URLs for verification
    - Cultural priorities
    - Work environment details
    """
    try:
        service = CompanyResearchService()

        values_data = await service.research_company_values_culture(
            company_name=request.company_name,
            industry=request.industry,
            job_title=request.job_title
        )

        return {
            "success": True,
            "data": values_data
        }

    except Exception as e:
        print(f"Failed to fetch company values: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch company values: {str(e)}"
        )


class CommonQuestionsRequest(BaseModel):
    interview_prep_id: int


@router.post("/common-questions/generate")
async def generate_common_questions(
    request: CommonQuestionsRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate tailored responses for 10 common interview questions.

    This endpoint:
    1. Fetches the interview prep and associated data
    2. Fetches the resume and job description
    3. Uses OpenAI to generate personalized answers for 10 questions
    4. Returns structured data with tailored answers

    Each question includes:
    - Why it's hard (explanation)
    - Common mistakes (bullet list)
    - Exceptional answer builder (detailed guidance)
    - What to say (short and long versions)
    """
    try:
        if not x_user_id:
            raise HTTPException(status_code=400, detail="X-User-ID header is required")

        # Fetch interview prep with user validation
        result = await db.execute(
            select(InterviewPrep, TailoredResume)
            .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
            .where(
                and_(
                    InterviewPrep.id == request.interview_prep_id,
                    InterviewPrep.is_deleted == False,
                    TailoredResume.session_user_id == x_user_id,
                    TailoredResume.is_deleted == False
                )
            )
        )
        result_row = result.first()

        if not result_row:
            raise HTTPException(status_code=404, detail="Interview prep not found")

        interview_prep, tailored_resume = result_row

        # Fetch base resume for full experience
        result = await db.execute(
            select(BaseResume).where(BaseResume.id == tailored_resume.base_resume_id)
        )
        base_resume = result.scalar_one_or_none()

        if not base_resume:
            raise HTTPException(status_code=404, detail="Base resume not found")

        # Fetch job
        result = await db.execute(
            select(Job).where(Job.id == tailored_resume.job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Build resume text
        resume_text = f"""
PROFESSIONAL SUMMARY:
{base_resume.summary or 'N/A'}

SKILLS:
{', '.join(json.loads(base_resume.skills) if isinstance(base_resume.skills, str) else base_resume.skills or [])}

EXPERIENCE:
"""
        experience_data = json.loads(base_resume.experience) if isinstance(base_resume.experience, str) else base_resume.experience or []
        for exp in experience_data:
            resume_text += f"\n{exp.get('header', exp.get('title', 'Position'))} | {exp.get('dates', 'Dates')}\n"
            resume_text += "\n".join([f"- {bullet}" for bullet in exp.get('bullets', [])])
            resume_text += "\n"

        resume_text += f"""
EDUCATION:
{base_resume.education or 'N/A'}

CERTIFICATIONS:
{base_resume.certifications or 'N/A'}
"""

        # Build job description
        job_description = f"""
{job.title} at {job.company}
Location: {job.location or 'Not specified'}

{job.description}
"""

        # Generate common questions using OpenAI
        ai_service = OpenAICommonQuestions()

        result_data = await ai_service.generate_common_questions(
            resume_text=resume_text,
            job_description=job_description,
            company_name=job.company,
            job_title=job.title,
            prep_data=interview_prep.prep_data
        )

        print(f"✓ Generated common questions for interview prep {request.interview_prep_id}")

        return {
            "success": True,
            "data": result_data
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to generate common questions: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate common questions: {str(e)}"
        )


class RegenerateQuestionRequest(BaseModel):
    interview_prep_id: int
    question_id: str  # e.g., "q1", "q2"


@router.post("/common-questions/regenerate")
async def regenerate_single_question(
    request: RegenerateQuestionRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Regenerate a single common interview question.

    This allows the user to get a fresh answer if they're not satisfied
    with the initially generated response.
    """
    try:
        if not x_user_id:
            raise HTTPException(status_code=400, detail="X-User-ID header is required")

        # Fetch interview prep with user validation
        result = await db.execute(
            select(InterviewPrep, TailoredResume)
            .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
            .where(
                and_(
                    InterviewPrep.id == request.interview_prep_id,
                    InterviewPrep.is_deleted == False,
                    TailoredResume.session_user_id == x_user_id,
                    TailoredResume.is_deleted == False
                )
            )
        )
        result_row = result.first()

        if not result_row:
            raise HTTPException(status_code=404, detail="Interview prep not found")

        interview_prep, tailored_resume = result_row

        # Fetch base resume
        result = await db.execute(
            select(BaseResume).where(BaseResume.id == tailored_resume.base_resume_id)
        )
        base_resume = result.scalar_one_or_none()
        if not base_resume:
            raise HTTPException(status_code=404, detail="Base resume not found")

        # Fetch job
        result = await db.execute(
            select(Job).where(Job.id == tailored_resume.job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Build resume text
        resume_text = f"""
PROFESSIONAL SUMMARY:
{base_resume.summary or 'N/A'}

SKILLS:
{', '.join(json.loads(base_resume.skills) if isinstance(base_resume.skills, str) else base_resume.skills or [])}

EXPERIENCE:
"""
        experience_data = json.loads(base_resume.experience) if isinstance(base_resume.experience, str) else base_resume.experience or []
        for exp in experience_data:
            resume_text += f"\n{exp.get('header', exp.get('title', 'Position'))} | {exp.get('dates', 'Dates')}\n"
            resume_text += "\n".join([f"- {bullet}" for bullet in exp.get('bullets', [])])
            resume_text += "\n"

        resume_text += f"""
EDUCATION:
{base_resume.education or 'N/A'}

CERTIFICATIONS:
{base_resume.certifications or 'N/A'}
"""

        job_description = f"""
{job.title} at {job.company}
Location: {job.location or 'Not specified'}

{job.description}
"""

        # Regenerate all questions
        ai_service = OpenAICommonQuestions()
        result_data = await ai_service.generate_common_questions(
            resume_text=resume_text,
            job_description=job_description,
            company_name=job.company,
            job_title=job.title,
            prep_data=interview_prep.prep_data
        )

        # Extract only the requested question
        regenerated_question = None
        for q in result_data.get('questions', []):
            if q.get('id') == request.question_id:
                regenerated_question = q
                break

        if not regenerated_question:
            raise HTTPException(status_code=404, detail=f"Question {request.question_id} not found")

        print(f"✓ Regenerated question {request.question_id} for interview prep {request.interview_prep_id}")

        return {
            "success": True,
            "data": regenerated_question
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to regenerate question: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate question: {str(e)}"
        )


# ============================================================================
# INTERVIEW INTELLIGENCE ENDPOINTS (Phase 1 - Sales Navigator Features)
# ============================================================================


class ScoreRelevanceRequest(BaseModel):
    content_items: List[Dict]  # Strategic initiatives or news items
    job_description: str
    job_title: str
    content_type: str = "strategy"  # "strategy" or "news"


@router.post("/score-relevance")
async def score_content_relevance(request: ScoreRelevanceRequest):
    """
    Score how relevant company research is to the specific job.
    Similar to LinkedIn Sales Navigator's Buyer Intent Score.

    Returns content items with:
    - relevance_score (0-10)
    - priority (Critical/High/Medium/Context)
    - why_it_matters
    - job_alignment
    - talking_point
    """
    try:
        service = InterviewIntelligenceService()

        scored_items = await service.score_relevance(
            content_items=request.content_items,
            job_description=request.job_description,
            job_title=request.job_title,
            content_type=request.content_type
        )

        return {
            "success": True,
            "data": {
                "scored_items": scored_items,
                "total_items": len(scored_items)
            }
        }

    except Exception as e:
        print(f"Failed to score relevance: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to score relevance: {str(e)}"
        )


class TalkingPointsRequest(BaseModel):
    content: Dict  # Company research content
    job_description: str
    job_title: str
    company_name: str


@router.post("/generate-talking-points")
async def generate_talking_points(request: TalkingPointsRequest):
    """
    Generate actionable talking points for how to use company research in interviews.

    Returns:
    - how_to_use_in_interview
    - example_statements
    - questions_to_ask
    - dos_and_donts
    - prep_time_minutes
    """
    try:
        service = InterviewIntelligenceService()

        talking_points = await service.generate_talking_points(
            content=request.content,
            job_description=request.job_description,
            job_title=request.job_title,
            company_name=request.company_name
        )

        return {
            "success": True,
            "data": talking_points
        }

    except Exception as e:
        print(f"Failed to generate talking points: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate talking points: {str(e)}"
        )


class JobAlignmentRequest(BaseModel):
    company_research: Dict
    job_description: str
    job_title: str
    company_name: str


@router.post("/analyze-job-alignment")
async def analyze_job_alignment(request: JobAlignmentRequest):
    """
    Analyze how company research aligns with specific job requirements.

    Returns:
    - requirement_mapping (list of job requirements matched to company evidence)
    - overall_alignment_score (0-10)
    - top_alignment_areas
    - gaps_to_address
    - interview_strategy
    """
    try:
        service = InterviewIntelligenceService()

        alignment = await service.analyze_job_alignment(
            company_research=request.company_research,
            job_description=request.job_description,
            job_title=request.job_title,
            company_name=request.company_name
        )

        return {
            "success": True,
            "data": alignment
        }

    except Exception as e:
        print(f"Failed to analyze job alignment: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze job alignment: {str(e)}"
        )


class ReadinessRequest(BaseModel):
    prep_data: Dict  # Full interview prep data
    sections_completed: List[str]  # List of section IDs user has reviewed


@router.post("/calculate-readiness")
async def calculate_interview_readiness(request: ReadinessRequest):
    """
    Calculate overall interview readiness score.
    Similar to an aggregate account score showing preparation progress.

    Returns:
    - readiness_score (0-10)
    - progress_percentage
    - time_invested_minutes
    - critical_gaps
    - next_actions (prioritized list)
    - status (Interview Ready, Nearly Ready, etc.)
    - recommendation
    """
    try:
        service = InterviewIntelligenceService()

        readiness = await service.calculate_interview_readiness(
            prep_data=request.prep_data,
            sections_completed=request.sections_completed
        )

        return {
            "success": True,
            "data": readiness
        }

    except Exception as e:
        print(f"Failed to calculate readiness: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate readiness: {str(e)}"
        )


class ValuesAlignmentRequest(BaseModel):
    stated_values: List[Dict]
    candidate_background: str
    job_description: str
    company_name: str


@router.post("/values-alignment")
async def generate_values_alignment(request: ValuesAlignmentRequest):
    """
    Generate values alignment scorecard showing culture fit.

    Returns:
    - overall_culture_fit (0-10)
    - value_matches (list with match_percentage, evidence, how_to_discuss)
    - dos_and_donts
    - top_strengths
    - areas_to_emphasize
    - star_story_prompts
    """
    try:
        service = InterviewIntelligenceService()

        alignment = await service.generate_values_alignment_scorecard(
            stated_values=request.stated_values,
            candidate_background=request.candidate_background,
            job_description=request.job_description,
            company_name=request.company_name
        )

        return {
            "success": True,
            "data": alignment
        }

    except Exception as e:
        print(f"Failed to generate values alignment: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate values alignment: {str(e)}"
        )


# ============================================================================
# PRACTICE QUESTIONS - JOB-SPECIFIC WITH AI-GENERATED STAR STORIES
# ============================================================================

class GeneratePracticeQuestionsRequest(BaseModel):
    interview_prep_id: int
    num_questions: int = 10


@router.post("/generate-practice-questions")
async def generate_practice_questions(
    request: GeneratePracticeQuestionsRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate job-specific practice questions based on job description responsibilities.
    Returns: List of tailored questions with category, difficulty, why_asked, key_skills_tested
    """
    try:
        result = await db.execute(
            select(InterviewPrep).where(
                InterviewPrep.id == request.interview_prep_id,
                InterviewPrep.is_deleted == False
            )
        )
        interview_prep = result.scalar_one_or_none()

        if not interview_prep:
            raise HTTPException(status_code=404, detail="Interview prep not found")

        result = await db.execute(
            select(TailoredResume)
            .options(selectinload(TailoredResume.job))
            .where(
                TailoredResume.id == interview_prep.tailored_resume_id,
                TailoredResume.is_deleted == False
            )
        )
        tailored_resume = result.scalar_one_or_none()

        if not tailored_resume:
            raise HTTPException(status_code=404, detail="Tailored resume not found")

        prep_data = interview_prep.prep_data
        role_analysis = prep_data.get("role_analysis", {})
        company_profile = prep_data.get("company_profile", {})

        job_title = role_analysis.get("job_title", "")
        core_responsibilities = role_analysis.get("core_responsibilities", [])
        must_have_skills = role_analysis.get("must_have_skills", [])
        company_name = company_profile.get("name", "")

        job_description = ""
        if tailored_resume.job:
            job_description = tailored_resume.job.description or ""

        service = PracticeQuestionsService()
        questions = service.generate_job_specific_questions(
            job_description=job_description,
            job_title=job_title,
            core_responsibilities=core_responsibilities,
            must_have_skills=must_have_skills,
            company_name=company_name,
            num_questions=request.num_questions
        )

        return {
            "success": True,
            "data": {
                "questions": questions,
                "job_title": job_title,
                "company_name": company_name,
                "total_questions": len(questions)
            }
        }

    except Exception as e:
        print(f"Failed to generate practice questions: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate practice questions: {str(e)}"
        )


class GenerateStarStoryRequest(BaseModel):
    interview_prep_id: int
    question: str


@router.post("/generate-practice-star-story")
async def generate_practice_star_story(
    request: GenerateStarStoryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate an AI-powered STAR story to answer a specific interview question.
    Returns: STAR story with Situation, Task, Action, Result
    """
    try:
        result = await db.execute(
            select(InterviewPrep).where(
                InterviewPrep.id == request.interview_prep_id,
                InterviewPrep.is_deleted == False
            )
        )
        interview_prep = result.scalar_one_or_none()

        if not interview_prep:
            raise HTTPException(status_code=404, detail="Interview prep not found")

        result = await db.execute(
            select(TailoredResume)
            .options(selectinload(TailoredResume.job))
            .where(
                TailoredResume.id == interview_prep.tailored_resume_id,
                TailoredResume.is_deleted == False
            )
        )
        tailored_resume = result.scalar_one_or_none()

        if not tailored_resume:
            raise HTTPException(status_code=404, detail="Tailored resume not found")

        candidate_background = tailored_resume.tailored_summary or tailored_resume.summary or ""

        prep_data = interview_prep.prep_data
        role_analysis = prep_data.get("role_analysis", {})
        job_title = role_analysis.get("job_title", "")

        job_description = ""
        if tailored_resume.job:
            job_description = tailored_resume.job.description or ""

        service = PracticeQuestionsService()
        star_story = service.generate_star_story(
            question=request.question,
            candidate_background=candidate_background,
            job_description=job_description,
            job_title=job_title
        )

        return {
            "success": True,
            "data": {
                "star_story": star_story,
                "question": request.question
            }
        }

    except Exception as e:
        print(f"Failed to generate STAR story: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate STAR story: {str(e)}"
        )


class SavePracticeResponseRequest(BaseModel):
    interview_prep_id: int
    question_text: str
    question_category: Optional[str] = None
    star_story: Optional[Dict] = None
    audio_recording_url: Optional[str] = None
    video_recording_url: Optional[str] = None
    written_answer: Optional[str] = None
    practice_duration_seconds: Optional[int] = None


@router.post("/save-practice-response")
async def save_practice_response(
    request: SavePracticeResponseRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Save or update a practice question response with recordings and STAR story.
    Returns: Saved response ID
    """
    try:
        result = await db.execute(
            select(PracticeQuestionResponse).where(
                and_(
                    PracticeQuestionResponse.interview_prep_id == request.interview_prep_id,
                    PracticeQuestionResponse.question_text == request.question_text,
                    PracticeQuestionResponse.is_deleted == False
                )
            )
        )
        existing_response = result.scalar_one_or_none()

        if existing_response:
            if request.star_story:
                existing_response.star_story = request.star_story
            if request.audio_recording_url:
                existing_response.audio_recording_url = request.audio_recording_url
            if request.video_recording_url:
                existing_response.video_recording_url = request.video_recording_url
            if request.written_answer is not None:
                existing_response.written_answer = request.written_answer
            if request.practice_duration_seconds:
                existing_response.practice_duration_seconds = request.practice_duration_seconds

            existing_response.times_practiced += 1
            existing_response.last_practiced_at = datetime.utcnow()
            existing_response.updated_at = datetime.utcnow()

            await db.commit()
            await db.refresh(existing_response)

            return {
                "success": True,
                "data": {
                    "id": existing_response.id,
                    "times_practiced": existing_response.times_practiced,
                    "message": "Practice response updated successfully"
                }
            }
        else:
            new_response = PracticeQuestionResponse(
                interview_prep_id=request.interview_prep_id,
                question_text=request.question_text,
                question_category=request.question_category,
                star_story=request.star_story,
                audio_recording_url=request.audio_recording_url,
                video_recording_url=request.video_recording_url,
                written_answer=request.written_answer,
                practice_duration_seconds=request.practice_duration_seconds,
                times_practiced=1,
                last_practiced_at=datetime.utcnow()
            )

            db.add(new_response)
            await db.commit()
            await db.refresh(new_response)

            return {
                "success": True,
                "data": {
                    "id": new_response.id,
                    "times_practiced": 1,
                    "message": "Practice response saved successfully"
                }
            }

    except Exception as e:
        await db.rollback()
        print(f"Failed to save practice response: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save practice response: {str(e)}"
        )


@router.get("/practice-responses/{interview_prep_id}")
async def get_practice_responses(
    interview_prep_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all practice responses for an interview prep.
    Returns: List of all practice responses with recordings and STAR stories
    """
    try:
        result = await db.execute(
            select(PracticeQuestionResponse).where(
                and_(
                    PracticeQuestionResponse.interview_prep_id == interview_prep_id,
                    PracticeQuestionResponse.is_deleted == False
                )
            ).order_by(PracticeQuestionResponse.last_practiced_at.desc())
        )
        responses = result.scalars().all()

        return {
            "success": True,
            "data": {
                "responses": [
                    {
                        "id": r.id,
                        "question_text": r.question_text,
                        "question_category": r.question_category,
                        "question_key": r.question_key,
                        "star_story": r.star_story,
                        "audio_recording_url": r.audio_recording_url,
                        "video_recording_url": r.video_recording_url,
                        "written_answer": r.written_answer,
                        "practice_duration_seconds": r.practice_duration_seconds,
                        "times_practiced": r.times_practiced,
                        "last_practiced_at": r.last_practiced_at.isoformat() if r.last_practiced_at else None,
                        "created_at": r.created_at.isoformat()
                    }
                    for r in responses
                ],
                "total_responses": len(responses)
            }
        }

    except Exception as e:
        print(f"Failed to get practice responses: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get practice responses: {str(e)}"
        )


class GenerateBehavioralTechnicalQuestionsRequest(BaseModel):
    interview_prep_id: int


@router.post("/generate-behavioral-technical-questions")
async def generate_behavioral_technical_questions(
    request: GenerateBehavioralTechnicalQuestionsRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate 10 behavioral and 10 technical interview questions.

    This endpoint:
    1. Fetches interview prep, tailored resume, base resume, and job data
    2. Uses Perplexity to research company's actual tech stack
    3. Generates 10 behavioral questions with STAR story prompts
    4. Generates 10 technical questions aligned to:
       - Company's tech stack
       - Candidate's skills from resume
       - Job requirements

    Returns:
    - company_tech_stack: Real technologies the company uses
    - behavioral: 10 questions with STAR prompts and guidance
    - technical: 10 questions with skill leverage tips
    - tech_stack_analysis: How candidate skills match company needs
    """
    try:
        if not x_user_id:
            raise HTTPException(status_code=400, detail="X-User-ID header is required")

        # Fetch interview prep with user validation
        result = await db.execute(
            select(InterviewPrep, TailoredResume)
            .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
            .where(
                and_(
                    InterviewPrep.id == request.interview_prep_id,
                    InterviewPrep.is_deleted == False,
                    TailoredResume.session_user_id == x_user_id,
                    TailoredResume.is_deleted == False
                )
            )
        )
        result_row = result.first()

        if not result_row:
            raise HTTPException(status_code=404, detail="Interview prep not found")

        interview_prep, tailored_resume = result_row
        prep_data = interview_prep.prep_data

        # Fetch base resume for candidate skills and experience
        result = await db.execute(
            select(BaseResume).where(BaseResume.id == tailored_resume.base_resume_id)
        )
        base_resume = result.scalar_one_or_none()

        if not base_resume:
            raise HTTPException(status_code=404, detail="Base resume not found")

        # Fetch job
        result = await db.execute(
            select(Job).where(Job.id == tailored_resume.job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Parse candidate data from resume
        candidate_skills = []
        if base_resume.skills:
            try:
                skills_data = json.loads(base_resume.skills) if isinstance(base_resume.skills, str) else base_resume.skills
                candidate_skills = skills_data if isinstance(skills_data, list) else []
            except:
                candidate_skills = []

        candidate_experience = []
        if base_resume.experience:
            try:
                exp_data = json.loads(base_resume.experience) if isinstance(base_resume.experience, str) else base_resume.experience
                candidate_experience = exp_data if isinstance(exp_data, list) else []
            except:
                candidate_experience = []

        # Extract data from prep_data
        role_analysis = prep_data.get('role_analysis', {})
        values_culture = prep_data.get('values_and_culture', {})
        company_profile = prep_data.get('company_profile', {})

        core_responsibilities = role_analysis.get('core_responsibilities', [])
        must_have_skills = role_analysis.get('must_have_skills', [])
        nice_to_have_skills = role_analysis.get('nice_to_have_skills', [])

        # Get company values for behavioral questions
        company_values = [v.get('name', '') for v in values_culture.get('stated_values', [])]

        # Build job description
        job_description = f"""
Job Title: {job.title}
Company: {job.company}
Location: {job.location or 'Not specified'}

Description:
{job.description or 'No description available'}

Requirements:
{job.requirements or 'No specific requirements listed'}
"""

        # Initialize the question generator service
        generator = InterviewQuestionsGenerator()

        # Generate full question set
        questions_data = await generator.generate_full_interview_questions(
            job_description=job_description,
            job_title=job.title,
            company_name=job.company,
            core_responsibilities=core_responsibilities,
            must_have_skills=must_have_skills,
            nice_to_have_skills=nice_to_have_skills,
            candidate_skills=candidate_skills,
            candidate_experience=candidate_experience,
            company_values=company_values,
            industry=company_profile.get('industry')
        )

        return {
            "success": True,
            "data": questions_data
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to generate behavioral/technical questions: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate questions: {str(e)}"
        )


class SaveStarStoryForQuestionRequest(BaseModel):
    interview_prep_id: int
    question_id: int
    question_text: str
    question_type: str  # "behavioral" or "technical"
    star_story: dict  # {situation, task, action, result}
    question_key: Optional[str] = None  # e.g. behavioral_3, technical_7


@router.post("/save-question-star-story")
async def save_star_story_for_question(
    request: SaveStarStoryForQuestionRequest,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Save a user's STAR story for a specific behavioral/technical question.
    Uses the PracticeQuestionResponse model to store the response.
    """
    try:
        if not x_user_id:
            raise HTTPException(status_code=400, detail="X-User-ID header is required")

        # Validate interview prep belongs to user
        result = await db.execute(
            select(InterviewPrep, TailoredResume)
            .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
            .where(
                and_(
                    InterviewPrep.id == request.interview_prep_id,
                    InterviewPrep.is_deleted == False,
                    TailoredResume.session_user_id == x_user_id,
                    TailoredResume.is_deleted == False
                )
            )
        )

        if not result.first():
            raise HTTPException(status_code=404, detail="Interview prep not found")

        # Build question_key for reliable lookup
        unique_question_key = request.question_key or f"{request.question_type}_{request.question_id}"

        # Try lookup by question_key first (most reliable), fallback to question_text
        existing_response = None
        result = await db.execute(
            select(PracticeQuestionResponse).where(
                and_(
                    PracticeQuestionResponse.interview_prep_id == request.interview_prep_id,
                    PracticeQuestionResponse.question_key == unique_question_key,
                    PracticeQuestionResponse.is_deleted == False
                )
            )
        )
        existing_response = result.scalar_one_or_none()

        if not existing_response:
            # Fallback: lookup by question_text
            result = await db.execute(
                select(PracticeQuestionResponse).where(
                    and_(
                        PracticeQuestionResponse.interview_prep_id == request.interview_prep_id,
                        PracticeQuestionResponse.question_text == request.question_text,
                        PracticeQuestionResponse.is_deleted == False
                    )
                )
            )
            existing_response = result.scalar_one_or_none()

        if existing_response:
            # Update existing response
            existing_response.star_story = request.star_story
            existing_response.question_category = request.question_type
            existing_response.question_key = unique_question_key
            existing_response.updated_at = datetime.utcnow()
            existing_response.times_practiced = (existing_response.times_practiced or 0) + 1
            existing_response.last_practiced_at = datetime.utcnow()
            await db.commit()
            await db.refresh(existing_response)

            return {
                "success": True,
                "data": {
                    "id": existing_response.id,
                    "message": "STAR story updated",
                    "times_practiced": existing_response.times_practiced
                }
            }
        else:
            # Create new response
            new_response = PracticeQuestionResponse(
                interview_prep_id=request.interview_prep_id,
                question_text=request.question_text,
                question_category=request.question_type,
                question_key=unique_question_key,
                star_story=request.star_story,
                times_practiced=1,
                last_practiced_at=datetime.utcnow()
            )
            db.add(new_response)
            await db.commit()
            await db.refresh(new_response)

            return {
                "success": True,
                "data": {
                    "id": new_response.id,
                    "message": "STAR story saved",
                    "times_practiced": 1
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to save STAR story: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save STAR story: {str(e)}"
        )
