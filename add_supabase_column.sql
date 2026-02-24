-- Add supabase_id column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS supabase_id VARCHAR;

-- Create unique index on supabase_id
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_supabase_id ON users(supabase_id);
