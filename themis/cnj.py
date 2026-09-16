"""
Numeração única de processos (CNJ): limpeza, formatação, dígito verificador e tribunal.

Funções puras, sem I/O. Referência: Resolução CNJ nº 65/2008.

Copyright (c) 2026 Márcio Luis Amorim — Licença MIT
"""

from __future__ import annotations

import re

from themis.constantes import TR_PARA_UF, TRIBUNAIS, UFS_JUSTICA_MILITAR_ESTADUAL

TAMANHO = 20

MSG_TAMANHO = "Número CNJ deve ter 20 dígitos (formato 0000000-00.0000.0.00.0000)."
MSG_DIGITO = "Número CNJ com dígito verificador inválido — confira se o número foi digitado corretamente."

_RE_NAO_DIGITO = re.compile(r"\D")
_RE_CNJ = re.compile(r"\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}")


def limpar(texto: str) -> str:
    """Mantém apenas os dígitos do texto."""
    return _RE_NAO_DIGITO.sub("", texto or "")


def formatar(numero: str) -> str:
    """Formata como NNNNNNN-DD.AAAA.J.TR.OOOO; devolve a entrada intacta se não tiver 20 dígitos."""
    n = limpar(numero)
    if len(n) != TAMANHO:
        return numero
    return f"{n[0:7]}-{n[7:9]}.{n[9:13]}.{n[13]}.{n[14:16]}.{n[16:20]}"


def validar_digito(cnj_limpo: str) -> bool:
    """Confere o dígito verificador (módulo 97, Resolução CNJ 65/2008)."""
    if len(cnj_limpo) != TAMANHO or not cnj_limpo.isdigit():
        return False
    dd = int(cnj_limpo[7:9])
    # NNNNNNN + AAAA + J + TR + OOOO + "00" (os "00" ocupam o lugar do DD)
    base = cnj_limpo[0:7] + cnj_limpo[9:20] + "00"
    return dd == 98 - (int(base) % 97)


def identificar_tribunal(cnj_limpo: str) -> str | None:
    """Deduz o código do tribunal (chave de TRIBUNAIS) pelos campos J e TR do número."""
    if len(cnj_limpo) != TAMANHO or not cnj_limpo.isdigit():
        return None
    j, tr = cnj_limpo[13], cnj_limpo[14:16]  # Resolução CNJ 65/2008: NNNNNNN-DD.AAAA.J.TR.OOOO
    uf = TR_PARA_UF.get(tr)

    codigo: str | None = None
    if j == "1":
        codigo = "stf"
    elif j == "3":
        codigo = "stj"
    elif j == "4":
        codigo = f"trf{int(tr)}"
    elif j == "5":
        codigo = "tst" if tr == "00" else f"trt{int(tr)}"
    elif j == "6":
        codigo = "tse" if tr == "00" else (f"tre-{uf}" if uf else None)
    elif j == "7":
        codigo = "stm" if tr == "00" else None
    elif j == "8":
        codigo = f"tj{uf}" if uf else None
    elif j == "9":
        codigo = f"tjm{uf}" if uf in UFS_JUSTICA_MILITAR_ESTADUAL else None
    # J=2 (CNJ) não é tribunal consultável no DataJud.

    return codigo if codigo in TRIBUNAIS else None


def validar(texto: str) -> tuple[str | None, str | None]:
    """Devolve (cnj_limpo, None) se válido ou (None, mensagem de erro em português)."""
    n = limpar(texto)
    if len(n) != TAMANHO:
        return None, MSG_TAMANHO
    if not validar_digito(n):
        return None, MSG_DIGITO
    return n, None


def extrair_todos(texto: str) -> list[str]:
    """Extrai todos os números CNJ válidos do texto, sem duplicatas, na ordem de aparição."""
    encontrados: list[str] = []
    for achado in _RE_CNJ.findall(texto or ""):
        n = limpar(achado)
        if validar_digito(n) and n not in encontrados:
            encontrados.append(n)
    return encontrados
