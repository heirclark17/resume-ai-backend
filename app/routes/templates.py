"""
Template Preview Routes

Endpoints for generating and retrieving AI-powered template preview images.
"""

from fastapi import APIRouter, HTTPException
from app.services.template_preview_service import (
    generate_template_preview,
    generate_all_previews,
    get_preview_url,
    get_all_preview_urls,
    TEMPLATE_PROMPTS,
)
from app.utils.logger import logger

router = APIRouter(prefix="/api/templates", tags=["Templates"])


@router.get("/previews")
async def list_preview_urls():
    """Get all template preview image URLs."""
    urls = get_all_preview_urls()
    return {"previews": urls}


@router.get("/previews/{template_id}")
async def get_preview(template_id: str):
    """Get the preview URL for a specific template."""
    if template_id not in TEMPLATE_PROMPTS:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return {"template_id": template_id, "preview_url": get_preview_url(template_id)}


@router.post("/generate-preview/{template_id}")
async def generate_single_preview(template_id: str):
    """Generate an AI preview image for a single template. Costs ~$0.08 per image."""
    if template_id not in TEMPLATE_PROMPTS:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")

    try:
        result = await generate_template_preview(template_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate preview for {template_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")


@router.post("/generate-all-previews")
async def generate_all():
    """Generate AI preview images for all 15 templates. Costs ~$1.20 total."""
    try:
        results = await generate_all_previews()
        successes = [r for r in results if "preview_url" in r]
        failures = [r for r in results if "error" in r]
        return {
            "total": len(results),
            "success": len(successes),
            "failed": len(failures),
            "results": results,
        }
    except Exception as e:
        logger.error(f"Failed to generate all previews: {e}")
        raise HTTPException(status_code=500, detail=str(e))
