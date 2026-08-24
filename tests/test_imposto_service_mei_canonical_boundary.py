"""RED: imposto_service nao pode produzir DAS MEI fora do boundary canonico."""

from app.scripts.mei_publication_reachability_census import (
    MEI_ENGINE_EXECUTE_ID,
    PRODUCER_ID,
    _direct_callees,
    _function_node,
    _parse_app,
)


SERVICE_ID = "app.services.imposto_service.calcular_imposto_simples"


def test_imposto_service_mei_uses_canonical_engine_not_direct_producer_red():
    modules = _parse_app()

    found = _function_node(modules, SERVICE_ID)
    assert found is not None

    module, node = found
    callees = _direct_callees(module, node)

    assert PRODUCER_ID not in callees
    assert MEI_ENGINE_EXECUTE_ID in callees
