"""Testes do módulo analise — THEMIS Monitor. Copyright (c) 2026 Márcio Luis Amorim — MIT."""

from datetime import datetime, timedelta

from themis import analise


def test_normalizar_remove_acentos_e_baixa_caixa():
    assert analise.normalizar("Intimação Ação Ordinária") == "intimacao acao ordinaria"
    assert analise.normalizar(None) == ""


def test_urgencia_movimento():
    assert analise.urgencia_movimento("Penhora") == "urgente"
    assert analise.urgencia_movimento("Intimação") == "alerta"
    assert analise.urgencia_movimento("Juntada de petição") == "ok"
    assert analise.urgencia_movimento("Conclusão", "para análise de liminar") == "urgente"


def test_detectar_urgencia_penhora_e_urgente():
    movs = [("2026-01-10T10:00:00", "Penhora", "", 1)]
    assert analise.detectar_urgencia(movs) == "urgente"


def test_detectar_urgencia_intimacao_e_alerta():
    movs = [("2026-01-10T10:00:00", "Intimação", "", 1)]
    assert analise.detectar_urgencia(movs) == "alerta"


def test_detectar_urgencia_lista_vazia_e_ok():
    assert analise.detectar_urgencia([]) == "ok"


def test_detectar_urgencia_urgente_vence_alerta():
    movs = [
        ("2026-01-12T10:00:00", "Intimação", "", 1),
        ("2026-01-10T10:00:00", "Bloqueio Judicial", "via Sisbajud", 0),
    ]
    assert analise.detectar_urgencia(movs) == "urgente"


def test_detectar_urgencia_so_analisa_dez_mais_recentes():
    movs = [("2026-01-01T00:00:00", "Juntada", "", 0)] * 10
    movs.append(("2025-01-01T00:00:00", "Penhora", "", 0))
    assert analise.detectar_urgencia(movs) == "ok"


def test_calcular_prazo_intimacao():
    assert analise.calcular_prazo("Intimação", "2026-01-10T10:00:00") == ("25/01/2026", 15)


def test_calcular_prazo_sem_prazo():
    assert analise.calcular_prazo("Juntada de documento", "2026-01-10T10:00:00") == (None, None)


def test_calcular_prazo_data_invalida():
    assert analise.calcular_prazo("Intimação", "lixo") == (None, None)
    assert analise.calcular_prazo("Intimação", "") == (None, None)


def test_dias_desde():
    assert analise.dias_desde("lixo") == 9999
    assert analise.dias_desde("") == 9999
    assert analise.dias_desde(None) == 9999
    ontem = (datetime.now() - timedelta(days=3)).isoformat()
    assert analise.dias_desde(ontem) == 3


def test_formatar_data():
    assert analise.formatar_data("") == "—"
    assert analise.formatar_data(None) == "—"
    assert analise.formatar_data("2026-01-10T10:30:00.000Z") == "10/01/2026"
    assert analise.formatar_data("2026-01-10") == "10/01/2026"


def test_formatar_data_hora():
    assert analise.formatar_data_hora("") == "—"
    assert analise.formatar_data_hora("2026-01-10T10:30:00") == "10/01/2026 10:30"
    assert analise.formatar_data_hora("data-estranha-sem-formato") == "data-estranha-se"


def test_formatar_valor():
    assert analise.formatar_valor(1234.5) == "R$ 1.234,50"
    assert analise.formatar_valor("1000000") == "R$ 1.000.000,00"
    assert analise.formatar_valor("") == "—"
    assert analise.formatar_valor(None) == "—"
    assert analise.formatar_valor("abc") == "abc"
