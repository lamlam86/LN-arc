@echo off
title LN-ARC - Fix Login & Restart
echo.
echo ============================================
echo   LN-ARC Login Fix
echo ============================================
echo.
echo Step 1: Checking Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop is not running! Start it first.
    pause
    exit /b 1
)
echo [OK] Docker is running
echo.

echo Step 2: Ensuring PostgreSQL container is up...
docker ps --filter "name=lnai-postgres" --format "{{.Status}}" 2>nul | findstr /i "Up" >nul
if errorlevel 1 (
    echo [DB] Starting lnai-postgres...
    docker start lnai-postgres 2>nul
    if errorlevel 1 (
        echo [ERROR] Container lnai-postgres not found. Run start.bat first to create it.
        pause
        exit /b 1
    )
    timeout /t 3 /noq >nul
)
echo [OK] PostgreSQL is running
echo.

echo Step 3: Resetting password hash in database...
docker exec lnai-postgres psql -U artex -d artex -c "DELETE FROM settings WHERE key = 'auth.password_hash';"
if errorlevel 1 (
    echo [ERROR] Failed to reset password hash!
    pause
    exit /b 1
)
echo [OK] Password hash cleared
echo.

echo Step 4: Killing old backend process...
taskkill /f /im lnai.exe >nul 2>&1
timeout /t 2 /noq >nul
echo [OK] Old backend stopped
echo.

echo Step 5: Starting fresh backend...
set ARTEX_PG_DSN=postgres://artex:change-me-please@localhost:5432/artex?sslmode=disable
set ARTEX_ADMIN_PASSWORD=admin123
set ARTEX_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://192.168.100.1:3000
start "" cmd /c "title LN-ARC Backend && set ARTEX_PG_DSN=postgres://artex:change-me-please@localhost:5432/artex?sslmode=disable && set ARTEX_ADMIN_PASSWORD=admin123 && set ARTEX_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://192.168.100.1:3000 && "%~dp0dist\artex-windows-amd64\lnai.exe" 2>&1 || (echo BACKEND CRASHED && pause)"
timeout /t 3 /noq >nul
echo [OK] Backend starting on port 8787
echo.

echo ============================================
echo   FIX COMPLETE!
echo.
echo   Login at: http://localhost:3000
echo   Login: LN-ARC
echo   Password: admin123
echo.
echo   (If Next.js isn't running, open another
echo    CMD in the web folder and run: npx next dev)
echo ============================================
echo.
pause
