"""RED: FastAPI Depends edges are executable app call-graph edges."""

from __future__ import annotations


def test_formalizacao_route_resolves_app_dependencies_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    route_id = (
        "app.routers.formalizacao_router.comparar_regimes_endpoint"
    )
    route = census_module._function_node(modules, route_id)
    assert route is not None
    route_module, route_node = route
    route_callees = census_module._direct_callees(route_module, route_node)

    assert "app.security.get_usuario_atual" in route_callees

    auth = census_module._function_node(
        modules,
        "app.security.get_usuario_atual",
    )
    assert auth is not None
    auth_module, auth_node = auth
    auth_callees = census_module._direct_callees(auth_module, auth_node)

    assert "app.database.get_db" in auth_callees
