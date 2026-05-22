@echo off
title AI Note Taker - Zoom Monitor
cd /d "%~dp0"
echo Starting Zoom monitor...
echo.
venv\Scripts\python.exe main.py
echo.
pause
