@echo off
REM ============================================================
REM  MAAT Monitor - Painel Web
REM  Copyright (c) 2026 Marcio Luis Amorim - Licenca MIT
REM ============================================================
chcp 65001 >nul
title MAAT - Painel Web
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
set "PYTHON_ARGS="
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
    where python >nul 2>nul
    if errorlevel 1 (
        where py >nul 2>nul
        if errorlevel 1 (
            echo [ERRO] Python nao encontrado. Instale em https://www.python.org/downloads/
            echo        marcando "Add Python to PATH", reinicie o PC e rode instalar.bat.
            pause
            exit /b 1
        )
        set "PYTHON_EXE=py"
        set "PYTHON_ARGS=-3"
    )
)

echo.
echo  Iniciando o painel em http://127.0.0.1:5000 ...
echo  O navegador abrira sozinho. Para encerrar: feche esta janela ou Ctrl+C.
echo.
"%PYTHON_EXE%" %PYTHON_ARGS% maat.py painel
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao iniciar o painel. Leia a mensagem acima.
    pause
)
