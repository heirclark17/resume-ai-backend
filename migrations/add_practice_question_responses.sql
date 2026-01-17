-- Migration: Add PracticeQuestionResponse table
-- Date: 2026-01-16
-- Description: Adds functionality for storing practice question responses with AI-generated STAR stories and video/audio recordings

-- Create PracticeQuestionResponse table
CREATE TABLE IF NOT EXISTS practice_question_responses (
    id SERIAL PRIMARY KEY,
    interview_prep_id INTEGER NOT NULL REFERENCES interview_preps(id) ON DELETE CASCADE,

    -- Question details
    question_text TEXT NOT NULL,
    question_category VARCHAR(100),  -- behavioral, technical, situational, role_specific

    -- AI-generated STAR story for this question
    star_story JSONB,  -- {situation, task, action, result}

    -- User's response recordings
    audio_recording_url TEXT,
    video_recording_url TEXT,

    -- User's written notes/answer
    written_answer TEXT,

    -- Practice session metadata
    practice_duration_seconds INTEGER,
    times_practiced INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_practiced_at TIMESTAMP,

    -- Soft delete
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP
);

-- Create indexes for PracticeQuestionResponse
CREATE INDEX IF NOT EXISTS idx_practice_question_responses_interview_prep_id ON practice_question_responses(interview_prep_id);
CREATE INDEX IF NOT EXISTS idx_practice_question_responses_created_at ON practice_question_responses(created_at);
CREATE INDEX IF NOT EXISTS idx_practice_question_responses_is_deleted ON practice_question_responses(is_deleted);
CREATE INDEX IF NOT EXISTS idx_practice_question_responses_question_category ON practice_question_responses(question_category);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_practice_question_responses_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_practice_question_responses_updated_at
    BEFORE UPDATE ON practice_question_responses
    FOR EACH ROW
    EXECUTE FUNCTION update_practice_question_responses_updated_at();
