"""Resume Builder AI Routes - Summary generation, bullet enhancement, skill suggestions"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.middleware.auth import get_user_id
from app.services.builder_ai_service import builder_ai_service
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/builder", tags=["Builder AI"])
logger = get_logger()
limiter = Limiter(key_func=get_remote_address)


class GenerateSummaryRequest(BaseModel):
    job_title: str
    years_experience: Optional[str] = ""
    highlights: Optional[list[str]] = None
    existing_skills: Optional[list[str]] = None
    tone: Optional[str] = "professional"


class EnhanceBulletsRequest(BaseModel):
    job_title: str
    company: str
    bullets: list[str]
    mode: Optional[str] = "enhance"


class SuggestSkillsRequest(BaseModel):
    job_title: str
    existing_skills: Optional[list[str]] = None
    experience_titles: Optional[list[str]] = None


@router.post("/generate-summary")
@limiter.limit("30/hour")
async def generate_summary(
    request: Request,
    body: GenerateSummaryRequest,
    user_id: str = Depends(get_user_id),
):
    """Generate 3 professional summary variants using AI."""
    try:
        logger.info(f"[Builder] Generating summaries for user={user_id}, title={body.job_title}")
        variants = await builder_ai_service.generate_summaries(
            job_title=body.job_title,
            years_experience=body.years_experience or "",
            highlights=body.highlights,
            existing_skills=body.existing_skills,
            tone=body.tone or "professional",
        )
        return {"variants": variants}
    except Exception as e:
        logger.error(f"[Builder] Summary generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate summary")


@router.post("/enhance-bullets")
@limiter.limit("30/hour")
async def enhance_bullets(
    request: Request,
    body: EnhanceBulletsRequest,
    user_id: str = Depends(get_user_id),
):
    """Enhance experience bullet points with AI."""
    try:
        logger.info(f"[Builder] Enhancing {len(body.bullets)} bullets for user={user_id}")
        enhanced = await builder_ai_service.enhance_bullets(
            job_title=body.job_title,
            company=body.company,
            bullets=body.bullets,
            mode=body.mode or "enhance",
        )
        return {"enhanced_bullets": enhanced}
    except Exception as e:
        logger.error(f"[Builder] Bullet enhancement failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to enhance bullets")


@router.post("/suggest-skills")
@limiter.limit("30/hour")
async def suggest_skills(
    request: Request,
    body: SuggestSkillsRequest,
    user_id: str = Depends(get_user_id),
):
    """Suggest categorized skills using AI."""
    try:
        logger.info(f"[Builder] Suggesting skills for user={user_id}, title={body.job_title}")
        result = await builder_ai_service.suggest_skills(
            job_title=body.job_title,
            existing_skills=body.existing_skills,
            experience_titles=body.experience_titles,
        )
        return result
    except Exception as e:
        logger.error(f"[Builder] Skill suggestion failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to suggest skills")
