-- Migration: Add session_user_id column for session-based user isolation
-- Run this via run_migration.py or directly in Railway's PostgreSQL console
-- Date: 2026-01-14

-- Add session_user_id column to base_resumes table (nullable for existing records)
ALTER TABLE base_resumes
ADD COLUMN IF NOT EXISTS session_user_id VARCHAR;

-- Add session_user_id column to tailored_resumes table (nullable for existing records)
ALTER TABLE tailored_resumes
ADD COLUMN IF NOT EXISTS session_user_id VARCHAR;

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_base_resumes_session_user_id ON base_resumes(session_user_id);
CREATE INDEX IF NOT EXISTS idx_tailored_resumes_session_user_id ON tailored_resumes(session_user_id);

-- Success message
SELECT 'Migration completed successfully! session_user_id columns added.' AS status;
