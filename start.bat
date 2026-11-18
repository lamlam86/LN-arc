@echo off
title LN-ARC - Starting...

echo.
echo  _     _   _       _    ___
echo ^| ^|   ^| \ ^| ^|     / \  ^|_ _^|
echo ^| ^|   ^|  \^| ^|    / _ \  ^| ^|
echo ^| ^|___^|\   ^| ^|  / ___ \ ^| ^|
echo ^|_____^|_^|\_/^|_^| /_/   \_\___^|
echo.
echo   AI Autonomous Reconnaissance Console
echo   Starting backend + frontend...
echo.

:: Set environment
set ARTEX_PG_DSN=postgres://artex:change-me-please@localhost:5432/artex?sslmode=disable
set ARTEX_ADMIN_PASSWORD=admin123
set ARTEX_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://192.168.100.1:3000

:: Check Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running! Please start Docker Desktop first.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

:: Check Docker PostgreSQL
docker ps --filter "name=lnai-postgres" --format "{{.Status}}" 2>nul | findstr /i "Up" >nul
if errorlevel 1 (
    echo [DB] Starting PostgreSQL...
    docker start lnai-postgres 2>nul || docker run -d --name lnai-postgres -e POSTGRES_USER=artex -e POSTGRES_PASSWORD=change-me-please -e POSTGRES_DB=artex -p 5432:5432 postgres:16-alpine
    if errorlevel 1 (
        echo [ERROR] Failed to start PostgreSQL container!
        echo Press any key to exit...
        pause >nul
        exit /b 1
    )
    echo [DB] Waiting for PostgreSQL to be ready...
    timeout /t 5 /noq >nul
) else (
    echo [DB] PostgreSQL already running
)

:: Check if backend binary exists
if not exist "%~dp0dist\artex-windows-amd64\lnai.exe" (
    echo [ERROR] Backend binary not found at dist\artex-windows-amd64\lnai.exe
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

:: Start backend - NOW WITH VISIBLE OUTPUT
echo [BACKEND] Starting LN-ARC backend on :8787...
start "" cmd /c "title LN-ARC Backend && "%~dp0dist\artex-windows-amd64\lnai.exe" 2>&1 || (echo. && echo [BACKEND CRASHED] Press any key to close... && pause >nul)"

timeout /t 3 /noq >nul

:: Start frontend
echo [FRONTEND] Starting Next.js on :3000...
echo.
echo ========================================
echo   Open http://localhost:3000 in browser
echo   Login: LN-ARC  /  Password: admin123
echo ========================================
echo.

cd /d "%~dp0web"
call npx next dev
