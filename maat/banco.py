"""
Banco de dados SQLite local do MAAT Monitor: schema, gravação, leitura e backup.

Copyright (c) 2026 Márcio Luis Amorim — Licença MIT
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from maat import analise, cnj

if TYPE_CHECKING:  # pragma: no cover
    from maat.config import Caminhos

BACKUPS_MANTIDOS = 10
PREFIXO_BACKUP = "maat_backup_"
LIMITE_MOVIMENTOS = 100

# Colunas acrescentadas ao longo das versões. Lista CONSTANTE: nunca vem de entrada do usuário,
# por isso é seguro interpolá-la no ALTER TABLE (SQLite não aceita parâmetros em DDL).
_COLUNAS_PROCESSOS_EXTRA: tuple[tuple[str, str], ...] = (
    ("rotulo", "TEXT DEFAULT ''"),
    ("valor_causa", "TEXT DEFAULT ''"),
    ("total_movimentos", "INTEGER DEFAULT 0"),
    ("cliente", "TEXT DEFAULT ''"),
    ("area", "TEXT DEFAULT ''"),
    ("status_processo", "TEXT DEFAULT 'Ativo'"),
)

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS processos (
        cnj TEXT PRIMARY KEY,
        rotulo TEXT DEFAULT '',
        cliente TEXT DEFAULT '',
        area TEXT DEFAULT '',
        status_processo TEXT DEFAULT 'Ativo',
        tribunal TEXT,
        classe TEXT,
        assunto TEXT,
        orgao_julgador TEXT,
        grau TEXT,
        valor_causa TEXT DEFAULT '',
        data_ajuizamento TEXT,
        data_ultima_atualizacao TEXT,
        total_movimentos INTEGER DEFAULT 0,
        json_completo TEXT,
        primeiro_check TEXT,
        ultimo_check TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS movimentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cnj TEXT,
        data_hora TEXT,
        codigo INTEGER,
        nome TEXT,
        complemento TEXT,
        detectado_em TEXT,
        novo INTEGER DEFAULT 0,
        UNIQUE(cnj, data_hora, codigo, nome)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS execucoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_hora TEXT,
        total_processos INTEGER,
        sucesso INTEGER,
        erros INTEGER,
        novos_andamentos INTEGER
    )
    """,
)


def conectar(caminho: Path | str) -> sqlite3.Connection:
    """Abre (ou cria) o banco, garante o schema e devolve a conexão com row_factory=Row."""
    conn = sqlite3.connect(str(caminho))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if str(caminho) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    with conn:
        for ddl in _SCHEMA:
            conn.execute(ddl)
        existentes = {r["name"] for r in conn.execute("PRAGMA table_info(processos)")}
        for coluna, definicao in _COLUNAS_PROCESSOS_EXTRA:
            if coluna not in existentes:
                conn.execute(f"ALTER TABLE processos ADD COLUMN {coluna} {definicao}")  # noqa: S608
    return conn


def _nome_de(obj: Any) -> str:
    """Extrai `nome` de um dicionário do DataJud, ou '?' quando ausente."""
    if isinstance(obj, dict) and obj.get("nome"):
        return str(obj["nome"])
    return "?"


def _fonte_valida(fonte: Any) -> bool:
    """Valida a estrutura inteira do documento DataJud antes de qualquer escrita."""
    if not isinstance(fonte, dict) or not fonte:
        return False
    movimentos = fonte.get("movimentos") or []
    assuntos = fonte.get("assuntos") or []
    if not isinstance(movimentos, list) or not isinstance(assuntos, list):
        return False
    if any(not isinstance(x, dict) for x in movimentos + assuntos):
        return False
    for mov in movimentos:
        comps = mov.get("complementosTabelados") or []
        if not isinstance(comps, list) or any(not isinstance(x, dict) for x in comps):
            return False
    return True


def salvar_resultado(
    conn: sqlite3.Connection,
    cnj_limpo: str,
    fonte: dict,
    rotulo: str = "",
    cliente: str = "",
    area: str = "",
) -> tuple[bool, int]:
    """Grava o documento do DataJud. Devolve (True, n_movimentos_novos) ou (False, 0) se a fonte é inválida."""
    if not _fonte_valida(fonte):
        return False, 0

    movimentos: list[dict] = fonte.get("movimentos") or []
    assuntos: list[dict] = fonte.get("assuntos") or []
    agora = datetime.now().isoformat()

    classe = _nome_de(fonte.get("classe"))
    orgao = _nome_de(fonte.get("orgaoJulgador"))
    assunto = ", ".join(str(a.get("nome") or "") for a in assuntos)[:300]
    grau = str(fonte.get("grau") or "?")
    tribunal = str(fonte.get("tribunal") or "?")
    data_aj = str(fonte.get("dataAjuizamento") or "")
    data_at = str(fonte.get("dataHoraUltimaAtualizacao") or "")
    valor_novo = fonte.get("valorCausa")
    json_fonte = json.dumps(fonte, ensure_ascii=False)

    novos = 0
    with conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT rotulo, cliente, area, valor_causa, json_completo FROM processos WHERE cnj = ?",
            (cnj_limpo,),
        )
        row = cur.fetchone()
        tinha_historico = bool(row and row["json_completo"])

        rotulo_f = rotulo or (row["rotulo"] if row else "") or ""
        cliente_f = cliente or (row["cliente"] if row else "") or ""
        area_f = area or (row["area"] if row else "") or ""
        if valor_novo in (None, ""):
            valor = (row["valor_causa"] if row else "") or ""
        else:
            valor = str(valor_novo)

        if row:
            cur.execute(
                """
                UPDATE processos
                SET rotulo=?, tribunal=?, classe=?, assunto=?, orgao_julgador=?, grau=?,
                    valor_causa=?, data_ajuizamento=?, data_ultima_atualizacao=?,
                    total_movimentos=?, json_completo=?, ultimo_check=?, cliente=?, area=?
                WHERE cnj=?
                """,
                (rotulo_f, tribunal, classe, assunto, orgao, grau, valor, data_aj, data_at,
                 len(movimentos), json_fonte, agora, cliente_f, area_f, cnj_limpo),
            )
        else:
            cur.execute(
                """
                INSERT INTO processos
                    (cnj, rotulo, cliente, area, status_processo, tribunal, classe, assunto,
                     orgao_julgador, grau, valor_causa, data_ajuizamento, data_ultima_atualizacao,
                     total_movimentos, json_completo, primeiro_check, ultimo_check)
                VALUES (?, ?, ?, ?, 'Ativo', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cnj_limpo, rotulo_f, cliente_f, area_f, tribunal, classe, assunto, orgao, grau,
                 valor, data_aj, data_at, len(movimentos), json_fonte, agora, agora),
            )

        marcar_novo = 1 if tinha_historico else 0
        for mov in movimentos:
            comps = mov.get("complementosTabelados") or []
            complemento = "; ".join(str(x.get("nome") or "") for x in comps)[:500]
            data_hora = str(mov.get("dataHora") or "")
            nome = str(mov.get("nome") or "")
            try:
                codigo = int(mov.get("codigo") or 0)
            except (TypeError, ValueError):
                codigo = 0
            # COALESCE reconhece também linhas antigas com campos NULL na chave.
            cur.execute(
                """
                INSERT INTO movimentos (cnj, data_hora, codigo, nome, complemento, detectado_em, novo)
                SELECT ?, ?, ?, ?, ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM movimentos
                    WHERE cnj = ? AND COALESCE(data_hora, '') = ?
                      AND COALESCE(codigo, 0) = ? AND COALESCE(nome, '') = ?
                )
                """,
                (cnj_limpo, data_hora, codigo, nome, complemento, agora, marcar_novo,
                 cnj_limpo, data_hora, codigo, nome),
            )
            if tinha_historico and cur.rowcount > 0:
                novos += cur.rowcount
    return True, novos


def _movimentos_de(conn: sqlite3.Connection, cnj_limpo: str) -> list[tuple]:
    """Movimentos mais recentes de um processo como tuplas (data_hora, nome, complemento, novo)."""
    cur = conn.execute(
        """
        SELECT data_hora, nome, complemento, novo FROM movimentos
        WHERE cnj = ? ORDER BY julianday(data_hora) DESC, id DESC LIMIT ?
        """,
        (cnj_limpo, LIMITE_MOVIMENTOS),
    )
    return [tuple(r) for r in cur.fetchall()]


def _prazo_txt(movs: list[tuple]) -> str:
    """Texto do primeiro prazo estimado entre os 5 movimentos mais recentes."""
    for data_hora, nome, _comp, _novo in movs[:5]:
        data_fmt, dias = analise.calcular_prazo(nome or "", data_hora or "")
        if data_fmt:
            return f"Prazo estimado ({nome}): {data_fmt} ({dias} dias corridos)"
    return ""


def ler_processos(
    conn: sqlite3.Connection, dias_parado: int = 30, apenas_cnj: str | None = None
) -> list[dict]:
    """Lista os processos com movimentos, urgência, prazo e campos formatados, por último check DESC."""
    sql = """
        SELECT cnj, rotulo, cliente, area, status_processo, tribunal, classe, assunto,
               orgao_julgador, grau, valor_causa, data_ajuizamento, data_ultima_atualizacao,
               total_movimentos, primeiro_check, ultimo_check
        FROM processos
    """
    params: tuple = ()
    if apenas_cnj:
        sql += " WHERE cnj = ?"
        params = (apenas_cnj,)
    sql += " ORDER BY ultimo_check DESC"

    resultado: list[dict] = []
    for r in conn.execute(sql, params).fetchall():
        p = dict(r)
        movs = _movimentos_de(conn, p["cnj"])
        dias_sem = analise.dias_desde(p.get("data_ultima_atualizacao") or "")
        p["movimentos"] = movs
        p["tem_novo"] = any(m[3] for m in movs)
        p["urgencia"] = analise.detectar_urgencia(movs)
        p["parado"] = dias_sem >= dias_parado
        p["dias_sem"] = dias_sem
        p["cnj_fmt"] = cnj.formatar(p["cnj"])
        p["rotulo_exibir"] = p.get("rotulo") or p["cnj_fmt"]
        p["valor_fmt"] = analise.formatar_valor(p.get("valor_causa") or "")
        p["data_aj_fmt"] = analise.formatar_data(p.get("data_ajuizamento") or "")
        p["data_at_fmt"] = analise.formatar_data(p.get("data_ultima_atualizacao") or "")
        p["check_fmt"] = analise.formatar_data(p.get("ultimo_check") or "")
        p["prazo_txt"] = _prazo_txt(movs)
        resultado.append(p)
    return resultado


def registrar_execucao(conn: sqlite3.Connection, total: int, sucesso: int, erros: int, novos: int) -> None:
    """Registra uma rodada de monitoramento na tabela execucoes."""
    with conn:
        conn.execute(
            """
            INSERT INTO execucoes (data_hora, total_processos, sucesso, erros, novos_andamentos)
            VALUES (?, ?, ?, ?, ?)
            """,
            (datetime.now().isoformat(), int(total), int(sucesso), int(erros), int(novos)),
        )


def ler_historico(conn: sqlite3.Connection, limite: int = 15) -> list[dict]:
    """Últimas execuções, mais recentes primeiro, com data formatada dd/mm/aaaa HH:MM."""
    cur = conn.execute(
        """
        SELECT data_hora, total_processos, sucesso, erros, novos_andamentos
        FROM execucoes ORDER BY data_hora DESC, id DESC LIMIT ?
        """,
        (int(limite),),
    )
    saida: list[dict] = []
    for r in cur.fetchall():
        data_iso = r["data_hora"] or ""
        try:
            data_fmt = datetime.fromisoformat(data_iso[:19]).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            data_fmt = data_iso[:16]
        saida.append({
            "data": data_fmt,
            "data_iso": data_iso,
            "total": r["total_processos"] or 0,
            "sucesso": r["sucesso"] or 0,
            "erros": r["erros"] or 0,
            "novos": r["novos_andamentos"] or 0,
        })
    return saida


def fazer_backup(c: Caminhos) -> Path | None:
    """Snapshot consistente do banco (inclusive WAL) em backups/. Mantém os 10 mais recentes."""
    if not c.banco.exists():
        return None
    c.backups.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    destino = c.backups / f"{PREFIXO_BACKUP}{ts}.db"
    temporario = destino.with_suffix(".tmp")
    try:
        with closing(sqlite3.connect(str(c.banco))) as origem, closing(sqlite3.connect(str(temporario))) as copia:
            origem.backup(copia)
        temporario.replace(destino)
    except (sqlite3.Error, OSError):
        temporario.unlink(missing_ok=True)
        raise
    antigos = sorted(c.backups.glob(f"{PREFIXO_BACKUP}*.db"))
    for velho in antigos[:-BACKUPS_MANTIDOS]:
        velho.unlink()
    return destino
