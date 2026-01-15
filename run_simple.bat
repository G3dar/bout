@echo off
REM Ejecutar sin diarizacion (mas rapido, no requiere token de HuggingFace)
echo ============================================================
echo   TRANSCRIPTOR (Modo Simple - Sin identificacion de hablantes)
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
python -m transcriptor.main --no-diarization %*
pause
