@echo off
setlocal
cd /d "%~dp0"
if not exist "data\catalog.sqlite" (
 echo Missing data\catalog.sqlite. Copy it from the original project package.
 pause
 exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
 py -3 -c "import sys; assert sys.version_info >= (3,12), 'Python 3.12 or newer is required'"
 if errorlevel 1 goto failed
 py -3 -m venv .venv
 if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -c "import sys; assert sys.version_info >= (3,12), 'Python 3.12 or newer is required'"
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo After "Running on" appears, open http://127.0.0.1:8000 in your browser.
echo Keep this window open. Press Ctrl+C to stop the site.
echo.
.venv\Scripts\python.exe -m flask --app wsgi run --host 127.0.0.1 --port 8000
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Startup failed. Copy the error above when requesting help.
pause
exit /b 1
