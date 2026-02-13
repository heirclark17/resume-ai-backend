-- Migration: Interview Prep Cached Data + Career Plans Table
-- Purpose: Store AI-generated data persistently
-- Run this migration on your production PostgreSQL/Supabase database

-- =====================================================
-- PART 1: Add columns to interview_preps table
-- =====================================================

ALTER TABLE interview_preps
ADD COLUMN IF NOT EXISTS readiness_score_data JSONB DEFAULT NULL,
ADD COLUMN IF NOT EXISTS values_alignment_data JSONB DEFAULT NULL,
ADD COLUMN IF NOT EXISTS company_research_data JSONB DEFAULT NULL,
ADD COLUMN IF NOT EXISTS strategic_news_data JSONB DEFAULT NULL,
ADD COLUMN IF NOT EXISTS competitive_intelligence_data JSONB DEFAULT NULL,
ADD COLUMN IF NOT EXISTS interview_strategy_data JSONB DEFAULT NULL,
ADD COLUMN IF NOT EXISTS executive_insights_data JSONB DEFAULT NULL,
ADD COLUMN IF NOT EXISTS certification_recommendations_data JSONB DEFAULT NULL;

-- Add comments for documentation
COMMENT ON COLUMN interview_preps.readiness_score_data IS 'Cached interview readiness score from AI';
COMMENT ON COLUMN interview_preps.values_alignment_data IS 'Cached values alignment scorecard from AI';
COMMENT ON COLUMN interview_preps.company_research_data IS 'Cached company research data';
COMMENT ON COLUMN interview_preps.strategic_news_data IS 'Cached strategic news items';
COMMENT ON COLUMN interview_preps.competitive_intelligence_data IS 'Cached competitive intelligence data';
COMMENT ON COLUMN interview_preps.interview_strategy_data IS 'Cached interview strategy recommendations';
COMMENT ON COLUMN interview_preps.executive_insights_data IS 'Cached executive insights';
COMMENT ON COLUMN interview_preps.certification_recommendations_data IS 'Cached certification recommendations';

-- =====================================================
-- PART 2: Create career_plans table (if not exists)
-- =====================================================

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
);

-- Create indexes for career_plans
CREATE INDEX IF NOT EXISTS ix_career_plans_session_user_id ON career_plans(session_user_id);
CREATE INDEX IF NOT EXISTS ix_career_plans_is_deleted ON career_plans(is_deleted);
CREATE INDEX IF NOT EXISTS ix_career_plans_created_at ON career_plans(created_at);

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Verify interview_preps columns were added
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'interview_preps'
AND column_name LIKE '%_data'
ORDER BY column_name;

-- Verify career_plans table exists
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'career_plans'
ORDER BY ordinal_position;
