from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
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
