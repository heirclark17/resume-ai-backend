@echo off
echo ============================================================
echo Testing Video Recording Setup
echo ============================================================
echo.

railway run python VERIFY_SETUP.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo SUCCESS! Ready to test in browser.
    echo ============================================================
    echo.
    echo Open: https://talorme.com
    echo Go to: Interview Prep ^> Behavioral/Technical Questions
    echo Click: "Record Practice" button
    echo.
)

pause
