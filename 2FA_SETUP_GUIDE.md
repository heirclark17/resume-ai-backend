# Two-Factor Authentication (2FA) Setup Guide

## Overview

TOTP-based two-factor authentication has been added to enhance account security. Users can enable 2FA using authenticator apps like Google Authenticator, Authy, or Microsoft Authenticator.

---

## Database Migration

### New Columns Added to users Table

The User model now includes three new columns for 2FA:

```sql
-- Add 2FA columns to users table
ALTER TABLE users ADD COLUMN totp_secret VARCHAR(255);
ALTER TABLE users ADD COLUMN twofa_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN twofa_backup_codes TEXT;
```

**Column Details:**
- `totp_secret` (VARCHAR): Encrypted TOTP secret key (base32-encoded)
- `twofa_enabled` (BOOLEAN): Whether 2FA is enabled for this user
- `twofa_backup_codes` (TEXT): Encrypted JSON containing backup codes

### Migration Steps

1. **Backup database** before applying migration
2. **Apply SQL migration**:
   ```bash
   # Railway CLI
   railway run psql -c "ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(255);"
   railway run psql -c "ALTER TABLE users ADD COLUMN IF NOT EXISTS twofa_enabled BOOLEAN DEFAULT FALSE;"
   railway run psql -c "ALTER TABLE users ADD COLUMN IF NOT EXISTS twofa_backup_codes TEXT;"
   ```

3. **Verify migration**:
   ```bash
   railway run psql -c "\d users"
   # Should show totp_secret, twofa_enabled, twofa_backup_codes columns
   ```

---

## API Endpoints

All endpoints require authentication via `X-API-Key` header.

### 1. Setup 2FA

**POST** `/api/auth/2fa/setup`

Generates TOTP secret and QR code for initial setup.

**Request:**
```bash
curl -X POST https://your-api.railway.app/api/auth/2fa/setup   -H "X-API-Key: your_api_key"
```

**Response:**
```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "backup_codes": [
    "A1B2-C3D4-E5F6",
    "G7H8-I9J0-K1L2",
    ...
  ]
}
```

**Save the backup codes!** Store them securely - they can be used to access your account if you lose your authenticator device.

---

## Testing 2FA

### Test with Google Authenticator

1. Install Google Authenticator on mobile device
2. Call `/api/auth/2fa/setup` endpoint
3. Scan QR code with app
4. Enter 6-digit code in `/api/auth/2fa/verify`
5. Verify `enabled: true` via `/api/auth/2fa/status`

---

## Security Features

### Encryption

- **TOTP secrets** are encrypted using Fernet (AES-256) before database storage
- **Backup codes** are encrypted and tracked (used codes marked)
- **Encryption key** is stored in `ENCRYPTION_KEY` environment variable

### Time-Based Validation

- TOTP codes valid for 30 seconds
- ±30 second window for clock drift tolerance
- Codes cannot be reused (time-based uniqueness)

### Backup Codes

- 10 backup codes generated per setup
- One-time use (marked as used after verification)
- Can be regenerated (requires TOTP code)
- Encrypted storage with usage tracking

---

## Compliance Benefits

### PCI DSS Requirement 8.3

- Multi-factor authentication for remote access
- Something you know (API key) + something you have (TOTP device)

### NIST 800-63B

- Authenticator Assurance Level 2 (AAL2)
- Time-based one-time passwords (TOTP)
- Backup authentication methods (recovery codes)

---

**Status:** Implementation Complete - Ready for Testing

**Last Updated:** 2026-01-11
