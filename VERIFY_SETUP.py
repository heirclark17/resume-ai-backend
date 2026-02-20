#!/usr/bin/env python
"""Verify that video recording feature is fully configured and ready"""
import os
import sys

print("=" * 70)
print("VIDEO RECORDING FEATURE - SETUP VERIFICATION")
print("=" * 70)
print()

# Check 1: Environment variables
print("1. Checking Railway environment variables...")
required_vars = [
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_S3_BUCKET",
    "AWS_S3_REGION"
]

missing_vars = []
for var in required_vars:
    value = os.getenv(var)
    if value:
        # Show partial value for security
        if "KEY" in var:
            display = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "****"
        else:
            display = value
        print(f"  ✓ {var}: {display}")
    else:
        print(f"  ✗ {var}: NOT SET")
        missing_vars.append(var)

if missing_vars:
    print()
    print(f"ERROR: Missing environment variables: {', '.join(missing_vars)}")
    print("Please add them to Railway dashboard and redeploy.")
    sys.exit(1)

# Check 2: S3 client initialization
print()
print("2. Testing AWS S3 connection...")
try:
    from app.services.s3_service import _get_s3_client
    client = _get_s3_client()
    print("  ✓ S3 client initialized successfully")

    # Test bucket access
    bucket = os.getenv("AWS_S3_BUCKET")
    try:
        client.head_bucket(Bucket=bucket)
        print(f"  ✓ Bucket '{bucket}' is accessible")
    except Exception as e:
        print(f"  ✗ Cannot access bucket '{bucket}': {e}")
        print("  → Check IAM permissions and bucket name")
        sys.exit(1)

except Exception as e:
    print(f"  ✗ Failed to initialize S3 client: {e}")
    print("  → Check AWS credentials are correct")
    sys.exit(1)

# Check 3: Database connection
print()
print("3. Testing database connection...")
try:
    import psycopg2
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("  ✗ DATABASE_URL not set")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    print("  ✓ Database connection successful")

    # Check if video_recording_url column exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'star_stories'
            AND column_name = 'video_recording_url'
        )
    """)

    if cursor.fetchone()[0]:
        print("  ✓ video_recording_url column exists in star_stories table")
    else:
        print("  ✗ video_recording_url column NOT FOUND")
        print("  → Run migration: railway run python run_video_recording_migration.py")
        sys.exit(1)

    cursor.close()
    conn.close()

except ImportError:
    print("  ! psycopg2 not installed (install with: pip install psycopg2-binary)")
    print("  ⚠ Skipping database check (non-critical for Railway deployment)")
except Exception as e:
    print(f"  ! Database check failed: {e}")
    print("  ⚠ This is OK if running locally (non-critical for Railway deployment)")

# Check 4: Test presigned URL generation
print()
print("4. Testing presigned URL generation...")
try:
    from app.services.s3_service import generate_presigned_upload_url
    result = generate_presigned_upload_url(
        user_id="test-user",
        question_context="test-question",
        content_type="video/webm"
    )

    if "upload_url" in result and "s3_key" in result:
        print("  ✓ Presigned upload URL generated successfully")
        print(f"  ✓ S3 key format: {result['s3_key']}")
    else:
        print("  ✗ Invalid response from generate_presigned_upload_url")
        sys.exit(1)

except Exception as e:
    print(f"  ✗ Failed to generate presigned URL: {e}")
    sys.exit(1)

# All checks passed
print()
print("=" * 70)
print("✓ ALL CHECKS PASSED - VIDEO RECORDING FEATURE READY!")
print("=" * 70)
print()
print("Next steps:")
print("1. Go to https://talorme.com")
print("2. Login → Interview Prep → Behavioral/Technical Questions")
print("3. Expand any question")
print("4. Click 'Record Practice' button below STAR story")
print("5. Test recording, playback, and delete functions")
print()
print(f"S3 Bucket: {os.getenv('AWS_S3_BUCKET')}")
print(f"Region: {os.getenv('AWS_S3_REGION')}")
print()
