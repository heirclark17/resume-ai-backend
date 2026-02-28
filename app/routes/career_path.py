"""
Career Path Designer API Routes
Orchestrates research -> synthesis -> validation -> storage
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List
from datetime import datetime
import os

from app.database import get_db, AsyncSessionLocal
from app.middleware.auth import get_user_id
from app.models.career_plan import CareerPlan as CareerPlanModel
from app.schemas.career_plan import (
    IntakeRequest,
    GenerateRequest,
    GenerateResponse,
    ResearchRequest,
    ResearchResponse,
    RefreshEventsRequest,
    CareerPlanListItem,
    CareerPlan
)
from app.services.career_path_research_service import CareerPathResearchService
from app.services.career_path_synthesis_service import CareerPathSynthesisService
from app.services import job_manager
from app.services.perplexity_client import PerplexityClient
from app.utils.logger import logger


router = APIRouter(prefix="/api/career-path", tags=["career-path"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/research")
@limiter.limit("10/hour")
async def research_career_path(
    request: Request,
    data: ResearchRequest,
    db: AsyncSession = Depends(get_db)
) -> ResearchResponse:
    """
    PASS 1: Web-grounded research using Perplexity

    Returns verified facts about:
    - Certifications (with official links)
    - Education options (with program URLs)
    - Events (with registration links)
    """

    logger.info(f"Starting research for roles: {', '.join(data.target_roles)}")

    try:
        research_service = CareerPathResearchService()

        # Run comprehensive research
        research_data = await research_service.research_all(
            target_roles=data.target_roles,
            location=data.location,
            current_experience=5.0,  # TODO: Get from intake
            current_education=data.education_level,
            budget="flexible",  # Budget field removed from intake form
            format_preference="online"  # TODO: Get from intake
        )

        return ResearchResponse(
            certifications=research_data["certifications"],
            education_options=research_data["education_options"],
            events=research_data["events"],
            research_sources=research_data["research_sources"]
        )

    except Exception as e:
        logger.error(f"Research error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Research failed: {str(e)}"
        )


@router.post("/generate")
@limiter.limit("5/hour")
async def generate_career_plan(
    request: Request,
    data: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id)
) -> GenerateResponse:
    """
    PASS 2: Complete career plan generation

    Flow:
    1. If no research_data provided, run research first
    2. Synthesize complete plan with OpenAI
    3. Validate against schema
    4. Repair if needed
    5. Save to database
    6. Return plan
    """

    logger.info(f"Generating career plan for {data.intake.current_role_title}")

    try:
        # Build intake context dict for enhanced research queries
        intake_context = {
            "current_role_title": data.intake.current_role_title,
            "current_industry": data.intake.current_industry,
            "tools": data.intake.tools,
            "existing_certifications": getattr(data.intake, 'existing_certifications', []),
            "already_started": getattr(data.intake, 'already_started', False),
            "steps_already_taken": getattr(data.intake, 'steps_already_taken', ''),
            "preferred_platforms": data.intake.preferred_platforms,
            "specific_companies": data.intake.specific_companies,
        }

        # Step 1: Research if not provided
        research_data = None
        skip_research = os.getenv("SKIP_RESEARCH", "false").lower() == "true"

        if data.research_data:
            research_data = data.research_data.dict()
        elif skip_research:
            logger.warning("Skipping research (SKIP_RESEARCH=true)")
            research_data = {
                "certifications": [],
                "education_options": [],
                "events": [],
                "research_sources": []
            }
        else:
            # Determine target roles for research
            target_roles = []
            if data.intake.target_role_interest:
                target_roles = [data.intake.target_role_interest]
            else:
                target_roles = [f"{data.intake.current_industry} Professional"]

            logger.info(f"Running research for: {', '.join(target_roles)}")
            research_service = CareerPathResearchService()
            research_result = await research_service.research_all(
                target_roles=target_roles,
                location=data.intake.location,
                current_experience=data.intake.years_experience,
                current_education=data.intake.education_level,
                budget=getattr(data.intake, 'training_budget', None) or "flexible",
                format_preference=data.intake.in_person_vs_remote,
                intake_context=intake_context
            )
            research_data = research_result

        # Step 1.5: Research salary data with Perplexity for each target role
        logger.info("Researching salary data with Perplexity...")
        perplexity = PerplexityClient()
        salary_insights = {}
        current_salary = getattr(data.intake, 'current_salary_range', None)

        for role in target_roles[:3]:
            try:
                salary_data = await perplexity.research_salary_insights(
                    job_title=role,
                    location=data.intake.location,
                    experience_level=f"{data.intake.years_experience} years, career changer from {data.intake.current_role_title}" if data.intake.years_experience else None
                )
                # Add career changer salary context
                if current_salary and isinstance(salary_data, dict):
                    salary_data["current_salary"] = current_salary
                    salary_data["career_changer_note"] = f"Candidate currently earns {current_salary}. First-role salary as career changer may differ from established median."
                salary_insights[role] = salary_data
                logger.info(f"Salary research for {role}: {salary_data.get('salary_range', 'N/A')}")
            except Exception as e:
                logger.warning(f"Salary research failed for {role}: {e}")
                salary_insights[role] = {
                    "salary_range": "Competitive",
                    "market_insights": "Data unavailable",
                    "sources": []
                }

        # Add salary insights to research_data
        research_data["salary_insights"] = salary_insights

        # Step 2: Synthesize plan with OpenAI
        logger.info("Synthesizing plan with OpenAI...")
        synthesis_service = CareerPathSynthesisService()
        synthesis_result = await synthesis_service.generate_career_plan(
            intake=data.intake,
            research_data=research_data
        )

        if not synthesis_result.get("success"):
            # Log validation errors if present
            validation_errors = synthesis_result.get("validation_errors", [])
            if validation_errors:
                logger.error(f"Validation errors ({len(validation_errors)} total)")
                for i, err in enumerate(validation_errors[:10]):
                    logger.error(f"  {i+1}. {err.get('field', 'unknown')}: {err.get('error', 'unknown')}")

            return GenerateResponse(
                success=False,
                error=synthesis_result.get("error", "Synthesis failed"),
                validation_errors=validation_errors if validation_errors else None
            )

        plan_data = synthesis_result["plan"]

        # Step 3: Validate (already done in synthesis service)
        logger.info("Plan validated")

        # Step 4: Save to database
        career_plan = CareerPlanModel(
            session_user_id=user_id,
            intake_json=data.intake.dict(),
            research_json=research_data,
            plan_json=plan_data,
            version="1.0"
        )

        db.add(career_plan)
        await db.commit()
        await db.refresh(career_plan)

        logger.info(f"Saved plan ID: {career_plan.id}")

        # Step 5: Return plan
        return GenerateResponse(
            success=True,
            plan=CareerPlan(**plan_data),
            plan_id=career_plan.id
        )

    except Exception as e:
        logger.error(f"Generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Plan generation failed: {str(e)}"
        )


@router.get("/{plan_id}")
async def get_career_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id)
) -> GenerateResponse:
    """
    Retrieve a previously generated career plan
    """

    try:
        result = await db.execute(
            select(CareerPlanModel).where(
                CareerPlanModel.id == plan_id,
                CareerPlanModel.session_user_id == user_id,
                CareerPlanModel.is_deleted == False
            )
        )

        plan = result.scalar_one_or_none()

        if not plan:
            raise HTTPException(status_code=404, detail="Career plan not found")

        # Try strict validation first; fall back to raw dict if stored data
        # doesn't match current schema (old plans, relaxed AI output, etc.)
        try:
            plan_obj = CareerPlan(**plan.plan_json)
            return GenerateResponse(
                success=True,
                plan=plan_obj,
                plan_id=plan.id
            )
        except Exception:
            # Return raw stored data directly, bypassing Pydantic response model
            return JSONResponse(content={
                "success": True,
                "plan": plan.plan_json,
                "plan_id": plan.id
            })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving plan: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve plan: {str(e)}"
        )


@router.get("/")
async def list_career_plans(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id)
) -> List[CareerPlanListItem]:
    """
    List all career plans for the current user
    """

    try:
        result = await db.execute(
            select(CareerPlanModel)
            .where(
                CareerPlanModel.session_user_id == user_id,
                CareerPlanModel.is_deleted == False
            )
            .order_by(CareerPlanModel.created_at.desc())
        )

        plans = result.scalars().all()

        def _get(d, *keys, default=None):
            """Safe lookup supporting both camelCase and snake_case keys."""
            if not isinstance(d, dict):
                return default
            for k in keys:
                val = d.get(k)
                if val is not None:
                    return val
            return default

        items = []
        for plan in plans:
            intake = plan.intake_json or {}
            plan_data = plan.plan_json or {}
            cert_path = _get(plan_data, "certification_path", "certificationPath", default=[])
            exp_plan = _get(plan_data, "experience_plan", "experiencePlan", default=[])
            target_roles_list = _get(plan_data, "target_roles", "targetRoles", default=[])
            skills = _get(plan_data, "skills_analysis", "skillsAnalysis", default={})
            timeline_data = _get(plan_data, "timeline", default={})
            events = _get(plan_data, "events", default=[])
            edu_options = _get(plan_data, "education_options", "educationOptions", default=[])

            # Salary range from first target role
            salary_range = None
            if isinstance(target_roles_list, list) and len(target_roles_list) > 0:
                salary_range = _get(target_roles_list[0], "salary_range", "salaryRange", default=None)

            # Top 3 certification names
            top_certs = []
            if isinstance(cert_path, list):
                for c in cert_path[:3]:
                    name = _get(c, "name", "title", default=None) if isinstance(c, dict) else None
                    if name:
                        top_certs.append(name)

            # Skills counts
            need_to_build = _get(skills, "need_to_build", "needToBuild", default=[])
            already_have = _get(skills, "already_have", "alreadyHave", default=[])
            skills_gap_count = len(need_to_build) if isinstance(need_to_build, list) else 0
            skills_have_count = len(already_have) if isinstance(already_have, list) else 0

            # Bridge role from first target role
            bridge_role = None
            if isinstance(target_roles_list, list) and len(target_roles_list) > 0:
                bridge_roles = _get(target_roles_list[0], "bridge_roles", "bridgeRoles", default=[])
                if isinstance(bridge_roles, list) and len(bridge_roles) > 0:
                    bridge_role = _get(bridge_roles[0], "title", "name", default=None)

            # Top education option
            top_education = None
            if isinstance(edu_options, list) and len(edu_options) > 0:
                top_education = _get(edu_options[0], "name", "title", default=None)

            # Current phase from timeline
            current_phase = None
            if isinstance(timeline_data, dict):
                phases = _get(timeline_data, "phases", default=[])
                if isinstance(phases, list) and len(phases) > 0:
                    current_phase = _get(phases[0], "name", "title", default=None)

            # Number of events
            num_events = len(events) if isinstance(events, list) else 0

            items.append({
                "id": plan.id,
                "target_roles": [
                    role.get("title", "") if isinstance(role, dict) else ""
                    for role in (target_roles_list if isinstance(target_roles_list, list) else [])
                ],
                "dream_role": intake.get("target_role_interest", ""),
                "current_role": intake.get("current_role_title", ""),
                "current_industry": intake.get("current_industry", ""),
                "timeline": intake.get("timeline", ""),
                "target_industries": intake.get("target_industries", []),
                "num_certifications": len(cert_path) if isinstance(cert_path, list) else 0,
                "num_projects": len(exp_plan) if isinstance(exp_plan, list) else 0,
                "profile_summary": _get(plan_data, "profile_summary", "profileSummary", default=""),
                "salary_range": salary_range,
                "top_certifications": top_certs,
                "skills_gap_count": skills_gap_count,
                "skills_have_count": skills_have_count,
                "bridge_role": bridge_role,
                "top_education": top_education,
                "current_phase": current_phase,
                "num_events": num_events,
                "created_at": plan.created_at.isoformat(),
                "updated_at": plan.updated_at.isoformat(),
                "version": plan.version
            })
        return items

    except Exception as e:
        logger.error(f"Error listing plans: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list plans: {str(e)}"
        )


@router.post("/refresh-events")
async def refresh_events(
    request: RefreshEventsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id)
) -> GenerateResponse:
    """
    Refresh only the events section without regenerating entire plan

    Useful for updating event data as registration dates change
    """

    try:
        # Get existing plan
        result = await db.execute(
            select(CareerPlanModel).where(
                CareerPlanModel.id == request.plan_id,
                CareerPlanModel.session_user_id == user_id,
                CareerPlanModel.is_deleted == False
            )
        )

        plan = result.scalar_one_or_none()

        if not plan:
            raise HTTPException(status_code=404, detail="Career plan not found")

        # Extract target roles from existing plan
        plan_data = plan.plan_json
        target_roles = [role["title"] for role in plan_data.get("target_roles", [])]

        if not target_roles:
            raise HTTPException(status_code=400, detail="No target roles in plan")

        # Research fresh events
        logger.info(f"Refreshing events for: {', '.join(target_roles)}")
        research_service = CareerPathResearchService()
        new_events = await research_service.research_events(
            target_roles=target_roles,
            location=request.location,
            beginner_friendly=True
        )

        # Update plan_json with new events
        plan_data["events"] = new_events
        plan_data["generated_at"] = datetime.utcnow().isoformat()

        # Update database
        await db.execute(
            update(CareerPlanModel)
            .where(CareerPlanModel.id == request.plan_id)
            .values(
                plan_json=plan_data,
                updated_at=datetime.utcnow()
            )
        )
        await db.commit()

        # Refresh to get updated data
        await db.refresh(plan)

        logger.info(f"Refreshed {len(new_events)} events")

        return GenerateResponse(
            success=True,
            plan=CareerPlan(**plan_data),
            plan_id=plan.id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing events: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh events: {str(e)}"
        )


@router.post("/generate-async")
async def generate_career_plan_async(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id)
):
    """
    ASYNC: Start career plan generation and return job_id immediately

    This endpoint:
    1. Creates a durable job in PostgreSQL
    2. Returns job_id immediately (no timeout)
    3. Runs Perplexity research + OpenAI synthesis in background
    4. Client polls /job/{job_id} for status
    """

    logger.info(f"Creating async job for {request.intake.current_role_title}")

    try:
        # Create job in PostgreSQL (survives restarts)
        job_id = await job_manager.enqueue_job(
            db=db,
            job_type="career_plan",
            user_id=user_id,
            input_data=request.intake.dict(),
        )

        # Start background task (creates its own db session)
        background_tasks.add_task(
            process_career_plan_job,
            job_id,
            request,
            user_id
        )

        return {
            "success": True,
            "job_id": job_id,
            "message": "Job created - poll /api/career-path/job/{job_id} for status"
        }

    except Exception as e:
        logger.error(f"Error creating async job: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create job: {str(e)}"
        )


@router.post("/generate-tasks")
async def generate_tasks_for_role(request: dict):
    """
    Auto-generate typical tasks for a given job role.

    When experience_bullets are provided (from a parsed resume), uses OpenAI to
    extract the user's actual top tasks from their resume content.
    Otherwise falls back to Perplexity AI to generate generic tasks for the role.

    Request body:
    - role_title: str (e.g., "Software Engineer", "Product Manager")
    - industry: str (optional, e.g., "Technology", "Healthcare")
    - experience_bullets: list[str] (optional, actual resume bullet points from current role)

    Returns:
    - tasks: List[str] (3-5 tasks for the role)
    - source: "resume" | "generated"
    """
    role_title = request.get("role_title", "").strip()
    industry = request.get("industry", "").strip()
    experience_bullets = request.get("experience_bullets", [])

    if not role_title:
        raise HTTPException(status_code=400, detail="role_title is required")

    # If we have resume bullets, extract tasks from the actual resume
    if experience_bullets and len(experience_bullets) >= 2:
        try:
            import openai
            from app.config import get_settings
            settings = get_settings()

            client = openai.OpenAI(api_key=settings.openai_api_key)

            bullets_text = "\n".join(f"- {b}" for b in experience_bullets[:20])

            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You extract the top 3-5 daily tasks/responsibilities from resume bullet points. "
                            "Each task should be a concise phrase (4-10 words) describing what this person actually does day-to-day. "
                            "Focus on recurring responsibilities, not one-time achievements. "
                            "Return ONLY a numbered list, one task per line, no extra text."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Role: {role_title}\nIndustry: {industry or 'General'}\n\nResume bullets:\n{bullets_text}\n\nExtract the top 3-5 daily tasks:"
                    }
                ],
                temperature=0.2,
                max_tokens=300
            )

            answer = response.choices[0].message.content.strip()

            tasks = []
            for line in answer.split('\n'):
                line = line.strip().lstrip('0123456789.-*)  ')
                if line and 10 < len(line) < 120:
                    tasks.append(line)

            tasks = tasks[:5]

            if tasks and len(tasks) >= 3:
                return {
                    "success": True,
                    "role_title": role_title,
                    "industry": industry or "General",
                    "tasks": tasks,
                    "source": "resume"
                }
            # If extraction didn't produce enough tasks, fall through to Perplexity
        except Exception as e:
            logger.error(f"Error extracting tasks from resume: {e}")
            import traceback
            traceback.print_exc()
            # Fall through to Perplexity generation

    # Fallback: generate generic tasks with Perplexity
    try:
        from app.services.perplexity_client import PerplexityClient
        perplexity = PerplexityClient()

        industry_context = f" in the {industry} industry" if industry else ""
        query = f"What are the top 3-5 most common daily tasks and responsibilities for a {role_title}{industry_context}? List them as a brief, concrete tasks that someone in this role performs regularly."

        response = perplexity.client.chat.completions.create(
            model="llama-3.1-sonar-small-128k-online",
            messages=[
                {
                    "role": "system",
                    "content": "You are a career expert. Provide concise, specific daily tasks for job roles. Each task should be 3-8 words, actionable, and realistic."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            temperature=0.3,
            max_tokens=500
        )

        answer = response.choices[0].message.content.strip()

        # Parse the answer to extract task lines
        tasks = []
        lines = answer.split('\n')
        for line in lines:
            line = line.strip()
            # Remove numbering (1., 2., -, *, etc.)
            line = line.lstrip('0123456789.-* ')
            if line and len(line) > 10 and len(line) < 100:
                tasks.append(line)

        # Limit to 3-5 tasks
        tasks = tasks[:5]

        if not tasks or len(tasks) < 3:
            # Fallback generic tasks
            tasks = [
                "Collaborate with team members",
                "Complete assigned project work",
                "Attend meetings and provide updates"
            ]

        return {
            "success": True,
            "role_title": role_title,
            "industry": industry or "General",
            "tasks": tasks,
            "source": "generated"
        }

    except Exception as e:
        logger.error(f"Error generating tasks: {e}")
        import traceback
        traceback.print_exc()

        # Return generic fallback tasks
        return {
            "success": True,
            "role_title": role_title,
            "industry": industry or "General",
            "tasks": [
                "Collaborate with team members",
                "Complete assigned project work",
                "Attend meetings and provide updates"
            ],
            "source": "fallback"
        }


@router.get("/job/{job_id}")
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get status of async career plan generation job

    Returns:
    - status: pending/researching/synthesizing/completed/failed
    - progress: 0-100
    - message: Current step
    - result: Complete plan data (when status=completed)
    - error: Error message (when status=failed)
    """

    job = await job_manager.get_job_status(db, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


async def process_career_plan_job(job_id: str, request: GenerateRequest, user_id: str):
    """
    Background task: Run Perplexity research + OpenAI synthesis

    Updates job status throughout process:
    - pending (0%)
    - researching (10-50%)
    - synthesizing (50-90%)
    - completed (100%)
    - failed (error)

    Creates its own database session (request-scoped sessions don't work)
    """

    # Create new DB session for this background task
    async with AsyncSessionLocal() as db:
      try:

          # Step 0: Extract job posting details if URL provided
          job_details = None
          if getattr(request.intake, 'job_url', None):
              try:
                  await job_manager.update_progress(db, job_id, 5, "Extracting job posting details...")
                  from app.services.firecrawl_client import FirecrawlClient
                  firecrawl = FirecrawlClient()
                  job_details = await firecrawl.extract_job_details(request.intake.job_url)
                  if job_details:
                      logger.info(f"[Job {job_id}] ✓ Extracted job: {job_details.get('title', 'Unknown')} at {job_details.get('company', 'Unknown')}")
                  else:
                      logger.info(f"[Job {job_id}] ⚠ Job extraction returned empty, continuing without")
              except Exception as e:
                  logger.warning(f"[Job {job_id}] Job extraction failed (non-fatal): {e}")
                  job_details = None

          # Step 1: Research with Perplexity (if not provided)
          research_data = None

          if request.research_data:
              research_data = request.research_data.dict()
              await job_manager.update_progress(db, job_id, 50, "Using provided research data")
          else:
              # Determine target roles for research
              target_roles = []
              # If we extracted a job title from the URL, use it as the primary target
              if job_details and job_details.get('title'):
                  target_roles = [job_details['title']]
                  if request.intake.target_role_interest and request.intake.target_role_interest != job_details['title']:
                      target_roles.append(request.intake.target_role_interest)
              elif request.intake.target_role_interest:
                  target_roles = [request.intake.target_role_interest]
              else:
                  # Use current role + industry as hint
                  target_roles = [f"{request.intake.current_industry} Professional"]

              logger.info(f"[Job {job_id}] Running Perplexity research for: {', '.join(target_roles)}")

              await job_manager.update_progress(db, job_id, 10, f"Researching certifications, education, and events for {', '.join(target_roles)}")

              # Build intake context for enhanced research queries
              intake_context = {
                  "current_role_title": request.intake.current_role_title,
                  "current_industry": request.intake.current_industry,
                  "tools": request.intake.tools,
                  "existing_certifications": getattr(request.intake, 'existing_certifications', []),
                  "already_started": getattr(request.intake, 'already_started', False),
                  "steps_already_taken": getattr(request.intake, 'steps_already_taken', ''),
                  "preferred_platforms": request.intake.preferred_platforms,
                  "specific_companies": request.intake.specific_companies,
              }

              research_service = CareerPathResearchService()
              research_result = await research_service.research_all(
                  target_roles=target_roles,
                  location=request.intake.location,
                  current_experience=request.intake.years_experience,
                  current_education=request.intake.education_level,
                  budget=getattr(request.intake, 'training_budget', None) or "flexible",
                  format_preference=request.intake.in_person_vs_remote,
                  intake_context=intake_context
              )
              research_data = research_result

              await job_manager.update_progress(db, job_id, 50, "Research completed - starting plan synthesis")

          # Step 2: Synthesize plan with OpenAI
          logger.info(f"[Job {job_id}] Synthesizing plan with OpenAI GPT-4.1-mini...")

          # Research salary data with Perplexity (career changer context)
          logger.info(f"[Job {job_id}] Researching salary data with Perplexity...")
          perplexity = PerplexityClient()
          salary_insights = {}
          current_salary = getattr(request.intake, 'current_salary_range', None)

          for role in target_roles[:3]:
              try:
                  salary_data = await perplexity.research_salary_insights(
                      job_title=role,
                      location=request.intake.location,
                      experience_level=f"{request.intake.years_experience} years, career changer from {request.intake.current_role_title}" if request.intake.years_experience else None
                  )
                  # Add career changer salary context
                  if current_salary and isinstance(salary_data, dict):
                      salary_data["current_salary"] = current_salary
                      salary_data["career_changer_note"] = f"Candidate currently earns {current_salary}. First-role salary as career changer may differ from established median."
                  salary_insights[role] = salary_data
                  logger.info(f"[Job {job_id}] ✓ Salary: {role} - {salary_data.get('salary_range', 'N/A')}")
              except Exception as e:
                  logger.warning(f"[Job {job_id}] Salary research failed for {role}: {e}")
                  salary_insights[role] = {
                      "salary_range": "Competitive",
                      "market_insights": "Data unavailable",
                      "sources": []
                  }

          research_data["salary_insights"] = salary_insights

          await job_manager.update_progress(db, job_id, 60, "Generating personalized career plan with AI")

          synthesis_service = CareerPathSynthesisService()
          synthesis_result = await synthesis_service.generate_career_plan(
              intake=request.intake,
              research_data=research_data,
              job_details=job_details
          )

          if not synthesis_result.get("success"):
              # Synthesis failed
              validation_errors = synthesis_result.get("validation_errors", [])
              if validation_errors:
                  logger.info(f"[Job {job_id}] ✗ Validation errors ({len(validation_errors)} total):")
                  for i, err in enumerate(validation_errors[:10]):
                      logger.error(f"    {i+1}. {err.get('field', 'unknown')}: {err.get('error', 'unknown')}")

              await job_manager.fail_job(db, job_id, synthesis_result.get("error", "Synthesis failed"))
              return

          plan_data = synthesis_result["plan"]

          await job_manager.update_progress(db, job_id, 80, "Plan validated - saving to database")

          # Step 3: Save to database
          career_plan = CareerPlanModel(
              session_user_id=user_id,
              intake_json=request.intake.dict(),
              research_json=research_data,
              plan_json=plan_data,
              version="1.0"
          )

          db.add(career_plan)
          await db.commit()
          await db.refresh(career_plan)

          logger.info(f"[Job {job_id}] Saved plan ID: {career_plan.id}")

          # Step 4: Mark job as completed
          await job_manager.complete_job(db, job_id, {
              "plan": plan_data,
              "plan_id": career_plan.id,
          })

      except Exception as e:
          logger.error(f"[Job {job_id}] Error: {e}")
          import traceback
          traceback.print_exc()

          await job_manager.fail_job(db, job_id, str(e))


@router.delete("/all")
async def delete_all_career_plans(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id)
):
    """
    Soft delete all career plans for the current user
    """

    try:
        result = await db.execute(
            update(CareerPlanModel)
            .where(
                CareerPlanModel.session_user_id == user_id,
                CareerPlanModel.is_deleted == False
            )
            .values(
                is_deleted=True,
                deleted_at=datetime.utcnow(),
                deleted_by=user_id
            )
        )
        await db.commit()

        return {"success": True, "message": f"All career plans deleted", "count": result.rowcount}

    except Exception as e:
        logger.error(f"Error deleting all plans: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete plans: {str(e)}"
        )


@router.delete("/{plan_id}")
async def delete_career_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id)
):
    """
    Soft delete a career plan
    """

    try:
        await db.execute(
            update(CareerPlanModel)
            .where(
                CareerPlanModel.id == plan_id,
                CareerPlanModel.session_user_id == user_id
            )
            .values(
                is_deleted=True,
                deleted_at=datetime.utcnow(),
                deleted_by=user_id
            )
        )
        await db.commit()

        return {"success": True, "message": "Career plan deleted"}

    except Exception as e:
        logger.error(f"Error deleting plan: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete plan: {str(e)}"
        )
