from app.services.assistente_service import (
    _parse_valor_br,
    extrair_faturamento,
)


def test_parse_valor_br_preserva_milhar_e_centavos():
    assert _parse_valor_br("7.500,50") == 7_500.50
    assert _parse_valor_br("7.000") == 7_000.0
    assert _parse_valor_br("7,50") == 7.50


def test_extrair_faturamento_ignora_ano_antes_do_valor():
    resultado = extrair_faturamento(
        "em 2026, faturamos 50 mil por mes"
    )

    assert resultado == 50_000


def test_extrair_faturamento_prioriza_valor_associado_ao_faturamento():
    resultado = extrair_faturamento(
        "tenho 3 funcionarios e faturamento de 5000 por mes em 2026"
    )

    assert resultado == 5_000


def test_extrair_faturamento_preserva_valor_que_parece_ano():
    resultado = extrair_faturamento(
        "faturamos 2000 por mes"
    )

    assert resultado == 2_000


def test_extrair_faturamento_preserva_2000_sem_palavra_faturamento():
    resultado = extrair_faturamento(
        "quanto pago de MEI em 2026 com 2000 por mes"
    )

    assert resultado == 2_000


def test_extrair_faturamento_nao_usa_numero_sem_contexto_financeiro():
    resultado = extrair_faturamento(
        "tenho 3 funcionarios e quero saber as regras do MEI em 2026"
    )

    assert resultado is None


def test_extrair_faturamento_nao_usa_contagem_apos_faturamento_ausente():
    resultado = extrair_faturamento(
        "faturamento nao informado; tenho 3 funcionarios em 2026"
    )

    assert resultado is None


def test_extrair_faturamento_apenas_ano_retorna_none():
    resultado = extrair_faturamento(
        "regra do MEI para 2026"
    )

    assert resultado is None


def test_extrair_faturamento_preserva_formato_br_com_centavos():
    resultado = extrair_faturamento(
        "faturamento de 7.500,50 por mes em 2026"
    )

    assert resultado == 7_500.50
