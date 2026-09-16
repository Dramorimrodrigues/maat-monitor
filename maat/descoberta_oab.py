"""
Guia de descoberta de processos por OAB do MAAT Monitor.

Gera um arquivo HTML local com links para os portais dos tribunais (com a OAB
pré-preenchida quando o portal aceita), instruções passo a passo e um campo para
colar o texto copiado dos portais: o próprio navegador extrai os números CNJ e
monta as linhas prontas para o processos.txt. Nenhuma automação de CAPTCHA.

Copyright (c) 2026 Márcio Luis Amorim — Licença MIT
"""

from __future__ import annotations

import webbrowser
from datetime import datetime
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from maat import __version__

if TYPE_CHECKING:  # pragma: no cover
    from maat.config import Caminhos

NOME_ARQUIVO = "buscar-oab-guia.html"

# CSS e JavaScript são constantes (sem dados do usuário), separados do f-string
# para evitar escapes de chaves. O JS não usa alert(): mensagens ficam inline.
_ESTILO = """
* { box-sizing: border-box; }
body { font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
       background: #f4f0fa; color: #1a0832; margin: 0; padding: 20px; }
.container { max-width: 900px; margin: 0 auto; }
h1 { color: #3d1a6e; border-bottom: 3px solid #c9a440; padding-bottom: 10px; margin-top: 0; }
.cabecalho { background: white; padding: 20px; border-radius: 12px;
             box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; }
.passos { background: #fffbeb; border-left: 4px solid #c9a440; padding: 15px 20px;
          border-radius: 8px; margin: 15px 0; }
.passos ol { margin: 10px 0; padding-left: 25px; }
.passos li { margin: 8px 0; }
.portal { background: white; padding: 20px; border-radius: 12px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 15px; }
.portal h3 { margin-top: 0; }
.btn { display: inline-block; padding: 10px 20px; background: #3d1a6e;
       color: white; text-decoration: none; border-radius: 6px; font-weight: 600;
       margin: 5px 5px 5px 0; }
.btn:hover { opacity: 0.9; }
.btn.fallback { background: #718096; }
.instrucao { background: #f7fafc; padding: 12px; border-radius: 6px;
             margin: 10px 0; font-size: 14px; color: #4a5568; }
.colar-area { background: white; padding: 25px; border-radius: 12px;
              box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-top: 20px; }
textarea { width: 100%; min-height: 200px; font-family: 'Courier New', monospace;
           font-size: 14px; padding: 12px; border: 1px solid #cbd5e0;
           border-radius: 6px; resize: vertical; }
.botoes { margin-top: 15px; }
button { padding: 10px 20px; background: #3d1a6e; color: white; border: none;
         border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 14px;
         margin-right: 8px; }
button:hover { background: #2a1050; }
button.secundario { background: #718096; }
.saida { background: #1a202c; color: #e2e8f0; padding: 15px;
         border-radius: 6px; margin-top: 15px; font-family: 'Courier New', monospace;
         font-size: 13px; max-height: 300px; overflow-y: auto; white-space: pre-wrap;
         display: none; }
.saida.visivel { display: block; }
.contador { display: inline-block; margin-left: 10px; font-weight: 600; color: #3d1a6e; }
.mensagem { margin-top: 12px; padding: 10px 14px; border-radius: 6px; font-size: 14px;
            display: none; }
.mensagem.visivel { display: block; }
.mensagem.ok { background: #e6f7ef; color: #1a8a5a; border-left: 4px solid #1a8a5a; }
.mensagem.erro { background: #fdecea; color: #c0392b; border-left: 4px solid #c0392b; }
.rodape { text-align: center; font-size: 12px; color: #888; margin: 30px 0 10px; }
"""

_SCRIPT = r"""
function mostrarMensagem(texto, tipo) {
  var el = document.getElementById('mensagem');
  el.textContent = texto;
  el.className = 'mensagem visivel ' + tipo;
}
function limparEGerar() {
  var texto = document.getElementById('colado').value;
  // Regex CNJ: 7-2.4.1.2.4 (com ou sem pontuação)
  var regex = /(?:^|[^0-9])(\d{7}[.\-]?\d{2}[.\-]?\d{4}[.\-]?\d[.\-]?\d{2}[.\-]?\d{4})(?![0-9])/g;
  var matches = [];
  var match;
  while ((match = regex.exec(texto)) !== null) matches.push(match[1]);
  var unicos = {};
  var lista = [];
  for (var i = 0; i < matches.length; i++) {
    var n = matches[i].replace(/[^0-9]/g, '');
    if (n.length === 20 && !unicos[n]) {
      unicos[n] = true;
      var fmt = n.substr(0,7)+'-'+n.substr(7,2)+'.'+n.substr(9,4)+'.'+n.substr(13,1)+'.'+n.substr(14,2)+'.'+n.substr(16,4);
      lista.push(fmt);
    }
  }
  var saida = document.getElementById('saida');
  saida.classList.add('visivel');
  document.getElementById('contador').textContent = lista.length + ' processo(s) encontrado(s)';
  if (lista.length === 0) {
    saida.textContent = 'Nenhum número CNJ válido encontrado no texto colado.\n\nVerifique se você copiou os números completos dos portais.';
    mostrarMensagem('Nenhum número CNJ encontrado. Cole o texto copiado dos portais e tente de novo.', 'erro');
  } else {
    saida.textContent = '# Cole as linhas abaixo no arquivo processos.txt:\n\n' + lista.join('\n');
    mostrarMensagem(lista.length + ' processo(s) prontos. Clique em "Copiar resultado" e cole no processos.txt.', 'ok');
  }
}
function copiar() {
  var saida = document.getElementById('saida');
  if (!saida.textContent || saida.textContent.indexOf('# Cole as linhas') !== 0) {
    mostrarMensagem('Gere uma lista de processos antes de copiar.', 'erro');
    return;
  }
  var falha = function() {
    mostrarMensagem('Não foi possível copiar automaticamente. Selecione o resultado e copie com Ctrl+C.', 'erro');
  };
  if (!navigator.clipboard || !navigator.clipboard.writeText) {
    falha();
    return;
  }
  navigator.clipboard.writeText(saida.textContent).then(function() {
    mostrarMensagem('Lista copiada! Cole no arquivo processos.txt.', 'ok');
  }).catch(falha);
}
"""


def _portais(oab_numero: str, oab_uf: str) -> list[dict]:
    """Portais de consulta por OAB. As cores são constantes; os textos passam por escape no HTML."""
    consulta_tjrj = urlencode({
        "numProcesso": "", "tipoPesquisa": "advogado", "numeroOAB": oab_numero,
        "letraOAB": "", "estadoOAB": oab_uf,
    })
    oab_txt = f"{oab_numero}/{oab_uf}"
    return [
        {
            "nome": "TJRJ — Tribunal de Justiça do Rio de Janeiro",
            "url": f"http://www4.tjrj.jus.br/numeracaoUnica/faces/index.jsp?{consulta_tjrj}",
            "url_fallback": "http://www4.tjrj.jus.br/consultaProcessoWebV2/",
            "instrucao": (
                "Clique em 'Consultar Processo'. Selecione 'Consulta Avançada' > 'Por OAB'. "
                f"Digite {oab_txt}. Resolva o CAPTCHA. Copie os números CNJ da lista."
            ),
            "cor": "#2c5282",
        },
        {
            "nome": "TRF2 — Tribunal Regional Federal da 2ª Região",
            "url": "https://eproc.trf2.jus.br/eproc/externo_controlador.php?acao=processo_consulta_publica_oab",
            "url_fallback": "https://www10.trf2.jus.br/portal/consulta-processual/",
            "instrucao": (
                f"No campo 'Número da OAB' digite {oab_numero}, selecione UF {oab_uf}, "
                "resolva o CAPTCHA e clique em Pesquisar."
            ),
            "cor": "#2f855a",
        },
        {
            "nome": "TRT1 — Tribunal Regional do Trabalho da 1ª Região",
            "url": "https://pje.trt1.jus.br/consultaprocessual/pages/consultas/ConsultaProcessual.seam",
            "url_fallback": "https://pje.trt1.jus.br/consultaprocessual/",
            "instrucao": (
                f"Selecione a aba 'Por OAB'. Digite {oab_numero}, UF {oab_uf}. "
                "Resolva o CAPTCHA. Os processos aparecerão listados."
            ),
            "cor": "#c05621",
        },
        {
            "nome": "TJSP — Tribunal de Justiça de São Paulo (e-SAJ)",
            "url": "https://esaj.tjsp.jus.br/cpopg/open.do",
            "url_fallback": "https://esaj.tjsp.jus.br/",
            "instrucao": (
                "Em 'Consultar por', escolha 'OAB'. "
                f"Digite {oab_numero}{oab_uf} (número seguido da UF, sem barra). "
                "Resolva o CAPTCHA e clique em Consultar. Copie os números da lista."
            ),
            "cor": "#6b46c1",
        },
        {
            "nome": "Outros tribunais (PJe, e-SAJ, Eproc, Projudi)",
            "url": "https://www.cnj.jus.br/poder-judiciario/tribunais/",
            "url_fallback": "https://www.cnj.jus.br/",
            "instrucao": (
                "Abra o portal do tribunal desejado, procure a 'Consulta pública' ou 'Consulta processual' "
                f"e a opção 'Por OAB' ou 'Por advogado'. Digite {oab_txt}, resolva o CAPTCHA e copie os números."
            ),
            "cor": "#718096",
        },
    ]


def gerar_guia(config: dict, caminhos: Caminhos) -> Path:
    """Grava o guia HTML em ``caminhos.base / NOME_ARQUIVO`` e devolve o caminho."""
    oab_numero = str(config.get("oab_numero") or "").strip()
    oab_uf = str(config.get("oab_uf") or "").strip().upper()
    nome = str(config.get("nome") or "").strip()
    arquivo = caminhos.base / NOME_ARQUIVO
    gerado_em = datetime.now().strftime("%d/%m/%Y às %H:%M")

    partes = [
        f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MAAT — Descoberta de Processos por OAB {escape(oab_numero)}/{escape(oab_uf)}</title>
<style>{_ESTILO}</style>
</head>
<body>
<div class="container">

<div class="cabecalho">
<h1>Descoberta de Processos por OAB</h1>
<p><b>Advogado(a):</b> {escape(nome)} &middot;
<b>OAB:</b> {escape(oab_numero)}/{escape(oab_uf)} &middot;
<b>Gerado em:</b> {escape(gerado_em)}</p>
</div>

<div class="passos">
<b>Como usar este guia:</b>
<ol>
<li>Clique em cada botão roxo abaixo — ele abre o portal do tribunal em nova aba</li>
<li>Em cada portal, resolva o CAPTCHA (são uns 30 segundos por portal)</li>
<li>Quando aparecer a lista dos seus processos, <b>selecione todos os números</b> e copie (Ctrl+C)</li>
<li>Volte para esta página e cole tudo no campo grande no final (Ctrl+V)</li>
<li>Repita para cada tribunal em que você atua</li>
<li>Clique em "Limpar e gerar lista" — ele formata os números e mostra como deve ficar o processos.txt</li>
<li>Copie o resultado final e cole no arquivo <code>processos.txt</code> (ou use o painel do MAAT)</li>
</ol>
</div>
"""
    ]

    for p in _portais(oab_numero, oab_uf):
        partes.append(f"""
<div class="portal" style="border-left: 4px solid {p['cor']};">
<h3 style="color: {p['cor']};">{escape(p['nome'])}</h3>
<a href="{escape(p['url'], quote=True)}" target="_blank" rel="noopener" class="btn" style="background: {p['cor']};">
Abrir portal</a>
<a href="{escape(p['url_fallback'], quote=True)}" target="_blank" rel="noopener" class="btn fallback">
Página principal (caso o link acima não funcione)</a>
<div class="instrucao">{escape(p['instrucao'])}</div>
</div>
""")

    partes.append(f"""
<div class="colar-area">
<h2>Cole aqui os números que você coletou</h2>
<p>Cole o texto bruto copiado dos portais. O guia extrai os números CNJ
automaticamente. <span class="contador" id="contador"></span></p>
<textarea id="colado" placeholder="Cole aqui o texto copiado dos portais dos tribunais..."></textarea>
<div class="botoes">
<button type="button" onclick="limparEGerar()">Limpar e gerar lista para processos.txt</button>
<button type="button" onclick="copiar()" class="secundario">Copiar resultado</button>
</div>
<div id="mensagem" class="mensagem" role="status"></div>
<div id="saida" class="saida"></div>
</div>

<p class="rodape">MAAT Monitor v{escape(__version__)} — © 2026 Márcio Luis Amorim</p>
</div>
<script>{_SCRIPT}</script>
</body>
</html>
""")

    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text("".join(partes), encoding="utf-8")
    return arquivo


def executar(config: dict, caminhos: Caminhos, abrir_navegador: bool = True) -> int:
    """Imprime instruções, gera o guia e (opcionalmente) abre no navegador. Devolve o código de saída."""
    oab_numero = str(config.get("oab_numero") or "").strip()
    oab_uf = str(config.get("oab_uf") or "").strip().upper()

    print()
    print("  Descoberta de Processos por OAB")
    print()
    if not oab_numero or oab_numero == "000000":
        print("  AVISO: OAB não configurada em config.ini (campo oab_numero).")
        print("         O guia será gerado, mas os portais não virão pré-preenchidos.")
    else:
        print(f"  OAB: {oab_numero}/{oab_uf}")
    print()
    print("  Gerando guia interativo de descoberta...")

    arquivo = gerar_guia(config, caminhos)
    print(f"  Guia gerado: {arquivo}")
    print()

    if abrir_navegador:
        print("  Abrindo o guia no seu navegador padrão...")
        webbrowser.open(arquivo.as_uri())
    else:
        print("  Abra o arquivo acima no seu navegador.")

    print()
    print("=" * 60)
    print("  PRÓXIMOS PASSOS")
    print("=" * 60)
    print("  1. Siga o guia no navegador e resolva o CAPTCHA de cada portal")
    print("  2. Cole os CNJs encontrados no arquivo processos.txt (ou no painel)")
    print("  3. Execute monitorar.bat (Windows) ou ./maat.sh monitorar (Mac/Linux)")
    print("=" * 60)
    print()
    return 0
