"""
Cliente HTTP da API pública DataJud/CNJ.

Consulta um processo pelo número CNJ no índice do tribunal correspondente.
Nunca lança: devolve sempre um ``Resultado`` com mensagem de erro em português.
A validação de certificado SSL é sempre mantida ativa.

Copyright (c) 2026 Márcio Luis Amorim — Licença MIT
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from themis import __version__, cnj, constantes

try:  # certificados do sistema operacional (evita erros de SSL no Windows)
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover - truststore é dependência opcional em tempo de execução
    pass

log = logging.getLogger("themis.datajud")

USER_AGENT = f"THEMIS-Monitor/{__version__} (+https://github.com/Dramorimrodrigues/themis-monitor)"

# CNJ público conhecido do TJ-SP, usado apenas para testar a conexão.
CNJ_TESTE_CONEXAO = "00010540420108260100"
TRIBUNAL_TESTE_CONEXAO = "tjsp"

MSG_NAO_ENCONTRADO = (
    "Processo não encontrado no DataJud (pode estar em segredo de justiça, "
    "ser muito antigo ou ainda não ter sido enviado pelo tribunal)."
)
MSG_SSL = "Erro de certificado SSL ao conectar ao DataJud. Atualize o Python/certifi ou verifique proxy/antivírus."
MSG_TIMEOUT = "O DataJud demorou demais para responder (timeout). Tente novamente."
MSG_CONEXAO = "Falha de conexão com o DataJud. Verifique sua internet."
MSG_INVALIDA = "Resposta do DataJud inválida ou incompleta."
MSG_DIVERGENTE = "Resposta do DataJud com número de processo divergente."

_sessao = requests.Session()
_sessao.headers.update({"User-Agent": USER_AGENT})


@dataclass(frozen=True)
class Resultado:
    """Resultado de uma consulta: ``ok`` com ``fonte`` (o ``_source``) ou ``erro`` em português."""

    ok: bool
    fonte: dict | None = None
    erro: str | None = None


def _erro(mensagem: str) -> Resultado:
    log.info(mensagem)
    return Resultado(False, erro=mensagem)


def _dica_http(status: int | None) -> str:
    if status == 429:
        return "Muitas consultas — aguarde alguns minutos."
    if status is not None and 500 <= status <= 599:
        return "Serviço instável — tente mais tarde."
    return "Verifique o número do processo e tente novamente."


def _extrair_fonte(corpo: object, cnj_limpo: str) -> Resultado:
    """Valida a estrutura do JSON do DataJud e extrai o ``_source`` do primeiro hit."""
    if not isinstance(corpo, dict) or not isinstance(corpo.get("hits"), dict):
        return _erro(MSG_INVALIDA)
    hits = corpo["hits"].get("hits")
    if not isinstance(hits, list):
        return _erro(MSG_INVALIDA)
    if not hits:
        return _erro(MSG_NAO_ENCONTRADO)
    primeiro = hits[0]
    if not isinstance(primeiro, dict):
        return _erro(MSG_INVALIDA)
    fonte = primeiro.get("_source")
    if not isinstance(fonte, dict) or not fonte:
        return _erro(MSG_INVALIDA)
    if cnj.limpar(str(fonte.get("numeroProcesso") or "")) != cnj_limpo:
        return _erro(MSG_DIVERGENTE)
    return Resultado(True, fonte=fonte)


def consultar(cnj_limpo: str, tribunal: str, timeout: float = 30) -> Resultado:
    """Consulta o processo ``cnj_limpo`` (20 dígitos) no índice do ``tribunal`` (chave de TRIBUNAIS)."""
    info = constantes.TRIBUNAIS.get(tribunal)
    if not info:
        return _erro(f"Tribunal '{tribunal}' não é suportado pelo DataJud.")

    url = f"{constantes.DATAJUD_BASE_URL}/{info['alias']}/_search"
    headers = {
        "Authorization": f"APIKey {constantes.DATAJUD_API_KEY_PUBLICA}",
        "Content-Type": "application/json",
    }
    payload = {"query": {"match": {"numeroProcesso": cnj_limpo}}, "size": 1}

    try:
        resposta = _sessao.post(url, headers=headers, json=payload, timeout=timeout)
        resposta.raise_for_status()
        corpo = resposta.json()
    except requests.exceptions.SSLError:
        return _erro(MSG_SSL)
    except requests.exceptions.Timeout:
        return _erro(MSG_TIMEOUT)
    except requests.exceptions.HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        return _erro(f"DataJud respondeu HTTP {status}. {_dica_http(status)}")
    except requests.exceptions.RequestException as exc:
        log.debug("Falha de rede ao consultar o DataJud: %s", type(exc).__name__)
        return _erro(MSG_CONEXAO)
    except ValueError:  # JSON inválido (inclui json.JSONDecodeError)
        return _erro(MSG_INVALIDA)

    return _extrair_fonte(corpo, cnj_limpo)


def testar_conexao() -> Resultado:
    """Testa a conexão com o DataJud; "não encontrado" também conta como conexão OK."""
    resultado = consultar(CNJ_TESTE_CONEXAO, TRIBUNAL_TESTE_CONEXAO)
    if resultado.ok or (resultado.erro and "não encontrado" in resultado.erro):
        return Resultado(True)
    return resultado
