"""Testes do painel web local — THEMIS Monitor. Copyright (c) 2026 Márcio Luis Amorim — MIT."""

import http.client
import json
import threading

import pytest

from themis import config, datajud, painel

CNJ = "00000010520258260100"  # 0000001-05.2025.8.26.0100 (dígito válido)
CNJ_FMT = "0000001-05.2025.8.26.0100"
CNJ_DIGITO_ERRADO = "0000001-06.2025.8.26.0100"


def fonte_ok() -> dict:
    return {
        "numeroProcesso": CNJ,
        "classe": {"nome": "Procedimento Comum Cível"},
        "assuntos": [{"nome": "Indenização"}],
        "orgaoJulgador": {"nome": "1ª Vara Cível"},
        "grau": "G1",
        "tribunal": "TJSP",
        "dataAjuizamento": "2025-01-10T00:00:00.000Z",
        "dataHoraUltimaAtualizacao": "2025-01-10T12:00:00.000Z",
        "movimentos": [
            {"dataHora": "2025-01-10T10:00:00.000Z", "codigo": 26, "nome": "Distribuição",
             "complementosTabelados": []},
            {"dataHora": "2025-01-12T10:00:00.000Z", "codigo": 12265, "nome": "Intimação <b>x</b>",
             "complementosTabelados": []},
        ],
    }


@pytest.fixture
def servidor(tmp_home):
    """Painel em porta efêmera numa thread; devolve (host, porta)."""
    c = config.caminhos()
    config.garantir_arquivos_iniciais(c)
    c.processos.write_text("# vazio\n", encoding="utf-8")
    srv = painel.criar_servidor(porta=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv.server_address[0], srv.server_address[1]
    srv.shutdown()
    srv.server_close()
    thread.join(timeout=5)


def requisitar(servidor, metodo, caminho, corpo=None, headers=None):
    """Faz uma requisição e devolve (status, headers, corpo em texto)."""
    host, porta = servidor
    conn = http.client.HTTPConnection(host, porta, timeout=10)
    try:
        conn.request(metodo, caminho, body=corpo, headers=headers or {})
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read().decode("utf-8")
    finally:
        conn.close()


def post_json(servidor, caminho, dados, headers=None):
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    status, _, corpo = requisitar(servidor, "POST", caminho, json.dumps(dados).encode("utf-8"), h)
    return status, json.loads(corpo)


def test_get_pagina_principal(servidor):
    status, headers, corpo = requisitar(servidor, "GET", "/")
    assert status == 200
    assert headers["Content-Type"].startswith("text/html")
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["Cache-Control"] == "no-cache"
    assert "THEMIS" in corpo and "Painel Interativo" in corpo
    assert "Consultar por CNJ" in corpo and "Importar por OAB" in corpo
    assert "alert(" not in corpo


def test_host_externo_recebe_403(servidor):
    status, _, corpo = requisitar(servidor, "GET", "/", headers={"Host": "exemplo.com"})
    assert status == 403
    assert "erro" in json.loads(corpo)
    status, dados = post_json(servidor, "/api/consultar", {"cnj": CNJ}, headers={"Host": "exemplo.com"})
    assert status == 403 and "erro" in dados


def test_origin_diferente_recebe_403(servidor):
    status, dados = post_json(servidor, "/api/consultar", {"cnj": CNJ}, headers={"Origin": "http://evil.example"})
    assert status == 403 and "erro" in dados


def test_post_sem_json_recebe_415(servidor):
    status, _, corpo = requisitar(
        servidor, "POST", "/api/consultar", b"cnj=1", {"Content-Type": "text/plain"}
    )
    assert status == 415
    assert "erro" in json.loads(corpo)


def test_json_invalido_recebe_400(servidor):
    status, _, corpo = requisitar(
        servidor, "POST", "/api/consultar", b"{nao e json", {"Content-Type": "application/json"}
    )
    assert status == 400
    assert "erro" in json.loads(corpo)


def test_corpo_nao_objeto_recebe_400(servidor):
    status, dados = post_json(servidor, "/api/consultar", ["lista"])
    assert status == 400 and "erro" in dados
    status, dados = post_json(servidor, "/api/consultar", {"cnj": 123})
    assert status == 400 and "erro" in dados


def test_rota_desconhecida_recebe_404(servidor):
    status, _, corpo = requisitar(servidor, "GET", "/nao-existe")
    assert status == 404 and "erro" in json.loads(corpo)
    status, dados = post_json(servidor, "/api/nada", {})
    assert status == 404 and "erro" in dados


def test_consultar_cnj_invalido_nao_chama_rede(servidor, monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("datajud.consultar não deveria ser chamado")

    monkeypatch.setattr(datajud, "consultar", explode)
    status, dados = post_json(servidor, "/api/consultar", {"cnj": CNJ_DIGITO_ERRADO})
    assert status == 200
    assert "dígito" in dados["erro"]
    status, dados = post_json(servidor, "/api/consultar", {"cnj": "123"})
    assert status == 200 and "20 dígitos" in dados["erro"]


def test_consultar_com_datajud_mockado_salva_e_exibe(servidor, monkeypatch):
    chamadas = []

    def falso(cnj_limpo, tribunal, timeout=30):
        chamadas.append((cnj_limpo, tribunal))
        return datajud.Resultado(True, fonte=fonte_ok())

    monkeypatch.setattr(datajud, "consultar", falso)
    status, dados = post_json(servidor, "/api/consultar", {"cnj": CNJ_FMT})
    assert status == 200
    assert dados["ok"] is True
    assert dados["cnj"] == CNJ_FMT
    assert dados["tribunal"] == "TJ-SP"
    assert dados["total_movimentos"] == 2
    assert dados["ultimo_andamento"] == "Intimação <b>x</b>"
    assert chamadas == [(CNJ, "tjsp")]

    status, _, corpo = requisitar(servidor, "GET", "/")
    assert status == 200
    assert CNJ_FMT in corpo
    assert "Intimação &lt;b&gt;x&lt;/b&gt;" in corpo
    assert "<b>x</b>" not in corpo


def test_consultar_erro_do_datajud_vira_json(servidor, monkeypatch):
    monkeypatch.setattr(datajud, "consultar", lambda *a, **k: datajud.Resultado(False, erro="Falhou"))
    status, dados = post_json(servidor, "/api/consultar", {"cnj": CNJ})
    assert status == 200 and dados == {"erro": "Falhou"}


def test_adicionar_lote_com_duplicata(servidor):
    status, dados = post_json(
        servidor, "/api/adicionar-lote",
        {"itens": [{"cnj": CNJ}, {"cnj": CNJ_FMT}], "cliente": "Cliente X", "area": "Cível"},
    )
    assert status == 200
    assert dados["ok"] is True
    assert dados["adicionados"] == [CNJ_FMT]
    assert len(dados["ignorados"]) == 1 and "já existe" in dados["ignorados"][0]
    conteudo = config.caminhos().processos.read_text(encoding="utf-8")
    assert f"{CNJ_FMT} |  | Cliente X | Cível" in conteudo


def test_adicionar_lote_item_com_barra_recebe_erro(servidor):
    status, dados = post_json(servidor, "/api/adicionar-lote", {"itens": [{"cnj": CNJ, "rotulo": "a|b"}]})
    assert status == 200 and "erro" in dados
    assert CNJ_FMT not in config.caminhos().processos.read_text(encoding="utf-8")


def test_adicionar_lote_vazio_e_itens_invalidos(servidor):
    status, dados = post_json(servidor, "/api/adicionar-lote", {"itens": []})
    assert status == 200 and "erro" in dados
    status, dados = post_json(servidor, "/api/adicionar-lote", {"itens": "x"})
    assert status == 400
    status, dados = post_json(servidor, "/api/adicionar-lote", {"itens": [{"cnj": 5}]})
    assert status == 400


def test_adicionar_unico(servidor):
    status, dados = post_json(servidor, "/api/adicionar", {"cnj": CNJ, "rotulo": "Caso"})
    assert status == 200 and dados == {"ok": True}
    status, dados = post_json(servidor, "/api/adicionar", {"cnj": CNJ})
    assert status == 200 and "já existe" in dados["erro"]
    status, dados = post_json(servidor, "/api/adicionar", {"cnj": CNJ_DIGITO_ERRADO})
    assert status == 200 and "dígito" in dados["erro"]


def test_gerar_pagina_sem_banco(tmp_home):
    config.garantir_arquivos_iniciais(config.caminhos())
    pagina = painel.gerar_pagina()
    assert "THEMIS" in pagina
    assert "Nenhum processo" in pagina


def test_executar_porta_ocupada(servidor, capsys):
    _, porta = servidor
    codigo = painel.executar(porta=porta, abrir_navegador=False)
    assert codigo == 1
    assert "já está em uso" in capsys.readouterr().out
