@echo off
cd /d "%~dp0"
echo ============================================
echo  DART research: sanggye-nabip cases
echo  (This may take a few minutes. Please wait.)
echo ============================================
echo.
where python >nul 2>nul
if %errorlevel% equ 0 (
    python run_research.py
) else (
    py -3 run_research.py
)
if errorlevel 1 (
    echo.
    echo [ERROR] Research failed. Check Python, .env, and your network connection.
    pause
    exit /b 1
)
echo.
echo Done. Please tell Claude it is finished.
echo.
pause
