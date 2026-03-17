@echo off
title Dashboard iFood - Allury Perfumaria
echo.
echo  ====================================
echo   Dashboard iFood - Allury Perfumaria
echo  ====================================
echo.

:: Verifica se Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale em https://python.org
    pause
    exit /b 1
)

:: Instala dependencias se necessario
echo Verificando dependencias...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias...
    pip install -r "%~dp0requirements.txt"
)

echo.
echo Iniciando servidor em http://localhost:9000
echo Pressione Ctrl+C para parar.
echo.
start "" http://localhost:9000
python "%~dp0ifood_server.py"
pause
