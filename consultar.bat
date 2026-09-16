@echo off
REM ============================================================
REM  THEMIS Monitor - Consulta Avulsa
REM  Copyright (c) 2026 Marcio Luis Amorim - Licenca MIT
REM ============================================================
chcp 65001 >nul
title THEMIS - Consulta Avulsa
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
setlocal EnableExtensions EnableDelayedExpansion
echo.
echo  Digite o numero CNJ (ex.: 0000001-23.2025.8.26.0100)
echo.
set /p "CNJ=Numero CNJ: "
if "!CNJ!"=="" (
    echo Nenhum numero informado.
    pause
    exit /b 1
)
rem Delayed expansion evita que caracteres especiais sejam interpretados pelo cmd.
"%PYTHON_EXE%" %PYTHON_ARGS% themis.py consultar "!CNJ!"
if errorlevel 1 (
    echo.
    echo [ERRO] Consulta falhou. Verifique o numero e a conexao com a internet.
)
echo.
pause
