@echo off
echo ============================================================
echo   SANTIESUN BOUT - Transcriptor de Videos
echo ============================================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo ERROR: No se encontro el entorno virtual.
    echo Ejecuta primero: install.bat
    pause
    exit /b 1
)

REM Agregar FFmpeg al PATH
set PATH=%PATH%;C:\ffmpeg

call venv\Scripts\activate.bat
python -m santiesun_bout.app
pause
