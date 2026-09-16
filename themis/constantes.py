"""
Constantes do THEMIS Monitor: tribunais do DataJud, palavras-chave e prazos.

Copyright (c) 2026 Márcio Luis Amorim — Licença MIT
"""

from __future__ import annotations

# ------------------------------------------------------------------
# API pública DataJud (CNJ)
# ------------------------------------------------------------------

DATAJUD_BASE_URL = "https://api-publica.datajud.cnj.jus.br"

# Chave PÚBLICA oficial, publicada pelo próprio CNJ na documentação do DataJud
# (https://datajud-wiki.cnj.jus.br/api-publica/acesso). Não é um segredo:
# é a mesma chave distribuída a qualquer pessoa que acesse a API pública.
DATAJUD_API_KEY_PUBLICA = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="

# ------------------------------------------------------------------
# Tribunais
# ------------------------------------------------------------------

# Código TR (2 dígitos) da Justiça Estadual/Eleitoral → sigla da UF.
# Mesma numeração usada pelo CNJ para os TJs (J=8) e TREs (J=6).
TR_PARA_UF: dict[str, str] = {
    "01": "ac", "02": "al", "03": "ap", "04": "am", "05": "ba",
    "06": "ce", "07": "dft", "08": "es", "09": "go", "10": "ma",
    "11": "mt", "12": "ms", "13": "mg", "14": "pa", "15": "pb",
    "16": "pr", "17": "pe", "18": "pi", "19": "rj", "20": "rn",
    "21": "rs", "22": "ro", "23": "rr", "24": "sc", "25": "se",
    "26": "sp", "27": "to",
}

# UFs com Tribunal de Justiça Militar próprio (J=9)
UFS_JUSTICA_MILITAR_ESTADUAL = ("mg", "rs", "sp")


def _montar_tribunais() -> dict[str, dict]:
    """Gera o catálogo completo de tribunais expostos pelo DataJud."""
    tribunais: dict[str, dict] = {}

    def add(codigo: str, nome: str, tipo: str) -> None:
        tribunais[codigo] = {"nome": nome, "alias": f"api_publica_{codigo}", "tipo": tipo}

    add("stf", "STF", "Supremo")
    add("stj", "STJ", "Superior")
    add("tst", "TST", "Trabalho")
    add("tse", "TSE", "Eleitoral")
    add("stm", "STM", "Militar")

    for n in range(1, 7):
        add(f"trf{n}", f"TRF-{n}", "Federal")

    for n in range(1, 25):
        add(f"trt{n}", f"TRT-{n}", "Trabalho")

    for uf in TR_PARA_UF.values():
        add(f"tj{uf}", f"TJ-{uf.upper()}", "Estadual")

    for uf in TR_PARA_UF.values():
        add(f"tre-{uf}", f"TRE-{uf.upper()}", "Eleitoral")

    for uf in UFS_JUSTICA_MILITAR_ESTADUAL:
        add(f"tjm{uf}", f"TJM-{uf.upper()}", "Militar Estadual")

    return tribunais


TRIBUNAIS: dict[str, dict] = _montar_tribunais()

# ------------------------------------------------------------------
# Palavras-chave (sem acento, minúsculas — comparar após normalizar())
# ------------------------------------------------------------------

PALAVRAS_URGENTES: list[str] = [
    "mandado de prisao",
    "penhora",
    "bloqueio judicial",
    "arresto",
    "sequestro de bens",
    "liminar",
    "tutela de urgencia",
    "busca e apreensao",
    "leilao",
    "hasta publica",
    "execucao fiscal",
]

PALAVRAS_ALERTA: list[str] = [
    "intimacao",
    "citacao",
    "notificacao",
    "prazo",
    "sentenca",
    "acordao",
    "transito em julgado",
    "julgado",
    "embargos",
    "apelacao",
    "recurso",
    "agravo",
    "audiencia",
    "pericia",
    "julgamento",
    "decisao",
    "despacho",
]

# Prazos típicos em dias corridos por tipo de andamento (estimativa, não substitui o PJe)
PRAZOS_TIPICOS: dict[str, int] = {
    "intimacao": 15,
    "citacao": 15,
    "notificacao": 10,
    "embargos": 5,
    "agravo": 15,
    "apelacao": 15,
    "recurso": 15,
    "contestacao": 15,
    "resposta": 15,
}
