"""
Notificações do MAAT Monitor: e-mail (SMTP com STARTTLS) e WhatsApp (CallMeBot).

Nenhuma credencial é gravada em log. As funções de envio nunca lançam: devolvem
``True`` em sucesso e ``False`` quando desativadas, incompletas ou em falha.

Copyright (c) 2026 Márcio Luis Amorim — Licença MIT
"""

from __future__ import annotations

import html
import logging
import smtplib
import ssl
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from maat import __version__

log = logging.getLogger("maat.notificacoes")

CALLMEBOT_URL = "https://api.callmebot.com/whatsapp.php"
MAX_PROCESSOS_WHATSAPP = 5


def _ativo(config: dict, chave: str) -> bool:
    return str(config.get(chave, "nao")).strip().lower() == "sim"


def _porta(config: dict) -> int:
    try:
        return int(config.get("email_porta") or 587)
    except (TypeError, ValueError):
        return 587


def enviar_email(config: dict, assunto: str, corpo_html: str, texto: str = "") -> bool:
    """Envia o resumo por e-mail via SMTP/STARTTLS. Devolve True se enviado."""
    if not _ativo(config, "email_ativo"):
        return False
    servidor = str(config.get("email_smtp") or "").strip()
    remetente = str(config.get("email_remetente") or "").strip()
    senha = str(config.get("email_senha_app") or "")
    destinatario = str(config.get("email_destinatario") or "").strip()
    if not (servidor and remetente and senha and destinatario):
        log.warning(
            "E-mail: preencha email_smtp, email_remetente, email_senha_app e email_destinatario no config.ini."
        )
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = remetente
        msg["To"] = destinatario
        if texto:
            msg.attach(MIMEText(texto, "plain", "utf-8"))
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))
        with smtplib.SMTP(servidor, _porta(config), timeout=30) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(remetente, senha)
            smtp.sendmail(remetente, destinatario, msg.as_string())
        log.info("E-mail enviado com sucesso.")
        return True
    except Exception as exc:  # noqa: BLE001 - nunca propagar; só o tipo, nunca a senha
        log.warning("Erro ao enviar e-mail: %s", type(exc).__name__)
        return False


def enviar_whatsapp(config: dict, mensagem: str) -> bool:
    """Envia mensagem via CallMeBot. Devolve True se a API respondeu HTTP 200.

    Para ativar: envie "I allow callmebot to send me messages" para +34 644 59 97 45
    no WhatsApp e aguarde o token de resposta.
    """
    if not _ativo(config, "whatsapp_ativo"):
        return False
    telefone = str(config.get("whatsapp_telefone") or "").strip()
    token = str(config.get("whatsapp_token") or "").strip()
    if not (telefone and token):
        log.warning("WhatsApp: preencha whatsapp_telefone e whatsapp_token no config.ini.")
        return False
    try:
        url = CALLMEBOT_URL + "?" + urllib.parse.urlencode(
            {"phone": telefone, "text": mensagem, "apikey": token}
        )
        resposta = requests.get(url, timeout=15)
        if resposta.status_code == 200:
            log.info("WhatsApp enviado com sucesso.")
            return True
        log.warning("WhatsApp: status inesperado %s.", resposta.status_code)
        return False
    except Exception as exc:  # noqa: BLE001 - nunca propagar; só o tipo, nunca o token
        log.warning("Erro ao enviar WhatsApp: %s", type(exc).__name__)
        return False


def montar_email_html(
    estatisticas: dict,
    processos_com_novidade: list[tuple[str, str, int]],
    agora_fmt: str,
) -> str:
    """Monta o corpo HTML do e-mail de resumo (todo texto de dados é escapado)."""
    e = html.escape
    itens = "".join(
        f"<li><strong>{e(str(rotulo or cnj_fmt))}</strong> &mdash; {int(novos)} novo(s) andamento(s)</li>"
        for cnj_fmt, rotulo, novos in processos_com_novidade
    )
    lista = f"<ul>{itens}</ul>" if itens else "<p>Nenhuma novidade nesta rodada.</p>"
    total = int(estatisticas.get("total", 0))
    sucesso = int(estatisticas.get("sucesso", 0))
    erros = int(estatisticas.get("erros", 0))
    novos_and = int(estatisticas.get("novos_andamentos", 0))
    return f"""<html><body style="font-family:sans-serif;color:#1a0832;max-width:600px;margin:auto">
<h2 style="color:#3d1a6e">MAAT &mdash; Resumo do Monitoramento</h2>
<p style="color:#888">{e(str(agora_fmt))}</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0">
  <tr><td style="padding:8px;background:#f4f0fa"><strong>Processos verificados</strong></td><td style="padding:8px">{total}</td></tr>
  <tr><td style="padding:8px;background:#f4f0fa"><strong>Atualizados com sucesso</strong></td><td style="padding:8px;color:#1a8a5a">{sucesso}</td></tr>
  <tr><td style="padding:8px;background:#f4f0fa"><strong>Erros</strong></td><td style="padding:8px;color:#c0392b">{erros}</td></tr>
  <tr><td style="padding:8px;background:#f4f0fa"><strong>Novos andamentos</strong></td><td style="padding:8px;font-weight:700;color:#c9a440">{novos_and}</td></tr>
</table>
<h3 style="color:#3d1a6e">Processos com novidade</h3>
{lista}
<hr style="margin-top:32px">
<p style="font-size:11px;color:#aaa">MAAT Monitor v{e(__version__)} &mdash; &copy; 2026 Márcio Luis Amorim &mdash; Dados via DataJud/CNJ</p>
</body></html>"""


def montar_whatsapp_texto(
    estatisticas: dict,
    processos_com_novidade: list[tuple[str, str, int]],
    agora_fmt: str,
) -> str:
    """Monta o texto curto do WhatsApp (totais e até 5 processos com novidade)."""
    linhas = [
        f"*MAAT — Novidades {agora_fmt}*",
        f"Verificados: {int(estatisticas.get('total', 0))} | "
        f"OK: {int(estatisticas.get('sucesso', 0))} | "
        f"Erros: {int(estatisticas.get('erros', 0))} | "
        f"Novos andamentos: {int(estatisticas.get('novos_andamentos', 0))}",
    ]
    if processos_com_novidade:
        for cnj_fmt, rotulo, novos in processos_com_novidade[:MAX_PROCESSOS_WHATSAPP]:
            linhas.append(f"• {rotulo or cnj_fmt}: {int(novos)} andamento(s)")
        restantes = len(processos_com_novidade) - MAX_PROCESSOS_WHATSAPP
        if restantes > 0:
            linhas.append(f"… e mais {restantes} processo(s).")
    else:
        linhas.append("Nenhuma novidade nesta rodada.")
    return "\n".join(linhas)
