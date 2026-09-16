"""
Análise de andamentos: normalização, urgência, prazo estimado e formatadores.

Funções puras, sem I/O.

Copyright (c) 2026 Márcio Luis Amorim — Licença MIT
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from typing import Any

from themis.constantes import PALAVRAS_ALERTA, PALAVRAS_URGENTES, PRAZOS_TIPICOS

# Quantos andamentos recentes entram na análise de urgência
MOVIMENTOS_ANALISADOS = 10

# (data_hora, nome, complemento, novo)
Movimento = Sequence[Any]


def normalizar(texto: str | None) -> str:
    """Remove acentos e converte para minúsculas; None vira ''."""
    return unicodedata.normalize("NFD", (texto or "").lower()).encode("ascii", "ignore").decode()


def urgencia_movimento(nome: str, complemento: str = "") -> str:
    """Classifica um único andamento como 'urgente', 'alerta' ou 'ok'."""
    texto = normalizar(nome) + " " + normalizar(complemento)
    if any(p in texto for p in PALAVRAS_URGENTES):
        return "urgente"
    if any(p in texto for p in PALAVRAS_ALERTA):
        return "alerta"
    return "ok"


def detectar_urgencia(movimentos: Iterable[Movimento]) -> str:
    """Analisa os andamentos mais recentes; 'urgente' prevalece sobre 'alerta'."""
    resultado = "ok"
    for m in list(movimentos)[:MOVIMENTOS_ANALISADOS]:
        nome = m[1] if len(m) > 1 else ""
        complemento = m[2] if len(m) > 2 else ""
        nivel = urgencia_movimento(nome or "", complemento or "")
        if nivel == "urgente":
            return "urgente"
        if nivel == "alerta":
            resultado = "alerta"
    return resultado


def _parse_iso(iso: str | None) -> datetime | None:
    """Converte string ISO (com ou sem hora) em datetime; None se inválida."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso)[:19])
    except ValueError:
        return None


def calcular_prazo(nome_movimento: str, data_iso: str) -> tuple[str | None, int | None]:
    """Estima ('dd/mm/aaaa', dias) a partir de PRAZOS_TIPICOS; (None, None) se não se aplica."""
    nome = normalizar(nome_movimento)
    for chave, dias in PRAZOS_TIPICOS.items():
        if chave in nome:
            dt = _parse_iso(data_iso)
            if dt is None:
                return None, None
            return (dt + timedelta(days=dias)).strftime("%d/%m/%Y"), dias
    return None, None


def dias_desde(iso: str | None) -> int:
    """Dias corridos desde a data ISO; 9999 se vazia ou inválida."""
    dt = _parse_iso(iso)
    if dt is None:
        return 9999
    return (datetime.now() - dt).days


def formatar_data(iso: str | None) -> str:
    """'dd/mm/aaaa' ou '—' se vazia; devolve os 10 primeiros caracteres se não for ISO."""
    if not iso:
        return "—"
    dt = _parse_iso(iso)
    return dt.strftime("%d/%m/%Y") if dt else str(iso)[:10]


def formatar_data_hora(iso: str | None) -> str:
    """'dd/mm/aaaa HH:MM' ou '—' se vazia; devolve os 16 primeiros caracteres se não for ISO."""
    if not iso:
        return "—"
    dt = _parse_iso(iso)
    return dt.strftime("%d/%m/%Y %H:%M") if dt else str(iso)[:16]


def formatar_valor(valor: Any) -> str:
    """Formata como 'R$ 1.234,50'; '—' se vazio; string original se não for numérico."""
    if valor is None or valor == "":
        return "—"
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    return f"R$ {numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
