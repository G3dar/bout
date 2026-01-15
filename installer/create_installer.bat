@echo off
title BOUT - Crear Instalador
echo.
echo ============================================================
echo           BOUT - Creador de Instalador
echo ============================================================
echo.

:: Check if PS2EXE is installed
powershell -Command "Get-Module -ListAvailable -Name ps2exe" >nul 2>&1
if %errorLevel% neq 0 (
    echo Instalando PS2EXE...
    powershell -Command "Install-Module -Name ps2exe -Force -Scope CurrentUser"
)

echo.
echo Compilando instalador...
echo.

:: Create output directory
if not exist "output" mkdir output

:: Compile PowerShell to EXE
powershell -Command "Invoke-PS2EXE -InputFile '.\BOUT_Installer.ps1' -OutputFile '.\output\BOUT_Setup.exe' -requireAdmin -noConsole -title 'BOUT Installer' -company 'BOUT' -product 'BOUT Video Transcription' -version '2.0.0.0'"

if exist "output\BOUT_Setup.exe" (
    echo.
    echo ============================================================
    echo         INSTALADOR CREADO EXITOSAMENTE!
    echo ============================================================
    echo.
    echo Archivo: output\BOUT_Setup.exe
    echo.
    echo Este archivo incluye:
    echo   - Descarga automatica de BOUT desde GitHub
    echo   - Instalacion de Python si es necesario
    echo   - Instalacion de FFmpeg si es necesario
    echo   - Creacion de entorno virtual
    echo   - Instalacion de dependencias
    echo   - Acceso directo en escritorio
    echo   - Tutorial de configuracion
    echo.
) else (
    echo.
    echo ERROR: No se pudo crear el instalador
    echo.
)

pause
