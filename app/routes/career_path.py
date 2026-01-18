"""
Career Path Designer API Routes
Orchestrates research -> synthesis -> validation -> storage
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List
from datetime import datetime
import os

from app.database import get_db, AsyncSessionLocal
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
from app.services.job_store import job_store


router = APIRouter(prefix="/api/career-path", tags=["career-path"])


def get_session_user_id() -> str:
    """Get session user ID (placeholder - integrate with auth later)"""
    # TODO: Integrate with actual auth system
    return "user_session_temp"


@router.post("/research")
async def research_career_path(
    request: ResearchRequest,
    db: AsyncSession = Depends(get_db)
) -> ResearchResponse:
    """
    PASS 1: Web-grounded research using Perplexity

    Returns verified facts about:
    - Certifications (with official links)
    - Education options (with program URLs)
    - Events (with registration links)
    """

    print(f"🔍 Starting research for roles: {', '.join(request.target_roles)}")

    try:
        research_service = CareerPathResearchService()

        # Run comprehensive research
        research_data = await research_service.research_all(
            target_roles=request.target_roles,
            location=request.location,
            current_experience=5.0,  # TODO: Get from intake
            current_education=request.education_level,
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
        print(f"✗ Research error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Research failed: {str(e)}"
        )


@router.post("/generate")
async def generate_career_plan(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db)
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

    session_user_id = get_session_user_id()

    print(f"📝 Generating career plan for {request.intake.current_role_title}")

    try:
        # Step 1: Research if not provided
        research_data = None
        skip_research = os.getenv("SKIP_RESEARCH", "false").lower() == "true"

        if request.research_data:
            research_data = request.research_data.dict()
        elif skip_research:
            # Skip research to avoid Railway timeout (60s limit)
            # Synthesis will work with empty research data
            print("  ⚠ Skipping research (SKIP_RESEARCH=true)")
            research_data = {
                "certifications": [],
                "education_options": [],
                "events": [],
                "research_sources": []
            }
        else:
            # Determine target roles for research
            target_roles = []
            if request.intake.target_role_interest:
                target_roles = [request.intake.target_role_interest]
            else:
                # Will be determined by AI synthesis
                # For research, use current role + industry as hint
                target_roles = [f"{request.intake.current_industry} Professional"]

            print(f"  Running research for: {', '.join(target_roles)}")
            research_service = CareerPathResearchService()
            research_result = await research_service.research_all(
                target_roles=target_roles,
                location=request.intake.location,
                current_experience=request.intake.years_experience,
                current_education=request.intake.education_level,
                budget="flexible",  # Budget field removed from intake form
                format_preference=request.intake.in_person_vs_remote
            )
            research_data = research_result

        # Step 2: Synthesize plan with OpenAI
        print(f"  Synthesizing plan with OpenAI...")
        synthesis_service = CareerPathSynthesisService()
        synthesis_result = await synthesis_service.generate_career_plan(
            intake=request.intake,
            research_data=research_data
        )

        if not synthesis_result.get("success"):
            # Log validation errors if present
            validation_errors = synthesis_result.get("validation_errors", [])
            if validation_errors:
                print(f"  ✗ Validation errors ({len(validation_errors)} total):")
                for i, err in enumerate(validation_errors[:10]):
                    print(f"    {i+1}. {err.get('field', 'unknown')}: {err.get('error', 'unknown')}")

            return GenerateResponse(
                success=False,
                error=synthesis_result.get("error", "Synthesis failed"),
                validation_errors=validation_errors if validation_errors else None
            )

        plan_data = synthesis_result["plan"]

        # Step 3: Validate (already done in synthesis service)
        print(f"  ✓ Plan validated")

        # Step 4: Save to database
        career_plan = CareerPlanModel(
            session_user_id=session_user_id,
            intake_json=request.intake.dict(),
            research_json=research_data,
            plan_json=plan_data,
            version="1.0"
        )

        db.add(career_plan)
        await db.commit()
        await db.refresh(career_plan)

        print(f"  ✓ Saved plan ID: {career_plan.id}")

        # Step 5: Return plan
        return GenerateResponse(
            success=True,
            plan=CareerPlan(**plan_data),
            plan_id=career_plan.id
        )

    except Exception as e:
        print(f"✗ Generation error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Plan generation failed: {str(e)}"
        )


@router.get("/{plan_id}")
async def get_career_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db)
) -> GenerateResponse:
    """
    Retrieve a previously generated career plan
    """

    session_user_id = get_session_user_id()

    try:
        result = await db.execute(
            select(CareerPlanModel).where(
                CareerPlanModel.id == plan_id,
                CareerPlanModel.session_user_id == session_user_id,
                CareerPlanModel.is_deleted == False
            )
        )

        plan = result.scalar_one_or_none()

        if not plan:
            raise HTTPException(status_code=404, detail="Career plan not found")

        return GenerateResponse(
            success=True,
            plan=CareerPlan(**plan.plan_json),
            plan_id=plan.id
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Error retrieving plan: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve plan: {str(e)}"
        )


@router.get("/")
async def list_career_plans(
    db: AsyncSession = Depends(get_db)
) -> List[CareerPlanListItem]:
    """
    List all career plans for the current user
    """

    session_user_id = get_session_user_id()

    try:
        result = await db.execute(
            select(CareerPlanModel)
            .where(
                CareerPlanModel.session_user_id == session_user_id,
                CareerPlanModel.is_deleted == False
            )
            .order_by(CareerPlanModel.created_at.desc())
        )

        plans = result.scalars().all()

        return [
            CareerPlanListItem(
                id=plan.id,
                target_roles=[
                    role["title"]
                    for role in plan.plan_json.get("target_roles", [])
                ],
                created_at=plan.created_at.isoformat(),
                updated_at=plan.updated_at.isoformat(),
                version=plan.version
            )
            for plan in plans
        ]

    except Exception as e:
        print(f"✗ Error listing plans: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list plans: {str(e)}"
        )


@router.post("/refresh-events")
async def refresh_events(
    request: RefreshEventsRequest,
    db: AsyncSession = Depends(get_db)
) -> GenerateResponse:
    """
    Refresh only the events section without regenerating entire plan

    Useful for updating event data as registration dates change
    """

    session_user_id = get_session_user_id()

    try:
        # Get existing plan
        result = await db.execute(
            select(CareerPlanModel).where(
                CareerPlanModel.id == request.plan_id,
                CareerPlanModel.session_user_id == session_user_id,
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
        print(f"🔄 Refreshing events for: {', '.join(target_roles)}")
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

        print(f"  ✓ Refreshed {len(new_events)} events")

        return GenerateResponse(
            success=True,
            plan=CareerPlan(**plan_data),
            plan_id=plan.id
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Error refreshing events: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh events: {str(e)}"
        )


@router.post("/generate-async")
async def generate_career_plan_async(
    request: GenerateRequest,
    background_tasks: BackgroundTasks
):
    """
    ASYNC: Start career plan generation and return job_id immediately

    This endpoint:
    1. Creates a background job
    2. Returns job_id immediately (no timeout)
    3. Runs Perplexity research + OpenAI synthesis in background
    4. Client polls /job/{job_id} for status
    """

    session_user_id = get_session_user_id()

    print(f"📝 Creating async job for {request.intake.current_role_title}")

    try:
        # Create job in job store
        job_id = job_store.create_job(
            user_id=session_user_id,
            intake_data=request.intake.dict()
        )

        # Start background task (no db session - task creates its own)
        background_tasks.add_task(
            process_career_plan_job,
            job_id,
            request
        )

        return {
            "success": True,
            "job_id": job_id,
            "message": "Job created - poll /api/career-path/job/{job_id} for status"
        }

    except Exception as e:
        print(f"✗ Error creating async job: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create job: {str(e)}"
        )


@router.post("/generate-tasks")
async def generate_tasks_for_role(request: dict):
    """
    Auto-generate typical tasks for a given job role using Perplexity AI

    Request body:
    - role_title: str (e.g., "Software Engineer", "Product Manager")
    - industry: str (optional, e.g., "Technology", "Healthcare")

    Returns:
    - tasks: List[str] (3-5 typical tasks for the role)
    """
    from app.services.perplexity_client import PerplexityClient

    role_title = request.get("role_title", "").strip()
    industry = request.get("industry", "").strip()

    if not role_title:
        raise HTTPException(status_code=400, detail="role_title is required")

    try:
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
            "tasks": tasks
        }

    except Exception as e:
        print(f"✗ Error generating tasks: {e}")
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
            "fallback": True
        }


@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """
    Get status of async career plan generation job

    Returns:
    - status: pending/researching/synthesizing/completed/failed
    - progress: 0-100
    - message: Current step
    - plan: Complete plan (when status=completed)
    - error: Error message (when status=failed)
    """

    job = job_store.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


async def process_career_plan_job(job_id: str, request: GenerateRequest):
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
          session_user_id = get_session_user_id()

          # Step 1: Research with Perplexity (if not provided)
          research_data = None

          if request.research_data:
              research_data = request.research_data.dict()
              job_store.update_job(
                  job_id,
                  status="researching",
                  progress=50,
                  message="Using provided research data"
              )
          else:
              # Determine target roles for research
              target_roles = []
              if request.intake.target_role_interest:
                  target_roles = [request.intake.target_role_interest]
              else:
                  # Use current role + industry as hint
                  target_roles = [f"{request.intake.current_industry} Professional"]

              print(f"  [Job {job_id}] Running Perplexity research for: {', '.join(target_roles)}")

              job_store.update_job(
                  job_id,
                  status="researching",
                  progress=10,
                  message=f"Researching certifications, education, and events for {', '.join(target_roles)}"
              )

              research_service = CareerPathResearchService()
              research_result = await research_service.research_all(
                  target_roles=target_roles,
                  location=request.intake.location,
                  current_experience=request.intake.years_experience,
                  current_education=request.intake.education_level,
                  budget="flexible",
                  format_preference=request.intake.in_person_vs_remote
              )
              research_data = research_result

              job_store.update_job(
                  job_id,
                  status="researching",
                  progress=50,
                  message="Research completed - starting plan synthesis",
                  research_data=research_data
              )

          # Step 2: Synthesize plan with OpenAI
          print(f"  [Job {job_id}] Synthesizing plan with OpenAI GPT-4.1-mini...")

          job_store.update_job(
              job_id,
              status="synthesizing",
              progress=60,
              message="Generating personalized career plan with AI"
          )

          synthesis_service = CareerPathSynthesisService()
          synthesis_result = await synthesis_service.generate_career_plan(
              intake=request.intake,
              research_data=research_data
          )

          if not synthesis_result.get("success"):
              # Synthesis failed
              validation_errors = synthesis_result.get("validation_errors", [])
              if validation_errors:
                  print(f"  [Job {job_id}] ✗ Validation errors ({len(validation_errors)} total):")
                  for i, err in enumerate(validation_errors[:10]):
                      print(f"    {i+1}. {err.get('field', 'unknown')}: {err.get('error', 'unknown')}")

              job_store.update_job(
                  job_id,
                  status="failed",
                  progress=100,
                  message="Plan generation failed",
                  error=synthesis_result.get("error", "Synthesis failed")
              )
              return

          plan_data = synthesis_result["plan"]

          job_store.update_job(
              job_id,
              status="synthesizing",
              progress=80,
              message="Plan validated - saving to database"
          )

          # Step 3: Save to database
          career_plan = CareerPlanModel(
              session_user_id=session_user_id,
              intake_json=request.intake.dict(),
              research_json=research_data,
              plan_json=plan_data,
              version="1.0"
          )

          db.add(career_plan)
          await db.commit()
          await db.refresh(career_plan)

          print(f"  [Job {job_id}] ✓ Saved plan ID: {career_plan.id}")

          # Step 4: Mark job as completed
          job_store.update_job(
              job_id,
              status="completed",
              progress=100,
              message="Career plan generated successfully",
              plan=plan_data,
              plan_id=career_plan.id
          )

      except Exception as e:
          print(f"✗ [Job {job_id}] Error: {e}")
          import traceback
          traceback.print_exc()

          job_store.update_job(
              job_id,
              status="failed",
              progress=100,
              message="Job failed",
              error=str(e)
          )


@router.delete("/{plan_id}")
async def delete_career_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Soft delete a career plan
    """

    session_user_id = get_session_user_id()

    try:
        await db.execute(
            update(CareerPlanModel)
            .where(
                CareerPlanModel.id == plan_id,
                CareerPlanModel.session_user_id == session_user_id
            )
            .values(
                is_deleted=True,
                deleted_at=datetime.utcnow(),
                deleted_by=session_user_id
            )
        )
        await db.commit()

        return {"success": True, "message": "Career plan deleted"}

    except Exception as e:
        print(f"✗ Error deleting plan: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete plan: {str(e)}"
        )
