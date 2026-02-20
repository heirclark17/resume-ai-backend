#!/usr/bin/env python
"""Run database migration directly using provided connection string"""
import psycopg2
import sys

# Database connection string
DATABASE_URL = "postgresql://postgres:SUCByvKQvPeSxnLxystaiyRvEMpRvDUn@switchyard.proxy.rlwy.net:54571/railway"

print("=" * 70)
print("RUNNING VIDEO RECORDING DATABASE MIGRATION")
print("=" * 70)
print()

try:
    # Connect to database
    print("1. Connecting to Railway PostgreSQL database...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    print("   [OK] Connected successfully")
    print()

    # Run migration: Add column
    print("2. Adding video_recording_url column to star_stories table...")
    cursor.execute("""
        ALTER TABLE star_stories ADD COLUMN IF NOT EXISTS video_recording_url TEXT;
    """)
    conn.commit()
    print("   [OK] Column added (or already exists)")
    print()

    # Create index
    print("3. Creating index for faster lookups...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_star_stories_video_recording_url
        ON star_stories(video_recording_url)
        WHERE video_recording_url IS NOT NULL;
    """)
    conn.commit()
    print("   [OK] Index created (or already exists)")
    print()

    # Verify column exists
    print("4. Verifying migration...")
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'star_stories'
        AND column_name = 'video_recording_url';
    """)

    result = cursor.fetchone()
    if result:
        column_name, data_type, is_nullable = result
        print(f"   [OK] Column verified:")
        print(f"     - Name: {column_name}")
        print(f"     - Type: {data_type}")
        print(f"     - Nullable: {is_nullable}")
    else:
        print("   [ERROR] Column not found!")
        sys.exit(1)

    # Close connection
    cursor.close()
    conn.close()

    print()
    print("=" * 70)
    print("[SUCCESS] MIGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Test at https://talorme.com")
    print("2. Go to: Interview Prep > Behavioral/Technical Questions")
    print("3. Expand a question and click 'Record Practice'")
    print("4. Test recording, playback, and delete functions")
    print()

except Exception as e:
    print(f"[ERROR] Migration failed: {e}")
    sys.exit(1)
