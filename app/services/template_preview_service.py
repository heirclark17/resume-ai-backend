"""
Template Preview Service

Generates AI-powered resume template preview images using OpenAI DALL-E
and stores them in Supabase Storage for reuse.
"""

import httpx
import base64
import os
from openai import AsyncOpenAI
from app.config import get_settings
from app.utils.logger import logger

BUCKET = "template-previews"

# Template visual descriptions for DALL-E prompt generation
TEMPLATE_PROMPTS = {
    "classic-professional": {
        "style": "classic corporate",
        "colors": "navy blue headings on white paper",
        "layout": "single column",
        "fonts": "serif headings, clean sans-serif body",
        "mood": "traditional, authoritative, timeless corporate feel",
    },
    "clean-minimal": {
        "style": "ultra-clean minimalist",
        "colors": "bright blue accents on crisp white, black text",
        "layout": "single column with generous spacing",
        "fonts": "modern sans-serif throughout",
        "mood": "airy, spacious, fresh and modern",
    },
    "traditional-serif": {
        "style": "traditional legal/finance",
        "colors": "all black text with subtle gray borders",
        "layout": "single column with bordered sections",
        "fonts": "elegant serif typography throughout like Times New Roman",
        "mood": "formal, prestigious, law firm or investment bank aesthetic",
    },
    "modern-two-column": {
        "style": "contemporary two-column",
        "colors": "blue accent sidebar on white, dark gray text",
        "layout": "two columns - left sidebar with contact and skills, right main content",
        "fonts": "Inter or modern sans-serif, clean and geometric",
        "mood": "tech-forward, organized, balanced modern professional",
    },
    "modern-accent": {
        "style": "bold modern with accent color",
        "colors": "vibrant indigo/purple accent headings on white, dark text",
        "layout": "single column with bold colored section headers and accent bar on left",
        "fonts": "Poppins-style rounded modern sans-serif headings",
        "mood": "creative tech, startup culture, energetic and bold",
    },
    "modern-sidebar": {
        "style": "modern with colored sidebar panel",
        "colors": "emerald green tinted sidebar panel on left, white main content area",
        "layout": "sidebar layout - left colored panel with contact/skills, right white main area",
        "fonts": "Montserrat-style geometric sans-serif",
        "mood": "design-conscious, creative professional, eye-catching",
    },
    "minimal-elegant": {
        "style": "luxury minimalist",
        "colors": "pure black headings on white with extreme whitespace",
        "layout": "single column with very generous margins and spacing",
        "fonts": "elegant thin sans-serif, large name in thin weight",
        "mood": "high-end luxury brand feel, like a fashion resume, refined elegance",
    },
    "minimal-line": {
        "style": "clean lines minimalist",
        "colors": "blue accent lines as dividers, dark text on white",
        "layout": "single column with thin line dividers between sections",
        "fonts": "Raleway-style modern sans-serif with clean geometric shapes",
        "mood": "structured yet minimal, clean and organized",
    },
    "executive-classic": {
        "style": "C-suite executive",
        "colors": "deep navy blue accent with gray borders, dark authoritative text",
        "layout": "single column with elegant borders around experience sections",
        "fonts": "Didot or Bodoni-style high-contrast serif headings, refined body text",
        "mood": "boardroom ready, authoritative leadership, Fortune 500 executive",
    },
    "executive-modern": {
        "style": "contemporary executive",
        "colors": "dark slate headings with subtle slate borders on white",
        "layout": "single column with divider lines between sections, sophisticated spacing",
        "fonts": "Playfair Display serif headings with modern sans-serif body",
        "mood": "modern leadership, sophisticated elegance, senior management",
    },
    "creative-bold": {
        "style": "bold creative",
        "colors": "amber/gold accent color on white, dark text, warm tones",
        "layout": "two columns - wider left column with skills in colored cards, right main content",
        "fonts": "Bebas Neue bold condensed headings, rounded body text",
        "mood": "graphic designer portfolio, bold and eye-catching, marketing professional",
    },
    "creative-portfolio": {
        "style": "artistic portfolio",
        "colors": "hot pink/magenta accent on white, playful warm color palette",
        "layout": "single column with artistic touches, rounded corners on elements",
        "fonts": "Abril Fatface display heading, Work Sans body",
        "mood": "art director, UX designer, creative agency, expressive and unique",
    },
    "tech-simple": {
        "style": "clean developer",
        "colors": "emerald green accents on white, dark text",
        "layout": "single column with line dividers, skills prominently featured",
        "fonts": "Fira Sans/Fira Code monospace accents for a developer feel",
        "mood": "software engineer, developer, GitHub profile aesthetic, clean and technical",
    },
    "balanced-professional": {
        "style": "balanced versatile",
        "colors": "royal blue accent headings on white, warm gray text",
        "layout": "single column with subtle dividers, well-balanced spacing",
        "fonts": "Merriweather serif headings with Open Sans body, professional mix",
        "mood": "works for any industry, polished and professional, reliable and trustworthy",
    },
    "corporate-standard": {
        "style": "standard corporate",
        "colors": "dark gray headings with gray borders, businesslike",
        "layout": "single column with bordered sections, traditional corporate structure",
        "fonts": "Calibri or Arial throughout, standard business fonts",
        "mood": "HR-friendly, safe corporate choice, standard business format",
    },
}


def _build_prompt(template_id: str) -> str:
    """Build a DALL-E prompt for a specific template."""
    info = TEMPLATE_PROMPTS.get(template_id)
    if not info:
        info = {
            "style": "professional",
            "colors": "blue accents on white",
            "layout": "single column",
            "fonts": "clean sans-serif",
            "mood": "professional and polished",
        }

    return (
        f"A photorealistic mockup of a professional resume template document on a clean white "
        f"background. The resume is a single sheet of US letter paper (8.5x11 inches) shown "
        f"at a slight angle with a subtle shadow. "
        f"Style: {info['style']}. "
        f"Color scheme: {info['colors']}. "
        f"Layout: {info['layout']}. "
        f"Typography: {info['fonts']}. "
        f"Overall mood: {info['mood']}. "
        f"The resume shows realistic placeholder content with a person's name, contact info, "
        f"professional summary, work experience with bullet points, skills section, and education. "
        f"The text should look realistic but doesn't need to be readable - focus on the visual "
        f"layout, typography hierarchy, spacing, and color scheme to make this template "
        f"visually distinctive. High quality, studio lighting, clean product photography style. "
        f"No watermarks, no hands, no desk items - just the resume document."
    )


async def _ensure_bucket_exists():
    """Create the template-previews bucket if it doesn't exist."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        logger.warning("Supabase not configured, skipping bucket creation")
        return False

    url = f"{settings.supabase_url}/storage/v1/bucket"
    async with httpx.AsyncClient() as client:
        # Check if bucket exists
        resp = await client.get(
            f"{url}/{BUCKET}",
            headers={"Authorization": f"Bearer {settings.supabase_service_role_key}"},
        )
        if resp.status_code == 200:
            logger.info(f"Bucket '{BUCKET}' already exists")
            return True

        # Create bucket
        resp = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": "application/json",
            },
            json={
                "id": BUCKET,
                "name": BUCKET,
                "public": True,
                "allowed_mime_types": ["image/png", "image/webp", "image/jpeg"],
                "file_size_limit": 10485760,
            },
        )
        if resp.status_code < 300:
            logger.info(f"Created bucket '{BUCKET}'")
            return True
        else:
            logger.error(f"Failed to create bucket: {resp.status_code} {resp.text}")
            return False


async def _upload_to_supabase(template_id: str, image_data: bytes) -> str:
    """Upload image bytes to Supabase Storage and return the public URL."""
    settings = get_settings()
    object_path = f"{template_id}.png"
    url = f"{settings.supabase_url}/storage/v1/object/{BUCKET}/{object_path}"

    async with httpx.AsyncClient() as client:
        resp = await client.put(
            url,
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": "image/png",
                "x-upsert": "true",
                "Cache-Control": "max-age=31536000",
            },
            content=image_data,
        )
        if resp.status_code >= 300:
            raise Exception(f"Upload failed: {resp.status_code} {resp.text}")

    public_url = f"{settings.supabase_url}/storage/v1/object/public/{BUCKET}/{object_path}"
    logger.info(f"Uploaded template preview: {public_url}")
    return public_url


async def generate_template_preview(template_id: str) -> dict:
    """Generate an AI preview image for a single template and upload it."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    prompt = _build_prompt(template_id)

    logger.info(f"Generating DALL-E preview for template: {template_id}")

    response = await client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1792",  # Portrait orientation (closest to letter paper)
        quality="hd",
        n=1,
        response_format="b64_json",
    )

    image_b64 = response.data[0].b64_json
    image_bytes = base64.b64decode(image_b64)

    # Ensure bucket exists then upload
    await _ensure_bucket_exists()
    public_url = await _upload_to_supabase(template_id, image_bytes)

    return {
        "template_id": template_id,
        "preview_url": public_url,
        "revised_prompt": response.data[0].revised_prompt,
    }


async def generate_all_previews() -> list[dict]:
    """Generate AI preview images for all templates."""
    results = []
    for template_id in TEMPLATE_PROMPTS:
        try:
            result = await generate_template_preview(template_id)
            results.append(result)
            logger.info(f"[OK] {template_id}: {result['preview_url']}")
        except Exception as e:
            logger.error(f"[FAIL] {template_id}: {e}")
            results.append({
                "template_id": template_id,
                "error": str(e),
            })
    return results


def get_preview_url(template_id: str) -> str:
    """Get the public URL for a template preview image."""
    settings = get_settings()
    return f"{settings.supabase_url}/storage/v1/object/public/{BUCKET}/{template_id}.png"


def get_all_preview_urls() -> dict[str, str]:
    """Get public URLs for all template previews."""
    return {tid: get_preview_url(tid) for tid in TEMPLATE_PROMPTS}
