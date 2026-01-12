-- Migration: Add Two-Factor Authentication (2FA) columns to users table
-- Date: 2026-01-11
-- Description: Adds TOTP secret, enabled flag, and backup codes storage

-- Add totp_secret column (stores encrypted TOTP secret key)
ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(255);

-- Add twofa_enabled column (boolean flag for 2FA status)
ALTER TABLE users ADD COLUMN IF NOT EXISTS twofa_enabled BOOLEAN DEFAULT FALSE;

-- Add twofa_backup_codes column (stores encrypted backup codes JSON)
ALTER TABLE users ADD COLUMN IF NOT EXISTS twofa_backup_codes TEXT;

-- Verify migration
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'users'
  AND column_name IN ('totp_secret', 'twofa_enabled', 'twofa_backup_codes')
ORDER BY ordinal_position;
