-- Migration: Add missing columns to base_resumes and tailored_resumes tables
-- Fixed order: Add columns first, then create indexes

-- Step 1: Add all columns to base_resumes
ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS file_signature VARCHAR;
ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;
ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS deleted_by INTEGER REFERENCES users(id) ON DELETE SET NULL;

-- Step 2: Add all columns to tailored_resumes
ALTER TABLE tailored_resumes ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE tailored_resumes ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;
ALTER TABLE tailored_resumes ADD COLUMN IF NOT EXISTS deleted_by INTEGER REFERENCES users(id) ON DELETE SET NULL;

-- Step 3: Create indexes for base_resumes
CREATE INDEX IF NOT EXISTS idx_base_resumes_user_id ON base_resumes(user_id);
CREATE INDEX IF NOT EXISTS idx_base_resumes_is_deleted ON base_resumes(is_deleted);
CREATE INDEX IF NOT EXISTS idx_base_resumes_uploaded_at ON base_resumes(uploaded_at);

-- Step 4: Create indexes for tailored_resumes
CREATE INDEX IF NOT EXISTS idx_tailored_resumes_is_deleted ON tailored_resumes(is_deleted);
CREATE INDEX IF NOT EXISTS idx_tailored_resumes_base_resume_id ON tailored_resumes(base_resume_id);
CREATE INDEX IF NOT EXISTS idx_tailored_resumes_job_id ON tailored_resumes(job_id);
CREATE INDEX IF NOT EXISTS idx_tailored_resumes_quality_score ON tailored_resumes(quality_score);
CREATE INDEX IF NOT EXISTS idx_tailored_resumes_created_at ON tailored_resumes(created_at);

-- Success message
SELECT 'Migration completed successfully!' AS status;
