# API Authentication Guide

## Overview

The Resume AI Backend API uses **API Key authentication** for secure access to protected endpoints. This document explains authentication requirements, how to obtain API keys, and best practices for API usage.

---

## Table of Contents

1. [Authentication Methods](#authentication-methods)
2. [Getting an API Key](#getting-an-api-key)
3. [Using Your API Key](#using-your-api-key)
4. [Endpoint Authentication Requirements](#endpoint-authentication-requirements)
5. [Security Best Practices](#security-best-practices)
6. [Rate Limits](#rate-limits)
7. [Rotating API Keys](#rotating-api-keys)
8. [Troubleshooting](#troubleshooting)

---

## Authentication Methods

### API Key Authentication

All protected endpoints require an API key passed via the `X-API-Key` header:

```http
X-API-Key: your_api_key_here
```

**Security Features:**
- API keys are hashed using bcrypt (never stored in plaintext)
- Keys are 256-bit cryptographically secure tokens
- Failed authentication attempts are rate-limited
- Keys can be rotated without losing access

---

## Getting an API Key

### Register a New Account

**Endpoint:** `POST /api/auth/register`

**Request:**
```json
{
  "email": "user@example.com",
  "username": "johndoe"
}
```

**Response:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "johndoe",
  "api_key": "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
  "created_at": "2026-01-11T12:00:00Z",
  "warning": "Save this API key - it won't be shown again!"
}
```

**⚠️ IMPORTANT:**
- The API key is **only shown once** during registration
- Save it securely (password manager, environment variables)
- If lost, you must rotate to a new key using `/api/auth/rotate-key`

**Rate Limit:** 5 registrations per hour per IP

---

## Using Your API Key

### Example Requests

#### cURL
```bash
curl -X GET "https://api.example.com/api/resumes/list" \
  -H "X-API-Key: AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
```

#### Python (requests)
```python
import requests

headers = {
    "X-API-Key": "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
}

response = requests.get(
    "https://api.example.com/api/resumes/list",
    headers=headers
)
```

#### JavaScript (fetch)
```javascript
const response = await fetch('https://api.example.com/api/resumes/list', {
  method: 'GET',
  headers: {
    'X-API-Key': 'AbCdEfGhIjKlMnOpQrStUvWxYz0123456789'
  }
});
```

#### Postman
1. Select "Headers" tab
2. Add key: `X-API-Key`
3. Add value: `your_api_key_here`

---

## Endpoint Authentication Requirements

### Public Endpoints (No Auth Required)

These endpoints are publicly accessible:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/`      | Root endpoint (health check) |
| GET    | `/health` | Health check |
| POST   | `/api/auth/register` | Create new account |

### Protected Endpoints (Auth Required)

All other endpoints require authentication:

#### Authentication Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/auth/me` | Get current user info |
| POST   | `/api/auth/rotate-key` | Rotate API key |

#### Resume Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/resumes/upload` | Upload resume (optional auth*) |
| GET    | `/api/resumes/list` | List your resumes |
| GET    | `/api/resumes/{id}` | Get resume details |
| POST   | `/api/resumes/{id}/delete` | Delete resume |

*Upload endpoint accepts optional authentication. If authenticated, resume is linked to your account. If not, it's anonymous.

#### Tailoring Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/tailor/tailor` | Tailor resume for job |
| GET    | `/api/tailor/tailored/{id}` | Get tailored resume |
| GET    | `/api/tailor/list` | List tailored resumes |
| POST   | `/api/tailor/tailor/batch` | Batch tailor for multiple jobs |

---

## Security Best Practices

### ✅ DO:

1. **Store API keys securely:**
   - Use environment variables (`export API_KEY=...`)
   - Use password managers
   - Use secrets management (AWS Secrets Manager, HashiCorp Vault)

2. **Use HTTPS only:**
   - Never send API keys over unencrypted HTTP
   - Verify SSL certificates

3. **Rotate keys regularly:**
   - Rotate every 90 days
   - Rotate immediately if compromised

4. **Implement timeout and retry logic:**
   - Handle rate limit errors (HTTP 429)
   - Use exponential backoff for retries

5. **Log authentication failures:**
   - Monitor for unauthorized access attempts
   - Alert on suspicious patterns

### ❌ DON'T:

1. **Never commit API keys to version control:**
   ```bash
   # Bad - hardcoded in code
   API_KEY = "AbCdEfGh..."  # DON'T DO THIS

   # Good - from environment
   API_KEY = os.environ.get("API_KEY")
   ```

2. **Never share API keys:**
   - Each user should have their own key
   - Don't share keys via email or chat

3. **Never log API keys:**
   ```python
   # Bad
   logger.info(f"Using API key: {api_key}")

   # Good
   logger.info("API request authenticated")
   ```

4. **Never embed in client-side code:**
   - Don't put API keys in JavaScript
   - Don't include in mobile app binaries
   - Use backend proxy instead

---

## Rate Limits

To prevent abuse, endpoints are rate-limited:

| Endpoint | Rate Limit |
|----------|------------|
| `POST /api/auth/register` | 5 per hour per IP |
| `POST /api/auth/rotate-key` | 3 per day per IP |
| `POST /api/resumes/upload` | 5 per minute per IP |
| `POST /api/tailor/tailor` | 10 per hour per IP |
| `POST /api/tailor/tailor/batch` | 2 per hour per IP |

**Rate Limit Response:**
```json
{
  "detail": "Too Many Requests"
}
```

**HTTP Status:** 429 Too Many Requests

**Headers:**
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1673452800
```

**Handling Rate Limits:**
```python
import time

response = requests.post(url, headers=headers)

if response.status_code == 429:
    # Wait before retrying
    retry_after = int(response.headers.get('Retry-After', 60))
    print(f"Rate limited. Retrying in {retry_after} seconds...")
    time.sleep(retry_after)
    response = requests.post(url, headers=headers)
```

---

## Rotating API Keys

If your API key is compromised or you want to rotate regularly:

### Rotate API Key

**Endpoint:** `POST /api/auth/rotate-key`

**Headers:**
```
X-API-Key: current_api_key_here
```

**Response:**
```json
{
  "success": true,
  "new_api_key": "NewAbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
  "warning": "Save this API key - it won't be shown again! Your old key is now invalid.",
  "user_id": 1,
  "username": "johndoe"
}
```

**⚠️ IMPORTANT:**
- Old API key is immediately invalidated
- Save the new key securely
- Update all applications using the old key
- Rate limited to 3 rotations per day per IP

---

## Troubleshooting

### Error: "API key required. Provide X-API-Key header."

**Cause:** Missing authentication header

**Solution:**
```bash
# Add X-API-Key header
curl -X GET "https://api.example.com/api/resumes/list" \
  -H "X-API-Key: your_api_key"
```

### Error: "Invalid API key"

**Cause:** API key is incorrect, expired, or rotated

**Solutions:**
1. Verify key is correct (no typos)
2. Check if key was rotated
3. Register new account if key is lost

### Error: "Access denied: You don't own this resume"

**Cause:** Trying to access another user's resume

**Solution:** You can only access resumes you uploaded while authenticated

### Error: "Too Many Requests" (HTTP 429)

**Cause:** Exceeded rate limit

**Solution:** Wait for rate limit window to reset, then retry

---

## Security Incidents

If you suspect your API key has been compromised:

1. **Immediately rotate your key:** `POST /api/auth/rotate-key`
2. **Review API usage logs** for suspicious activity
3. **Update all applications** with the new key
4. **Contact support** if you see unauthorized access

---

## Support

For questions about authentication:

- **Documentation:** This file and inline API docs at `/docs`
- **Issues:** Report bugs at https://github.com/anthropics/claude-code/issues
- **Email:** support@example.com (if configured)

---

## Changelog

### Version 2.0 (2026-01-11)
- Added bcrypt API key hashing
- Added API key rotation endpoint
- Added rate limiting on all endpoints
- Added soft delete with audit trail
- Added file encryption at rest

### Version 1.0 (Initial Release)
- Basic API key authentication
- User registration
- Public health check endpoints

---

## Compliance

This API authentication system complies with:

- **OWASP Top 10** - Identification and Authentication Failures (A07)
- **PCI DSS** - Requirement 8 (Identify and authenticate access)
- **GDPR** - Article 32 (Security of processing)
- **NIST Cybersecurity Framework** - PR.AC (Identity Management)

---

**Last Updated:** 2026-01-11
**Status:** Production Ready ✅
