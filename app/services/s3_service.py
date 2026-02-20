import boto3
from botocore.exceptions import ClientError
from uuid import uuid4
from app.config import get_settings
from app.utils.logger import logger


def _get_s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        region_name=settings.aws_s3_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def generate_presigned_upload_url(
    user_id: str, question_context: str, content_type: str
) -> dict:
    """Generate a presigned URL for direct browser-to-S3 upload.

    Returns { upload_url, s3_key } with a 15-minute expiry.
    """
    settings = get_settings()
    ext = "webm" if "webm" in content_type else "mp4"
    s3_key = f"recordings/{user_id}/{question_context}/{uuid4()}.{ext}"

    client = _get_s3_client()
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.aws_s3_bucket,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=900,  # 15 minutes
    )
    logger.info(f"Generated presigned upload URL for key: {s3_key}")
    return {"upload_url": upload_url, "s3_key": s3_key}


def generate_presigned_download_url(s3_key: str) -> str:
    """Generate a presigned URL for playback (1-hour expiry)."""
    settings = get_settings()
    client = _get_s3_client()
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.aws_s3_bucket, "Key": s3_key},
        ExpiresIn=3600,  # 1 hour
    )
    logger.info(f"Generated presigned download URL for key: {s3_key}")
    return url


def delete_object(s3_key: str) -> bool:
    """Delete an object from S3. Returns True on success."""
    settings = get_settings()
    client = _get_s3_client()
    try:
        client.delete_object(Bucket=settings.aws_s3_bucket, Key=s3_key)
        logger.info(f"Deleted S3 object: {s3_key}")
        return True
    except ClientError as e:
        logger.error(f"Failed to delete S3 object {s3_key}: {e}")
        return False
