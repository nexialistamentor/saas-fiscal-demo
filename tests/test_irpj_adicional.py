"""Limite do adicional de IRPJ na base presumida (RIR 2018, art. 622 — R$ 20 mil/mês)."""

from datetime import date

from app.services.tax_engines.irpj_adicional import (
    calcular_adicional_irpj_presumido,
    limiar_adicional_irpj,
    periodo_meses_from_context,
)
from app.services.tax_engines.irpj_engine import IRPJEngine
from app.services.tax_engines.lucro_presumido_engine import calcular_lucro_presumido


def test_periodo_meses_default_1_sem_ou_com_data_referencia():
    assert periodo_meses_from_context({}) == 1
    assert periodo_meses_from_context({"data_referencia": None}) == 1
    assert periodo_meses_from_context({"data_referencia": date(2026, 3, 15)}) == 1


def test_limiar_20_mil_com_apuracao_mensal():
    ctx = {"data_referencia": date(2026, 1, 31)}
    assert limiar_adicional_irpj(ctx) == 20_000.0


def test_calcular_adicional_presumido_excedente():
    ctx = {}
    # Base 32.000 — limiar 20.000 → excedente 12.000 × 10% = 1.200
    assert calcular_adicional_irpj_presumido(32_000.0, ctx) == 1_200.0
    assert calcular_adicional_irpj_presumido(20_000.0, ctx) == 0.0
    assert calcular_adicional_irpj_presumido(19_999.99, ctx) == 0.0


def test_irpj_engine_usa_limiar_escalado_pelo_contexto():
    eng = IRPJEngine()
    base = 32_000.0
    r = eng.execute({"base_calculo": base, "data_referencia": date(2026, 5, 1)})
    assert r["irpj"] == base * 0.15
    assert r["adicional_irpj"] == 1_200.0
    assert r["total_irpj"] == r["irpj"] + r["adicional_irpj"]


def test_lucro_presumido_irpj_alinha_com_motor_irpj_servicos():
    # Faturamento 100k serviços → base IRPJ 32%
    dados = {"faturamento": 100_000.0, "atividade": "servicos"}
    pres = calcular_lucro_presumido(dados)
    irpj_eng = IRPJEngine().execute({"base_calculo": 32_000.0})
    assert pres["data"]["tributos"]["irpj"] == irpj_eng["total_irpj"]
