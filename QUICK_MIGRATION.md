# Quick Migration Instructions

## Run this in your terminal (takes 30 seconds):

1. Open your terminal/command prompt
2. Navigate to backend folder:
   ```bash
   cd C:\Users\derri\projects\resume-ai-app\backend
   ```

3. Link to Railway project (select "distinguished-illumination"):
   ```bash
   railway link
   ```
   Use arrow keys to select "distinguished-illumination" and press Enter.

4. Run the migration:
   ```bash
   railway run psql -c "ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE; ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS file_signature VARCHAR; ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE; ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP; ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS deleted_by INTEGER REFERENCES users(id) ON DELETE SET NULL; CREATE INDEX IF NOT EXISTS idx_base_resumes_user_id ON base_resumes(user_id); CREATE INDEX IF NOT EXISTS idx_base_resumes_is_deleted ON base_resumes(is_deleted); CREATE INDEX IF NOT EXISTS idx_base_resumes_uploaded_at ON base_resumes(uploaded_at); ALTER TABLE tailored_resumes ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE; ALTER TABLE tailored_resumes ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP; ALTER TABLE tailored_resumes ADD COLUMN IF NOT EXISTS deleted_by INTEGER REFERENCES users(id) ON DELETE SET NULL; CREATE INDEX IF NOT EXISTS idx_tailored_resumes_is_deleted ON tailored_resumes(is_deleted); CREATE INDEX IF NOT EXISTS idx_tailored_resumes_base_resume_id ON tailored_resumes(base_resume_id); CREATE INDEX IF NOT EXISTS idx_tailored_resumes_job_id ON tailored_resumes(job_id); CREATE INDEX IF NOT EXISTS idx_tailored_resumes_quality_score ON tailored_resumes(quality_score); CREATE INDEX IF NOT EXISTS idx_tailored_resumes_created_at ON tailored_resumes(created_at);"
   ```

Done! Your uploads will work after this.
