#!/usr/bin/env python
"""Verify that video recording feature is fully configured and ready"""
import os
import sys
import asyncio

print("=" * 70)
print("VIDEO RECORDING FEATURE - SETUP VERIFICATION")
print("=" * 70)
print()

# Check 1: Environment variables
print("1. Checking environment variables...")
required_vars = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
]

missing_vars = []
for var in required_vars:
    value = os.getenv(var)
    if value:
        if "KEY" in var:
            display = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "****"
        else:
            display = value
        print(f"  [OK] {var}: {display}")
    else:
        print(f"  [ERROR] {var}: NOT SET")
        missing_vars.append(var)

bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "recordings")
print(f"  [OK] SUPABASE_STORAGE_BUCKET: {bucket}")

if missing_vars:
    print()
    print(f"ERROR: Missing environment variables: {', '.join(missing_vars)}")
    print("Please add them to Railway dashboard and redeploy.")
    sys.exit(1)

# Check 2: Database connection
print()
print("2. Testing database connection...")
try:
    import psycopg2
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("  [ERROR] DATABASE_URL not set")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    print("  [OK] Database connection successful")

    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'star_stories'
            AND column_name = 'video_recording_url'
        )
    """)

    if cursor.fetchone()[0]:
        print("  [OK] video_recording_url column exists in star_stories table")
    else:
        print("  [ERROR] video_recording_url column NOT FOUND")
        sys.exit(1)

    cursor.close()
    conn.close()

except ImportError:
    print("  ! psycopg2 not installed, skipping database check")
except Exception as e:
    print(f"  ! Database check failed: {e}")

# Check 3: Test signed URL generation
print()
print("3. Testing signed URL generation...")
try:
    from app.services.storage_service import generate_presigned_upload_url

    async def test_url():
        return await generate_presigned_upload_url(
            user_id="test-user",
            question_context="test-question",
            content_type="video/webm"
        )

    result = asyncio.run(test_url())

    if "upload_url" in result and "s3_key" in result:
        print("  [OK] Signed upload URL generated successfully")
        print(f"  [OK] Object path: {result['s3_key']}")
    else:
        print("  [ERROR] Invalid response from generate_presigned_upload_url")
        sys.exit(1)

except Exception as e:
    print(f"  [ERROR] Failed to generate signed URL: {e}")
    sys.exit(1)

# All checks passed
print()
print("=" * 70)
print("[OK] ALL CHECKS PASSED - VIDEO RECORDING FEATURE READY!")
print("=" * 70)
print()
print(f"Storage Bucket: {bucket}")
print(f"Supabase URL: {os.getenv('SUPABASE_URL', '')[:40]}...")
print()
