@echo off
title AI Note Taker - Transcribe
cd /d "%~dp0"
if "%~1"=="" (
    set /p FILEPATH="Drag audio file here or enter path: "
) else (
    set FILEPATH=%~1
)
echo.
venv\Scripts\python.exe transcribe.py "%FILEPATH%"
echo.
pause
