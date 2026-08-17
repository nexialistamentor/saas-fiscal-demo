"""
Testes do motor de regime tributário soberano V1.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from app.services.regime_engine import (
    LIMITE_SIMPLES_ANUAL,
    ResultadoComparacao,
    ResultadoRegime,
    _anexo_por_secao_e_fator_r,
    _calcular_fator_r,
    calcular_simples,
    comparar_regimes,
)
from app.services.tax_engines.mei_constants import (
    MEI_LIMITE_ANUAL_FATURAMENTO,
    calcular_das_mei,
    obter_salario_minimo,
)
from app.services.tax_engines.base_tax_engine import TempoNormativoAusenteError

_ANO_REF = 2026


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
    r = calcular_simples(Decimal("300000"), Decimal("84000"), "J", _ANO_REF)
    assert isinstance(r, ResultadoRegime)
    assert r.regime == "simples"


def test_simples_anexo_iii_com_fator_r_alto():
    r = calcular_simples(Decimal("300000"), Decimal("84000"), "J", _ANO_REF)
    assert r.anexo_simples == "III"
    assert r.fator_r == pytest.approx(0.28, rel=1e-3)


def test_simples_anexo_v_com_fator_r_baixo():
    r = calcular_simples(Decimal("300000"), Decimal("10000"), "J", _ANO_REF)
    assert r.anexo_simples == "V"


def test_simples_carga_positiva():
    r = calcular_simples(Decimal("500000"), Decimal("100000"), "G", _ANO_REF)
    assert r.carga_anual > 0
    assert r.carga_mensal > 0


def test_simples_aliquota_entre_0_e_100():
    r = calcular_simples(Decimal("200000"), Decimal("50000"), "M", _ANO_REF)
    assert 0 <= r.aliquota_efetiva_pct <= 100


# ---------------------------------------------------------------------------
# MEI
# ---------------------------------------------------------------------------
def test_mei_elegivel_abaixo_limite():
    r = comparar_regimes(
        faturamento_anual=Decimal("60000"),
        atividade="comercio",
        regimes_permitidos=["mei"],
        ano_referencia=_ANO_REF,
    )
    assert "mei" in r.resultados
    assert "mei" not in r.regimes_inelegiveis


def test_mei_inelegivel_acima_limite():
    r = comparar_regimes(
        faturamento_anual=Decimal(str(MEI_LIMITE_ANUAL_FATURAMENTO)) + Decimal("1"),
        atividade="comercio",
        regimes_permitidos=["mei"],
        ano_referencia=_ANO_REF,
    )
    assert "mei" in r.regimes_inelegiveis


def test_mei_carga_fixa():
    """DAS MEI calculado via fonte canónica — não hardcoded."""
    r = comparar_regimes(
        faturamento_anual=Decimal("60000"),
        atividade="comercio",
        regimes_permitidos=["mei"],
        ano_referencia=_ANO_REF,
    )
    das_mensal_esperado = Decimal(
        str(calcular_das_mei(obter_salario_minimo(_ANO_REF), "comercio"))
    )
    das_anual_esperado = Decimal(str(round(float(das_mensal_esperado) * 12, 2)))
    assert r.resultados["mei"].carga_mensal == das_mensal_esperado
    assert r.resultados["mei"].carga_anual == das_anual_esperado


@pytest.mark.parametrize("atividade", [None, "", "desconhecida"])
def test_mei_r001_comparar_regimes_bloqueia_atividade_invalida(atividade):
    with pytest.raises(ValueError, match="Atividade MEI"):
        comparar_regimes(
            faturamento_anual=Decimal("60000"),
            atividade=atividade,
            regimes_permitidos=["mei"],
            ano_referencia=_ANO_REF,
        )


# ---------------------------------------------------------------------------
# Comparação de regimes
# ---------------------------------------------------------------------------
def test_comparacao_retorna_resultado():
    r = comparar_regimes(
        faturamento_anual=Decimal("500000"),
        folha_anual=Decimal("100000"),
        lucro_contabil=Decimal("100000"),
        secao_cnae="J",
        ano_referencia=_ANO_REF,
    )
    assert isinstance(r, ResultadoComparacao)


def test_regime_recomendado_preenchido():
    r = comparar_regimes(
        faturamento_anual=Decimal("500000"),
        folha_anual=Decimal("100000"),
        lucro_contabil=Decimal("100000"),
        secao_cnae="J",
        ano_referencia=_ANO_REF,
    )
    assert r.regime_recomendado in ("simples", "lp", "lr", "mei")


def test_economia_nao_negativa():
    r = comparar_regimes(
        faturamento_anual=Decimal("500000"),
        folha_anual=Decimal("100000"),
        lucro_contabil=Decimal("100000"),
        secao_cnae="J",
        ano_referencia=_ANO_REF,
    )
    assert r.economia_anual_vs_pior >= 0


def test_simples_inelegivel_acima_limite():
    r = comparar_regimes(
        faturamento_anual=LIMITE_SIMPLES_ANUAL + Decimal("1"),
        regimes_permitidos=["simples", "lp"],
        lucro_contabil=Decimal("500000"),
        ano_referencia=_ANO_REF,
    )
    assert "simples" in r.regimes_inelegiveis


def test_lr_inelegivel_sem_lucro_contabil():
    r = comparar_regimes(
        faturamento_anual=Decimal("1000000"),
        regimes_permitidos=["lr"],
        lucro_contabil=None,
        ano_referencia=_ANO_REF,
    )
    assert "lr" in r.regimes_inelegiveis


def test_sem_regimes_elegiveis():
    r = comparar_regimes(
        faturamento_anual=Decimal("0"),
        regimes_permitidos=["lr"],
        lucro_contabil=None,
        ano_referencia=_ANO_REF,
    )
    assert r.regime_recomendado == "indefinido"


def test_justificativa_preenchida():
    r = comparar_regimes(
        faturamento_anual=Decimal("300000"),
        folha_anual=Decimal("80000"),
        lucro_contabil=Decimal("60000"),
        secao_cnae="G",
        ano_referencia=_ANO_REF,
    )
    assert len(r.justificativa) > 0


def test_carga_tributaria_nunca_negativa():
    r = comparar_regimes(
        faturamento_anual=Decimal("100000"),
        folha_anual=Decimal("0"),
        lucro_contabil=Decimal("-50000"),
        secao_cnae="J",
        ano_referencia=_ANO_REF,
    )
    for regime in r.resultados.values():
        assert regime.carga_anual >= 0


def test_regime_recomendado_tem_menor_carga():
    r = comparar_regimes(
        faturamento_anual=Decimal("500000"),
        folha_anual=Decimal("100000"),
        lucro_contabil=Decimal("100000"),
        secao_cnae="J",
        ano_referencia=_ANO_REF,
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
        ano_referencia=_ANO_REF,
    )
    for regime in r.resultados.values():
        assert isinstance(regime.carga_anual, Decimal)
        assert isinstance(regime.carga_mensal, Decimal)


def test_secao_desconhecida_fallback_anexo_iii():
    anexo = _anexo_por_secao_e_fator_r("ZZ", None)
    assert anexo == "III"


# ---------------------------------------------------------------------------
# B13-OPS-13A — bloqueio temporal normativo
# ---------------------------------------------------------------------------
def test_comparar_regimes_sem_ano_referencia_bloqueia():
    with pytest.raises(TempoNormativoAusenteError):
        comparar_regimes(faturamento_anual=Decimal("500000"), regimes_permitidos=["simples"])


def test_mei_sem_ano_nao_aparece_como_inelegivel_bloqueia_antes():
    with pytest.raises(TempoNormativoAusenteError):
        comparar_regimes(faturamento_anual=Decimal("60000"), regimes_permitidos=["mei"])


def test_pad001_das_mei_sem_hardcoded_legacy():
    for caminho in [
        "app/services/regime_engine.py",
        "app/services/tax_engines/mei_engine.py",
    ]:
        src = Path(caminho).read_text(encoding="utf-8")
        assert "756" not in src
        assert "63.00" not in src
        assert "1412" not in src
        assert "0.05 + 1" not in src
        assert "salario_minimo = 1412" not in src


def test_pad001_das_mei_usa_fonte_canonica():
    for caminho in [
        "app/services/regime_engine.py",
        "app/services/tax_engines/mei_engine.py",
    ]:
        src = Path(caminho).read_text(encoding="utf-8")
        assert "calcular_das_mei" in src
        assert "obter_salario_minimo" in src
