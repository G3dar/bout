@echo off
title BOUT - Instalador
color 0A

echo.
echo ============================================================
echo                    BOUT - INSTALADOR
echo              Video Transcription Tool
echo ============================================================
echo.

:: Check if running as admin (optional but recommended)
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Ejecutando como administrador
) else (
    echo [!] Nota: Para mejor experiencia, ejecuta como administrador
)

echo.
echo [1/6] Verificando Python...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [X] Python no encontrado!
    echo.
    echo Por favor instala Python 3.10 o superior desde:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANTE: Marca la opcion "Add Python to PATH" durante la instalacion
    echo.
    pause
    exit /b 1
)
python --version
echo [OK] Python encontrado

echo.
echo [2/6] Creando entorno virtual...
if not exist "venv" (
    python -m venv venv
    echo [OK] Entorno virtual creado
) else (
    echo [OK] Entorno virtual ya existe
)

echo.
echo [3/6] Activando entorno virtual...
call venv\Scripts\activate.bat
echo [OK] Entorno activado

echo.
echo [4/6] Actualizando pip...
python -m pip install --upgrade pip --quiet
echo [OK] Pip actualizado

echo.
echo [5/6] Instalando dependencias...
echo     Esto puede tomar varios minutos...
pip install -r requirements.txt --quiet
if %errorLevel% neq 0 (
    echo [X] Error instalando dependencias
    echo     Intentando instalacion detallada...
    pip install -r requirements.txt
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas

:: Install drag and drop support
echo.
echo     Instalando soporte drag and drop...
pip install tkinterdnd2 --quiet 2>nul
if %errorLevel% == 0 (
    echo [OK] Drag and drop habilitado
) else (
    echo [!] Drag and drop no disponible - puedes hacer clic para seleccionar archivos
)

echo.
echo [6/6] Verificando FFmpeg...
ffmpeg -version >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] FFmpeg no encontrado
    echo.
    echo     FFmpeg es necesario para procesar video.
    echo     Por favor descargalo de: https://ffmpeg.org/download.html
    echo     Y agregalo al PATH del sistema.
    echo.
    echo     O ejecuta: winget install ffmpeg
    echo.
) else (
    echo [OK] FFmpeg encontrado
)

echo.
echo ============================================================
echo                 INSTALACION COMPLETADA
echo ============================================================
echo.
echo Para usar BOUT:
echo   1. Ejecuta "BOUT.bat" para abrir la interfaz grafica
echo   2. O usa la linea de comandos:
echo      venv\Scripts\python -m bout transcribe video.mp4 --diarize
echo.
echo Recuerda aceptar las licencias en HuggingFace:
echo   - https://hf.co/pyannote/speaker-diarization-3.1
echo   - https://hf.co/pyannote/segmentation-3.0
echo.
pause
