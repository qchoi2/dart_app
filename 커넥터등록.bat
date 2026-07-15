@echo off
cd /d "%~dp0"
echo ============================================
echo  Registering opendart into the REAL config
echo ============================================
echo.
where python >nul 2>nul
if %errorlevel% equ 0 (
    python merge_config.py
) else (
    py -3 merge_config.py
)
if errorlevel 1 (
    echo.
    echo [ERROR] Registration failed. Review the message above.
    pause
    exit /b 1
)
echo.
echo Please tell Claude it is finished.
echo.
pause
