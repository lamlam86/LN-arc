@echo off
title LN-ARC - Start Fresh
echo.
echo ============================================
echo   LN-ARC - Start Fresh
echo ============================================
echo.
echo [INFO] No password hash exists yet - database is clean.
echo [INFO] Backend will initialize with password: admin123
echo.

echo Step 1: Killing old backend if running...
taskkill /f /im lnai.exe >nul 2>&1
timeout /t 2 /noq >nul
echo [OK] Done
echo.

echo Step 2: Starting backend with admin123 password...
set ARTEX_PG_DSN=postgres://artex:change-me-please@localhost:5432/artex?sslmode=disable
set ARTEX_ADMIN_PASSWORD=admin123
set ARTEX_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://192.168.100.1:3000
start "" cmd /c "title LN-ARC Backend && set ARTEX_PG_DSN=postgres://artex:change-me-please@localhost:5432/artex?sslmode=disable && set ARTEX_ADMIN_PASSWORD=admin123 && set ARTEX_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://192.168.100.1:3000 && "%~dp0dist\artex-windows-amd64\lnai.exe" 2>&1 || (echo BACKEND CRASHED && pause)"
timeout /t 4 /noq >nul
echo [OK] Backend starting on port 8787
echo.

echo Step 3: Starting Next.js frontend...
cd /d "%~dp0web"
start "" cmd /c "title LN-ARC Frontend && npx next dev"
timeout /t 5 /noq >nul
echo [OK] Frontend starting on port 3000
echo.

echo ============================================
echo   READY!
echo.
echo   Open: http://localhost:3000
echo   Login: LN-ARC
echo   Password: admin123
echo ============================================
echo.
pause
