"""Testes do cliente DataJud (sem rede). Copyright (c) 2026 Márcio Luis Amorim — MIT."""

from __future__ import annotations

import pytest
import requests

from maat import datajud

CNJ = "00010540420108260100"


class RespostaFake:
    """Imita o mínimo de ``requests.Response`` usado pelo módulo."""

    def __init__(self, corpo=None, status=200, json_invalido=False):
        self._corpo = corpo
        self.status_code = status
        self._json_invalido = json_invalido

    def raise_for_status(self):
        if self.status_code >= 400:
            erro = requests.exceptions.HTTPError(f"HTTP {self.status_code}")
            erro.response = self
            raise erro

    def json(self):
        if self._json_invalido:
            raise ValueError("JSON inválido")
        return self._corpo


def _corpo_hit(numero: str = CNJ) -> dict:
    return {"hits": {"hits": [{"_source": {"numeroProcesso": numero, "movimentos": []}}]}}


@pytest.fixture
def post_fake(monkeypatch):
    """Substitui ``_sessao.post`` e registra as chamadas; ``resposta`` pode ser exceção."""
    chamadas: list[dict] = []
    estado = {"resposta": RespostaFake(_corpo_hit())}

    def fake(url, **kwargs):
        chamadas.append({"url": url, **kwargs})
        resposta = estado["resposta"]
        if isinstance(resposta, BaseException):
            raise resposta
        return resposta

    monkeypatch.setattr(datajud._sessao, "post", fake)
    estado["chamadas"] = chamadas
    return estado


def test_hit_valido(post_fake):
    r = datajud.consultar(CNJ, "tjsp")
    assert r.ok is True
    assert r.erro is None
    assert r.fonte["numeroProcesso"] == CNJ
    chamada = post_fake["chamadas"][0]
    assert chamada["url"].endswith("/api_publica_tjsp/_search")
    assert chamada["headers"]["Authorization"].startswith("APIKey ")
    assert chamada["json"] == {"query": {"match": {"numeroProcesso": CNJ}}, "size": 1}
    assert chamada["timeout"] == 30


def test_verify_nunca_false(post_fake):
    datajud.consultar(CNJ, "tjsp", timeout=5)
    for chamada in post_fake["chamadas"]:
        assert chamada.get("verify", True) is not False
    assert "MAAT-Monitor/" in datajud._sessao.headers["User-Agent"]


def test_hits_vazio(post_fake):
    post_fake["resposta"] = RespostaFake({"hits": {"hits": []}})
    r = datajud.consultar(CNJ, "tjsp")
    assert r.ok is False
    assert "não encontrado" in r.erro


def test_numero_divergente(post_fake):
    post_fake["resposta"] = RespostaFake(_corpo_hit("00010540420108260101"))
    r = datajud.consultar(CNJ, "tjsp")
    assert r.ok is False
    assert "divergente" in r.erro


def test_timeout(post_fake):
    post_fake["resposta"] = requests.exceptions.Timeout()
    r = datajud.consultar(CNJ, "tjsp")
    assert r.ok is False
    assert "timeout" in r.erro.lower()


def test_ssl(post_fake):
    post_fake["resposta"] = requests.exceptions.SSLError()
    r = datajud.consultar(CNJ, "tjsp")
    assert r.ok is False
    assert "SSL" in r.erro


def test_http_429(post_fake):
    post_fake["resposta"] = RespostaFake(status=429)
    r = datajud.consultar(CNJ, "tjsp")
    assert r.ok is False
    assert "429" in r.erro
    assert "aguarde" in r.erro


def test_http_503(post_fake):
    post_fake["resposta"] = RespostaFake(status=503)
    r = datajud.consultar(CNJ, "tjsp")
    assert "503" in r.erro
    assert "instável" in r.erro


def test_falha_conexao_generica(post_fake):
    post_fake["resposta"] = requests.exceptions.ConnectionError()
    r = datajud.consultar(CNJ, "tjsp")
    assert "internet" in r.erro


def test_json_nao_dict(post_fake):
    post_fake["resposta"] = RespostaFake(["lista", "inesperada"])
    r = datajud.consultar(CNJ, "tjsp")
    assert r.ok is False
    assert "inválida" in r.erro


def test_json_invalido(post_fake):
    post_fake["resposta"] = RespostaFake(json_invalido=True)
    r = datajud.consultar(CNJ, "tjsp")
    assert "inválida" in r.erro


def test_source_ausente(post_fake):
    post_fake["resposta"] = RespostaFake({"hits": {"hits": [{"_id": "x"}]}})
    r = datajud.consultar(CNJ, "tjsp")
    assert "inválida" in r.erro


def test_tribunal_desconhecido_sem_rede(post_fake):
    r = datajud.consultar(CNJ, "tjxx")
    assert r.ok is False
    assert "não é suportado" in r.erro
    assert "tjxx" in r.erro
    assert post_fake["chamadas"] == []


def test_testar_conexao_nao_encontrado_conta_como_ok(post_fake):
    post_fake["resposta"] = RespostaFake({"hits": {"hits": []}})
    r = datajud.testar_conexao()
    assert r.ok is True
    assert post_fake["chamadas"][0]["url"].endswith("/api_publica_tjsp/_search")


def test_testar_conexao_falha(post_fake):
    post_fake["resposta"] = requests.exceptions.ConnectionError()
    r = datajud.testar_conexao()
    assert r.ok is False
    assert "internet" in r.erro
