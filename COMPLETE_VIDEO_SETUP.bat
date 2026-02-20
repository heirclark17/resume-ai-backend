@echo off
echo ============================================================
echo Video Recording Feature - Complete Setup Script
echo ============================================================
echo.

echo Step 1: Running Database Migration...
echo ----------------------------------------
railway run python run_video_recording_migration.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Migration failed!
    echo.
    echo Please check:
    echo 1. Railway CLI is logged in: railway login
    echo 2. Project is linked: railway link
    echo 3. PostgreSQL service is running
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo ✓ DATABASE MIGRATION COMPLETED
echo ============================================================
echo.
echo Next Steps:
echo 1. Open AWS_S3_SETUP.md and follow ALL steps to create S3 bucket
echo 2. Add 4 AWS environment variables to Railway dashboard
echo 3. Wait for Railway to redeploy (~2-3 minutes)
echo 4. Test video recording feature at https://talorme.com
echo.
echo Files to reference:
echo - AWS_S3_SETUP.md (complete AWS setup guide)
echo - RUN_VIDEO_MIGRATION.md (migration troubleshooting)
echo.
pause
