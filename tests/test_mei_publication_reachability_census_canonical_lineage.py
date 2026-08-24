"""RED focal: o census deve provar a lineage canonica MEI atual.

Este contrato nao cria scanner paralelo. Ele exige que o census existente
represente a arquitetura produtiva ja provada:
formalizacao -> comparar_regimes -> MEITaxEngine.execute -> calcular_das_mei,
e que o DAS mensal usado na decisao venha de tributos["das"] do resultado do
engine canonico.
"""

from __future__ import annotations


ENGINE_ID = "app.services.tax_engines.mei_tax_engine.MEITaxEngine.execute"
PRODUCER_ID = "app.services.tax_engines.mei_constants.calcular_das_mei"
REGIME_ID = "app.services.regime_engine.comparar_regimes"


def _build_census() -> dict:
    from app.scripts.mei_publication_reachability_census import build_census

    return build_census()


def _entry(census: dict, entrypoint: str) -> dict:
    matches = [
        item
        for item in census.get("paths", [])
        if item.get("entrypoint") == entrypoint
    ]
    assert len(matches) == 1
    return matches[0]


def _assert_canonical_formalizacao_trace(path: dict, route_id: str) -> None:
    trace = path["trace"]
    expected = [route_id, REGIME_ID, ENGINE_ID, PRODUCER_ID]
    positions = [trace.index(function_id) for function_id in expected]

    assert positions == sorted(positions)
    assert trace[positions[1] + 1] == ENGINE_ID
    assert trace[positions[2] + 1] == PRODUCER_ID


def test_comparar_regimes_census_requires_canonical_engine_lineage_red():
    path = _entry(_build_census(), "/formalizacao/comparar-regimes")

    _assert_canonical_formalizacao_trace(
        path,
        "app.routers.formalizacao_router.comparar_regimes_endpoint",
    )


def test_simular_empresa_census_requires_canonical_engine_lineage_red():
    path = _entry(_build_census(), "/formalizacao/simular-empresa")

    _assert_canonical_formalizacao_trace(
        path,
        "app.routers.formalizacao_router.simular_empresa",
    )


def test_regime_decision_provenance_requires_engine_das_source_red():
    path = _entry(_build_census(), "/formalizacao/comparar-regimes")
    provenance = path["decision_provenance"]

    assert provenance["engine_id"] == ENGINE_ID
    assert provenance["producer_id"] == PRODUCER_ID
    assert provenance["das_source"] == '_resultado_mei["tributos"]["das"]'
    assert provenance["steps"] == [
        "_das_mensal",
        "_das_anual",
        "ResultadoRegime.carga_anual",
        "sorted:key:carga_anual",
        "regime_melhor",
        "ResultadoComparacao.regime_recomendado",
    ]
