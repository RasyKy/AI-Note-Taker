@echo off
title AI Note Taker - Live Recording
cd /d "%~dp0"
echo Starting live audio capture...
echo.
venv\Scripts\python.exe record_now.py
echo.
pause
