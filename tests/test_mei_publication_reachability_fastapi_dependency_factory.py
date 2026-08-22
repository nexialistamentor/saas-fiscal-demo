"""RED: FastAPI dependency factories must expose their returned dependency chain."""

from __future__ import annotations


def test_fastapi_dependency_factory_is_resolved_through_returned_dependency_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    module = modules["app.routes.metrics_router"]
    node = module.functions["obter_metricas"]

    callees = census_module._direct_callees(module, node)

    assert "app.security.require_role" in callees
    assert "app.security.get_usuario_atual" in callees
