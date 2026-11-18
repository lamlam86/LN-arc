@echo off
echo ============================================
echo   LN-ARC Password Reset
echo ============================================
echo.
echo This will reset the admin password to: admin123
echo.

echo [DB] Resetting password hash...
docker exec lnai-postgres psql -U artex -d artex -c "DELETE FROM settings WHERE key = 'auth.password_hash';"
if errorlevel 1 (
    echo.
    echo [ERROR] Could not reset password.
    echo Make sure Docker Desktop is running and lnai-postgres container exists.
    echo.
    echo Try manually: docker exec lnai-postgres psql -U artex -d artex -c "DELETE FROM settings WHERE key = 'auth.password_hash';"
) else (
    echo.
    echo [OK] Password reset successful!
    echo Now close all CMD windows and run start.bat
    echo Login at http://localhost:3000 with password: admin123
)
echo.
pause
