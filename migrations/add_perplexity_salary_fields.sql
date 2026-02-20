-- Migration: Add Perplexity salary research fields to jobs table
-- Date: 2026-02-20
-- Description: Add fields to store Perplexity-researched salary data (median, insights, sources, timestamp)

-- Add median_salary column (e.g., "$150,000")
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS median_salary VARCHAR(100);

-- Add salary_insights column (market trends and analysis)
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_insights TEXT;

-- Add salary_sources column (JSON array of citation URLs)
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_sources TEXT;

-- Add salary_last_updated column (timestamp of Perplexity research)
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_last_updated TIMESTAMP;

-- Create index on salary_last_updated for cache invalidation queries
CREATE INDEX IF NOT EXISTS idx_jobs_salary_last_updated ON jobs(salary_last_updated);

-- Comment on columns for documentation
COMMENT ON COLUMN jobs.median_salary IS 'Median salary from Perplexity real-time research';
COMMENT ON COLUMN jobs.salary_insights IS 'Market insights and trends from Perplexity';
COMMENT ON COLUMN jobs.salary_sources IS 'JSON array of source URLs from Perplexity citations';
COMMENT ON COLUMN jobs.salary_last_updated IS 'Timestamp when salary data was last researched';
