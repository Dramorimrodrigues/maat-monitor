"""
Caminhos de dados, leitura de config.ini e de processos.txt do THEMIS Monitor.

Copyright (c) 2026 Márcio Luis Amorim — Licença MIT
"""

from __future__ import annotations

import configparser
import os
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from themis import cnj

# Raiz do repositório: pai do pacote themis/ (onde ficam os arquivos .example)
RAIZ_REPO = Path(__file__).resolve().parent.parent

# Protege processos.txt contra escritas simultâneas (painel + CLI na mesma máquina)
CADASTRO_LOCK = threading.Lock()

CARACTERES_PROIBIDOS = ("|", "\r", "\n")


@dataclass(frozen=True)
class Caminhos:
    """Localização dos arquivos de dados do usuário e dos modelos de exemplo."""

    base: Path
    config: Path
    processos: Path
    banco: Path
    relatorios: Path
    backups: Path
    exemplos: Path


class Processo(NamedTuple):
    """Uma linha de processos.txt já validada (cnj com 20 dígitos)."""

    cnj: str
    rotulo: str
    cliente: str
    area: str


def caminhos() -> Caminhos:
    """Monta os caminhos a partir da env THEMIS_HOME (ou da raiz do repositório)."""
    home = os.environ.get("THEMIS_HOME", "").strip()
    base = Path(home).expanduser().resolve() if home else RAIZ_REPO
    return Caminhos(
        base=base,
        config=base / "config.ini",
        processos=base / "processos.txt",
        banco=base / "themis.db",
        relatorios=base / "relatorios",
        backups=base / "backups",
        exemplos=RAIZ_REPO,
    )


def garantir_arquivos_iniciais(c: Caminhos) -> list[str]:
    """Cria config.ini/processos.txt a partir dos exemplos e as pastas de saída. Devolve os nomes criados."""
    criados: list[str] = []
    c.base.mkdir(parents=True, exist_ok=True)
    for destino, exemplo in (
        (c.config, c.exemplos / "config.example.ini"),
        (c.processos, c.exemplos / "processos.example.txt"),
    ):
        if not destino.exists() and exemplo.exists():
            shutil.copyfile(exemplo, destino)
            criados.append(destino.name)
    c.relatorios.mkdir(parents=True, exist_ok=True)
    c.backups.mkdir(parents=True, exist_ok=True)
    return criados


def carregar_config(c: Caminhos) -> dict:
    """Lê config.ini com fallbacks sensatos; sem arquivo, devolve apenas os fallbacks."""
    parser = configparser.ConfigParser(interpolation=None)
    if c.config.exists():
        parser.read(c.config, encoding="utf-8")

    def texto(secao: str, chave: str, padrao: str) -> str:
        return parser.get(secao, chave, fallback=padrao).strip()

    def inteiro(secao: str, chave: str, padrao: int) -> int:
        try:
            return parser.getint(secao, chave, fallback=padrao)
        except ValueError:
            return padrao

    def decimal(secao: str, chave: str, padrao: float) -> float:
        try:
            return parser.getfloat(secao, chave, fallback=padrao)
        except ValueError:
            return padrao

    tribunais = [t.strip().lower() for t in texto("tribunais", "ativos", "tjsp").split(",")]
    return {
        "oab_numero": texto("advogado", "oab_numero", ""),
        "oab_uf": texto("advogado", "oab_uf", "SP").upper(),
        "nome": texto("advogado", "nome", "Advogado(a)"),
        "tribunais_ativos": [t for t in tribunais if t],
        "dias_alerta_parado": inteiro("execucao", "dias_alerta_parado", 30),
        "delay_segundos": decimal("execucao", "delay_segundos", 1.5),
        "email_ativo": texto("notificacoes", "email_ativo", "nao"),
        "email_smtp": texto("notificacoes", "email_smtp", "smtp.gmail.com"),
        "email_porta": inteiro("notificacoes", "email_porta", 587),
        "email_remetente": texto("notificacoes", "email_remetente", ""),
        "email_senha_app": texto("notificacoes", "email_senha_app", ""),
        "email_destinatario": texto("notificacoes", "email_destinatario", ""),
        "whatsapp_ativo": texto("notificacoes", "whatsapp_ativo", "nao"),
        "whatsapp_telefone": texto("notificacoes", "whatsapp_telefone", ""),
        "whatsapp_token": texto("notificacoes", "whatsapp_token", ""),
    }


def _linhas_uteis(caminho: Path):
    """Itera (numero_da_linha, conteudo) ignorando comentários e linhas vazias."""
    with open(caminho, encoding="utf-8-sig") as f:
        for numero, bruta in enumerate(f, start=1):
            linha = bruta.strip()
            if not linha or linha.startswith("#"):
                continue
            yield numero, linha


def _dividir_linha(linha: str) -> list[str]:
    """Divide `CNJ | Apelido | Cliente | Area` em 4 campos aparados."""
    partes = [p.strip() for p in linha.split("|")]
    partes += [""] * (4 - len(partes))
    return partes[:4]


def carregar_processos(c: Caminhos) -> tuple[list[Processo], list[str]]:
    """Lê processos.txt. Devolve (processos válidos sem duplicatas, avisos em português)."""
    processos: list[Processo] = []
    avisos: list[str] = []
    if not c.processos.exists():
        avisos.append(f"Arquivo não encontrado: {c.processos}")
        return processos, avisos
    vistos: set[str] = set()
    for numero, linha in _linhas_uteis(c.processos):
        cnj_parte, rotulo, cliente, area = _dividir_linha(linha)
        cnj_limpo, erro = cnj.validar(cnj_parte)
        if cnj_limpo is None:
            avisos.append(f"Linha {numero} ignorada: {erro} ({cnj_parte})")
            continue
        if cnj_limpo in vistos:
            avisos.append(f"Linha {numero} ignorada: processo repetido ({cnj.formatar(cnj_limpo)})")
            continue
        vistos.add(cnj_limpo)
        processos.append(Processo(cnj_limpo, rotulo, cliente, area))
    return processos, avisos


def _cnjs_existentes(caminho: Path) -> set[str]:
    """Conjunto de CNJs (limpos) já presentes no arquivo, válidos ou não."""
    if not caminho.exists():
        return set()
    return {cnj.limpar(linha.split("|")[0]) for _, linha in _linhas_uteis(caminho)}


def _montar_linha(cnj_fmt: str, rotulo: str, cliente: str, area: str) -> str:
    """Monta a linha aparando os campos finais vazios (ex.: só o CNJ)."""
    campos = [cnj_fmt, rotulo, cliente, area]
    while len(campos) > 1 and not campos[-1]:
        campos.pop()
    return " | ".join(campos)


def _termina_em_quebra(caminho: Path) -> bool:
    """True se o arquivo está vazio/ausente ou termina com quebra de linha."""
    if not caminho.exists() or caminho.stat().st_size == 0:
        return True
    with open(caminho, "rb") as f:
        f.seek(-1, os.SEEK_END)
        return f.read(1) in (b"\n", b"\r")


def adicionar_processos(c: Caminhos, itens: list[Processo]) -> tuple[list[str], list[str]]:
    """Acrescenta processos ao processos.txt. Devolve (CNJs formatados adicionados, ignorados com motivo)."""
    adicionados: list[str] = []
    ignorados: list[str] = []
    preparados: list[tuple[str, str]] = []

    for item in itens:
        campos = [str(x or "") for x in (item.cnj, item.rotulo, item.cliente, item.area)]
        if any(ch in campo for campo in campos for ch in CARACTERES_PROIBIDOS):
            ignorados.append(
                f"{campos[0].strip() or '(vazio)'}: campos não podem conter barra vertical ou quebra de linha."
            )
            continue
        campos = [x.strip() for x in campos]
        cnj_limpo, erro = cnj.validar(campos[0])
        if cnj_limpo is None:
            ignorados.append(f"{campos[0] or '(vazio)'}: {erro}")
            continue
        preparados.append((cnj_limpo, _montar_linha(cnj.formatar(cnj_limpo), *campos[1:])))

    with CADASTRO_LOCK:
        existentes = _cnjs_existentes(c.processos)
        linhas: list[str] = []
        for cnj_limpo, linha in preparados:
            cnj_fmt = cnj.formatar(cnj_limpo)
            if cnj_limpo in existentes:
                ignorados.append(f"{cnj_fmt}: já existe.")
                continue
            existentes.add(cnj_limpo)
            linhas.append(linha)
            adicionados.append(cnj_fmt)
        if linhas:
            c.processos.parent.mkdir(parents=True, exist_ok=True)
            prefixo = "" if _termina_em_quebra(c.processos) else "\n"
            with open(c.processos, "a", encoding="utf-8") as f:
                f.write(prefixo + "\n".join(linhas) + "\n")

    return adicionados, ignorados
