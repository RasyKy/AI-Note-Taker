@echo off
title AI Note Taker - Summarize
cd /d "%~dp0"
if "%~1"=="" (
    set /p FILEPATH="Drag transcript (.txt) here or enter path: "
) else (
    set FILEPATH=%~1
)
echo.
venv\Scripts\python.exe summarize.py "%FILEPATH%"
echo.
pause
