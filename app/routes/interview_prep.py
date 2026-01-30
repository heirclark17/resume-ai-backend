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
            company_research=company_data,
            company_name=job.company,
            job_title=job.title
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


@router.get("/{interview_prep_id}/practice-history")
async def get_practice_history(
    interview_prep_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get practice history for an interview prep (alias for practice-responses).
    Returns: List of practice history items with question text, category, response, and STAR story
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

        return [
            {
                "id": r.id,
                "question_text": r.question_text,
                "question_category": r.question_category,
                "response_text": r.written_answer,
                "star_story": r.star_story,
                "times_practiced": r.times_practiced,
                "last_practiced_at": r.last_practiced_at.isoformat() if r.last_practiced_at else None,
                "practice_duration_seconds": r.practice_duration_seconds
            }
            for r in responses
        ]

    except Exception as e:
        print(f"Failed to get practice history: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get practice history: {str(e)}"
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


# ============================================================================
# MOBILE APP GET ENDPOINTS - Interview Intelligence Features
# These GET endpoints are called by the mobile app with prep_id in the URL
# ============================================================================


@router.get("/{prep_id}/readiness-score")
async def get_readiness_score(
    prep_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get interview readiness score for a specific interview prep.
    Mobile app calls this with the prep_id in the URL.

    Returns:
    - confidence_level: 0-100
    - preparation_level: "Well Prepared", "Needs Work", etc.
    - strengths: List of strengths
    - areas_for_improvement: List of areas to improve
    - recommendations: List of recommendations
    """
    try:
        # Fetch interview prep with user validation
        result = await db.execute(
            select(InterviewPrep, TailoredResume)
            .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
            .where(
                and_(
                    InterviewPrep.id == prep_id,
                    InterviewPrep.is_deleted == False,
                    TailoredResume.is_deleted == False
                )
            )
        )
        result_row = result.first()

        if not result_row:
            raise HTTPException(status_code=404, detail="Interview prep not found")

        interview_prep, tailored_resume = result_row
        prep_data = interview_prep.prep_data

        # Calculate readiness based on prep data completeness
        service = InterviewIntelligenceService()

        # Determine which sections are complete based on prep_data
        sections_completed = []
        if prep_data.get('company_profile'):
            sections_completed.append('company_profile')
        if prep_data.get('role_analysis'):
            sections_completed.append('role_analysis')
        if prep_data.get('values_and_culture'):
            sections_completed.append('values_culture')
        if prep_data.get('strategy_and_news'):
            sections_completed.append('strategy_news')
        if prep_data.get('interview_preparation'):
            sections_completed.append('interview_prep_checklist')
        if prep_data.get('questions_to_ask_interviewer'):
            sections_completed.append('questions_to_ask')
        if prep_data.get('candidate_positioning'):
            sections_completed.append('practice_questions')

        readiness = await service.calculate_interview_readiness(
            prep_data=prep_data,
            sections_completed=sections_completed
        )

        # Transform to match mobile app expected format
        confidence_level = int(readiness.get('readiness_score', 7) * 10)  # Convert 0-10 to 0-100

        return {
            "success": True,
            "data": {
                "confidence_level": confidence_level,
                "preparation_level": readiness.get('status', 'In Progress'),
                "strengths": [
                    f"Completed {len(sections_completed)} of 7 prep sections",
                    f"Progress: {readiness.get('progress_percentage', 0)}%",
                    f"Time invested: ~{readiness.get('time_invested_minutes', 0)} minutes"
                ],
                "areas_for_improvement": readiness.get('critical_gaps', []),
                "recommendations": [action.get('action', '') for action in readiness.get('next_actions', [])]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to get readiness score: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get readiness score: {str(e)}"
        )


@router.get("/{prep_id}/values-alignment")
async def get_values_alignment(
    prep_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get values alignment analysis for a specific interview prep.

    Returns:
    - alignment_score: 0-100
    - matched_values: List of matched values with evidence
    - value_gaps: List of values to develop
    - cultural_fit_insights: Text insights
    """
    try:
        # Fetch interview prep with user validation
        result = await db.execute(
            select(InterviewPrep, TailoredResume, Job)
            .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
            .join(Job, TailoredResume.job_id == Job.id)
            .where(
                and_(
                    InterviewPrep.id == prep_id,
                    InterviewPrep.is_deleted == False,
                    TailoredResume.is_deleted == False
                )
            )
        )
        result_row = result.first()

        if not result_row:
            raise HTTPException(status_code=404, detail="Interview prep not found")

        interview_prep, tailored_resume, job = result_row
        prep_data = interview_prep.prep_data

        # Get values from prep data
        values_and_culture = prep_data.get('values_and_culture', {})
        stated_values = values_and_culture.get('stated_values', [])

        # Get candidate background from tailored resume
        candidate_background = tailored_resume.tailored_summary or tailored_resume.summary or ""

        # Build job description
        job_description = f"{job.title} at {job.company}\n{job.description or ''}"

        # Generate values alignment
        service = InterviewIntelligenceService()
        alignment = await service.generate_values_alignment_scorecard(
            stated_values=stated_values,
            candidate_background=candidate_background,
            job_description=job_description,
            company_name=job.company
        )

        # Transform to match mobile app expected format
        value_matches = []
        value_gaps = []

        for vm in alignment.get('value_matches', []):
            match_pct = vm.get('match_percentage', 70)
            value_item = {
                "value": vm.get('value', ''),
                "company_context": vm.get('how_to_discuss', ''),
                "candidate_evidence": vm.get('your_evidence', '')
            }
            if match_pct >= 60:
                value_matches.append(value_item)
            else:
                value_gaps.append({
                    **value_item,
                    "suggestion": vm.get('star_story_prompt', '')
                })

        return {
            "success": True,
            "data": {
                "alignment_score": int(alignment.get('overall_culture_fit', 7.5) * 10),
                "matched_values": value_matches,
                "value_gaps": value_gaps,
                "cultural_fit_insights": f"Based on your background, you align well with {job.company}'s values. " +
                    f"Top strengths: {', '.join(alignment.get('top_strengths', []))}"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to get values alignment: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get values alignment: {str(e)}"
        )


@router.get("/{prep_id}/company-research")
async def get_company_research_for_prep(
    prep_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get company research for a specific interview prep.

    Returns:
    - company_overview: Summary text
    - recent_news: List of news items
    - key_products_services: List of products/services
    - competitors: List of competitors
    - financial_health: Financial status info
    - employee_sentiment: Employee review summary
    """
    try:
        # Fetch interview prep with job and company research
        result = await db.execute(
            select(InterviewPrep, TailoredResume, Job, CompanyResearch)
            .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
            .join(Job, TailoredResume.job_id == Job.id)
            .outerjoin(CompanyResearch, CompanyResearch.job_id == Job.id)
            .where(
                and_(
                    InterviewPrep.id == prep_id,
                    InterviewPrep.is_deleted == False,
                    TailoredResume.is_deleted == False
                )
            )
        )
        result_row = result.first()

        if not result_row:
            raise HTTPException(status_code=404, detail="Interview prep not found")

        interview_prep, tailored_resume, job, company_research = result_row
        prep_data = interview_prep.prep_data

        # Extract company profile from prep data
        company_profile = prep_data.get('company_profile', {})
        strategy_and_news = prep_data.get('strategy_and_news', {})

        # Build company research response
        recent_news = []
        for event in strategy_and_news.get('recent_events', [])[:5]:
            recent_news.append({
                "headline": event.get('title') or event.get('headline', ''),
                "date": event.get('date', ''),
                "summary": event.get('summary', ''),
                "source": event.get('source', '')
            })

        # Get competitor info if available
        competitors = []
        if company_research and company_research.initiatives:
            try:
                initiatives = json.loads(company_research.initiatives) if isinstance(company_research.initiatives, str) else company_research.initiatives
                # Look for competitor mentions in initiatives
                for initiative in initiatives[:3]:
                    competitors.append({
                        "name": initiative.get('name', 'Competitor'),
                        "context": initiative.get('description', '')
                    })
            except:
                pass

        return {
            "success": True,
            "data": {
                "company_overview": company_profile.get('overview_paragraph', f"{job.company} is a company in the {company_profile.get('industry', 'technology')} industry."),
                "recent_news": recent_news,
                "key_products_services": [tech.get('technology') or tech.get('name', '') for tech in strategy_and_news.get('technology_focus', [])],
                "competitors": competitors,
                "financial_health": {
                    "status": "stable",
                    "summary": f"{job.company} appears to be in stable financial health based on available information."
                },
                "employee_sentiment": {
                    "sentiment": "positive",
                    "rating": 4.0,
                    "summary": f"Employee sentiment for {job.company} appears positive based on company culture research."
                }
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to get company research: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get company research: {str(e)}"
        )


@router.get("/{prep_id}/strategic-news")
async def get_strategic_news(
    prep_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get strategic news items for a specific interview prep.

    Returns list of news items with:
    - headline, date, summary, source, url
    - relevance_score, talking_points
    """
    try:
        # Fetch interview prep
        result = await db.execute(
            select(InterviewPrep, TailoredResume, Job)
            .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
            .join(Job, TailoredResume.job_id == Job.id)
            .where(
                and_(
                    InterviewPrep.id == prep_id,
                    InterviewPrep.is_deleted == False,
                    TailoredResume.is_deleted == False
                )
            )
        )
        result_row = result.first()

        if not result_row:
            raise HTTPException(status_code=404, detail="Interview prep not found")

        interview_prep, tailored_resume, job = result_row
        prep_data = interview_prep.prep_data

        # Extract news from prep data
        strategy_and_news = prep_data.get('strategy_and_news', {})
        recent_events = strategy_and_news.get('recent_events', [])
        strategic_themes = strategy_and_news.get('strategic_themes', [])

        # Build strategic news list
        news_items = []

        for i, event in enumerate(recent_events[:10]):
            news_items.append({
                "headline": event.get('title') or event.get('headline', f'Company Update {i+1}'),
                "date": event.get('date', ''),
                "summary": event.get('summary', ''),
                "source": event.get('source', ''),
                "url": event.get('url') or event.get('source_url', ''),
                "relevance_score": 8 - (i * 0.5),  # Decreasing relevance
                "talking_points": [
                    f"This shows {job.company}'s commitment to {event.get('summary', 'innovation')[:50]}...",
                    f"I'd love to contribute to initiatives like this."
                ],
                "impact_summary": event.get('impact_summary', f"This development may impact the {job.title} role.")
            })

        # Add strategic themes as additional items
        for theme in strategic_themes[:5]:
            news_items.append({
                "headline": theme.get('theme') or theme.get('name', 'Strategic Initiative'),
                "date": "",
                "summary": theme.get('rationale') or theme.get('description', ''),
                "source": "Company Strategy",
                "url": "",
                "relevance_score": 7.5,
                "talking_points": [
                    f"This aligns with my experience in {theme.get('theme', 'this area')}",
                    "I can contribute to this strategic direction."
                ],
                "impact_summary": f"Strategic focus area for {job.company}"
            })

        return {
            "success": True,
            "data": news_items
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to get strategic news: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get strategic news: {str(e)}"
        )


@router.get("/{prep_id}/competitive-intelligence")
async def get_competitive_intelligence(
    prep_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get competitive intelligence for a specific interview prep.

    Returns:
    - market_position: Text description
    - competitive_advantages: List of advantages
    - challenges: List of challenges
    - interview_angles: List of angles to use in interview
    """
    try:
        # Fetch interview prep
        result = await db.execute(
            select(InterviewPrep, TailoredResume, Job)
            .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
            .join(Job, TailoredResume.job_id == Job.id)
            .where(
                and_(
                    InterviewPrep.id == prep_id,
                    InterviewPrep.is_deleted == False,
                    TailoredResume.is_deleted == False
                )
            )
        )
        result_row = result.first()

        if not result_row:
            raise HTTPException(status_code=404, detail="Interview prep not found")

        interview_prep, tailored_resume, job = result_row
        prep_data = interview_prep.prep_data

        # Extract data from prep
        company_profile = prep_data.get('company_profile', {})
        role_analysis = prep_data.get('role_analysis', {})
        strategy_and_news = prep_data.get('strategy_and_news', {})

        # Build competitive intelligence
        technology_focus = strategy_and_news.get('technology_focus', [])

        competitive_advantages = []
        for tech in technology_focus[:5]:
            competitive_advantages.append(
                f"{tech.get('technology') or tech.get('name', 'Technology')}: {tech.get('description', '')}"
            )

        # Generate interview angles
        interview_angles = [
            f"Discuss how your experience aligns with {job.company}'s focus on {technology_focus[0].get('technology', 'innovation') if technology_focus else 'innovation'}",
            f"Ask about growth opportunities in the {role_analysis.get('job_title', job.title)} role",
            f"Show enthusiasm for {company_profile.get('industry', 'the industry')}'s evolution",
            f"Reference their recent strategic initiatives to show you've done your research",
            f"Connect your skills to their {role_analysis.get('seniority_level', 'senior')}-level expectations"
        ]

        return {
            "success": True,
            "data": {
                "market_position": f"{job.company} is positioned as a {company_profile.get('size_estimate', 'leading')} player in the {company_profile.get('industry', 'technology')} industry.",
                "competitive_advantages": competitive_advantages if competitive_advantages else [
                    "Strong industry presence",
                    "Focus on innovation",
                    "Established market position"
                ],
                "challenges": [
                    "Competitive talent market",
                    "Rapid technology evolution",
                    "Market dynamics"
                ],
                "interview_angles": interview_angles
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to get competitive intelligence: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get competitive intelligence: {str(e)}"
        )


@router.get("/{prep_id}/interview-strategy")
async def get_interview_strategy(
    prep_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get interview strategy for a specific interview prep.

    Returns:
    - overall_approach: Text strategy
    - key_messages: List of key messages
    - questions_to_expect: List of likely questions
    - questions_to_ask: List of questions to ask
    - preparation_tips: List of tips
    """
    try:
        # Fetch interview prep
        result = await db.execute(
            select(InterviewPrep, TailoredResume, Job)
            .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
            .join(Job, TailoredResume.job_id == Job.id)
            .where(
                and_(
                    InterviewPrep.id == prep_id,
                    InterviewPrep.is_deleted == False,
                    TailoredResume.is_deleted == False
                )
            )
        )
        result_row = result.first()

        if not result_row:
            raise HTTPException(status_code=404, detail="Interview prep not found")

        interview_prep, tailored_resume, job = result_row
        prep_data = interview_prep.prep_data

        # Extract data
        role_analysis = prep_data.get('role_analysis', {})
        interview_preparation = prep_data.get('interview_preparation', {})
        candidate_positioning = prep_data.get('candidate_positioning', {})
        questions_to_ask = prep_data.get('questions_to_ask_interviewer', {})

        # Build questions to expect
        questions_to_expect = []
        for pq in interview_preparation.get('practice_questions_for_candidate', [])[:8]:
            if isinstance(pq, str):
                questions_to_expect.append(pq)
            elif isinstance(pq, dict):
                questions_to_expect.append(pq.get('question') or pq.get('text', ''))

        # Flatten questions to ask
        all_questions_to_ask = []
        for category in ['product', 'team', 'culture', 'performance', 'strategy']:
            for q in questions_to_ask.get(category, [])[:2]:
                all_questions_to_ask.append(q)

        return {
            "success": True,
            "data": {
                "overall_approach": f"Position yourself as a strong candidate for the {role_analysis.get('job_title', job.title)} role by emphasizing your relevant experience and alignment with {job.company}'s values and strategic direction.",
                "key_messages": candidate_positioning.get('resume_focus_areas', [
                    "Highlight relevant technical skills",
                    "Emphasize leadership experience",
                    "Show culture fit"
                ])[:5],
                "questions_to_expect": questions_to_expect[:8],
                "questions_to_ask": all_questions_to_ask[:8],
                "preparation_tips": interview_preparation.get('research_tasks', [
                    "Review the job description thoroughly",
                    "Research company recent news",
                    "Prepare STAR stories for behavioral questions",
                    "Practice technical concepts relevant to the role"
                ])[:6],
                "day_of_checklist": interview_preparation.get('day_of_checklist', [
                    "Review key talking points",
                    "Check technology setup",
                    "Prepare questions to ask",
                    "Review company values"
                ])[:5]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to get interview strategy: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get interview strategy: {str(e)}"
        )


@router.get("/{prep_id}/executive-insights")
async def get_executive_insights(
    prep_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get executive-level insights for a specific interview prep.

    Returns:
    - leadership_context: Leadership team context
    - strategic_priorities: List of strategic priorities
    - decision_making_style: Text description
    - c_suite_talking_points: List of executive-level talking points
    - strategic_initiatives: List of key initiatives
    """
    try:
        # Fetch interview prep
        result = await db.execute(
            select(InterviewPrep, TailoredResume, Job)
            .join(TailoredResume, InterviewPrep.tailored_resume_id == TailoredResume.id)
            .join(Job, TailoredResume.job_id == Job.id)
            .where(
                and_(
                    InterviewPrep.id == prep_id,
                    InterviewPrep.is_deleted == False,
                    TailoredResume.is_deleted == False
                )
            )
        )
        result_row = result.first()

        if not result_row:
            raise HTTPException(status_code=404, detail="Interview prep not found")

        interview_prep, tailored_resume, job = result_row
        prep_data = interview_prep.prep_data

        # Extract data
        company_profile = prep_data.get('company_profile', {})
        strategy_and_news = prep_data.get('strategy_and_news', {})
        values_and_culture = prep_data.get('values_and_culture', {})

        # Build strategic priorities
        strategic_priorities = []
        for theme in strategy_and_news.get('strategic_themes', [])[:5]:
            strategic_priorities.append(theme.get('theme') or theme.get('name', 'Strategic Initiative'))

        # Build c-suite talking points
        c_suite_talking_points = []
        for theme in strategy_and_news.get('strategic_themes', [])[:3]:
            c_suite_talking_points.append(
                f"I'm excited about {job.company}'s focus on {theme.get('theme', 'innovation')} and how my experience can contribute."
            )

        # Add value-based talking points
        for value in values_and_culture.get('stated_values', [])[:2]:
            value_name = value.get('name') or value.get('title', 'excellence')
            c_suite_talking_points.append(
                f"Your commitment to {value_name} resonates with my approach to work."
            )

        # Build strategic initiatives
        strategic_initiatives = []
        for tech in strategy_and_news.get('technology_focus', [])[:5]:
            strategic_initiatives.append(
                f"{tech.get('technology') or tech.get('name', 'Initiative')}: {tech.get('relevance_to_role', tech.get('description', ''))}"
            )

        return {
            "success": True,
            "data": {
                "leadership_context": f"{job.company}'s leadership team is focused on {company_profile.get('industry', 'industry')} excellence and strategic growth. The {job.title} role reports into this structure with clear expectations for impact.",
                "strategic_priorities": strategic_priorities if strategic_priorities else [
                    "Innovation and technology leadership",
                    "Customer satisfaction",
                    "Operational excellence"
                ],
                "decision_making_style": f"Based on {job.company}'s values and culture, they appear to value {values_and_culture.get('practical_implications', ['data-driven decision making', 'collaborative approaches'])[0] if values_and_culture.get('practical_implications') else 'thoughtful, data-driven decisions'}.",
                "c_suite_talking_points": c_suite_talking_points if c_suite_talking_points else [
                    f"I'm drawn to {job.company}'s vision and would be excited to contribute.",
                    "My experience aligns well with your strategic direction.",
                    "I'm eager to drive results in this role."
                ],
                "strategic_initiatives": strategic_initiatives if strategic_initiatives else [
                    "Technology modernization",
                    "Market expansion",
                    "Talent development"
                ]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to get executive insights: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get executive insights: {str(e)}"
        )


class SaveStarStoryForQuestionRequest(BaseModel):
    interview_prep_id: int
    question_id: int
    question_text: str
    question_type: str  # "behavioral" or "technical"
    star_story: dict  # {situation, task, action, result}


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

        # Check if response already exists for this question
        unique_question_key = f"{request.question_type}_{request.question_id}"
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
