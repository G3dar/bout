@echo off
REM Script para detectar GPU NVIDIA
REM Retorna el nombre de la GPU o "NO_GPU"

where nvidia-smi >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=*" %%i in ('nvidia-smi --query-gpu=name --format=csv,noheader 2^>nul') do (
        echo %%i
        exit /b 0
    )
)
echo NO_GPU
exit /b 1
