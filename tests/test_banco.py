"""Testes do módulo banco — THEMIS Monitor. Copyright (c) 2026 Márcio Luis Amorim — MIT."""

import copy

import pytest

from themis import banco, config

CNJ = "00000010520258260100"  # 0000001-05.2025.8.26.0100 (fictício, dígito válido)
CNJ_FMT = "0000001-05.2025.8.26.0100"


def fonte_base() -> dict:
    """Documento no formato do DataJud com um único movimento."""
    return {
        "numeroProcesso": CNJ,
        "classe": {"nome": "Procedimento Comum Cível"},
        "assuntos": [{"nome": "Indenização por Dano Moral"}],
        "orgaoJulgador": {"nome": "1ª Vara Cível"},
        "grau": "G1",
        "tribunal": "TJSP",
        "valorCausa": 1000,
        "dataAjuizamento": "2025-01-10T00:00:00.000Z",
        "dataHoraUltimaAtualizacao": "2025-01-10T12:00:00.000Z",
        "movimentos": [
            {
                "dataHora": "2025-01-10T10:00:00.000Z",
                "codigo": 26,
                "nome": "Distribuição",
                "complementosTabelados": [{"nome": "sorteio"}],
            }
        ],
    }


def fonte_com_intimacao() -> dict:
    f = copy.deepcopy(fonte_base())
    f["dataHoraUltimaAtualizacao"] = "2025-02-01T12:00:00.000Z"
    f["movimentos"].append(
        {"dataHora": "2025-02-01T09:30:00.000Z", "codigo": 12265, "nome": "Intimação", "complementosTabelados": []}
    )
    return f


@pytest.fixture
def conn():
    c = banco.conectar(":memory:")
    yield c
    c.close()


def test_conectar_cria_schema_e_row_factory(conn):
    tabelas = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"processos", "movimentos", "execucoes"} <= tabelas
    colunas = {r["name"] for r in conn.execute("PRAGMA table_info(processos)")}
    assert {"cliente", "area", "status_processo", "valor_causa", "total_movimentos", "rotulo"} <= colunas


def test_conectar_migra_banco_antigo(tmp_path):
    """Banco criado por versão antiga (sem colunas extras) ganha as colunas novas."""
    import sqlite3

    caminho = tmp_path / "antigo.db"
    velho = sqlite3.connect(caminho)
    velho.execute("CREATE TABLE processos (cnj TEXT PRIMARY KEY, tribunal TEXT, json_completo TEXT)")
    velho.commit()
    velho.close()
    c = banco.conectar(caminho)
    colunas = {r["name"] for r in c.execute("PRAGMA table_info(processos)")}
    assert {"cliente", "area", "status_processo"} <= colunas
    c.close()


def test_primeira_gravacao_sem_novos(conn):
    ok, novos = banco.salvar_resultado(conn, CNJ, fonte_base(), rotulo="Caso A", cliente="Cliente A", area="Civel")
    assert (ok, novos) == (True, 0)
    procs = banco.ler_processos(conn)
    assert len(procs) == 1
    p = procs[0]
    assert p["cnj_fmt"] == CNJ_FMT
    assert p["rotulo_exibir"] == "Caso A"
    assert p["cliente"] == "Cliente A" and p["area"] == "Civel"
    assert p["classe"] == "Procedimento Comum Cível"
    assert p["assunto"] == "Indenização por Dano Moral"
    assert p["valor_fmt"] == "R$ 1.000,00"
    assert p["data_aj_fmt"] == "10/01/2025"
    assert p["tem_novo"] is False
    assert p["movimentos"] == [("2025-01-10T10:00:00.000Z", "Distribuição", "sorteio", 0)]
    assert p["status_processo"] == "Ativo"


def test_segunda_gravacao_detecta_novo_movimento(conn):
    banco.salvar_resultado(conn, CNJ, fonte_base())
    ok, novos = banco.salvar_resultado(conn, CNJ, fonte_com_intimacao())
    assert (ok, novos) == (True, 1)
    p = banco.ler_processos(conn)[0]
    assert p["tem_novo"] is True
    assert p["movimentos"][0][1] == "Intimação"  # mais recente primeiro
    assert p["movimentos"][0][3] == 1
    assert p["total_movimentos"] == 2
    assert p["urgencia"] == "alerta"
    assert p["prazo_txt"].startswith("Prazo estimado (Intimação): 16/02/2025 (15 dias corridos)")
    # Terceira gravação igual: nada novo
    assert banco.salvar_resultado(conn, CNJ, fonte_com_intimacao()) == (True, 0)


def test_preserva_cliente_area_rotulo_e_valor_quando_vazios(conn):
    banco.salvar_resultado(conn, CNJ, fonte_base(), rotulo="Caso A", cliente="Cliente A", area="Civel")
    segunda = fonte_com_intimacao()
    segunda["valorCausa"] = None
    banco.salvar_resultado(conn, CNJ, segunda)
    p = banco.ler_processos(conn)[0]
    assert p["rotulo"] == "Caso A"
    assert p["cliente"] == "Cliente A"
    assert p["area"] == "Civel"
    assert p["valor_causa"] == "1000"
    # Valores novos não vazios substituem
    banco.salvar_resultado(conn, CNJ, segunda, cliente="Cliente B")
    assert banco.ler_processos(conn)[0]["cliente"] == "Cliente B"


@pytest.mark.parametrize(
    "estragar",
    [
        lambda f: f.update(movimentos="não é lista"),
        lambda f: f.update(movimentos=[1, 2]),
        lambda f: f.update(assuntos={"nome": "x"}),
        lambda f: f["movimentos"][0].update(complementosTabelados="x"),
    ],
)
def test_fonte_malformada_nao_grava(conn, estragar):
    f = fonte_base()
    estragar(f)
    assert banco.salvar_resultado(conn, CNJ, f) == (False, 0)
    assert conn.execute("SELECT COUNT(*) FROM processos").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM movimentos").fetchone()[0] == 0


def test_fonte_nao_dict_ou_vazia(conn):
    assert banco.salvar_resultado(conn, CNJ, {}) == (False, 0)
    assert banco.salvar_resultado(conn, CNJ, None) == (False, 0)
    assert banco.salvar_resultado(conn, CNJ, ["x"]) == (False, 0)


def test_movimento_com_campos_none_nao_explode(conn):
    f = fonte_base()
    f["classe"] = None
    f["orgaoJulgador"] = "texto solto"
    f["valorCausa"] = ""
    f["movimentos"] = [{"dataHora": None, "codigo": None, "nome": None, "complementosTabelados": None}]
    assert banco.salvar_resultado(conn, CNJ, f) == (True, 0)
    p = banco.ler_processos(conn)[0]
    assert p["classe"] == "?" and p["orgao_julgador"] == "?"
    assert p["valor_fmt"] == "—"
    assert p["movimentos"] == [("", "", "", 0)]
    assert p["urgencia"] == "ok"
    assert p["prazo_txt"] == ""


def test_ler_processos_filtra_e_marca_parado(conn):
    banco.salvar_resultado(conn, CNJ, fonte_base())
    outro = "08292298220248190209"
    banco.salvar_resultado(conn, outro, dict(fonte_base(), numeroProcesso=outro))
    assert len(banco.ler_processos(conn)) == 2
    so_um = banco.ler_processos(conn, dias_parado=30, apenas_cnj=CNJ)
    assert [p["cnj"] for p in so_um] == [CNJ]
    assert so_um[0]["parado"] is True  # data de 2025 já passou de 30 dias
    assert so_um[0]["dias_sem"] > 30
    assert banco.ler_processos(conn, dias_parado=10**6)[0]["parado"] is False


def test_historico_apos_registrar_execucao(conn):
    assert banco.ler_historico(conn) == []
    banco.registrar_execucao(conn, total=3, sucesso=2, erros=1, novos=4)
    banco.registrar_execucao(conn, total=5, sucesso=5, erros=0, novos=0)
    hist = banco.ler_historico(conn)
    assert len(hist) == 2
    assert hist[0] == {**hist[0], "total": 5, "sucesso": 5, "erros": 0, "novos": 0}
    assert hist[1]["total"] == 3 and hist[1]["erros"] == 1 and hist[1]["novos"] == 4
    assert len(hist[0]["data"]) == 16 and hist[0]["data"][2] == "/"
    assert hist[0]["data_iso"]
    assert len(banco.ler_historico(conn, limite=1)) == 1


def test_fazer_backup_sem_banco_devolve_none(tmp_home):
    assert banco.fazer_backup(config.caminhos()) is None


def test_fazer_backup_cria_arquivo_e_mantem_dez(tmp_home):
    c = config.caminhos()
    conn = banco.conectar(c.banco)
    banco.salvar_resultado(conn, CNJ, fonte_base(), rotulo="Caso A")
    conn.close()

    destino = banco.fazer_backup(c)
    assert destino is not None and destino.exists()
    assert destino.name.startswith("themis_backup_") and destino.suffix == ".db"
    copia = banco.conectar(destino)
    assert copia.execute("SELECT rotulo FROM processos WHERE cnj=?", (CNJ,)).fetchone()[0] == "Caso A"
    copia.close()

    for _ in range(11):
        banco.fazer_backup(c)
    restantes = sorted(c.backups.glob("themis_backup_*.db"))
    assert len(restantes) == 10
    assert not list(c.backups.glob("*.tmp"))
