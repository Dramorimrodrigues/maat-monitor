"""Testes do módulo cnj — THEMIS Monitor. Copyright (c) 2026 Márcio Luis Amorim — MIT."""

import pytest

from themis import cnj
from themis.constantes import TRIBUNAIS

# Números reais de exemplo (públicos, usados apenas para validar o dígito verificador)
CNJ_VALIDO_1 = "08292298220248190209"  # 0829229-82.2024.8.19.0209 (TJRJ)
CNJ_VALIDO_2 = "08000867020258190255"  # 0800086-70.2025.8.19.0255 (TJRJ)


def test_limpar_remove_tudo_que_nao_e_digito():
    assert cnj.limpar("0829229-82.2024.8.19.0209") == CNJ_VALIDO_1
    assert cnj.limpar(" 0829229 82 2024 8 19 0209 ") == CNJ_VALIDO_1
    assert cnj.limpar("") == ""


def test_formatar_20_digitos():
    assert cnj.formatar(CNJ_VALIDO_1) == "0829229-82.2024.8.19.0209"


def test_formatar_devolve_original_se_tamanho_errado():
    assert cnj.formatar("123") == "123"


@pytest.mark.parametrize("numero", [CNJ_VALIDO_1, CNJ_VALIDO_2])
def test_digito_verificador_valido(numero):
    assert cnj.validar_digito(numero) is True


def test_digito_verificador_invalido():
    assert cnj.validar_digito("08292298320248190209") is False  # DD trocado 82 -> 83
    assert cnj.validar_digito("123") is False


@pytest.mark.parametrize(
    "numero, esperado",
    [
        ("0000000000000100" + "0000", "stf"),  # J=1
        ("0000000000000300" + "0000", "stj"),  # J=3
        ("0000000000000402" + "0000", "trf2"),  # J=4 TR=02
        ("0000000000000500" + "0000", "tst"),  # J=5 TR=00
        ("0000000000000501" + "0000", "trt1"),  # J=5 TR=01
        ("0000000000000524" + "0000", "trt24"),  # J=5 TR=24
        ("0000000000000619" + "0000", "tre-rj"),  # J=6 TR=19
        ("0000000000000700" + "0000", "stm"),  # J=7 TR=00
        ("0000000000000819" + "0000", "tjrj"),  # J=8 TR=19
        ("0000000000000826" + "0000", "tjsp"),  # J=8 TR=26
        ("0000000000000926" + "0000", "tjmsp"),  # J=9 TR=26
        ("0000000000000813" + "0000", "tjmg"),  # J=8 TR=13
    ],
)
def test_identificar_tribunal(numero, esperado):
    assert cnj.identificar_tribunal(numero) == esperado


def test_identificar_tribunal_desconhecido():
    assert cnj.identificar_tribunal("0000000000000299" + "0000") is None  # J=2 não existe
    assert cnj.identificar_tribunal("123") is None


def test_todo_tribunal_identificado_esta_no_catalogo():
    """Cada código que identificar_tribunal pode devolver precisa ter alias no DataJud."""
    for j, trs in {"4": range(1, 7), "5": range(1, 25), "8": range(1, 28)}.items():
        for tr in trs:
            numero = f"0000000000000{j}{tr:02d}0000"
            codigo = cnj.identificar_tribunal(numero)
            assert codigo in TRIBUNAIS, f"{codigo} ausente para J={j} TR={tr:02d}"


def test_validar_ok():
    limpo, erro = cnj.validar("0829229-82.2024.8.19.0209")
    assert limpo == CNJ_VALIDO_1 and erro is None


def test_validar_tamanho_errado():
    limpo, erro = cnj.validar("0829229-82.2024")
    assert limpo is None and "20 dígitos" in erro


def test_validar_digito_errado():
    limpo, erro = cnj.validar("0829229-83.2024.8.19.0209")
    assert limpo is None and "dígito verificador" in erro


def test_extrair_todos_de_texto_com_ruido():
    texto = (
        "Processo: 0829229-82.2024.8.19.0209 (1ª Vara)\n"
        "outro 0800086-70.2025.8.19.0255 e repetido 0829229-82.2024.8.19.0209\n"
        "inválido 0829229-83.2024.8.19.0209 e lixo 12345"
    )
    assert cnj.extrair_todos(texto) == [CNJ_VALIDO_1, CNJ_VALIDO_2]
