@echo off
echo ============================================================
echo   Instalador de FFmpeg para Windows
echo ============================================================
echo.

REM Verificar si ya existe
where ffmpeg >nul 2>&1
if not errorlevel 1 (
    echo FFmpeg ya esta instalado!
    ffmpeg -version | findstr "ffmpeg version"
    pause
    exit /b 0
)

echo FFmpeg no encontrado. Descargando...
echo.

REM Crear carpeta temporal
if not exist "ffmpeg_temp" mkdir ffmpeg_temp
cd ffmpeg_temp

REM Descargar FFmpeg usando PowerShell
echo Descargando FFmpeg (esto puede tardar unos minutos)...
powershell -Command "& {Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile 'ffmpeg.zip'}"

if not exist "ffmpeg.zip" (
    echo ERROR: No se pudo descargar FFmpeg.
    echo Por favor descargalo manualmente de:
    echo https://www.gyan.dev/ffmpeg/builds/
    pause
    exit /b 1
)

echo Extrayendo archivos...
powershell -Command "& {Expand-Archive -Path 'ffmpeg.zip' -DestinationPath '.' -Force}"

REM Encontrar la carpeta extraida
for /d %%i in (ffmpeg-*) do set FFMPEG_DIR=%%i

if not defined FFMPEG_DIR (
    echo ERROR: No se pudo extraer FFmpeg.
    pause
    exit /b 1
)

echo Copiando a C:\ffmpeg...
if not exist "C:\ffmpeg" mkdir "C:\ffmpeg"
xcopy /E /Y "%FFMPEG_DIR%\bin\*" "C:\ffmpeg\" >nul

REM Agregar al PATH del usuario
echo Agregando al PATH...
setx PATH "%PATH%;C:\ffmpeg" >nul 2>&1

REM Limpiar
cd ..
rmdir /S /Q ffmpeg_temp

echo.
echo ============================================================
echo   FFmpeg instalado correctamente en C:\ffmpeg
echo ============================================================
echo.
echo IMPORTANTE: Cierra y abre una nueva terminal para que
echo el PATH se actualice correctamente.
echo.
echo Para verificar, abre una nueva terminal y ejecuta:
echo   ffmpeg -version
echo.
pause
