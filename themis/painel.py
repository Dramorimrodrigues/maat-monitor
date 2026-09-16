"""
Painel web local do THEMIS Monitor (http://127.0.0.1:5000).

Servidor HTTP da biblioteca padrão, sem framework. Escuta SOMENTE em 127.0.0.1,
aceita apenas requisições com Host/Origin locais, limita o corpo a 1 MB e responde
erros em JSON sem expor detalhes internos. Rotas POST: /api/consultar,
/api/adicionar e /api/adicionar-lote.

Copyright (c) 2026 Márcio Luis Amorim — Licença MIT
"""

from __future__ import annotations

import http.server
import json
import re
import socket
import sqlite3
import sys
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from html import escape
from typing import Any, Callable

from themis import __version__, banco, cnj, config, constantes, datajud, relatorio

LIMITE_CORPO = 1024 * 1024  # 1 MB
CAMPOS_TEXTO = ("cnj", "rotulo", "cliente", "area")
MSG_SOMENTE_LOCAL = "Acesso permitido somente pela origem local do painel."
MSG_ARMAZENAMENTO = "Falha ao acessar o armazenamento local. Verifique o acesso aos arquivos e tente novamente."

# ------------------------------------------------------------------
# JS exclusivo do painel (consulta, adição, abas e importação em lote)
# ------------------------------------------------------------------

JS_PAINEL = r"""
var ultimoCnj = '';

function esc(v) {
  return String(v == null ? '' : v).replace(/[&<>"']/g, function(c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  });
}

function mostrarErro(res, texto) {
  res.className = 'res-box res-erro';
  res.innerHTML = '<strong>&#10060; ' + esc(texto) + '</strong>';
  res.style.display = 'block';
}

function consultar() {
  var inp = document.getElementById('inp');
  var btn = document.getElementById('btn');
  var res = document.getElementById('res');
  var valor = inp.value.trim();
  if (!valor) {
    mostrarErro(res, 'Digite o número CNJ antes de consultar.');
    inp.focus();
    return;
  }
  btn.disabled = true; btn.innerHTML = '&#9203; Consultando...';
  res.className = 'res-box'; res.style.display = 'none';

  fetch('/api/consultar', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({cnj: valor})
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    btn.disabled = false; btn.innerHTML = '&#128269; CONSULTAR';
    if (d.erro) { mostrarErro(res, d.erro); return; }
    ultimoCnj = d.cnj;
    var novTxt = d.novos > 0
      ? '<strong style="color:var(--verde)">' + esc(d.novos) + ' novo(s) andamento(s) detectado(s)</strong>'
      : 'Sem novidades desde a última consulta.';
    res.className = 'res-box res-ok';
    res.innerHTML =
      '<div class="res-cnj">&#10003; ' + esc(d.cnj) + '</div>' +
      '<div class="res-linha"><strong>Tribunal:</strong> ' + esc(d.tribunal) + ' &nbsp;|&nbsp; <strong>Grau:</strong> ' + esc(d.grau) + '</div>' +
      '<div class="res-linha"><strong>Classe:</strong> ' + esc(d.classe) + '</div>' +
      '<div class="res-linha"><strong>&Oacute;rg&atilde;o:</strong> ' + esc(d.orgao) + '</div>' +
      '<div class="res-linha"><strong>Andamentos:</strong> ' + esc(d.total_movimentos) + ' &nbsp;|&nbsp; ' + novTxt + '</div>' +
      (d.ultimo_andamento ? '<div class="res-linha"><strong>&Uacute;ltimo andamento:</strong> ' + esc(d.ultimo_andamento) + '</div>' : '') +
      '<div class="res-acoes">' +
        '<button type="button" class="btn-add" onclick="mostraForm()">&#10133; Adicionar ao Monitoramento Fixo</button>' +
        '<button type="button" class="btn-reload" onclick="location.reload()">&#8635; Atualizar Painel</button>' +
      '</div>' +
      '<div id="af" class="add-form">' +
        '<strong>Dados opcionais:</strong><br><br>' +
        '<input id="ar" type="text" placeholder="Apelido do caso (ex: Ação de indenização - João Silva)"><br>' +
        '<div class="add-row">' +
          '<input id="ac" type="text" placeholder="Nome do cliente">' +
          '<input id="aa" type="text" placeholder="Área (Cível, Trabalhista...)">' +
        '</div>' +
        '<button type="button" class="btn-conf" onclick="adicionar()">&#10003; Confirmar Adição</button>' +
        '<span id="am2" class="add-msg"></span>' +
      '</div>';
    res.style.display = 'block';
  })
  .catch(function(e) {
    btn.disabled = false; btn.innerHTML = '&#128269; CONSULTAR';
    mostrarErro(res, 'Erro de conexão: ' + e.message);
  });
}

function mostraForm() {
  var f = document.getElementById('af');
  if (f) f.style.display = f.style.display === 'block' ? 'none' : 'block';
}

function adicionar() {
  var r = (document.getElementById('ar') || {}).value || '';
  var c = (document.getElementById('ac') || {}).value || '';
  var a = (document.getElementById('aa') || {}).value || '';
  var m = document.getElementById('am2');
  fetch('/api/adicionar', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({cnj: ultimoCnj, rotulo: r, cliente: c, area: a})
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    if (m) { m.textContent = d.ok ? '✓ Adicionado!' : ('Erro: ' + d.erro); m.style.color = d.ok ? 'var(--verde)' : 'var(--vermelho)'; }
  })
  .catch(function(e) { if (m) { m.textContent = 'Erro: ' + e.message; m.style.color = 'var(--vermelho)'; } });
}

// ===== ABAS =====
document.querySelectorAll('.tab-btn').forEach(function(b) {
  b.addEventListener('click', function() {
    var t = this.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(function(x) { x.classList.remove('active'); });
    document.querySelectorAll('.tab-panel').forEach(function(x) { x.classList.remove('active'); });
    this.classList.add('active');
    document.getElementById('tab-' + t).classList.add('active');
    if (t === 'cnj') document.getElementById('inp').focus();
    if (t === 'oab') document.getElementById('oab-txt').focus();
  });
});

// ===== OAB: EXTRAÇÃO E IMPORTAÇÃO EM LOTE =====
var cnjsExtraidos = [];

function renderChips() {
  var el = document.getElementById('oab-chips');
  var form = document.getElementById('oab-form');
  var btn = document.getElementById('btn-lote');
  if (!cnjsExtraidos.length) {
    el.innerHTML = '<span class="oab-vazio">Nenhum n&uacute;mero CNJ detectado.</span>';
    if (form) form.style.display = 'none';
    return;
  }
  el.innerHTML = cnjsExtraidos.map(function(c, i) {
    return '<span class="cnj-chip">' + esc(c) +
      '<button type="button" onclick="removerCnj(' + i + ')" title="Remover">&times;</button></span>';
  }).join('');
  if (form) form.style.display = 'block';
  if (btn) {
    btn.innerHTML = '&#10133; Adicionar ' + cnjsExtraidos.length + ' processo(s) ao Monitoramento';
    btn.style.background = 'var(--verde)'; btn.disabled = false;
  }
  var res = document.getElementById('lote-result');
  if (res) res.style.display = 'none';
  var msg = document.getElementById('oab-msg');
  if (msg) msg.textContent = '';
}

function extrairCnjs() {
  var txt = document.getElementById('oab-txt').value;
  var re = /\d{7}[.\-]?\d{2}[.\-]?\d{4}[.\-]?\d[.\-]?\d{2}[.\-]?\d{4}/g;
  var achs = txt.match(re) || [];
  var vistos = {};
  cnjsExtraidos = [];
  achs.forEach(function(raw) {
    var d = raw.replace(/[^0-9]/g, '');
    if (d.length !== 20 || vistos[d]) return;
    vistos[d] = true;
    cnjsExtraidos.push(d.slice(0, 7) + '-' + d.slice(7, 9) + '.' + d.slice(9, 13) + '.' + d[13] + '.' + d.slice(14, 16) + '.' + d.slice(16, 20));
  });
  renderChips();
}

function removerCnj(i) {
  cnjsExtraidos.splice(i, 1);
  renderChips();
}

function adicionarLote() {
  if (!cnjsExtraidos.length) return;
  var cli = (document.getElementById('oab-cli') || {}).value || '';
  var area = (document.getElementById('oab-area') || {}).value || '';
  var msg = document.getElementById('oab-msg');
  var btn = document.getElementById('btn-lote');
  var res = document.getElementById('lote-result');
  btn.disabled = true; btn.innerHTML = '&#9203; Adicionando...';
  if (msg) msg.textContent = '';
  if (res) res.style.display = 'none';
  var itens = cnjsExtraidos.map(function(c) { return {cnj: c}; });
  fetch('/api/adicionar-lote', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({itens: itens, cliente: cli, area: area})
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    btn.disabled = false;
    if (d.erro) {
      if (msg) { msg.textContent = '❌ ' + d.erro; msg.style.color = 'var(--vermelho)'; }
      btn.innerHTML = '&#10133; Tentar novamente'; btn.style.background = 'var(--verde)';
      return;
    }
    var html = '';
    if ((d.adicionados || []).length) html += '<div class="lote-ok">&#10003; Adicionados: ' + d.adicionados.map(esc).join(' &nbsp;&bull;&nbsp; ') + '</div>';
    if ((d.ignorados || []).length) html += '<div class="lote-err">&#9888; Ignorados: ' + d.ignorados.map(esc).join(' &nbsp;&bull;&nbsp; ') + '</div>';
    if (res) { res.innerHTML = html || '<div class="lote-ok">Conclu&iacute;do.</div>'; res.style.display = 'block'; }
    var n = (d.adicionados || []).length;
    btn.innerHTML = '&#10003; ' + n + ' adicionado(s)!';
    btn.style.background = 'var(--roxo-medio)';
    cnjsExtraidos = [];
    document.getElementById('oab-txt').value = '';
    document.getElementById('oab-chips').innerHTML = '<span class="oab-vazio">Cole novos processos acima para continuar importando.</span>';
  })
  .catch(function(e) {
    btn.disabled = false; btn.innerHTML = '&#10133; Tentar novamente'; btn.style.background = 'var(--verde)';
    if (msg) { msg.textContent = '❌ ' + e.message; msg.style.color = 'var(--vermelho)'; }
  });
}

document.addEventListener('DOMContentLoaded', function() {
  var inp = document.getElementById('inp');
  if (inp) inp.focus();
});
"""


# ------------------------------------------------------------------
# Página do painel
# ------------------------------------------------------------------


def _html_aba_cnj() -> str:
    """Aba "Consultar por CNJ"."""
    return """
  <div id="tab-cnj" class="tab-panel active">
    <div class="c-label">&#128269; Consultar Processo no DataJud</div>
    <div class="c-row">
      <input id="inp" class="c-input" type="text"
             placeholder="Digite o n&uacute;mero CNJ &mdash; ex: 0000001-05.2025.8.26.0100"
             maxlength="30" autocomplete="off"
             onkeydown="if(event.key==='Enter')consultar()">
      <button id="btn" type="button" class="c-btn" onclick="consultar()">&#128269; CONSULTAR</button>
    </div>
    <div class="c-dica">Pressione Enter ou clique CONSULTAR &mdash; fonte oficial API DataJud/CNJ</div>
    <div id="res" class="res-box"></div>
  </div>"""


def _html_aba_oab(oab_num: str, oab_uf: str) -> str:
    """Aba "Importar por OAB" com links dos portais e área de colagem."""
    num_q = urllib.parse.quote(oab_num)
    uf_q = urllib.parse.quote(oab_uf)
    return f"""
  <div id="tab-oab" class="tab-panel">
    <div class="c-label">&#9878; OAB {escape(oab_num)}/{escape(oab_uf)} &mdash; Importar Processos em Lote</div>
    <p class="oab-info">
      A API DataJud n&atilde;o permite busca por advogado (restri&ccedil;&atilde;o da LGPD).
      Abra um dos portais abaixo, localize seus processos e cole o texto aqui &mdash;
      os n&uacute;meros CNJ s&atilde;o extra&iacute;dos e adicionados ao monitoramento automaticamente.
    </p>
    <div class="oab-portais">
      <a href="http://www4.tjrj.jus.br/numeracaoUnica/faces/index.jsp?numProcesso=&amp;tipoPesquisa=advogado&amp;numeroOAB={num_q}&amp;letraOAB=&amp;estadoOAB={uf_q}"
         target="_blank" rel="noopener noreferrer" class="btn-portal tj">&#9878; TJ-RJ</a>
      <a href="https://esaj.tjsp.jus.br/cpopg/open.do"
         target="_blank" rel="noopener noreferrer" class="btn-portal tj">&#9878; TJ-SP</a>
      <a href="https://eproc.trf2.jus.br/eproc/externo_controlador.php?acao=processo_consulta_publica_oab"
         target="_blank" rel="noopener noreferrer" class="btn-portal trf">&#9878; TRF-2</a>
      <a href="https://pje.trt1.jus.br/consultaprocessual/pages/consultas/ConsultaProcessual.seam"
         target="_blank" rel="noopener noreferrer" class="btn-portal trt">&#9878; TRT-1</a>
      <a href="https://www.cnj.jus.br/tribunais/" target="_blank" rel="noopener noreferrer"
         class="btn-portal extra">&#128269; Outros tribunais</a>
    </div>
    <div class="c-label" style="margin-bottom:8px">Cole qualquer texto com n&uacute;meros CNJ:</div>
    <textarea id="oab-txt" class="oab-pasta" rows="5"
      placeholder="Cole aqui texto do portal, e-mail, documento ou lista de processos...&#10;&#10;Exemplo: 0000001-05.2025.8.26.0100&#10;O sistema detecta e extrai os n&uacute;meros automaticamente."
      oninput="extrairCnjs()"></textarea>
    <div id="oab-chips" class="oab-chips"><span class="oab-vazio">Nenhum n&uacute;mero detectado ainda &mdash; cole o texto acima.</span></div>
    <div id="oab-form" class="oab-form">
      <strong style="color:var(--ouro-claro);font-size:13px">Dados opcionais para todos os processos importados:</strong>
      <div class="add-row" style="margin-top:10px">
        <input id="oab-cli" type="text" placeholder="Nome do cliente (opcional)">
        <input id="oab-area" type="text" placeholder="&Aacute;rea: C&iacute;vel, Trabalhista, Federal...">
      </div>
      <button id="btn-lote" type="button" class="btn-lote" onclick="adicionarLote()">&#10133; Adicionar ao Monitoramento</button>
      <span id="oab-msg" class="oab-msg"></span>
      <div id="lote-result" class="lote-result"></div>
    </div>
  </div>"""


def gerar_pagina() -> str:
    """Monta o HTML completo do painel a partir do config e do banco atuais."""
    c = config.caminhos()
    cfg = config.carregar_config(c)
    c.base.mkdir(parents=True, exist_ok=True)
    conn = banco.conectar(c.banco)
    try:
        processos = banco.ler_processos(conn, int(cfg.get("dias_alerta_parado", 30)))
        historico = banco.ler_historico(conn)
    finally:
        conn.close()

    agora_fmt = datetime.now().strftime("%d/%m/%Y %H:%M")
    cont = relatorio.contar_situacoes(processos)
    oab_num = re.sub(r"[^0-9]", "", str(cfg.get("oab_numero", "")))
    oab_uf = str(cfg.get("oab_uf", "")).strip().upper()
    kpis = relatorio.html_kpis([
        ("Monitorados", cont["total"], ""),
        ("Urgentes", cont["urgente"], "alerta" if cont["urgente"] else "ok"),
        ("Com Novidade", cont["novo"], "ouro" if cont["novo"] else "ok"),
        ("Parados", cont["parado"], "amarelo" if cont["parado"] else "ok"),
    ])

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>THEMIS &mdash; Painel Interativo</title>
<style>{relatorio.CSS}</style>
</head>
<body>
{relatorio.html_cabecalho("Painel Interativo", cfg, agora_fmt)}

<div class="consulta">
  <div class="tabs">
    <button type="button" class="tab-btn active" data-tab="cnj">&#128269; Consultar por CNJ</button>
    <button type="button" class="tab-btn" data-tab="oab">&#9878; Importar por OAB</button>
  </div>
{_html_aba_cnj()}
{_html_aba_oab(oab_num, oab_uf)}
</div>
{relatorio.html_barra_filtros(cont)}
<div class="container">
{kpis}
<div id="sem-resultados" class="sem-resultados">Nenhum processo corresponde ao filtro selecionado.</div>
<div id="lista">{relatorio.html_cards(processos)}</div>
{relatorio.html_historico(historico)}
</div>
{relatorio.rodape_html('&mdash; <a href="/">&#8635; Atualizar</a>')}
<script>{relatorio.JS_FILTROS}</script>
<script>{JS_PAINEL}</script>
</body>
</html>"""


# ------------------------------------------------------------------
# Servidor HTTP
# ------------------------------------------------------------------


def _ordem_data(valor: Any) -> float:
    """Timestamp para ordenar movimentos por dataHora; datas inválidas vão para o fim."""
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()
    except (ValueError, TypeError, OverflowError, OSError):
        return float("-inf")


def _nome_de(obj: Any) -> str:
    if isinstance(obj, dict) and obj.get("nome"):
        return str(obj["nome"])
    return "?"


class Handler(http.server.BaseHTTPRequestHandler):
    """Atende o painel: página em GET / e a API JSON em POST /api/*."""

    server_version = f"THEMIS/{__version__}"
    sys_version = ""

    # ---- infraestrutura ----

    def _local_request(self) -> bool:
        """Só aceita Host local (127.0.0.1, localhost, ::1) e Origin igual ao Host."""
        host = self.headers.get("Host", "")
        try:
            parsed = urllib.parse.urlsplit("http://" + host)
            if parsed.hostname not in ("127.0.0.1", "localhost", "::1") or parsed.username or parsed.path:
                return False
            parsed.port  # noqa: B018 - dispara ValueError se a porta for inválida
        except ValueError:
            return False
        origin = self.headers.get("Origin")
        return not origin or origin == "http://" + host

    def _resp(self, code: int, ctype: str, data: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, result: dict) -> None:
        self._resp(code, "application/json; charset=utf-8", json.dumps(result, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D102 - silencioso de propósito
        pass

    # ---- rotas ----

    def do_GET(self) -> None:  # noqa: N802 - nome exigido pela biblioteca padrão
        if not self._local_request():
            self._json(403, {"erro": MSG_SOMENTE_LOCAL})
            return
        caminho = urllib.parse.urlsplit(self.path).path
        if caminho in ("/", "/index.html"):
            try:
                pagina = gerar_pagina()
            except (sqlite3.Error, OSError):
                self._json(500, {"erro": MSG_ARMAZENAMENTO})
                return
            self._resp(200, "text/html; charset=utf-8", pagina.encode("utf-8"))
        else:
            self._json(404, {"erro": "Rota não encontrada."})

    def _ler_corpo(self) -> bytes | None:
        """Lê o corpo até 1 MB. None se o Content-Length é inválido ou grande demais (não lê nada)."""
        try:
            tamanho = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return None
        if tamanho < 0 or tamanho > LIMITE_CORPO:
            return None
        return self.rfile.read(tamanho)

    def do_POST(self) -> None:  # noqa: N802
        # Lê o corpo antes de qualquer resposta: fechar o socket com dados não lidos
        # gera RST e o navegador não chega a ver o JSON de erro.
        corpo = self._ler_corpo()
        if not self._local_request():
            self._json(403, {"erro": MSG_SOMENTE_LOCAL})
            return
        rotas: dict[str, Callable[[dict], dict]] = {
            "/api/consultar": self._consultar,
            "/api/adicionar": self._adicionar,
            "/api/adicionar-lote": self._adicionar_lote,
        }
        caminho = urllib.parse.urlsplit(self.path).path
        if caminho not in rotas:
            self._json(404, {"erro": "Rota não encontrada."})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            self._json(415, {"erro": "Use Content-Type application/json."})
            return
        if not corpo:
            self._json(400, {"erro": "Tamanho da requisição inválido."})
            return
        try:
            body = json.loads(corpo)
            self._validar_corpo(body, caminho)
        except (ValueError, UnicodeError, TypeError):
            self._json(400, {"erro": "JSON ou campos de cadastro inválidos."})
            return
        try:
            resultado = rotas[caminho](body)
        except (sqlite3.Error, OSError):
            self._json(500, {"erro": MSG_ARMAZENAMENTO})
            return
        self._json(200, resultado)

    @staticmethod
    def _validar_corpo(body: Any, caminho: str) -> None:
        """Garante que o corpo é um objeto e que os campos de cadastro são texto."""
        if not isinstance(body, dict):
            raise ValueError("Corpo JSON deve ser um objeto.")
        for chave in CAMPOS_TEXTO:
            if chave in body and not isinstance(body[chave], str):
                raise ValueError("Campos de cadastro devem ser texto.")
        if caminho == "/api/adicionar-lote":
            itens = body.get("itens")
            if not isinstance(itens, list) or any(
                not isinstance(item, dict)
                or any(chave in item and not isinstance(item[chave], str) for chave in CAMPOS_TEXTO)
                for item in itens
            ):
                raise ValueError("Lista de processos inválida.")

    # ---- handlers da API ----

    def _consultar(self, body: dict) -> dict:
        """Consulta um CNJ no DataJud, grava no banco e devolve um resumo."""
        cnj_limpo, erro = cnj.validar(body.get("cnj", ""))
        if cnj_limpo is None:
            return {"erro": erro}
        tribunal = cnj.identificar_tribunal(cnj_limpo)
        if not tribunal:
            return {"erro": "Não foi possível identificar o tribunal pelo número CNJ."}
        res = datajud.consultar(cnj_limpo, tribunal)
        if not res.ok or not res.fonte:
            return {"erro": res.erro or datajud.MSG_INVALIDA}
        fonte = res.fonte

        c = config.caminhos()
        c.base.mkdir(parents=True, exist_ok=True)
        conn = banco.conectar(c.banco)
        try:
            sucesso, novos = banco.salvar_resultado(conn, cnj_limpo, fonte)
        finally:
            conn.close()
        if not sucesso:
            return {"erro": "Resposta do DataJud em formato inesperado; nada foi salvo."}

        movs = [m for m in (fonte.get("movimentos") or []) if isinstance(m, dict)]
        ultimo = max(movs, key=lambda m: _ordem_data(m.get("dataHora")), default={})
        assuntos = [a for a in (fonte.get("assuntos") or []) if isinstance(a, dict)]
        return {
            "ok": True,
            "cnj": cnj.formatar(cnj_limpo),
            "tribunal": constantes.TRIBUNAIS[tribunal]["nome"],
            "classe": _nome_de(fonte.get("classe")),
            "assunto": ", ".join(str(a.get("nome") or "") for a in assuntos)[:150],
            "orgao": _nome_de(fonte.get("orgaoJulgador")),
            "grau": str(fonte.get("grau") or "?"),
            "total_movimentos": len(movs),
            "ultimo_andamento": str(ultimo.get("nome") or ""),
            "novos": novos,
        }

    def _adicionar(self, body: dict) -> dict:
        """Adiciona um único processo ao processos.txt."""
        resultado = self._adicionar_lote({"itens": [body]})
        if resultado.get("erro"):
            return resultado
        if resultado["ignorados"]:
            return {"erro": resultado["ignorados"][0]}
        return {"ok": True}

    def _adicionar_lote(self, body: dict) -> dict:
        """Adiciona vários processos; cliente/área do corpo valem para itens que não os informam."""
        itens = body.get("itens") or []
        if not itens:
            return {"erro": "Nenhum processo informado."}
        preparados: list[config.Processo] = []
        for item in itens:
            campos = [str(item.get("cnj") or "")] + [
                str(item.get(chave) or body.get(chave) or "") for chave in ("rotulo", "cliente", "area")
            ]
            if any(ch in campo for campo in campos for ch in config.CARACTERES_PROIBIDOS):
                return {"erro": "Campos devem ser texto sem barras verticais ou quebras de linha."}
            preparados.append(config.Processo(*(x.strip() for x in campos)))
        adicionados, ignorados = config.adicionar_processos(config.caminhos(), preparados)
        return {"ok": True, "adicionados": adicionados, "ignorados": ignorados}


class _Servidor(http.server.ThreadingHTTPServer):
    """Servidor com threads. No Windows usa SO_EXCLUSIVEADDRUSE: lá o SO_REUSEADDR
    deixaria um segundo painel ocupar a mesma porta em silêncio."""

    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True

    def server_bind(self) -> None:
        if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def criar_servidor(host: str = "127.0.0.1", porta: int = 5000) -> http.server.HTTPServer:
    """Cria o servidor (sem iniciar). ``porta=0`` escolhe uma porta livre (útil em testes)."""
    return _Servidor((host, porta), Handler)


def executar(porta: int = 5000, abrir_navegador: bool = True) -> int:
    """Sobe o painel em 127.0.0.1 e bloqueia até Ctrl+C. Devolve o código de saída."""
    config.garantir_arquivos_iniciais(config.caminhos())
    print()
    print("=" * 58)
    print(f"  THEMIS Monitor v{__version__} — Painel Web Local")
    print("  © 2026 Márcio Luis Amorim — Licença MIT")
    print("=" * 58)
    print()
    try:
        servidor = criar_servidor(porta=porta)
    except OSError:
        print(f"  Porta {porta} já está em uso — feche o painel anterior ou use --porta")
        return 1
    porta_real = servidor.server_address[1]
    url = f"http://127.0.0.1:{porta_real}"
    print(f"  Servidor em: {url}")
    print("  Para encerrar: pressione Ctrl+C ou feche esta janela")
    print()

    if abrir_navegador:

        def abrir() -> None:
            time.sleep(1.5)
            webbrowser.open(url)

        threading.Thread(target=abrir, daemon=True).start()

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor encerrado.")
    finally:
        servidor.server_close()
    return 0
