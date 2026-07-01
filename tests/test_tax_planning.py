"""Planejamento tributário: engine delega para simular_regimes."""

from app.services.tax_engines.tax_planning_engine import (
    TaxPlanningEngine,
    simular_regimes,
)


def _dados_exemplo() -> dict:
    return {
        "faturamento": 100_000,
        "atividade": "comercio",
        "receita_bruta": 100_000,
        "custos": 40_000,
        "despesas": 20_000,
        "ano_referencia": 2026,
    }


def test_execute_delega_para_simular_regimes():
    dados = _dados_exemplo()
    engine = TaxPlanningEngine()
    resultado = engine.execute(dados)
    base = simular_regimes(dados)
    assert resultado["_ano_referencia"] == 2026
    assert resultado["_estado_temporal"] == "resolvido"
    assert {k: v for k, v in resultado.items() if not k.startswith("_")} == base


def test_simular_regimes_estrutura_e_melhor_regime_valido():
    r = simular_regimes(_dados_exemplo())
    assert set(r.keys()) >= {
        "comparacao",
        "melhor_regime",
        "economia_estimada",
        "alertas",
    }
    assert r["melhor_regime"] in ("lucro_real", "lucro_presumido")
    assert "lucro_presumido" in r["comparacao"]
    assert "lucro_real" in r["comparacao"]
    assert isinstance(r["economia_estimada"], (int, float))
    assert r["economia_estimada"] >= 0
