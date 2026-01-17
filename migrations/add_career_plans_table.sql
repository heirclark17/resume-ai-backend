-- Migration: Add career_plans table
-- Description: Stores AI-generated career path plans with intake, research, and synthesis data

CREATE TABLE IF NOT EXISTS career_plans (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    session_user_id VARCHAR(255) NOT NULL,

    -- JSON data columns
    intake_json JSONB NOT NULL,
    research_json JSONB,
    plan_json JSONB NOT NULL,

    -- Metadata
    version VARCHAR(10) DEFAULT '1.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Soft delete
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    deleted_by VARCHAR(255)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_career_plans_user_id ON career_plans(user_id);
CREATE INDEX IF NOT EXISTS idx_career_plans_session_user_id ON career_plans(session_user_id);
CREATE INDEX IF NOT EXISTS idx_career_plans_created_at ON career_plans(created_at);
CREATE INDEX IF NOT EXISTS idx_career_plans_is_deleted ON career_plans(is_deleted);

-- Trigger function to auto-update updated_at
CREATE OR REPLACE FUNCTION update_career_plans_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger
CREATE TRIGGER career_plans_updated_at_trigger
    BEFORE UPDATE ON career_plans
    FOR EACH ROW
    EXECUTE FUNCTION update_career_plans_updated_at();

COMMENT ON TABLE career_plans IS 'AI-generated career path plans with intake, research, and complete synthesis data';
COMMENT ON COLUMN career_plans.intake_json IS 'User input data from intake form';
COMMENT ON COLUMN career_plans.research_json IS 'Web-grounded facts from Perplexity (certs, events, education)';
COMMENT ON COLUMN career_plans.plan_json IS 'Complete career plan synthesized by OpenAI with strict schema validation';
