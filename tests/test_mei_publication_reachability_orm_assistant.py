"""RED: Assistant MEI persistence scan must traverse the qualified registry engine."""

from __future__ import annotations


def test_assistant_mei_persistence_scan_traverses_qualified_engine_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    route_function_id = "app.routers.assistente_router.perguntar"

    result = census_module._assistant_orm_persistence_inventory(
        modules,
        route_function_id=route_function_id,
    )

    assert result["qualified_trace"] == census_module._assistant_trace(
        modules,
        route_function_id,
    )
    assert census_module.MEI_ENGINE_EXECUTE_ID in result["qualified_trace"]
    assert census_module.PRODUCER_ID in result["qualified_trace"]
    assert result["sink_operations"] == {}
    assert result["unresolved_app_callees"] == []
    assert result["scan_complete"] is True
