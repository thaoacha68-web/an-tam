@echo off
cd /d "%~dp0"
python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health',timeout=1)" >nul 2>nul
if %errorlevel%==0 (
  start "" http://localhost:8000
  exit /b 0
)
start "" /b powershell -NoProfile -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:8000'"
python backend\server.py
pause
