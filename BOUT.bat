@echo off
title BOUT - Video Transcription
cd /d "%~dp0"

:: Check if venv exists
if not exist "venv\Scripts\python.exe" (
    echo.
    echo ERROR: El entorno virtual no existe.
    echo Por favor ejecuta primero: setup.bat
    echo.
    pause
    exit /b 1
)

:: Run GUI
venv\Scripts\python.exe -m bout.gui
