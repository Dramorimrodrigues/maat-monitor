"""Testes do módulo relatorio — MAAT Monitor. Copyright (c) 2026 Márcio Luis Amorim — MIT."""

import pytest

from maat import banco, config, relatorio

CNJ_A = "00000010520258260100"  # 0000001-05.2025.8.26.0100
CNJ_B = "00010540420108260100"  # 0001054-04.2010.8.26.0100
CNJ_B_FMT = "0001054-04.2010.8.26.0100"

CONFIG = {"nome": "Dra. Teste <b>", "oab_numero": "123456", "oab_uf": "SP", "dias_alerta_parado": 30}
STATS = {"total": 2, "sucesso": 2, "erros": 0, "novos_andamentos": 0}


def fonte(numero: str, classe: str = "Procedimento Comum Cível") -> dict:
    return {
        "numeroProcesso": numero,
        "classe": {"nome": classe},
        "assuntos": [{"nome": "Indenização"}],
        "orgaoJulgador": {"nome": "1ª Vara Cível"},
        "grau": "G1",
        "tribunal": "TJSP",
        "valorCausa": 1500.5,
        "dataAjuizamento": "2025-01-10T00:00:00.000Z",
        "dataHoraUltimaAtualizacao": "2025-02-01T12:00:00.000Z",
        "movimentos": [
            {"dataHora": "2025-01-10T10:00:00.000Z", "codigo": 26, "nome": "Distribuição",
             "complementosTabelados": [{"nome": "sorteio"}]},
            {"dataHora": "2025-02-01T09:30:00.000Z", "codigo": 12265, "nome": "Intimação",
             "complementosTabelados": []},
        ],
    }


@pytest.fixture
def conn():
    c = banco.conectar(":memory:")
    ok, _ = banco.salvar_resultado(c, CNJ_A, fonte(CNJ_A, "<script>alert(1)</script>"), rotulo="Caso A")
    assert ok
    ok, _ = banco.salvar_resultado(c, CNJ_B, fonte(CNJ_B), rotulo="Caso B", cliente="Maria & Cia", area="Cível")
    assert ok
    banco.registrar_execucao(c, 2, 2, 0, 0)
    yield c
    c.close()


@pytest.fixture
def caminhos(tmp_home):
    return config.caminhos()


def test_relatorio_escapa_html_vindo_do_tribunal(conn, caminhos):
    arquivo = relatorio.gerar_relatorio_html(conn, CONFIG, caminhos, STATS)
    html = arquivo.read_text(encoding="utf-8")
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Maria &amp; Cia" in html
    assert "Dra. Teste &lt;b&gt;" in html


def test_relatorio_contem_marca_autoria_e_arquivo_na_pasta(conn, caminhos):
    arquivo = relatorio.gerar_relatorio_html(conn, CONFIG, caminhos, STATS)
    assert arquivo.parent == caminhos.relatorios
    assert arquivo.name.startswith("relatorio_") and arquivo.suffix == ".html"
    html = arquivo.read_text(encoding="utf-8")
    assert "MAAT" in html
    assert "rcio Luis Amorim" in html  # "M&aacute;rcio Luis Amorim" no rodapé
    assert "<title>MAAT &mdash; Relat&oacute;rio" in html
    assert "Hist&oacute;rico de Execu" in html
    assert 'data-urgencia="alerta"' in html  # Intimação => alerta
    assert "Prazo estimado" in html


def test_relatorio_apenas_cnj_filtra_e_omite_historico(conn, caminhos):
    arquivo = relatorio.gerar_relatorio_html(conn, CONFIG, caminhos, STATS, apenas_cnj=CNJ_B)
    html = arquivo.read_text(encoding="utf-8")
    assert "Caso B" in html
    assert "Caso A" not in html
    assert "Hist&oacute;rico de Execu" not in html


def test_html_cards_vazio_mensagem_amigavel():
    saida = relatorio.html_cards([])
    assert "Nenhum processo" in saida
    assert "processo-card" not in saida


def test_html_cards_atributos_e_slug(conn):
    processos = banco.ler_processos(conn, 30, apenas_cnj=CNJ_B)
    saida = relatorio.html_cards(processos)
    assert f"toggleCard('{CNJ_B}')" in saida
    assert f'id="det-{CNJ_B}"' in saida
    assert 'data-novo="false"' in saida and 'data-parado="true"' in saida
    assert CNJ_B_FMT in saida


def test_html_historico(conn):
    hist = banco.ler_historico(conn)
    saida = relatorio.html_historico(hist)
    assert "<table" in saida and "hist-col-ok" in saida
    assert relatorio.html_historico([]) == ""


def test_rodape_html():
    rodape = relatorio.rodape_html("&mdash; extra")
    assert rodape.startswith("<footer>") and rodape.endswith("</footer>")
    assert "MAAT Monitor v" in rodape and "&mdash; extra" in rodape


@pytest.mark.parametrize("valor", ["=SOMA(A1)", "+1", "-1", "@cmd", "\t=x", "  =x"])
def test_celula_csv_neutraliza_formulas(valor):
    assert relatorio.celula_csv(valor).startswith("'")


def test_celula_csv_mantem_valores_normais():
    assert relatorio.celula_csv("texto") == "texto"
    assert relatorio.celula_csv(12) == 12
    assert relatorio.celula_csv(None) is None


def test_gerar_csv_bom_delimitador_e_conteudo(conn, caminhos):
    arq_proc, arq_mov = relatorio.gerar_csv(conn, caminhos)
    bruto = arq_proc.read_bytes()
    assert bruto.startswith(b"\xef\xbb\xbf")
    texto = bruto.decode("utf-8-sig")
    primeira = texto.splitlines()[0]
    assert primeira.startswith("CNJ;Apelido;")
    assert "Últ. verificação MAAT" in primeira
    assert CNJ_B_FMT in texto
    assert "<script>alert(1)</script>" in texto  # CSV não é HTML: só neutraliza fórmulas
    movs = arq_mov.read_bytes().decode("utf-8-sig")
    assert movs.splitlines()[0] == "CNJ;Data/Hora;Código;Nome;Complemento;Novo"
    assert "Intimação" in movs
