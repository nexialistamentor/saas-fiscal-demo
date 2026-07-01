"""E4 — PIS/COFINS não-cumulativo: créditos sobre insumos tributados (estimativa)."""

from app.services.tax_engines.lucro_real_engine import calcular_lucro_real
from app.services.tax_engines.pis_cofins_engine import (
    calcular_pis_cofins,
    creditos_sobre_insumos_tributados,
)


def test_creditos_insumos_aliquotas():
    pis_c, cofins_c = creditos_sobre_insumos_tributados(40_000)
    assert pis_c == 660.0
    assert cofins_c == 3040.0


def test_nao_cumulativo_com_insumos():
    r = calcular_pis_cofins(
        {"faturamento": 100_000, "icms": 0, "insumos_tributados": 40_000, "ano_referencia": 2026},
        regime="real",
    )
    assert r["creditos"]["fonte"] == "insumos_tributados"
    assert r["creditos"]["total"] == 3700.0
    assert r["tributos"]["pis"] + r["tributos"]["cofins"] == 9250.0
    assert r["tributos_liquidos"]["pis"] == 990.0
    assert r["tributos_liquidos"]["cofins"] == 4560.0


def test_manual_prevalece_sobre_insumos():
    r = calcular_pis_cofins(
        {
            "faturamento": 100_000,
            "icms": 0,
            "insumos_tributados": 40_000,
            "creditos_pis_cofins": 5000,
            "ano_referencia": 2026,
        },
        regime="real",
    )
    assert r["creditos"]["fonte"] == "manual"
    assert r["creditos"]["total"] == 5000.0


def test_lucro_real_usa_tributos_liquidos():
    out = calcular_lucro_real(
        {
            "faturamento": 100_000,
            "custos": 40_000,
            "despesas": 0,
            "insumos_tributados": 40_000,
            "ano_referencia": 2026,
        }
    )
    trib = out["data"]["tributos"]
    assert trib["pis"] == 990.0
    assert trib["cofins"] == 4560.0


def test_presumido_sem_credito_insumos():
    r = calcular_pis_cofins(
        {"faturamento": 50_000, "icms": 0, "insumos_tributados": 20_000, "ano_referencia": 2026},
        regime="presumido",
    )
    assert r["creditos"]["total"] == 0.0
    assert r["creditos"]["fonte"] is None
    assert r["tributos_liquidos"]["pis"] == r["tributos"]["pis"]
