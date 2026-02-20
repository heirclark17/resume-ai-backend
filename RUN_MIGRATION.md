# Run Database Migration

## Migration: add_perplexity_salary_fields.sql

### Purpose
Add Perplexity salary research fields to the `jobs` table for storing real-time salary data from batch tailor operations.

### How to Run (Railway Dashboard)

1. **Go to Railway Dashboard:**
   - Navigate to: https://railway.app/
   - Select your project: `resume-ai-backend`
   - Click on the PostgreSQL service

2. **Connect to Database:**
   - Click "Connect" tab
   - Click "Connect via psql" or use the connection string

3. **Run Migration:**
   ```bash
   # Copy the SQL from migrations/add_perplexity_salary_fields.sql
   # Paste into Railway psql terminal or run:

   psql $DATABASE_URL -f migrations/add_perplexity_salary_fields.sql
   ```

### Alternative: Run Locally

If you have the DATABASE_URL from Railway:

```bash
cd backend
psql "postgresql://..." -f migrations/add_perplexity_salary_fields.sql
```

### Verify Migration

Check that the columns were added:

```sql
\d jobs

-- Should show:
-- - median_salary (varchar)
-- - salary_insights (text)
-- - salary_sources (text)
-- - salary_last_updated (timestamp)
```

### Rollback (if needed)

```sql
ALTER TABLE jobs DROP COLUMN IF EXISTS median_salary;
ALTER TABLE jobs DROP COLUMN IF EXISTS salary_insights;
ALTER TABLE jobs DROP COLUMN IF EXISTS salary_sources;
ALTER TABLE jobs DROP COLUMN IF EXISTS salary_last_updated;
DROP INDEX IF EXISTS idx_jobs_salary_last_updated;
```

## After Migration

The salary data will be automatically populated when:
- Users batch tailor resumes
- Individual resumes are tailored
- Job URLs are processed

The data is cached (reused if already exists) to avoid redundant Perplexity API calls.
