@echo off
title Patent Drafting Tool - Dev
cd /d "C:\Users\melike\paten_draft_backend"

echo === Patent Drafting Tool - Dev start ===
echo.

echo [1/3] Bringing up Postgres container (and stopping stale app)...
docker-compose up -d db
docker stop paten_draft_backend-app-1 >nul 2>&1
echo.

echo [2/3] Activating venv...
call ".\.venv\Scripts\activate.bat"
echo.

echo [3/3] Starting uvicorn...
echo.
echo App URL: http://localhost:8000
echo Press Ctrl+C twice to stop, then close this window.
echo.

uvicorn app.main:app --reload --reload-dir app --reload-dir static

echo.
echo === uvicorn stopped ===
pause
