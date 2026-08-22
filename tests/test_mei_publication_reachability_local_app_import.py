"""RED: function-local app imports must remain visible to reachability."""

from __future__ import annotations


def test_function_local_app_import_is_resolved_into_direct_callees_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    module = modules["app.auth_router"]
    node = module.functions["accept_terms"]

    callees = census_module._direct_callees(module, node)

    assert "app.redis_connection.get_redis_connection" in callees
