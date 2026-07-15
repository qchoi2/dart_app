@echo off
cd /d "%~dp0"
echo ============================================
echo  Registering opendart into the REAL config
echo ============================================
echo.
"C:\Users\3100025\AppData\Local\Programs\Python\Python312\python.exe" merge_config.py
echo.
echo Please tell Claude it is finished.
echo.
pause
