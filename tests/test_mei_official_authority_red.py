"""RED causal: calculo MEI interno nao e DAS oficial sem autoridade operacional."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.services.source_authority_guard as source_authority_guard
import app.services.tax_engines.mei_tax_engine as mei_tax_engine
from app.routes.imposto_router import router
from app.services import analysis_orchestrator


def test_post_calcular_nao_publica_formula_interna_como_das_oficial_sem_autoridade(
    monkeypatch,
):
    chamadas_formula_interna = []
    chamadas_autoridade_oficial = []

    def formula_interna(salario_minimo, atividade):
        chamadas_formula_interna.append((salario_minimo, atividade))
        return 432.10

    def autoridade_oficial(*args, **kwargs):
        chamadas_autoridade_oficial.append((args, kwargs))
        raise AssertionError("autoridade oficial indisponivel neste cenario")

    monkeypatch.setattr(mei_tax_engine, "calcular_das_mei", formula_interna)
    monkeypatch.setattr(source_authority_guard, "verificar", autoridade_oficial)
    analysis_orchestrator.analysis_cache.clear()

    api = FastAPI()
    api.include_router(router, prefix="/imposto")
    with TestClient(api) as client:
        response = client.post(
            "/imposto/calcular",
            json={
                "tipo_usuario": "MEI",
                "faturamento_mensal": 5_000,
                "atividade": "servicos",
                "ano_referencia": 2026,
            },
        )

    assert chamadas_formula_interna == []
    assert chamadas_autoridade_oficial == []
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["tipo_bloqueio"] == "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL"
    assert "imposto_mensal" not in detail
    assert "imposto_anual" not in detail
