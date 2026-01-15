@echo off
echo ============================================================
echo   INSTALADOR - Transcriptor Automatico de Videos
echo ============================================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado.
    echo Descargalo de: https://www.python.org/downloads/
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

echo [1/4] Python encontrado
python --version

REM Crear entorno virtual
echo.
echo [2/4] Creando entorno virtual...
if not exist "venv" (
    python -m venv venv
)

REM Activar entorno virtual
call venv\Scripts\activate.bat

REM Actualizar pip
echo.
echo [3/4] Actualizando pip...
python -m pip install --upgrade pip

REM Instalar PyTorch con CUDA
echo.
echo [4/4] Instalando dependencias...
echo.
echo Instalando PyTorch con soporte GPU (esto puede tardar)...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

echo.
echo Instalando otras dependencias...
pip install -r requirements.txt

echo.
echo ============================================================
echo   INSTALACION COMPLETADA
echo ============================================================
echo.
echo IMPORTANTE - Pasos adicionales:
echo.
echo 1. FFMPEG: Si no lo tienes, descargalo de:
echo    https://www.gyan.dev/ffmpeg/builds/
echo    Descarga "ffmpeg-release-essentials.zip"
echo    Extrae y agrega la carpeta "bin" al PATH del sistema.
echo.
echo 2. HUGGING FACE (para identificacion de hablantes):
echo    a) Crea cuenta en: https://huggingface.co
echo    b) Acepta terminos en: https://huggingface.co/pyannote/speaker-diarization-3.1
echo    c) Genera token en: https://huggingface.co/settings/tokens
echo    d) Ejecuta: set HF_TOKEN=tu_token_aqui
echo.
echo Para ejecutar la aplicacion usa: run.bat
echo.
pause
