@echo off
cd /d "%~dp0"
python -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python -m playwright install chromium
if errorlevel 1 goto fail
echo Installation complete.
pause
exit /b
:fail
echo Installation failed. Check Python and network, then retry.
pause
