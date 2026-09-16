"""Testes de notificações (sem rede). Copyright (c) 2026 Márcio Luis Amorim — MIT."""

from __future__ import annotations

import smtplib
from unittest.mock import MagicMock

import pytest

from themis import __version__, notificacoes

CONFIG_EMAIL = {
    "email_ativo": "sim",
    "email_smtp": "smtp.exemplo.com",
    "email_porta": "587",
    "email_remetente": "eu@exemplo.com",
    "email_senha_app": "senha-secreta",
    "email_destinatario": "voce@exemplo.com",
}

CONFIG_WHATSAPP = {
    "whatsapp_ativo": "sim",
    "whatsapp_telefone": "+5521999990000",
    "whatsapp_token": "123456",
}


def _explodir(*args, **kwargs):
    raise AssertionError("SMTP não deveria ser chamado")


# ---------------------------------------------------------------- e-mail


def test_email_desativado_nao_toca_smtp(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", _explodir)
    config = dict(CONFIG_EMAIL, email_ativo="nao")
    assert notificacoes.enviar_email(config, "Assunto", "<p>x</p>") is False


def test_email_incompleto_nao_toca_smtp(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", _explodir)
    config = dict(CONFIG_EMAIL, email_senha_app="")
    assert notificacoes.enviar_email(config, "Assunto", "<p>x</p>") is False


@pytest.fixture
def smtp_mock(monkeypatch):
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    smtp.__exit__.return_value = False
    classe = MagicMock(return_value=smtp)
    monkeypatch.setattr(smtplib, "SMTP", classe)
    return classe, smtp


def test_email_ativado_envia(smtp_mock):
    classe, smtp = smtp_mock
    ok = notificacoes.enviar_email(CONFIG_EMAIL, "Assunto", "<p>x</p>", texto="x")
    assert ok is True
    classe.assert_called_once_with("smtp.exemplo.com", 587, timeout=30)
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("eu@exemplo.com", "senha-secreta")
    smtp.sendmail.assert_called_once()
    remetente, destinatario, corpo = smtp.sendmail.call_args[0]
    assert remetente == "eu@exemplo.com"
    assert destinatario == "voce@exemplo.com"
    assert "Subject: Assunto" in corpo


def test_email_falha_login(smtp_mock, caplog):
    _, smtp = smtp_mock
    smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    with caplog.at_level("WARNING", logger="themis.notificacoes"):
        assert notificacoes.enviar_email(CONFIG_EMAIL, "Assunto", "<p>x</p>") is False
    assert "SMTPAuthenticationError" in caplog.text
    assert "senha-secreta" not in caplog.text
    smtp.sendmail.assert_not_called()


def test_montar_email_html_escapa_rotulo():
    stats = {"total": 3, "sucesso": 2, "erros": 1, "novos_andamentos": 4}
    novidades = [("0001054-04.2010.8.26.0100", "<b>x</b>", 4)]
    saida = notificacoes.montar_email_html(stats, novidades, "16/09/2026 10:00")
    assert "<b>x</b>" not in saida
    assert "&lt;b&gt;x&lt;/b&gt;" in saida
    assert "THEMIS &mdash; Resumo do Monitoramento" in saida
    assert f"THEMIS Monitor v{__version__}" in saida
    assert "Márcio Luis Amorim" in saida
    assert "4 novo(s) andamento(s)" in saida


def test_montar_email_html_sem_novidade():
    stats = {"total": 1, "sucesso": 1, "erros": 0, "novos_andamentos": 0}
    saida = notificacoes.montar_email_html(stats, [], "16/09/2026 10:00")
    assert "Nenhuma novidade nesta rodada." in saida


# ---------------------------------------------------------------- WhatsApp


def test_whatsapp_desativado(monkeypatch):
    monkeypatch.setattr(notificacoes.requests, "get", _explodir)
    config = dict(CONFIG_WHATSAPP, whatsapp_ativo="nao")
    assert notificacoes.enviar_whatsapp(config, "oi") is False


def test_whatsapp_incompleto(monkeypatch):
    monkeypatch.setattr(notificacoes.requests, "get", _explodir)
    config = dict(CONFIG_WHATSAPP, whatsapp_token="")
    assert notificacoes.enviar_whatsapp(config, "oi") is False


def test_whatsapp_envia(monkeypatch):
    chamadas = []

    def fake_get(url, **kwargs):
        chamadas.append((url, kwargs))
        return MagicMock(status_code=200)

    monkeypatch.setattr(notificacoes.requests, "get", fake_get)
    assert notificacoes.enviar_whatsapp(CONFIG_WHATSAPP, "olá mundo & cia") is True
    url, kwargs = chamadas[0]
    assert url.startswith("https://api.callmebot.com/whatsapp.php?")
    assert "%2B5521999990000" in url
    assert "apikey=123456" in url
    assert "text=ol%C3%A1+mundo+%26+cia" in url
    assert kwargs["timeout"] == 15


def test_whatsapp_status_nao_200(monkeypatch):
    monkeypatch.setattr(notificacoes.requests, "get", lambda url, **kw: MagicMock(status_code=500))
    assert notificacoes.enviar_whatsapp(CONFIG_WHATSAPP, "oi") is False


def test_whatsapp_excecao(monkeypatch):
    def fake_get(url, **kwargs):
        raise OSError("sem rede")

    monkeypatch.setattr(notificacoes.requests, "get", fake_get)
    assert notificacoes.enviar_whatsapp(CONFIG_WHATSAPP, "oi") is False


def test_montar_whatsapp_texto_limita_a_cinco():
    stats = {"total": 10, "sucesso": 9, "erros": 1, "novos_andamentos": 7}
    novidades = [(f"cnj{i}", f"Rótulo {i}" if i % 2 else "", 1) for i in range(7)]
    texto = notificacoes.montar_whatsapp_texto(stats, novidades, "16/09/2026 10:00")
    assert texto.startswith("*THEMIS — Novidades 16/09/2026 10:00*")
    assert "Novos andamentos: 7" in texto
    assert texto.count("•") == 5
    assert "• cnj0: 1 andamento(s)" in texto
    assert "• Rótulo 1: 1 andamento(s)" in texto
    assert "mais 2 processo(s)" in texto
