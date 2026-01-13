@echo off
echo ======================================
echo   Database Migration Script
echo ======================================
echo.
echo This will run the migration on Railway's PostgreSQL database.
echo.

cd /d "%~dp0"

echo Linking to Railway project...
railway link

echo.
echo Running migration via Railway shell...
railway shell psql -f migrations/add_missing_columns.sql

echo.
echo ======================================
echo   Migration Complete!
echo ======================================
pause
