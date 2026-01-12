# reCAPTCHA v3 Setup Guide

## Overview

Google reCAPTCHA v3 protects the registration endpoint from bot abuse and automated account creation. It provides invisible protection with risk scoring (0.0-1.0).

---

## Setup Steps

### 1. Get reCAPTCHA Keys

1. Go to https://www.google.com/recaptcha/admin
2. Click "+" to create a new site
3. Fill in:
   - **Label:** ResumeAI
   - **reCAPTCHA type:** reCAPTCHA v3
   - **Domains:** your-domain.com, localhost (for testing)
4. Accept terms and submit
5. Save your keys:
   - **Site Key** (public) - for frontend
   - **Secret Key** (private) - for backend

### 2. Configure Backend

Set environment variables on Railway:

railway variables set RECAPTCHA_SECRET_KEY="your_secret_key"
railway variables set RECAPTCHA_MIN_SCORE="0.5"

RECAPTCHA_MIN_SCORE (optional):
- 0.0-1.0 (default: 0.5)
- Higher = stricter (0.7 recommended for production)
- Lower = more lenient (0.3 for testing)

### 3. Configure Frontend

Add reCAPTCHA script to HTML:

<script src="https://www.google.com/recaptcha/api.js?render=YOUR_SITE_KEY"></script>

---

## Frontend Integration

### Registration Form Example

// Get reCAPTCHA token
function getRecaptchaToken() {
  return new Promise((resolve, reject) => {
    grecaptcha.ready(() => {
      grecaptcha.execute('YOUR_SITE_KEY', {action: 'registration'})
        .then(token => resolve(token))
        .catch(err => reject(err));
    });
  });
}

// Register user
async function registerUser(email, username) {
  try {
    // Get reCAPTCHA token
    const recaptchaToken = await getRecaptchaToken();
    
    // Send registration request
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        email: email,
        username: username,
        recaptcha_token: recaptchaToken
      })
    });
    
    const data = await response.json();
    
    if (data.success) {
      console.log('API Key:', data.api_key);
      alert('Save your API key: ' + data.api_key);
    }
  } catch (error) {
    console.error('Registration failed:', error);
  }
}

---

## API Endpoint

### POST /api/auth/register

Registers a new user with reCAPTCHA protection.

**Request:**
{
  "email": "user@example.com",
  "username": "john_doe",
  "recaptcha_token": "03AGdBq26..."
}

**Response (Success):**
{
  "success": true,
  "message": "Registration successful. Save your API key - it will not be shown again!",
  "api_key": "ABC123...",
  "user_id": 1
}

**Response (Bot Detected):**
{
  "detail": "CAPTCHA verification failed: CAPTCHA score too low (likely bot): 0.1"
}

---

## Testing

### Test Without reCAPTCHA (Development)

If RECAPTCHA_SECRET_KEY is not set, verification is skipped:

curl -X POST https://your-api.railway.app/api/auth/register   -H "Content-Type: application/json"   -d '{"email": "test@example.com", "username": "testuser"}'

### Test With reCAPTCHA (Production)

1. Get token from frontend (see integration example above)
2. Include token in registration request
3. Check logs for verification result

---

## Score Interpretation

reCAPTCHA v3 returns a score (0.0-1.0):

- **1.0:** Very likely human
- **0.7-0.9:** Likely human (recommended threshold)
- **0.5:** Neutral (default threshold)
- **0.3-0.4:** Suspicious activity
- **0.0-0.2:** Very likely bot

### Recommended Thresholds

- **Strict (0.7):** Low false positives, some legitimate users blocked
- **Balanced (0.5):** Good balance (default)
- **Lenient (0.3):** Few false positives, some bots may pass

---

## Error Handling

### Common Errors

**"reCAPTCHA token required"**
- Cause: Missing recaptcha_token in request
- Fix: Include token from grecaptcha.execute()

**"CAPTCHA score too low (likely bot)"**
- Cause: Score below threshold
- Fix: Lower RECAPTCHA_MIN_SCORE or investigate bot activity

**"CAPTCHA action mismatch"**
- Cause: Action in token doesn't match expected action
- Fix: Use action: 'registration' in grecaptcha.execute()

**"CAPTCHA verification service unavailable"**
- Cause: Can't reach Google's verification API
- Fix: Check network connectivity, retry

---

## Security Features

### Bot Protection

- Invisible to users (no challenge)
- Risk-based scoring
- Action-based validation
- IP address logging

### False Positive Mitigation

- Adjustable score threshold
- Falls back gracefully if not configured
- Comprehensive error messages
- Retry support

---

## Monitoring

### Check Logs

railway logs | grep reCAPTCHA

Look for:
- "reCAPTCHA verification passed" (successful registrations)
- "Registration blocked by reCAPTCHA" (bot attempts)
- "reCAPTCHA score too low" (suspicious activity)

### Google reCAPTCHA Admin

View statistics at: https://www.google.com/recaptcha/admin

- Request volume
- Score distribution
- Blocked requests
- Domain verification

---

## Compliance

- **GDPR:** reCAPTCHA v3 is GDPR-compliant
- **CCPA:** Covered by Google's privacy policy
- **OWASP:** Addresses A07:2021 - Identification and Authentication Failures

---

**Status:** Implementation Complete
**Last Updated:** 2026-01-11
