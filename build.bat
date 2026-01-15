@echo off
echo ============================================================
echo   SANTIESUN BOUT - Script de Compilacion
echo ============================================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo ERROR: No se encontro el entorno virtual.
    echo Ejecuta primero: install.bat
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo Limpiando builds anteriores...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo.
echo Compilando aplicacion con PyInstaller...
echo Esto puede tomar varios minutos...
echo.

pyinstaller --clean santiesun_bout.spec

if errorlevel 1 (
    echo.
    echo ERROR: Fallo la compilacion.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Compilacion exitosa!
echo   El ejecutable esta en: dist\SANTIESUN_BOUT\
echo ============================================================
echo.

pause
