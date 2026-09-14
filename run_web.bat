@echo off
cd /d "%~dp0"
if not exist frontend\dist\index.html (
  echo Build the frontend first: cd frontend ^&^& npm install ^&^& npm run build
  exit /b 1
)
set "TRAVELDNA_PYTHON=python"
if exist "%USERPROFILE%\anaconda3\python.exe" set "TRAVELDNA_PYTHON=%USERPROFILE%\anaconda3\python.exe"
echo Open http://127.0.0.1:8000
"%TRAVELDNA_PYTHON%" -m uvicorn app.api:app --host 127.0.0.1 --port 8000
pause
