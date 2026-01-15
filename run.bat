@echo off
echo ============================================================
echo   TRANSCRIPTOR AUTOMATICO DE VIDEOS
echo ============================================================
echo.

REM Verificar entorno virtual
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: No se encontro el entorno virtual.
    echo Ejecuta primero: install.bat
    pause
    exit /b 1
)

REM Agregar FFmpeg al PATH
set PATH=%PATH%;C:\ffmpeg

REM Activar entorno virtual
call venv\Scripts\activate.bat

REM Ejecutar aplicacion
python -m transcriptor.main %*

REM Si se cierra sin errores
if errorlevel 0 (
    echo.
    echo Aplicacion cerrada.
)

pause
