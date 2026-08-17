"""Paridade MEITaxEngine (L2) vs calcular_imposto_simples (MEI) no legado."""

import pytest

from app.services.imposto_service import calcular_imposto_simples
from app.services.tax_engines.mei_constants import normalizar_atividade_mei
from app.services.tax_engines.mei_tax_engine import MEITaxEngine


def _assert_parity(faturamento_mensal: float, atividade: str):
    engine = MEITaxEngine()
    ctx = {"faturamento": faturamento_mensal, "ano_referencia": 2026}
    ctx["atividade"] = atividade
    l2 = engine.execute(ctx)
    legado = calcular_imposto_simples(
        faturamento_mensal,
        despesas=0,
        tipo="MEI",
        atividade=atividade,
        ano_referencia=2026,
    )

    assert l2["regime"] == "mei"
    assert l2["tributos"]["das"] == legado["imposto"]
    assert l2["alertas"] == legado["alertas"]
    assert l2["bases_calculo"]["faturamento_mensal"] == faturamento_mensal
    assert l2["bases_calculo"]["faturamento_anual"] == faturamento_mensal * 12
    assert l2["bases_calculo"]["atividade"] == normalizar_atividade_mei(atividade)


@pytest.mark.parametrize(
    "faturamento_mensal",
    [
        5000.0,
        6300.0,
        7000.0,
    ],
)
def test_mei_engine_paridade_comercio(faturamento_mensal: float):
    _assert_parity(faturamento_mensal, atividade="comercio")


@pytest.mark.parametrize(
    "faturamento_mensal",
    [4000.0, 6500.0],
)
def test_mei_engine_paridade_legado_servicos(faturamento_mensal: float):
    _assert_parity(faturamento_mensal, atividade="servicos")


@pytest.mark.parametrize("atividade", [None, "", "desconhecida"])
def test_mei_r001_engine_e_servico_bloqueiam_atividade_invalida(atividade):
    with pytest.raises(ValueError, match="Atividade MEI"):
        MEITaxEngine().execute(
            {
                "faturamento": 5000.0,
                "atividade": atividade,
                "ano_referencia": 2026,
            }
        )
    with pytest.raises(ValueError, match="Atividade MEI"):
        calcular_imposto_simples(
            5000.0,
            tipo="MEI",
            atividade=atividade,
            ano_referencia=2026,
        )
