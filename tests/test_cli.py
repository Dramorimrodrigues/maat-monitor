"""Testes da linha de comando — THEMIS Monitor. Copyright (c) 2026 Márcio Luis Amorim — MIT."""

import sys
import types
from pathlib import Path

import pytest

import themis
from themis import banco, cli, config, datajud, descoberta_oab

CNJ_FMT = "0000001-05.2025.8.26.0100"
CNJ_LIMPO = "00000010520258260100"

FONTE_MINIMA = {
    "numeroProcesso": CNJ_LIMPO,
    "classe": {"codigo": 7, "nome": "Procedimento Comum Cível"},
    "assuntos": [{"codigo": 1, "nome": "Indenização"}],
    "orgaoJulgador": {"codigo": 1, "nome": "1ª Vara Cível"},
    "grau": "G1",
    "tribunal": "TJSP",
    "movimentos": [{"codigo": 26, "nome": "Distribuição", "dataHora": "2025-01-10T10:00:00.000Z"}],
}


def _modulo_falso(monkeypatch, nome: str, **atributos) -> types.SimpleNamespace:
    """Instala um módulo falso `themis.<nome>` mesmo que o real exista ou ainda não exista."""
    falso = types.SimpleNamespace(**atributos)
    monkeypatch.setitem(sys.modules, f"themis.{nome}", falso)
    monkeypatch.setattr(themis, nome, falso, raising=False)
    return falso


@pytest.fixture
def sem_rede_nem_navegador(monkeypatch, tmp_home):
    """Bloqueia rede e navegador e instala relatorio/painel falsos."""
    def consultar_ok(cnj_limpo, tribunal, timeout=30):
        return datajud.Resultado(True, fonte=FONTE_MINIMA)

    def falhar_navegador(*_a, **_k):
        raise AssertionError("navegador não deve abrir nos testes")

    monkeypatch.setattr(datajud, "consultar", consultar_ok)
    monkeypatch.setattr(cli.webbrowser, "open", falhar_navegador)
    monkeypatch.setattr(descoberta_oab.webbrowser, "open", falhar_navegador)

    relatorios = Path(tmp_home) / "relatorios"
    relatorios.mkdir(exist_ok=True)
    html = relatorios / "relatorio_teste.html"
    csv_proc = relatorios / "processos.csv"
    csv_mov = relatorios / "movimentos.csv"

    def gerar_relatorio_html(conn, cfg, caminhos, estatisticas, apenas_cnj=None):
        html.write_text("<html></html>", encoding="utf-8")
        return html

    def gerar_csv(conn, caminhos):
        csv_proc.write_text("", encoding="utf-8")
        csv_mov.write_text("", encoding="utf-8")
        return csv_proc, csv_mov

    _modulo_falso(monkeypatch, "relatorio", gerar_relatorio_html=gerar_relatorio_html, gerar_csv=gerar_csv)
    _modulo_falso(monkeypatch, "painel", executar=lambda porta=5000, abrir_navegador=True: 0)
    return tmp_home


# ------------------------------------------------------------------
# Flags globais
# ------------------------------------------------------------------

def test_versao(capsys):
    assert cli.main(["--versao"]) == 0
    saida = capsys.readouterr().out
    assert "1.0.0" in saida
    assert "Márcio Luis Amorim" in saida
    assert "MIT" in saida


def test_sem_argumentos_imprime_ajuda(capsys):
    assert cli.main([]) == 2
    saida = capsys.readouterr().out
    assert "monitorar" in saida and "consultar" in saida


def test_preparar_cria_arquivos(tmp_home, capsys):
    assert cli.main(["--preparar"]) == 0
    assert (Path(tmp_home) / "config.ini").exists()
    assert (Path(tmp_home) / "processos.txt").exists()
    assert (Path(tmp_home) / "relatorios").is_dir()
    assert (Path(tmp_home) / "backups").is_dir()
    saida = capsys.readouterr().out
    assert "THEMIS Monitor v1.0.0" in saida
    assert "Arquivo criado: config.ini" in saida


def test_erro_de_uso_do_argparse_retorna_2(capsys):
    assert cli.main(["consultar"]) == 2  # falta o CNJ


# ------------------------------------------------------------------
# consultar
# ------------------------------------------------------------------

def test_consultar_cnj_invalido(tmp_home, capsys):
    assert cli.main(["consultar", "123"]) == 2
    assert "20 dígitos" in capsys.readouterr().out


def test_consultar_tribunal_nao_identificado(tmp_home, capsys):
    # J=2 (CNJ) não é consultável no DataJud: dígito válido, tribunal desconhecido
    from themis import cnj as mod_cnj

    base = "0000001" + "2025" + "2" + "00" + "0000"
    for dd in range(1, 100):
        candidato = base[:7] + f"{dd:02d}" + base[7:]
        if mod_cnj.validar_digito(candidato):
            break
    assert cli.main(["consultar", candidato, "--sem-navegador"]) == 2
    assert "identificar o tribunal" in capsys.readouterr().out


def test_consultar_ok(sem_rede_nem_navegador, capsys):
    assert cli.main(["consultar", CNJ_FMT, "--sem-navegador"]) == 0
    saida = capsys.readouterr().out
    assert "salvo com sucesso" in saida
    assert "relatorio_teste.html" in saida
    conn = banco.conectar(config.caminhos().banco)
    try:
        assert conn.execute("SELECT COUNT(*) FROM processos").fetchone()[0] == 1
    finally:
        conn.close()


def test_consultar_flag_antes_do_subcomando(sem_rede_nem_navegador):
    assert cli.main(["--sem-navegador", "consultar", CNJ_FMT]) == 0


def test_consultar_erro_datajud(sem_rede_nem_navegador, monkeypatch, capsys):
    monkeypatch.setattr(datajud, "consultar", lambda *a, **k: datajud.Resultado(False, erro="Falha simulada"))
    assert cli.main(["consultar", CNJ_FMT, "--sem-navegador"]) == 1
    assert "Falha simulada" in capsys.readouterr().out


# ------------------------------------------------------------------
# monitorar
# ------------------------------------------------------------------

def test_monitorar_ok(sem_rede_nem_navegador, capsys):
    caminhos = config.caminhos()
    config.garantir_arquivos_iniciais(caminhos)
    caminhos.processos.write_text(f"{CNJ_FMT} | Caso teste | Cliente | Cível\n", encoding="utf-8")

    assert cli.main(["monitorar", "--sem-navegador"]) == 0

    saida = capsys.readouterr().out
    assert "RESUMO DA EXECUÇÃO" in saida
    assert "Processos verificados:   1" in saida
    conn = banco.conectar(caminhos.banco)
    try:
        assert conn.execute("SELECT COUNT(*) FROM execucoes").fetchone()[0] == 1
        assert conn.execute("SELECT rotulo FROM processos").fetchone()[0] == "Caso teste"
    finally:
        conn.close()
    # Primeira execução: não havia banco antes, logo nenhum backup é gerado
    assert list(caminhos.backups.glob("*.db")) == []


def test_monitorar_segunda_rodada_gera_backup(sem_rede_nem_navegador, monkeypatch):
    caminhos = config.caminhos()
    config.garantir_arquivos_iniciais(caminhos)
    caminhos.processos.write_text(f"{CNJ_FMT}\n", encoding="utf-8")
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    assert cli.main(["monitorar", "--sem-navegador"]) == 0
    assert cli.main(["monitorar", "--sem-navegador"]) == 0
    assert len(list(caminhos.backups.glob("themis_backup_*.db"))) == 1


def test_monitorar_com_erro_retorna_1(sem_rede_nem_navegador, monkeypatch, capsys):
    caminhos = config.caminhos()
    config.garantir_arquivos_iniciais(caminhos)
    caminhos.processos.write_text(f"{CNJ_FMT}\n", encoding="utf-8")
    monkeypatch.setattr(datajud, "consultar", lambda *a, **k: datajud.Resultado(False, erro="Timeout simulado"))
    assert cli.main(["monitorar", "--sem-navegador"]) == 1
    saida = capsys.readouterr().out
    assert "Timeout simulado" in saida
    assert "Erros/não encontrados:   1" in saida
    conn = banco.conectar(caminhos.banco)
    try:
        assert conn.execute("SELECT erros FROM execucoes").fetchone()[0] == 1
    finally:
        conn.close()


def test_monitorar_sem_processos(sem_rede_nem_navegador, capsys):
    caminhos = config.caminhos()
    config.garantir_arquivos_iniciais(caminhos)
    caminhos.processos.write_text("# só comentários\n\n# nada aqui\n", encoding="utf-8")
    assert cli.main(["monitorar", "--sem-navegador"]) == 0
    saida = capsys.readouterr().out
    assert "Nenhum processo" in saida
    assert "processos.txt" in saida
    assert "painel" in saida


def test_monitorar_ignora_linhas_invalidas_com_aviso(sem_rede_nem_navegador, capsys):
    caminhos = config.caminhos()
    config.garantir_arquivos_iniciais(caminhos)
    caminhos.processos.write_text(f"123 | inválido\n{CNJ_FMT}\n", encoding="utf-8")
    assert cli.main(["monitorar", "--sem-navegador"]) == 0
    saida = capsys.readouterr().out
    assert "Linha 1 ignorada" in saida


# ------------------------------------------------------------------
# testar, painel, oab
# ------------------------------------------------------------------

def test_testar_ok(tmp_home, monkeypatch, capsys):
    monkeypatch.setattr(datajud, "testar_conexao", lambda: datajud.Resultado(True))
    assert cli.main(["testar"]) == 0
    assert "Conexão com o DataJud OK!" in capsys.readouterr().out


def test_testar_falha(tmp_home, monkeypatch, capsys):
    monkeypatch.setattr(datajud, "testar_conexao", lambda: datajud.Resultado(False, erro="Sem internet"))
    assert cli.main(["testar"]) == 1
    assert "Sem internet" in capsys.readouterr().out


def test_painel_repassa_porta_e_navegador(sem_rede_nem_navegador, monkeypatch):
    chamadas = []

    def executar(porta=5000, abrir_navegador=True):
        chamadas.append((porta, abrir_navegador))
        return 0

    _modulo_falso(monkeypatch, "painel", executar=executar)
    assert cli.main(["painel", "--porta", "8080", "--sem-navegador"]) == 0
    assert chamadas == [(8080, False)]


def test_oab_gera_guia(sem_rede_nem_navegador, capsys):
    caminhos = config.caminhos()
    config.garantir_arquivos_iniciais(caminhos)
    caminhos.config.write_text(
        "[advogado]\noab_numero = 123456\noab_uf = rj\nnome = Dr. <Teste> & Cia\n", encoding="utf-8"
    )
    assert cli.main(["oab", "--sem-navegador"]) == 0
    guia = caminhos.base / "buscar-oab-guia.html"
    assert guia.exists()
    html = guia.read_text(encoding="utf-8")
    assert "THEMIS" in html and "OGUM" not in html
    assert "numeroOAB=123456" in html and "estadoOAB=RJ" in html
    assert "Dr. &lt;Teste&gt; &amp; Cia" in html  # dados do config escapados
    assert "alert(" not in html
    assert "Márcio Luis Amorim" in html
    saida = capsys.readouterr().out
    assert "OAB: 123456/RJ" in saida


def test_gerar_guia_escapa_oab_maliciosa(tmp_home):
    caminhos = config.caminhos()
    config.garantir_arquivos_iniciais(caminhos)
    cfg = {"oab_numero": '"><script>x</script>', "oab_uf": "SP", "nome": "N"}
    html = descoberta_oab.gerar_guia(cfg, caminhos).read_text(encoding="utf-8")
    assert "<script>x</script>" not in html


# ------------------------------------------------------------------
# Tratamento de erros globais
# ------------------------------------------------------------------

def test_excecao_inesperada_retorna_1(tmp_home, monkeypatch, capsys):
    def explodir():
        raise RuntimeError("bum")

    monkeypatch.setattr(datajud, "testar_conexao", explodir)
    assert cli.main(["testar"]) == 1
    saida = capsys.readouterr().out
    assert "ERRO INESPERADO: RuntimeError: bum" in saida
    assert "issue" in saida


def test_interrupcao_retorna_130(tmp_home, monkeypatch, capsys):
    def interromper():
        raise KeyboardInterrupt

    monkeypatch.setattr(datajud, "testar_conexao", interromper)
    assert cli.main(["testar"]) == 130
    assert "Interrompido" in capsys.readouterr().out


def test_monitorar_com_erro_parcial_retorna_0(sem_rede_nem_navegador, monkeypatch, capsys):
    """Um processo não encontrado não é falha da execução: o resumo já o lista."""
    caminhos = config.caminhos()
    config.garantir_arquivos_iniciais(caminhos)
    outro = "0000002-87.2025.8.26.0100"  # dígito válido, tribunal TJSP
    caminhos.processos.write_text(f"{CNJ_FMT}\n{outro}\n", encoding="utf-8")

    def consultar(cnj_limpo, tribunal, timeout=30):
        if cnj_limpo == CNJ_LIMPO:
            return datajud.Resultado(True, fonte=FONTE_MINIMA)
        return datajud.Resultado(False, erro="Processo não encontrado no DataJud")

    monkeypatch.setattr(datajud, "consultar", consultar)
    assert cli.main(["monitorar", "--sem-navegador"]) == 0
    saida = capsys.readouterr().out
    assert "Atualizados com sucesso: 1" in saida
    assert "Erros/não encontrados:   1" in saida
