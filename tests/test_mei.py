"""Paridade MEITaxEngine (L2) vs calcular_imposto_simples (MEI) no legado."""

import pytest

from app.services.imposto_service import calcular_imposto_simples
from app.services.tax_engines.mei_constants import normalizar_atividade_mei
from app.services.tax_engines.mei_tax_engine import MEITaxEngine


def _assert_parity(faturamento_mensal: float, atividade: str | None = None):
    engine = MEITaxEngine()
    ctx = {"faturamento": faturamento_mensal}
    if atividade is not None:
        ctx["atividade"] = atividade
    l2 = engine.execute(ctx)
    legado = calcular_imposto_simples(
        faturamento_mensal,
        despesas=0,
        tipo="MEI",
        atividade=atividade,
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
def test_mei_engine_paridade_legado_sem_atividade_explicita(faturamento_mensal: float):
    _assert_parity(faturamento_mensal)


@pytest.mark.parametrize(
    "faturamento_mensal",
    [4000.0, 6500.0],
)
def test_mei_engine_paridade_legado_servicos(faturamento_mensal: float):
    _assert_parity(faturamento_mensal, atividade="servicos")
