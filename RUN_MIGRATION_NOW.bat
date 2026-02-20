@echo off
echo ============================================================
echo Running Video Recording Database Migration
echo ============================================================
echo.

echo Step 1: Logging into Railway...
railway login

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Railway login failed
    pause
    exit /b 1
)

echo.
echo Step 2: Linking to project...
railway link

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Railway link failed
    pause
    exit /b 1
)

echo.
echo Step 3: Running migration...
railway run python run_video_recording_migration.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Migration failed!
    echo.
    echo Please check:
    echo 1. Railway CLI is properly authenticated
    echo 2. Project is linked correctly
    echo 3. PostgreSQL service is running
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo SUCCESS! Database migration completed.
echo ============================================================
echo.
echo S3 bucket name: talorme-recordings
echo.
echo Next steps:
echo 1. Follow AWS_S3_SETUP.md to create S3 bucket "talorme-recordings"
echo 2. Add AWS environment variables to Railway
echo 3. Test video recording feature
echo.
pause
