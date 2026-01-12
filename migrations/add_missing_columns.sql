-- Migration: Add missing columns to base_resumes table
-- Run this in Railway's PostgreSQL console or via psql

-- Add user_id column (nullable for existing records)
ALTER TABLE base_resumes
ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;

-- Add file_signature column for integrity checking
ALTER TABLE base_resumes
ADD COLUMN IF NOT EXISTS file_signature VARCHAR;

-- Add soft delete columns for audit trail
ALTER TABLE base_resumes
ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;

ALTER TABLE base_resumes
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

ALTER TABLE base_resumes
ADD COLUMN IF NOT EXISTS deleted_by INTEGER REFERENCES users(id) ON DELETE SET NULL;

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_base_resumes_user_id ON base_resumes(user_id);
CREATE INDEX IF NOT EXISTS idx_base_resumes_is_deleted ON base_resumes(is_deleted);
CREATE INDEX IF NOT EXISTS idx_base_resumes_uploaded_at ON base_resumes(uploaded_at);

-- Do the same for tailored_resumes table
ALTER TABLE tailored_resumes
ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;

ALTER TABLE tailored_resumes
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

ALTER TABLE tailored_resumes
ADD COLUMN IF NOT EXISTS deleted_by INTEGER REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_tailored_resumes_is_deleted ON tailored_resumes(is_deleted);
CREATE INDEX IF NOT EXISTS idx_tailored_resumes_base_resume_id ON tailored_resumes(base_resume_id);
CREATE INDEX IF NOT EXISTS idx_tailored_resumes_job_id ON tailored_resumes(job_id);
CREATE INDEX IF NOT EXISTS idx_tailored_resumes_quality_score ON tailored_resumes(quality_score);
CREATE INDEX IF NOT EXISTS idx_tailored_resumes_created_at ON tailored_resumes(created_at);

-- Success message
SELECT 'Migration completed successfully!' AS status;
