#!/usr/bin/env python
"""Run database migration to add video_recording_url column to star_stories table"""
import os
import sys

print("Starting video recording migration...")

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 not installed. Installing...")
    os.system("pip install psycopg2-binary")
    import psycopg2

db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print("ERROR: DATABASE_URL not set")
    print("Please set DATABASE_URL environment variable with your Railway PostgreSQL connection string")
    sys.exit(1)

print(f"Connecting to database...")
try:
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    print("✓ Connected successfully")
except Exception as e:
    print(f"ERROR: Failed to connect to database: {e}")
    sys.exit(1)

# Check if star_stories table exists
print("\nChecking if star_stories table exists...")
cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'star_stories')")
if not cursor.fetchone()[0]:
    print("ERROR: star_stories table does not exist")
    sys.exit(1)
else:
    print("✓ Found star_stories table")

# Check if column already exists
print("\nChecking if video_recording_url column exists...")
cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.columns
        WHERE table_name = 'star_stories'
        AND column_name = 'video_recording_url'
    )
""")
column_exists = cursor.fetchone()[0]

if column_exists:
    print("✓ video_recording_url column already exists - skipping")
else:
    # Add video_recording_url column
    print("\nAdding video_recording_url column...")
    try:
        cursor.execute("ALTER TABLE star_stories ADD COLUMN video_recording_url TEXT")
        conn.commit()
        print("✓ Added video_recording_url column")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: Failed to add column: {e}")
        sys.exit(1)

# Create index if it doesn't exist
print("\nCreating index on video_recording_url...")
try:
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_star_stories_video_recording_url
        ON star_stories(video_recording_url)
        WHERE video_recording_url IS NOT NULL
    """)
    conn.commit()
    print("✓ Created index")
except Exception as e:
    conn.rollback()
    print(f"WARNING: Failed to create index (non-critical): {e}")

# Verify the migration
print("\nVerifying migration...")
cursor.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'star_stories'
    AND column_name = 'video_recording_url'
""")
result = cursor.fetchone()
if result:
    print(f"✓ Column verified: {result[0]} ({result[1]}, nullable={result[2]})")
else:
    print("ERROR: Column verification failed")
    sys.exit(1)

cursor.close()
conn.close()

print("\n" + "="*60)
print("✓ MIGRATION COMPLETED SUCCESSFULLY")
print("="*60)
print("\nNext steps:")
print("1. Set up AWS S3 bucket (see AWS_S3_SETUP.md)")
print("2. Add AWS environment variables to Railway")
print("3. Test video recording feature")
