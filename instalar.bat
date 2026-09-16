@echo off
REM ============================================================
REM  MAAT Monitor - Instalador (execute UMA vez)
REM  Copyright (c) 2026 Marcio Luis Amorim - Licenca MIT
REM ============================================================
chcp 65001 >nul
title MAAT - Instalador
cd /d "%~dp0"

echo.
echo ============================================================
echo   MAAT Monitor - Instalacao
echo ============================================================
echo.

set "PYTHON_EXE=python"
set "PYTHON_ARGS="
where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo [ERRO] Python nao encontrado.
        echo.
        echo   1. Acesse https://www.python.org/downloads/
        echo   2. Baixe e execute o instalador do Python 3
        echo   3. IMPORTANTE: marque "Add Python to PATH" antes de Install
        echo   4. Reinicie o computador e rode este instalar.bat de novo
        echo.
        pause
        exit /b 1
    )
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
)

echo [OK] Python encontrado:
"%PYTHON_EXE%" %PYTHON_ARGS% --version
echo.

echo Criando ambiente isolado (venv)...
"%PYTHON_EXE%" %PYTHON_ARGS% -m venv venv
if errorlevel 1 (
    echo [AVISO] Nao foi possivel criar o venv. Instalando no Python global.
    set "PIP=%PYTHON_EXE% %PYTHON_ARGS% -m pip"
) else (
    set "PIP=venv\Scripts\python.exe -m pip"
)

echo Instalando dependencias...
%PIP% install --upgrade pip >nul
%PIP% install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao instalar dependencias. Verifique sua internet e tente de novo.
    pause
    exit /b 1
)

echo.
echo Preparando arquivos de configuracao...
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe maat.py --preparar
) else (
    "%PYTHON_EXE%" %PYTHON_ARGS% maat.py --preparar
)

echo.
echo ============================================================
echo   INSTALACAO CONCLUIDA!
echo ============================================================
echo.
echo   Proximos passos:
echo     1. Abra config.ini e coloque sua OAB e seu nome
echo     2. Abra processos.txt e cole os numeros CNJ (ou use painel.bat)
echo     3. Clique duplo em monitorar.bat
echo.
pause
