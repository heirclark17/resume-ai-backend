import httpx
from uuid import uuid4
from app.config import get_settings
from app.utils.logger import logger


async def generate_presigned_upload_url(
    user_id: str, question_context: str, content_type: str
) -> dict:
    """Generate a signed upload URL for direct browser-to-Supabase upload.

    Returns { upload_url, s3_key } with a 15-minute expiry.
    The s3_key is the object path inside the bucket.
    """
    settings = get_settings()
    ext = "webm" if "webm" in content_type else "mp4"
    object_path = f"recordings/{user_id}/{question_context}/{uuid4()}.{ext}"

    url = (
        f"{settings.supabase_url}/storage/v1/object/upload/sign"
        f"/{settings.supabase_storage_bucket}/{object_path}"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": "application/json",
            },
            json={"expiresIn": 900},
        )
        resp.raise_for_status()
        data = resp.json()

    # Supabase returns { url: "/object/upload/sign/..." } — prepend base
    signed_path = data.get("url", "")
    if signed_path.startswith("/"):
        upload_url = f"{settings.supabase_url}/storage/v1{signed_path}"
    else:
        upload_url = signed_path

    logger.info(f"Generated signed upload URL for path: {object_path}")
    return {"upload_url": upload_url, "s3_key": object_path}


async def generate_presigned_download_url(s3_key: str) -> str:
    """Generate a signed download URL for playback (1-hour expiry)."""
    settings = get_settings()

    url = (
        f"{settings.supabase_url}/storage/v1/object/sign"
        f"/{settings.supabase_storage_bucket}/{s3_key}"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": "application/json",
            },
            json={"expiresIn": 3600},
        )
        resp.raise_for_status()
        data = resp.json()

    signed_path = data.get("signedURL", "") or data.get("signedUrl", "")
    if signed_path.startswith("/"):
        download_url = f"{settings.supabase_url}/storage/v1{signed_path}"
    else:
        download_url = signed_path

    logger.info(f"Generated signed download URL for path: {s3_key}")
    return download_url


async def delete_object(s3_key: str) -> bool:
    """Delete an object from Supabase Storage. Returns True on success."""
    settings = get_settings()

    url = (
        f"{settings.supabase_url}/storage/v1/object"
        f"/{settings.supabase_storage_bucket}"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            url,
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": "application/json",
            },
            json={"prefixes": [s3_key]},
        )

    if resp.status_code < 300:
        logger.info(f"Deleted storage object: {s3_key}")
        return True
    else:
        logger.error(f"Failed to delete storage object {s3_key}: {resp.status_code} {resp.text}")
        return False
