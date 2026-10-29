@echo off
title Antigravity Telegram Remote Bridge
cd /d "%~dp0"

:loop
echo ============================================================
echo 🚀 Starting Antigravity Telegram Remote Bridge...
echo ============================================================
python -u bridge.py
echo.
echo [Bridge exited or reloaded. Restarting automatically in 2 seconds...]
timeout /t 2 /nobreak >nul
goto loop
