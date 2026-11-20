@echo off
SETLOCAL EnableDelayedExpansion

echo ==========================================
echo   Smart Factory Worker - Setup ^& Run
echo ==========================================

:: 1. Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from python.org
    pause
    exit /b
)

:: 2. Create Virtual Environment
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

:: 3. Activate and Install
echo [INFO] Activating environment and checking dependencies...
call venv\Scripts\activate
pip install -r requirements.txt

:: 4. Check for .env
if not exist ".env" (
    echo [WARNING] .env file not found.
    set /p API_KEY="Enter your GEMINI_API_KEY: "
    echo GEMINI_API_KEY=!API_KEY! > .env
)

:: 5. Launch
echo [SUCCESS] Everything is ready.
echo [INFO] Starting the server...
echo [INFO] Once started, open: http://localhost:8000
echo.

cd factory_analyzer\backend
uvicorn main:app --reload --port 8000
pause
