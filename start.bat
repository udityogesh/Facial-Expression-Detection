@echo off
REM Startup script for Face Emotion Detection App (Windows)
setlocal
cd /d "%~dp0"

echo Starting Face Emotion Detection Application...

set "VENV_DIR=%~dp0.venv"

REM Check if virtual environment exists
if not exist "%VENV_DIR%\" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Error: Failed to create virtual environment.
        exit /b 1
    )
)

REM Install project dependencies into this project's environment
echo Installing dependencies...
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install project dependencies.
    exit /b 1
)

REM Check if model files exist
if not exist "emotiondetector.h5" (
    echo Error: Model files not found!
    echo Please ensure emotiondetector.h5 and emotiondetector.json are in the project directory.
    exit /b 1
)

if not exist "emotiondetector.json" (
    echo Error: Model files not found!
    echo Please ensure emotiondetector.h5 and emotiondetector.json are in the project directory.
    exit /b 1
)

REM Create .env if it doesn't exist
if not exist ".env" (
    echo Creating .env file from template...
    copy .env.example .env
    echo A local .env file was created. Set a persistent SECRET_KEY before deployment.
)

REM Set environment variables if not already set
if "%FLASK_ENV%"=="" set FLASK_ENV=development
if "%PORT%"=="" set PORT=5000

REM Start the application
echo Starting application on port %PORT%...
echo Landing page: http://localhost:%PORT%/
echo Detection:    http://localhost:%PORT%/detect
echo Press CTRL+C to stop the server
echo.

"%VENV_DIR%\Scripts\python.exe" app.py
endlocal
