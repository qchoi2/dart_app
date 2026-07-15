@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  OpenDART MCP Installer
echo ============================================
echo.

set "PYTHON_CMD="
where python >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
    where py >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    echo [ERROR] Python was not found.
    echo Install Python 3.10 or newer and enable "Add python.exe to PATH".
    pause
    exit /b 1
)

echo [1/4] Checking Python...
%PYTHON_CMD% --version
if errorlevel 1 goto :failed

echo.
echo [2/4] Checking the OpenDART API key...
if not exist ".env" (
    copy /Y ".env.example" ".env" >nul
    echo A new .env file was created.
    echo Enter your OpenDART API key, save the file, and close Notepad.
    start /wait "" notepad.exe ".env"
)

findstr /R /B /C:"DART_API_KEY=." ".env" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] DART_API_KEY is missing from .env.
    pause
    exit /b 1
)

findstr /C:"your_opendart_api_key_here" ".env" >nul 2>nul
if not errorlevel 1 (
    echo [ERROR] Replace the example API key in .env with your real key.
    pause
    exit /b 1
)

echo API key configuration found.

echo.
echo [3/4] Installing the MCP package...
%PYTHON_CMD% -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo [4/4] Registering OpenDART in Claude Desktop...
%PYTHON_CMD% merge_config.py
if errorlevel 1 goto :failed

echo.
echo ============================================
echo  Installation completed successfully.
echo ============================================
echo Close Claude Desktop completely, then open it again.
echo You can then ask Claude: "What OpenDART tools are available?"
echo.
pause
exit /b 0

:failed
echo.
echo [ERROR] Installation failed. Review the message above.
pause
exit /b 1
