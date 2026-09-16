@echo off
REM ============================================================
REM  THEMIS Monitor - Descoberta por OAB
REM  Copyright (c) 2026 Marcio Luis Amorim - Licenca MIT
REM ============================================================
chcp 65001 >nul
title THEMIS - Descoberta por OAB
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

"%PYTHON_EXE%" %PYTHON_ARGS% themis.py oab
if errorlevel 1 (
    echo.
    echo [ERRO] Algo deu errado. Leia a mensagem acima.
)
echo.
pause
