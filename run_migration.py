#!/usr/bin/env python
"""Run database migration for interview prep cached data and career plans table"""
import os
import sys

print("Starting migration...")

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 not installed")
    sys.exit(1)

db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

print("Connecting to database...")
conn = psycopg2.connect(db_url)
cursor = conn.cursor()

# Check if interview_preps table exists
cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'interview_preps')")
if not cursor.fetchone()[0]:
    print("WARNING: interview_preps table does not exist")
else:
    print("Found interview_preps table")

# Add columns to interview_preps
columns = [
    'readiness_score_data',
    'values_alignment_data',
    'company_research_data',
    'strategic_news_data',
    'competitive_intelligence_data',
    'interview_strategy_data',
    'executive_insights_data',
    'certification_recommendations_data'
]

for col in columns:
    try:
        cursor.execute(f"ALTER TABLE interview_preps ADD COLUMN IF NOT EXISTS {col} JSONB DEFAULT NULL")
        print(f"  + {col}")
    except Exception as e:
        print(f"  ! {col}: {e}")

# Create career_plans table
print("Creating career_plans table...")
cursor.execute("""
CREATE TABLE IF NOT EXISTS career_plans (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    session_user_id VARCHAR(255) NOT NULL,
    intake_json JSONB NOT NULL,
    research_json JSONB,
    plan_json JSONB NOT NULL,
    version VARCHAR(10) DEFAULT '1.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    deleted_by VARCHAR(255)
)
""")
print("  + career_plans table created")

# Create indexes
cursor.execute("CREATE INDEX IF NOT EXISTS ix_career_plans_session_user_id ON career_plans(session_user_id)")
cursor.execute("CREATE INDEX IF NOT EXISTS ix_career_plans_is_deleted ON career_plans(is_deleted)")
cursor.execute("CREATE INDEX IF NOT EXISTS ix_career_plans_created_at ON career_plans(created_at)")
print("  + indexes created")

conn.commit()
conn.close()

print("Migration complete!")
