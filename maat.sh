#!/usr/bin/env bash
# ============================================================
#  MAAT Monitor - lançador para macOS / Linux
#  Copyright (c) 2026 Márcio Luis Amorim - Licença MIT
#
#  Uso:
#    ./maat.sh instalar          (uma vez)
#    ./maat.sh monitorar
#    ./maat.sh painel
#    ./maat.sh consultar <CNJ>
#    ./maat.sh testar
#    ./maat.sh oab
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

PY="python3"
command -v "$PY" >/dev/null 2>&1 || PY="python"
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "[ERRO] Python 3 não encontrado. Instale em https://www.python.org/downloads/"
    exit 1
fi
[ -x "venv/bin/python" ] && PY="venv/bin/python"

case "${1:-}" in
    instalar)
        echo "Criando ambiente isolado (venv)..."
        python3 -m venv venv
        PY="venv/bin/python"
        "$PY" -m pip install --upgrade pip >/dev/null
        "$PY" -m pip install -r requirements.txt
        "$PY" maat.py --preparar
        echo
        echo "Instalação concluída. Edite config.ini e processos.txt, depois: ./maat.sh monitorar"
        ;;
    "")
        echo "Uso: ./maat.sh {instalar|monitorar|painel|consultar <CNJ>|testar|oab}"
        exit 2
        ;;
    *)
        exec "$PY" maat.py "$@"
        ;;
esac
