-- Migration: Add AI analysis data columns to saved_comparisons
-- Purpose: Store AI-generated analysis, keywords, and match scores with saved comparisons
-- Date: 2026-01-15

-- Add columns for AI analysis data
ALTER TABLE saved_comparisons
ADD COLUMN IF NOT EXISTS analysis_data TEXT,
ADD COLUMN IF NOT EXISTS keywords_data TEXT,
ADD COLUMN IF NOT EXISTS match_score_data TEXT;

-- Add indexes for performance (these columns will be queried frequently)
CREATE INDEX IF NOT EXISTS idx_saved_comparisons_has_analysis
ON saved_comparisons ((analysis_data IS NOT NULL));

-- Comment columns for documentation
COMMENT ON COLUMN saved_comparisons.analysis_data IS 'JSON: AI change analysis with explanations for each section modification';
COMMENT ON COLUMN saved_comparisons.keywords_data IS 'JSON: Keyword extraction and matching results from job description';
COMMENT ON COLUMN saved_comparisons.match_score_data IS 'JSON: Overall match score and detailed scoring breakdown';
