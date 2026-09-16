"""
Camada HTML/CSV do MAAT Monitor: folha de estilo e JS compartilhados, cards de
processos, relatório HTML e exportação CSV.

O painel (``maat.painel``) reutiliza as mesmas peças (``CSS``, ``JS_FILTROS``,
``html_cards``, ``html_historico``, ``rodape_html``), por isso relatório e painel
têm exatamente o mesmo visual. Todo texto vindo de dados passa por ``html.escape``.

Copyright (c) 2026 Márcio Luis Amorim — Licença MIT
"""

from __future__ import annotations

import csv
import re
import sqlite3
from datetime import datetime
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING, Any

from maat import __version__, analise, banco, cnj

if TYPE_CHECKING:  # pragma: no cover
    from maat.config import Caminhos

# ------------------------------------------------------------------
# CSS único (relatório + painel)
# ------------------------------------------------------------------

CSS = """
:root {
  --roxo-escuro:   #1a0832;
  --roxo-medio:    #3d1a6e;
  --roxo-suave:    #f4f0fa;
  --ouro:          #c9a440;
  --ouro-claro:    #f0d980;
  --branco:        #ffffff;
  --cinza-bg:      #f2f0f7;
  --cinza-borda:   #ddd8ea;
  --cinza-texto:   #5a5075;
  --verde:         #1a8a5a;
  --verde-claro:   #e6f7ef;
  --vermelho:      #c0392b;
  --vermelho-claro:#fdecea;
  --amarelo:       #c98000;
  --amarelo-claro: #fff3cd;
  --teal-claro:    #d0f0f0;
  --sombra:        0 2px 8px rgba(26,8,50,0.10);
  --sombra-hover:  0 4px 16px rgba(26,8,50,0.18);
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;background:var(--cinza-bg);color:var(--roxo-escuro);min-height:100vh}

/* CABEÇALHO */
.header{background:var(--roxo-escuro);padding:0 32px;display:flex;align-items:center;justify-content:space-between;height:64px;position:sticky;top:0;z-index:100;box-shadow:0 2px 12px rgba(0,0,0,.3)}
.header-logo{display:flex;align-items:center;gap:12px}
.header-logo .titulo{font-size:20px;font-weight:800;color:var(--ouro);letter-spacing:2px}
.header-logo .subtitulo{font-size:11px;color:rgba(255,255,255,.55);letter-spacing:1px;text-transform:uppercase;margin-top:1px}
.header-meta{font-size:12px;color:rgba(255,255,255,.5);text-align:right}
.header-meta strong{color:var(--ouro-claro)}

/* BARRA DE BUSCA / FILTROS */
.barra-busca{background:var(--roxo-medio);padding:12px 32px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.busca-input{flex:1;max-width:380px;min-width:180px;padding:9px 16px 9px 40px;border:none;border-radius:8px;font-size:14px;background:rgba(255,255,255,.12);color:#fff;outline:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='%23c9a440' viewBox='0 0 16 16'%3E%3Cpath d='M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.868-3.834zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:12px center}
.busca-input::placeholder{color:rgba(255,255,255,.4)}
.busca-input:focus{background-color:rgba(255,255,255,.18)}
.busca-count{font-size:13px;color:var(--ouro-claro);min-width:100px}
.filtros{display:flex;gap:6px;flex-wrap:wrap}
.btn-filtro{padding:5px 13px;border-radius:20px;border:1px solid rgba(255,255,255,.25);background:transparent;color:rgba(255,255,255,.7);font-size:12px;font-weight:600;cursor:pointer;transition:all .18s;letter-spacing:.3px}
.btn-filtro:hover{background:rgba(255,255,255,.12);color:#fff}
.btn-filtro.ativo{background:var(--ouro);color:var(--roxo-escuro);border-color:var(--ouro)}
.btn-filtro.f-novo.ativo{background:var(--verde);color:#fff;border-color:var(--verde)}
.btn-filtro.f-urgente.ativo{background:var(--vermelho);color:#fff;border-color:var(--vermelho)}
.btn-filtro.f-alerta.ativo{background:var(--amarelo);color:#fff;border-color:var(--amarelo)}
.btn-filtro.f-parado.ativo{background:#777;color:#fff;border-color:#777}

.container{max-width:1100px;margin:0 auto;padding:28px 24px 60px}

/* KPIs */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px;margin-bottom:28px}
.kpi{background:var(--branco);border-radius:12px;padding:18px 20px;box-shadow:var(--sombra);border-left:4px solid var(--roxo-medio);display:flex;flex-direction:column;gap:4px}
.kpi.ok{border-left-color:var(--verde)}.kpi.alerta{border-left-color:var(--vermelho)}.kpi.ouro{border-left-color:var(--ouro)}.kpi.amarelo{border-left-color:var(--amarelo)}
.kpi-valor{font-size:36px;font-weight:800;color:var(--roxo-escuro);line-height:1}
.kpi.ok .kpi-valor{color:var(--verde)}.kpi.alerta .kpi-valor{color:var(--vermelho)}.kpi.ouro .kpi-valor{color:var(--ouro)}.kpi.amarelo .kpi-valor{color:var(--amarelo)}
.kpi-rotulo{font-size:12px;color:var(--cinza-texto);font-weight:500}

/* CARDS */
.processo-card{background:var(--branco);border-radius:14px;box-shadow:var(--sombra);margin-bottom:18px;overflow:hidden;transition:box-shadow .2s;border-left:4px solid transparent}
.processo-card:hover{box-shadow:var(--sombra-hover)}
.processo-card.urgente{border-left-color:var(--vermelho)}.processo-card.tem-novo{border-left-color:var(--verde)}.processo-card.alerta{border-left-color:var(--amarelo)}.processo-card.parado{border-left-color:#bbb}
.card-cabecalho{padding:18px 22px 14px;display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap;cursor:pointer;user-select:none}
.card-cabecalho:hover{background:var(--roxo-suave)}
.card-titulo{flex:1;min-width:0}
.rotulo-processo{font-size:17px;font-weight:700;color:var(--roxo-escuro);margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cliente-processo{font-size:13px;color:var(--roxo-medio);font-weight:500;margin-bottom:2px}
.cnj-numero{font-family:'Courier New',monospace;font-size:12px;color:var(--cinza-texto);letter-spacing:.5px}
.badges{display:flex;align-items:center;gap:7px;flex-wrap:wrap;flex-shrink:0}
.badge{display:inline-flex;align-items:center;padding:3px 9px;border-radius:6px;font-size:11px;font-weight:700;white-space:nowrap}
.badge-tribunal{background:var(--roxo-medio);color:#fff}.badge-grau{background:var(--cinza-bg);color:var(--cinza-texto)}
.badge-area{background:var(--teal-claro);color:#1a5555}.badge-novo{background:var(--verde);color:#fff}
.badge-urgente{background:var(--vermelho);color:#fff}.badge-alerta{background:var(--amarelo-claro);color:var(--amarelo);border:1px solid var(--amarelo)}
.badge-parado{background:#eee;color:#888}.badge-mini{font-size:9px;padding:1px 5px}
.seta-card{color:var(--cinza-texto);font-size:17px;align-self:center}
.card-detalhes{border-top:1px solid var(--cinza-borda);display:none}
.card-detalhes.aberto{display:block}
.prazo-box{background:var(--vermelho-claro);border-left:4px solid var(--vermelho);padding:10px 20px;font-size:13px;font-weight:600;color:var(--vermelho)}
.info-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:0;padding:14px 20px;background:var(--roxo-suave);border-bottom:1px solid var(--cinza-borda)}
.info-item{padding:7px 10px}
.info-label{font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:var(--cinza-texto);font-weight:700;margin-bottom:3px}
.info-valor{font-size:13px;color:var(--roxo-escuro);font-weight:500;overflow-wrap:anywhere}
.info-valor.destaque{color:var(--ouro);font-weight:700}

/* TIMELINE DE ANDAMENTOS */
.movimentos-secao{padding:14px 22px 18px}
.movimentos-titulo{font-size:12px;font-weight:700;color:var(--cinza-texto);text-transform:uppercase;letter-spacing:.6px;margin-bottom:10px;display:flex;align-items:center;gap:8px}
.mov-count{background:var(--cinza-bg);color:var(--cinza-texto);border-radius:10px;padding:1px 8px;font-size:11px}
.timeline{position:relative;padding-left:20px}
.timeline::before{content:'';position:absolute;left:6px;top:8px;bottom:8px;width:2px;background:var(--cinza-borda)}
.mov-item{position:relative;padding:7px 0 7px 16px;border-bottom:1px solid var(--cinza-borda)}
.mov-item:last-child{border-bottom:none}
.mov-item::before{content:'';position:absolute;left:-14px;top:12px;width:10px;height:10px;border-radius:50%;background:var(--cinza-borda);border:2px solid var(--branco)}
.mov-item.novo::before{background:var(--verde)}.mov-item.urgente::before{background:var(--vermelho)}.mov-item.alerta::before{background:var(--amarelo)}
.mov-data{font-size:11px;color:var(--cinza-texto);font-family:monospace}.mov-nome{font-size:13px;font-weight:600;color:var(--roxo-escuro);margin:2px 0}
.mov-comp{font-size:12px;color:var(--cinza-texto);font-style:italic}.mov-prazo{font-size:11px;color:var(--vermelho);font-weight:700;margin-top:2px}

/* HISTÓRICO */
.historico-secao{background:var(--branco);border-radius:14px;box-shadow:var(--sombra);padding:22px;margin-top:32px}
.historico-titulo{font-size:15px;font-weight:700;color:var(--roxo-escuro);margin-bottom:14px}
.hist-table{width:100%;border-collapse:collapse;font-size:13px}
.hist-table th{background:var(--roxo-suave);color:var(--cinza-texto);text-align:left;padding:8px 12px;font-weight:700;text-transform:uppercase;font-size:10px;letter-spacing:.5px}
.hist-table td{padding:8px 12px;border-bottom:1px solid var(--cinza-borda)}
.hist-table tr:last-child td{border-bottom:none}
.hist-col-ok{color:var(--verde);font-weight:600}.hist-col-erro{color:var(--vermelho)}.hist-col-novo{color:var(--ouro);font-weight:700}

.sem-resultados{text-align:center;padding:60px 20px;color:var(--cinza-texto);display:none}
.sem-resultados.visivel{display:block}
.lista-vazia{text-align:center;color:#888;padding:40px 20px;line-height:1.7}

footer{text-align:center;color:var(--cinza-texto);font-size:12px;padding:22px;border-top:1px solid var(--cinza-borda);margin-top:20px}
footer strong{color:var(--ouro)}
footer a{color:var(--ouro);text-decoration:none}

/* ===== PAINEL: CONSULTA / ABAS ===== */
.consulta{background:linear-gradient(135deg,#250945,var(--roxo-medio));padding:22px 32px}
.tabs{display:flex;gap:0;margin-bottom:16px;border-bottom:2px solid rgba(255,255,255,.15)}
.tab-btn{padding:10px 22px;background:transparent;color:rgba(255,255,255,.5);border:none;border-bottom:3px solid transparent;font-size:13px;font-weight:700;cursor:pointer;transition:all .15s;margin-bottom:-2px;letter-spacing:.3px}
.tab-btn:hover{color:rgba(255,255,255,.85)}
.tab-btn.active{color:var(--ouro);border-bottom-color:var(--ouro)}
.tab-panel{display:none}.tab-panel.active{display:block}
.c-label{color:var(--ouro);font-size:12px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;margin-bottom:10px}
.c-row{display:flex;gap:10px;flex-wrap:wrap;align-items:stretch}
.c-input{flex:1;min-width:240px;padding:14px 18px;border:2px solid rgba(255,255,255,.18);border-radius:10px;font-size:16px;font-family:'Courier New',monospace;background:rgba(255,255,255,.08);color:#fff;outline:none;letter-spacing:.5px;transition:border-color .2s}
.c-input::placeholder{color:rgba(255,255,255,.3);font-family:sans-serif;font-size:13px}
.c-input:focus{border-color:var(--ouro);background:rgba(255,255,255,.13)}
.c-btn{padding:14px 32px;background:var(--ouro);color:var(--roxo-escuro);border:none;border-radius:10px;font-size:15px;font-weight:800;cursor:pointer;transition:all .15s;white-space:nowrap;letter-spacing:.3px}
.c-btn:hover{background:var(--ouro-claro);transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,.2)}
.c-btn:disabled{opacity:.55;cursor:not-allowed;transform:none}
.c-dica{font-size:11px;color:rgba(255,255,255,.35);margin-top:7px}

/* RESULTADO DA CONSULTA */
.res-box{display:none;margin-top:14px;padding:16px 20px;border-radius:10px;animation:fadein .25s}
@keyframes fadein{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}
.res-ok{background:var(--verde-claro);border-left:4px solid var(--verde);color:#1a3a2a}
.res-erro{background:var(--vermelho-claro);border-left:4px solid var(--vermelho);color:var(--vermelho)}
.res-cnj{font-family:monospace;font-size:16px;font-weight:800;margin-bottom:8px}
.res-linha{font-size:13px;margin-bottom:3px;color:#222}
.res-acoes{margin-top:12px;display:flex;gap:8px;flex-wrap:wrap}
.btn-add{padding:8px 18px;background:var(--roxo-medio);color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;transition:background .15s}
.btn-add:hover{background:var(--roxo-escuro)}
.btn-reload{padding:8px 18px;background:#555;color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer}
.btn-reload:hover{background:#333}
.add-form{display:none;margin-top:12px;padding:14px;background:rgba(0,0,0,.06);border-radius:8px}
.add-form input{padding:8px 12px;border:1px solid var(--cinza-borda);border-radius:6px;font-size:13px;margin:0 6px 6px 0;width:100%}
.add-row{display:flex;gap:8px;margin-bottom:6px}
.add-form .add-row input{margin:0;flex:1}
.btn-conf{padding:8px 20px;background:var(--verde);color:#fff;border:none;border-radius:6px;font-size:13px;font-weight:700;cursor:pointer}
.add-msg{font-size:12px;margin-left:8px;font-weight:600}

/* ABA OAB */
.oab-info{font-size:12px;color:rgba(255,255,255,.5);margin-bottom:14px;line-height:1.6}
.oab-portais{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}
.btn-portal{padding:10px 18px;border-radius:9px;font-size:12px;font-weight:700;text-decoration:none;display:inline-flex;align-items:center;gap:5px;transition:all .15s;border:none;letter-spacing:.2px}
.btn-portal:hover{transform:translateY(-2px);box-shadow:0 4px 14px rgba(0,0,0,.3);filter:brightness(1.1)}
.btn-portal.tj{background:#1a5c8f;color:#fff}.btn-portal.trf{background:#7b2d8b;color:#fff}
.btn-portal.trt{background:#1a7a5c;color:#fff}.btn-portal.extra{background:#8b6a1a;color:#fff}
.oab-pasta{width:100%;min-height:110px;padding:12px 14px;border:2px solid rgba(255,255,255,.18);border-radius:10px;background:rgba(255,255,255,.08);color:#fff;font-size:12px;font-family:'Courier New',monospace;resize:vertical;outline:none;transition:border-color .2s}
.oab-pasta::placeholder{color:rgba(255,255,255,.28);font-family:sans-serif;font-size:11px;line-height:1.6}
.oab-pasta:focus{border-color:var(--ouro)}
.oab-chips{margin-top:12px;display:flex;flex-wrap:wrap;gap:7px;min-height:26px}
.cnj-chip{display:inline-flex;align-items:center;gap:4px;padding:4px 10px;background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.22);border-radius:20px;font-family:'Courier New',monospace;font-size:11px;color:#fff}
.cnj-chip button{background:none;border:none;color:rgba(255,255,255,.45);cursor:pointer;font-size:14px;line-height:1;padding:0 2px;transition:color .1s}
.cnj-chip button:hover{color:#ff6b6b}
.oab-vazio{font-size:12px;color:rgba(255,255,255,.3);font-style:italic;padding:3px 0}
.oab-form{margin-top:14px;padding:14px;background:rgba(255,255,255,.07);border-radius:9px;display:none}
.oab-form .add-row{margin-bottom:10px}
.oab-form input{flex:1;padding:8px 12px;border:1px solid rgba(255,255,255,.2);border-radius:6px;background:rgba(255,255,255,.1);color:#fff;font-size:13px;outline:none}
.oab-form input::placeholder{color:rgba(255,255,255,.32)}
.oab-form input:focus{border-color:var(--ouro)}
.btn-lote{padding:10px 24px;background:var(--verde);color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;transition:background .15s}
.btn-lote:hover{background:#0e6b45}.btn-lote:disabled{opacity:.5;cursor:not-allowed}
.oab-msg{font-size:12px;margin-left:10px;font-weight:600;vertical-align:middle}
.lote-result{margin-top:10px;font-size:12px;line-height:1.8;display:none}
.lote-ok{color:#1a8a5a}.lote-err{color:var(--vermelho)}

@media(max-width:600px){
  .header{padding:10px 16px;height:auto;min-height:56px;flex-wrap:wrap;gap:8px}
  .barra-busca,.consulta{padding-left:16px;padding-right:16px}
  .container{padding:16px 12px 40px}
  .kpi-valor{font-size:28px}
}
"""

# ------------------------------------------------------------------
# JS compartilhado: busca, filtros e expandir/recolher card
# ------------------------------------------------------------------

JS_FILTROS = r"""
var filtroAtivo = 'todos';

function aplicarFiltros() {
  var campo = document.getElementById('busca');
  var termo = ((campo && campo.value) || '').toLowerCase().trim();
  var cards = document.querySelectorAll('.processo-card');
  var visiveis = 0;
  cards.forEach(function(card) {
    var texto = (card.dataset.busca || '').toLowerCase();
    var urgencia = card.dataset.urgencia || 'ok';
    var temNovo = card.dataset.novo === 'true';
    var parado = card.dataset.parado === 'true';
    var passa = !termo || texto.indexOf(termo) !== -1;
    if (filtroAtivo === 'novo') passa = passa && temNovo;
    else if (filtroAtivo === 'urgente') passa = passa && urgencia === 'urgente';
    else if (filtroAtivo === 'alerta') passa = passa && urgencia === 'alerta';
    else if (filtroAtivo === 'parado') passa = passa && parado;
    card.style.display = passa ? '' : 'none';
    if (passa) visiveis++;
  });
  atualizarContador(visiveis);
  var sem = document.getElementById('sem-resultados');
  if (sem) sem.classList.toggle('visivel', visiveis === 0 && cards.length > 0);
}

function setFiltro(f) {
  filtroAtivo = f;
  document.querySelectorAll('.btn-filtro').forEach(function(btn) {
    btn.classList.toggle('ativo', btn.dataset.filtro === f);
  });
  aplicarFiltros();
}

function atualizarContador(n) {
  var el = document.getElementById('busca-count');
  if (el) el.textContent = n + ' processo(s)';
}

function toggleCard(slug) {
  var det = document.getElementById('det-' + slug);
  var seta = document.getElementById('seta-' + slug);
  if (!det) return;
  var aberto = det.classList.toggle('aberto');
  if (seta) seta.innerHTML = aberto ? '&#9650;' : '&#9660;';
}

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.btn-filtro').forEach(function(btn) {
    btn.addEventListener('click', function() { setFiltro(this.dataset.filtro); });
  });
  var campo = document.getElementById('busca');
  if (campo) campo.addEventListener('input', aplicarFiltros);
  atualizarContador(document.querySelectorAll('.processo-card').length);
});
"""

# ------------------------------------------------------------------
# Peças HTML
# ------------------------------------------------------------------


def _e(valor: Any) -> str:
    """Escapa qualquer valor como texto HTML seguro (None vira '')."""
    return escape("" if valor is None else str(valor), quote=True)


def rodape_html(extra: str = "") -> str:
    """Rodapé padrão com versão e autoria; ``extra`` já deve ser HTML seguro."""
    return (
        f"<footer><strong>MAAT Monitor v{__version__}</strong> &mdash; "
        f"&copy; 2026 M&aacute;rcio Luis Amorim &mdash; Dados via API DataJud/CNJ {extra}</footer>"
    )


def html_kpis(itens: list[tuple[str, int, str]]) -> str:
    """Grade de KPIs a partir de (rótulo, valor, classe css: '', 'ok', 'alerta', 'ouro', 'amarelo')."""
    partes = ['<div class="kpis">']
    for rotulo, valor, classe in itens:
        css = f"kpi {classe}".strip()
        partes.append(
            f'<div class="{css}"><div class="kpi-valor">{int(valor)}</div>'
            f'<div class="kpi-rotulo">{_e(rotulo)}</div></div>'
        )
    partes.append("</div>")
    return "".join(partes)


def contar_situacoes(processos: list[dict]) -> dict[str, int]:
    """Conta processos por situação: total, novo, urgente, alerta, parado."""
    return {
        "total": len(processos),
        "novo": sum(1 for p in processos if p.get("tem_novo")),
        "urgente": sum(1 for p in processos if p.get("urgencia") == "urgente"),
        "alerta": sum(1 for p in processos if p.get("urgencia") == "alerta"),
        "parado": sum(1 for p in processos if p.get("parado")),
    }


def html_barra_filtros(contagens: dict[str, int]) -> str:
    """Barra com campo de busca e botões de filtro (consumida por ``JS_FILTROS``)."""
    return f"""
<div class="barra-busca">
  <input id="busca" class="busca-input" type="text"
         placeholder="Buscar por apelido, CNJ, cliente, classe, &oacute;rg&atilde;o..." autocomplete="off">
  <span id="busca-count" class="busca-count"></span>
  <div class="filtros">
    <button type="button" class="btn-filtro ativo" data-filtro="todos">Todos ({contagens['total']})</button>
    <button type="button" class="btn-filtro f-novo" data-filtro="novo">&#11044; Novidade ({contagens['novo']})</button>
    <button type="button" class="btn-filtro f-urgente" data-filtro="urgente">&#9888; Urgente ({contagens['urgente']})</button>
    <button type="button" class="btn-filtro f-alerta" data-filtro="alerta">&#9650; Alerta ({contagens['alerta']})</button>
    <button type="button" class="btn-filtro f-parado" data-filtro="parado">&#9632; Parado ({contagens['parado']})</button>
  </div>
</div>"""


def _html_movimento(mov: tuple) -> str:
    """Um item da timeline: (data_hora, nome, complemento, novo)."""
    data_h, nome, comp, novo = (list(mov) + [None] * 4)[:4]
    nome = str(nome or "")
    comp = str(comp or "")
    data_h = str(data_h or "")
    nivel = analise.urgencia_movimento(nome)
    if novo:
        classe = "mov-item novo"
    elif nivel == "urgente":
        classe = "mov-item urgente"
    elif nivel == "alerta":
        classe = "mov-item alerta"
    else:
        classe = "mov-item"
    badge = '<span class="badge badge-novo badge-mini">NOVO</span> ' if novo else ""
    prazo_dt, prazo_dias = analise.calcular_prazo(nome, data_h)
    prazo_h = (
        f'<div class="mov-prazo">&#9201; Prazo estimado: {_e(prazo_dt)} ({int(prazo_dias or 0)} dias)</div>'
        if prazo_dt
        else ""
    )
    comp_h = f'<div class="mov-comp">{_e(comp)}</div>' if comp else ""
    return (
        f'<div class="{classe}"><div class="mov-data">{_e(analise.formatar_data_hora(data_h))}</div>'
        f'<div class="mov-nome">{badge}{_e(nome) or "&mdash;"}</div>{comp_h}{prazo_h}</div>'
    )


def _html_card(p: dict) -> str:
    """Card expansível de um processo (saída de ``banco.ler_processos``)."""
    urg = p.get("urgencia") or "ok"
    novo = bool(p.get("tem_novo"))
    par = bool(p.get("parado"))
    movs = list(p.get("movimentos") or [])
    cnj_bruto = str(p.get("cnj") or "")
    slug = re.sub(r"[^a-z0-9]", "_", cnj_bruto.lower())
    cnj_fmt = _e(p.get("cnj_fmt") or cnj.formatar(cnj_bruto))
    rotulo = _e(p.get("rotulo"))
    cliente = _e(p.get("cliente"))
    area = _e(p.get("area"))
    status = _e(p.get("status_processo") or "Ativo")
    tribunal = _e(p.get("tribunal") or "?")
    grau = _e(p.get("grau") or "?")

    if urg == "urgente":
        classe_card = "processo-card urgente"
    elif novo:
        classe_card = "processo-card tem-novo"
    elif urg == "alerta":
        classe_card = "processo-card alerta"
    elif par:
        classe_card = "processo-card parado"
    else:
        classe_card = "processo-card"

    badges = ""
    if urg == "urgente":
        badges += '<span class="badge badge-urgente">&#9888; URGENTE</span>'
    if urg == "alerta":
        badges += '<span class="badge badge-alerta">&#9650; ALERTA</span>'
    if novo:
        badges += '<span class="badge badge-novo">&#11044; NOVO</span>'
    if par:
        badges += f'<span class="badge badge-parado">Parado {int(p.get("dias_sem") or 0)}d</span>'
    if area:
        badges += f'<span class="badge badge-area">{area}</span>'
    badges += f'<span class="badge badge-tribunal">{tribunal}</span>'
    badges += f'<span class="badge badge-grau">{grau}</span>'

    cliente_h = f'<div class="cliente-processo">&#128100; {cliente}</div>' if cliente else ""
    cnj_h = f'<div class="cnj-numero">{cnj_fmt}</div>' if rotulo else ""
    prazo_txt = p.get("prazo_txt") or ""
    prazo_h = f'<div class="prazo-box">&#9201; {_e(prazo_txt)}</div>' if prazo_txt else ""

    busca = " ".join(
        str(x)
        for x in (
            p.get("rotulo"), p.get("cnj_fmt"), cnj_bruto, p.get("classe"), p.get("assunto"),
            p.get("orgao_julgador"), p.get("tribunal"), p.get("grau"), p.get("cliente"), p.get("area"),
        )
        if x
    ).lower()

    movs_h = "".join(_html_movimento(m) for m in movs)
    total_movs = int(p.get("total_movimentos") or 0) or len(movs)

    return f"""
<div class="{classe_card}" data-busca="{_e(busca)}" data-urgencia="{_e(urg)}" data-novo="{'true' if novo else 'false'}" data-parado="{'true' if par else 'false'}">
  <div class="card-cabecalho" onclick="toggleCard('{slug}')">
    <div class="card-titulo">
      <div class="rotulo-processo">{_e(p.get("rotulo_exibir")) or cnj_fmt}</div>
      {cliente_h}{cnj_h}
    </div>
    <div class="badges">{badges}<span class="seta-card" id="seta-{slug}">&#9660;</span></div>
  </div>
  <div class="card-detalhes" id="det-{slug}">
    {prazo_h}
    <div class="info-grid">
      <div class="info-item"><div class="info-label">Classe</div><div class="info-valor">{_e(p.get("classe")) or "&mdash;"}</div></div>
      <div class="info-item"><div class="info-label">Assunto</div><div class="info-valor">{_e(p.get("assunto")) or "&mdash;"}</div></div>
      <div class="info-item"><div class="info-label">&Oacute;rg&atilde;o Julgador</div><div class="info-valor">{_e(p.get("orgao_julgador")) or "&mdash;"}</div></div>
      <div class="info-item"><div class="info-label">Grau</div><div class="info-valor">{grau}</div></div>
      <div class="info-item"><div class="info-label">Ajuizamento</div><div class="info-valor">{_e(p.get("data_aj_fmt") or "—")}</div></div>
      <div class="info-item"><div class="info-label">&Uacute;ltima Atualiza&ccedil;&atilde;o</div><div class="info-valor">{_e(p.get("data_at_fmt") or "—")}</div></div>
      <div class="info-item"><div class="info-label">Valor da Causa</div><div class="info-valor destaque">{_e(p.get("valor_fmt") or "—")}</div></div>
      <div class="info-item"><div class="info-label">Movimentos</div><div class="info-valor">{total_movs}</div></div>
      <div class="info-item"><div class="info-label">Cliente</div><div class="info-valor">{cliente or "&mdash;"}</div></div>
      <div class="info-item"><div class="info-label">&Aacute;rea / Status</div><div class="info-valor">{area or "&mdash;"} &middot; {status}</div></div>
      <div class="info-item"><div class="info-label">&Uacute;lt. verifica&ccedil;&atilde;o MAAT</div><div class="info-valor">{_e(p.get("check_fmt") or "—")}</div></div>
    </div>
    <div class="movimentos-secao">
      <div class="movimentos-titulo">Andamentos <span class="mov-count">{len(movs)}</span></div>
      <div class="timeline">{movs_h}</div>
    </div>
  </div>
</div>"""


def html_cards(processos: list[dict]) -> str:
    """Cards de todos os processos; lista vazia devolve uma mensagem amigável."""
    if not processos:
        return (
            '<p class="lista-vazia">Nenhum processo consultado ainda.<br>'
            "Use o campo de consulta ou cadastre n&uacute;meros CNJ em <code>processos.txt</code> "
            "e execute o monitoramento.</p>"
        )
    return "".join(_html_card(p) for p in processos)


def html_historico(hist: list[dict]) -> str:
    """Tabela de execuções (saída de ``banco.ler_historico``); vazio devolve ''."""
    if not hist:
        return ""
    linhas = []
    for ex in hist:
        erros = int(ex.get("erros") or 0)
        novos = int(ex.get("novos") or 0)
        erros_h = f'<span class="hist-col-erro">{erros}</span>' if erros else "0"
        novos_h = f'<span class="hist-col-novo">&#11044; {novos}</span>' if novos else "&mdash;"
        linhas.append(
            f"<tr><td>{_e(ex.get('data'))}</td><td>{int(ex.get('total') or 0)}</td>"
            f'<td class="hist-col-ok">{int(ex.get("sucesso") or 0)}</td>'
            f"<td>{erros_h}</td><td>{novos_h}</td></tr>"
        )
    return f"""
<div class="historico-secao">
  <div class="historico-titulo">Hist&oacute;rico de Execu&ccedil;&otilde;es</div>
  <table class="hist-table">
    <thead><tr><th>Data/Hora</th><th>Processos</th><th>Sucesso</th><th>Erros</th><th>Novos Andamentos</th></tr></thead>
    <tbody>{"".join(linhas)}</tbody>
  </table>
</div>"""


def html_cabecalho(subtitulo: str, config: dict, agora_fmt: str) -> str:
    """Cabeçalho roxo/ouro com nome e OAB do advogado (escapados)."""
    return f"""
<header class="header">
  <div class="header-logo">
    <div>
      <div class="titulo">MAAT</div>
      <div class="subtitulo">{_e(subtitulo)}</div>
    </div>
  </div>
  <div class="header-meta">
    <strong>{_e(config.get("nome"))}</strong><br>
    OAB {_e(config.get("oab_numero"))}/{_e(config.get("oab_uf"))} &middot; {_e(agora_fmt)}
  </div>
</header>"""


# ------------------------------------------------------------------
# Relatório HTML
# ------------------------------------------------------------------


def gerar_relatorio_html(
    conn: sqlite3.Connection,
    config: dict,
    caminhos: Caminhos,
    estatisticas: dict,
    apenas_cnj: str | None = None,
) -> Path:
    """Grava relatorios/relatorio_<ts>.html e devolve o caminho. ``apenas_cnj`` restringe a um processo."""
    caminhos.relatorios.mkdir(parents=True, exist_ok=True)
    agora = datetime.now()
    arquivo = caminhos.relatorios / f"relatorio_{agora.strftime('%Y-%m-%d_%H-%M-%S')}.html"
    agora_fmt = agora.strftime("%d/%m/%Y %H:%M")

    processos = banco.ler_processos(conn, int(config.get("dias_alerta_parado", 30)), apenas_cnj=apenas_cnj)
    cont = contar_situacoes(processos)
    erros = int(estatisticas.get("erros") or 0)
    novos = int(estatisticas.get("novos_andamentos") or 0)
    kpis = html_kpis([
        ("Processos", int(estatisticas.get("total") or 0), ""),
        ("Atualizados", int(estatisticas.get("sucesso") or 0), "ok"),
        ("Erros", erros, "alerta" if erros else "ok"),
        ("Novos andamentos", novos, "ouro" if novos else "ok"),
        ("Urgentes", cont["urgente"], "alerta" if cont["urgente"] else "ok"),
        ("Parados", cont["parado"], "amarelo" if cont["parado"] else "ok"),
    ])
    historico = html_historico(banco.ler_historico(conn)) if apenas_cnj is None else ""
    subtitulo = "Consulta avulsa" if apenas_cnj else "Relatório de monitoramento"

    pagina = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MAAT &mdash; Relat&oacute;rio {_e(agora_fmt)}</title>
<style>{CSS}</style>
</head>
<body>
{html_cabecalho(subtitulo, config, agora_fmt)}
{html_barra_filtros(cont)}
<div class="container">
{kpis}
<div id="sem-resultados" class="sem-resultados">Nenhum processo encontrado para esse filtro / busca.</div>
<div id="lista">{html_cards(processos)}</div>
{historico}
</div>
{rodape_html(f"&mdash; Gerado em {_e(agora_fmt)}")}
<script>{JS_FILTROS}</script>
</body>
</html>"""

    arquivo.write_text(pagina, encoding="utf-8")
    return arquivo


# ------------------------------------------------------------------
# CSV
# ------------------------------------------------------------------


def celula_csv(valor: Any) -> Any:
    """Neutraliza fórmulas (=, +, -, @ e controles) para a planilha não executar texto vindo de fora."""
    if isinstance(valor, str) and (
        valor.startswith(("\t", "\r", "\n")) or valor.lstrip().startswith(("=", "+", "-", "@"))
    ):
        return "'" + valor
    return valor


def gerar_csv(conn: sqlite3.Connection, caminhos: Caminhos) -> tuple[Path, Path]:
    """Exporta processos_<ts>.csv e movimentos_<ts>.csv (separador ';', UTF-8 com BOM para o Excel)."""
    caminhos.relatorios.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    arq_proc = caminhos.relatorios / f"processos_{ts}.csv"
    cur = conn.execute(
        """
        SELECT cnj, rotulo, cliente, area, status_processo,
               tribunal, classe, assunto, orgao_julgador, grau,
               valor_causa, data_ajuizamento, data_ultima_atualizacao,
               total_movimentos, ultimo_check
        FROM processos ORDER BY ultimo_check DESC
        """
    )
    with open(arq_proc, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([
            "CNJ", "Apelido", "Cliente", "Área", "Status",
            "Tribunal", "Classe", "Assunto", "Órgão Julgador",
            "Grau", "Valor da Causa", "Ajuizamento", "Últ. Atualização",
            "Total Movimentos", "Últ. verificação MAAT",
        ])
        for r in cur.fetchall():
            w.writerow([celula_csv(v) for v in [cnj.formatar(r[0])] + list(r[1:])])

    arq_mov = caminhos.relatorios / f"movimentos_{ts}.csv"
    cur = conn.execute(
        """
        SELECT cnj, data_hora, codigo, nome, complemento, novo
        FROM movimentos ORDER BY julianday(data_hora) DESC, id DESC
        """
    )
    with open(arq_mov, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["CNJ", "Data/Hora", "Código", "Nome", "Complemento", "Novo"])
        for r in cur.fetchall():
            w.writerow([celula_csv(v) for v in [cnj.formatar(r[0])] + list(r[1:5])] + ["SIM" if r[5] else ""])

    return arq_proc, arq_mov
