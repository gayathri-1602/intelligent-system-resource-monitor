@echo off
REM ============================================================================
REM        INTELLIGENT SYSTEM MONITOR - QUICK START
REM ============================================================================

cd /d "%~dp0"

echo.
echo Starting Intelligent System Monitor...
echo.

REM Activate and run
call .venv\Scripts\activate.bat
python app.py

pause
