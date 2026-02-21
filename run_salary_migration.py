#!/usr/bin/env python
"""Run salary fields migration directly to Railway PostgreSQL"""
import psycopg2
import sys

# Database connection string (Railway)
DATABASE_URL = "postgresql://postgres:SUCByvKQvPeSxnLxystaiyRvEMpRvDUn@switchyard.proxy.rlwy.net:54571/railway"

print("=" * 70)
print("RUNNING SALARY FIELDS DATABASE MIGRATION")
print("=" * 70)
print()

try:
    # Connect to database
    print("1. Connecting to Railway PostgreSQL database...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    print("   [OK] Connected successfully")
    print()

    # Run migration: Add median_salary column
    print("2. Adding median_salary column to jobs table...")
    cursor.execute("""
        ALTER TABLE jobs ADD COLUMN IF NOT EXISTS median_salary VARCHAR(100);
    """)
    conn.commit()
    print("   [OK] median_salary column added (or already exists)")
    print()

    # Add salary_insights column
    print("3. Adding salary_insights column to jobs table...")
    cursor.execute("""
        ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_insights TEXT;
    """)
    conn.commit()
    print("   [OK] salary_insights column added (or already exists)")
    print()

    # Add salary_sources column
    print("4. Adding salary_sources column to jobs table...")
    cursor.execute("""
        ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_sources TEXT;
    """)
    conn.commit()
    print("   [OK] salary_sources column added (or already exists)")
    print()

    # Add salary_last_updated column
    print("5. Adding salary_last_updated column to jobs table...")
    cursor.execute("""
        ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_last_updated TIMESTAMP;
    """)
    conn.commit()
    print("   [OK] salary_last_updated column added (or already exists)")
    print()

    # Create index
    print("6. Creating index on salary_last_updated...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_salary_last_updated
        ON jobs(salary_last_updated);
    """)
    conn.commit()
    print("   [OK] Index created (or already exists)")
    print()

    # Add column comments
    print("7. Adding column comments for documentation...")
    cursor.execute("""
        COMMENT ON COLUMN jobs.median_salary IS 'Median salary from Perplexity real-time research';
        COMMENT ON COLUMN jobs.salary_insights IS 'Market insights and trends from Perplexity';
        COMMENT ON COLUMN jobs.salary_sources IS 'JSON array of source URLs from Perplexity citations';
        COMMENT ON COLUMN jobs.salary_last_updated IS 'Timestamp when salary data was last researched';
    """)
    conn.commit()
    print("   [OK] Column comments added")
    print()

    # Verify columns exist
    print("8. Verifying migration...")
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'jobs'
        AND column_name IN ('median_salary', 'salary_insights', 'salary_sources', 'salary_last_updated')
        ORDER BY column_name;
    """)

    results = cursor.fetchall()
    if len(results) == 4:
        print(f"   [OK] All 4 columns verified:")
        for column_name, data_type, is_nullable in results:
            print(f"     - {column_name}: {data_type} (nullable: {is_nullable})")
    else:
        print(f"   [WARNING] Expected 4 columns, found {len(results)}")

    # Close connection
    cursor.close()
    conn.close()

    print()
    print("=" * 70)
    print("[SUCCESS] SALARY FIELDS MIGRATION COMPLETED!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Redeploy backend on Railway (or it will auto-deploy)")
    print("2. Test interview prep list endpoint in mobile app")
    print("3. Salary data will populate when jobs are processed")
    print()

except Exception as e:
    print(f"[ERROR] Migration failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
