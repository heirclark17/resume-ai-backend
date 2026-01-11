@echo off
echo ============================================
echo Resume AI Backend - GitHub Setup
echo ============================================
echo.

echo Step 1: Initialize Git repository
cd /d "%~dp0"
git init
git add .
git commit -m "Initial commit: FastAPI backend with PostgreSQL support"

echo.
echo Step 2: Create GitHub repository
echo.
echo Please go to: https://github.com/new
echo Repository name: resume-ai-backend
echo Description: FastAPI backend for Resume AI application
echo Visibility: Public (or Private if you prefer)
echo Do NOT initialize with README (we already have one)
echo.
pause

echo.
echo Step 3: Link to GitHub repository
echo.
set /p GITHUB_URL="Enter your GitHub repository URL (e.g., https://github.com/username/resume-ai-backend.git): "

git remote add origin %GITHUB_URL%
git branch -M main
git push -u origin main

echo.
echo ============================================
echo GitHub setup complete!
echo ============================================
echo.
echo Next steps:
echo 1. Go to https://railway.app
echo 2. Click "New Project"
echo 3. Select "Deploy from GitHub repo"
echo 4. Choose "resume-ai-backend"
echo 5. Add PostgreSQL database
echo 6. Set environment variables:
echo    - CLAUDE_API_KEY
echo    - PERPLEXITY_API_KEY
echo    - TEST_MODE=false
echo.
echo See README.md for detailed deployment instructions.
echo.
pause
