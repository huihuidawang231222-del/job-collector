@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 goto use_python
py -3 -c "import sys; sys.exit(sys.version_info < (3,10))"
if errorlevel 1 goto fail
py -3 -m venv .venv
goto install
:use_python
python -c "import sys; sys.exit(sys.version_info < (3,10))"
if errorlevel 1 goto fail
python -m venv .venv
:install
if errorlevel 1 goto fail
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python browser_runtime.py
if not errorlevel 1 goto complete
.venv\Scripts\python -m playwright install chromium
if errorlevel 1 goto fail
:complete
echo Installation complete.
pause
exit /b
:fail
echo Installation failed. Python 3.10+ and working network are required.
pause
