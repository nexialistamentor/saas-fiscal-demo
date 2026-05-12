"""
Testes do motor de regime tributário soberano V1.
"""

from decimal import Decimal

import pytest

from app.services.regime_engine import (
    LIMITE_MEI_ANUAL,
    LIMITE_SIMPLES_ANUAL,
    ResultadoComparacao,
    ResultadoRegime,
    _anexo_por_secao_e_fator_r,
    _calcular_fator_r,
    calcular_simples,
    comparar_regimes,
)


# ---------------------------------------------------------------------------
# Fator R
# ---------------------------------------------------------------------------
def test_fator_r_calculado():
    fr = _calcular_fator_r(Decimal("28000"), Decimal("100000"))
    assert fr == 0.28


def test_fator_r_zero_faturamento():
    fr = _calcular_fator_r(Decimal("10000"), Decimal("0"))
    assert fr is None


def test_fator_r_anexo_iii_quando_28():
    anexo = _anexo_por_secao_e_fator_r("J", 0.28)
    assert anexo == "III"


def test_fator_r_anexo_v_quando_abaixo_28():
    anexo = _anexo_por_secao_e_fator_r("J", 0.27)
    assert anexo == "V"


def test_fator_r_nao_aplica_para_comercio():
    """Secção G (comércio) não usa Fator R — sempre Anexo I."""
    anexo = _anexo_por_secao_e_fator_r("G", 0.10)
    assert anexo == "I"


# ---------------------------------------------------------------------------
# Simples Nacional
# ---------------------------------------------------------------------------
def test_calcular_simples_retorna_resultado():
    r = calcular_simples(Decimal("300000"), Decimal("84000"), "J")
    assert isinstance(r, ResultadoRegime)
    assert r.regime == "simples"


def test_simples_anexo_iii_com_fator_r_alto():
    r = calcular_simples(Decimal("300000"), Decimal("84000"), "J")
    assert r.anexo_simples == "III"
    assert r.fator_r == pytest.approx(0.28, rel=1e-3)


def test_simples_anexo_v_com_fator_r_baixo():
    r = calcular_simples(Decimal("300000"), Decimal("10000"), "J")
    assert r.anexo_simples == "V"


def test_simples_carga_positiva():
    r = calcular_simples(Decimal("500000"), Decimal("100000"), "G")
    assert r.carga_anual > 0
    assert r.carga_mensal > 0


def test_simples_aliquota_entre_0_e_100():
    r = calcular_simples(Decimal("200000"), Decimal("50000"), "M")
    assert 0 <= r.aliquota_efetiva_pct <= 100


# ---------------------------------------------------------------------------
# MEI
# ---------------------------------------------------------------------------
def test_mei_elegivel_abaixo_limite():
    r = comparar_regimes(
        faturamento_anual=Decimal("60000"),
        regimes_permitidos=["mei"],
    )
    assert "mei" in r.resultados
    assert "mei" not in r.regimes_inelegiveis


def test_mei_inelegivel_acima_limite():
    r = comparar_regimes(
        faturamento_anual=LIMITE_MEI_ANUAL + Decimal("1"),
        regimes_permitidos=["mei"],
    )
    assert "mei" in r.regimes_inelegiveis


def test_mei_carga_fixa():
    r = comparar_regimes(
        faturamento_anual=Decimal("60000"),
        regimes_permitidos=["mei"],
    )
    assert r.resultados["mei"].carga_anual == Decimal("756.00")


# ---------------------------------------------------------------------------
# Comparação de regimes
# ---------------------------------------------------------------------------
def test_comparacao_retorna_resultado():
    r = comparar_regimes(
        faturamento_anual=Decimal("500000"),
        folha_anual=Decimal("100000"),
        lucro_contabil=Decimal("100000"),
        secao_cnae="J",
    )
    assert isinstance(r, ResultadoComparacao)


def test_regime_recomendado_preenchido():
    r = comparar_regimes(
        faturamento_anual=Decimal("500000"),
        folha_anual=Decimal("100000"),
        lucro_contabil=Decimal("100000"),
        secao_cnae="J",
    )
    assert r.regime_recomendado in ("simples", "lp", "lr", "mei")


def test_economia_nao_negativa():
    r = comparar_regimes(
        faturamento_anual=Decimal("500000"),
        folha_anual=Decimal("100000"),
        lucro_contabil=Decimal("100000"),
        secao_cnae="J",
    )
    assert r.economia_anual_vs_pior >= 0


def test_simples_inelegivel_acima_limite():
    r = comparar_regimes(
        faturamento_anual=LIMITE_SIMPLES_ANUAL + Decimal("1"),
        regimes_permitidos=["simples", "lp"],
        lucro_contabil=Decimal("500000"),
    )
    assert "simples" in r.regimes_inelegiveis


def test_lr_inelegivel_sem_lucro_contabil():
    r = comparar_regimes(
        faturamento_anual=Decimal("1000000"),
        regimes_permitidos=["lr"],
        lucro_contabil=None,
    )
    assert "lr" in r.regimes_inelegiveis


def test_sem_regimes_elegiveis():
    r = comparar_regimes(
        faturamento_anual=Decimal("0"),
        regimes_permitidos=["lr"],
        lucro_contabil=None,
    )
    assert r.regime_recomendado == "indefinido"


def test_justificativa_preenchida():
    r = comparar_regimes(
        faturamento_anual=Decimal("300000"),
        folha_anual=Decimal("80000"),
        lucro_contabil=Decimal("60000"),
        secao_cnae="G",
    )
    assert len(r.justificativa) > 0


def test_carga_tributaria_nunca_negativa():
    r = comparar_regimes(
        faturamento_anual=Decimal("100000"),
        folha_anual=Decimal("0"),
        lucro_contabil=Decimal("-50000"),
        secao_cnae="J",
    )
    for regime in r.resultados.values():
        assert regime.carga_anual >= 0


def test_regime_recomendado_tem_menor_carga():
    r = comparar_regimes(
        faturamento_anual=Decimal("500000"),
        folha_anual=Decimal("100000"),
        lucro_contabil=Decimal("100000"),
        secao_cnae="J",
    )
    recomendado = r.resultados[r.regime_recomendado].carga_anual
    for regime in r.resultados.values():
        assert recomendado <= regime.carga_anual


def test_resultados_monetarios_sao_decimal():
    r = comparar_regimes(
        faturamento_anual=Decimal("300000"),
        folha_anual=Decimal("50000"),
        lucro_contabil=Decimal("70000"),
        secao_cnae="J",
    )
    for regime in r.resultados.values():
        assert isinstance(regime.carga_anual, Decimal)
        assert isinstance(regime.carga_mensal, Decimal)


def test_secao_desconhecida_fallback_anexo_iii():
    anexo = _anexo_por_secao_e_fator_r("ZZ", None)
    assert anexo == "III"
