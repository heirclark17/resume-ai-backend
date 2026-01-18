"""
Career Path Designer API Routes
Orchestrates research -> synthesis -> validation -> storage
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List
from datetime import datetime

from app.database import get_db
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
        if request.research_data:
            research_data = request.research_data.dict()
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
            return GenerateResponse(
                success=False,
                error=synthesis_result.get("error", "Synthesis failed")
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
