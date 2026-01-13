# Fix CORS Error - Allow talorme.com

## Issue
Frontend at https://talorme.com cannot access backend API due to CORS blocking.

## Solution
Set ALLOWED_ORIGINS environment variable on Railway:

```bash
railway variables set ALLOWED_ORIGINS="https://talorme.com,http://localhost:5173,http://localhost:3000"
```

Or via Railway Dashboard:
1. Go to your backend project
2. Click "Variables"
3. Add/Update: ALLOWED_ORIGINS = https://talorme.com,http://localhost:5173
4. Click "Deploy"

## Verify
After deployment, test:
```bash
curl -I -X OPTIONS https://resume-ai-backend-production-3134.up.railway.app/api/resumes/upload \
  -H "Origin: https://talorme.com" \
  -H "Access-Control-Request-Method: POST"
```

Should return:
- Access-Control-Allow-Origin: https://talorme.com
- Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
