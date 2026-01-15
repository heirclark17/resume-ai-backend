-- Migration: Add SavedComparison and TailoredResumeEdit tables
-- Date: 2026-01-15
-- Description: Adds functionality for saving resume comparisons and tracking user edits

-- Create SavedComparison table
CREATE TABLE IF NOT EXISTS saved_comparisons (
    id SERIAL PRIMARY KEY,
    tailored_resume_id INTEGER NOT NULL REFERENCES tailored_resumes(id) ON DELETE CASCADE,
    session_user_id VARCHAR NOT NULL,

    -- User-defined metadata
    title VARCHAR,
    notes TEXT,
    tags TEXT,  -- JSON array

    -- Status tracking
    is_pinned BOOLEAN DEFAULT FALSE,

    -- Metadata
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_viewed_at TIMESTAMP,

    -- Soft delete
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP
);

-- Create indexes for SavedComparison
CREATE INDEX IF NOT EXISTS idx_saved_comparisons_tailored_resume_id ON saved_comparisons(tailored_resume_id);
CREATE INDEX IF NOT EXISTS idx_saved_comparisons_session_user_id ON saved_comparisons(session_user_id);
CREATE INDEX IF NOT EXISTS idx_saved_comparisons_is_pinned ON saved_comparisons(is_pinned);
CREATE INDEX IF NOT EXISTS idx_saved_comparisons_saved_at ON saved_comparisons(saved_at);
CREATE INDEX IF NOT EXISTS idx_saved_comparisons_is_deleted ON saved_comparisons(is_deleted);

-- Create TailoredResumeEdit table
CREATE TABLE IF NOT EXISTS tailored_resume_edits (
    id SERIAL PRIMARY KEY,
    tailored_resume_id INTEGER NOT NULL REFERENCES tailored_resumes(id) ON DELETE CASCADE,
    session_user_id VARCHAR NOT NULL,

    -- What was edited
    section_name VARCHAR NOT NULL,  -- "summary", "skills", "experience", "alignment_statement"
    section_index INTEGER,  -- For array sections

    -- Edit details
    original_content TEXT,
    edited_content TEXT NOT NULL,

    -- Metadata
    edited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    edit_type VARCHAR,  -- "modify", "add", "delete"

    -- Soft delete
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP
);

-- Create indexes for TailoredResumeEdit
CREATE INDEX IF NOT EXISTS idx_tailored_resume_edits_tailored_resume_id ON tailored_resume_edits(tailored_resume_id);
CREATE INDEX IF NOT EXISTS idx_tailored_resume_edits_session_user_id ON tailored_resume_edits(session_user_id);
CREATE INDEX IF NOT EXISTS idx_tailored_resume_edits_edited_at ON tailored_resume_edits(edited_at);
CREATE INDEX IF NOT EXISTS idx_tailored_resume_edits_is_deleted ON tailored_resume_edits(is_deleted);
