@echo off
REM ============================================================
REM Agentic Infra Co-Pilot - Quick Start Script (Windows)
REM ============================================================

echo.
echo ============================================================
echo    Agentic Infra Co-Pilot - Docker Startup
echo ============================================================
echo.

REM Check if .env exists
if not exist ".env" (
    echo ERROR: .env file not found!
    echo.
    echo Please create a .env file with your GROQ_API_KEY:
    echo   1. Copy .env.example to .env
    echo   2. Add your Groq API key from https://console.groq.com
    echo.
    pause
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

echo Starting all services with Docker Compose...
echo.

REM Build and start
docker-compose up --build -d

echo.
echo ============================================================
echo    Services Starting...
echo ============================================================
echo.
echo    Neo4j Browser:    http://localhost:7474
echo    Telekom Minister: http://localhost:8001
echo    Siemens Tech:     http://localhost:8002
echo    Illigo Operator:  http://localhost:8003
echo    Streamlit UI:     http://localhost:8501
echo.
echo ============================================================
echo.
echo Waiting for services to be healthy (this may take 1-2 minutes)...
echo.

REM Wait a bit for services to start
timeout /t 30 /nobreak >nul

echo.
echo To view logs: docker-compose logs -f
echo To stop:      docker-compose down
echo.
echo Opening Streamlit UI in browser...
start http://localhost:8501

pause
