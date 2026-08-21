"""RED: the final Assistant MEI path must carry qualified ORM persistence evidence."""

from __future__ import annotations


def test_assistant_path_carries_qualified_persistence_inventory_red():
    import app.scripts.mei_publication_reachability_census as census_module

    census = census_module.build_census()
    assistant = next(
        item for item in census["paths"] if item["entrypoint"] == "/perguntar"
    )

    persistence = assistant["persistence_inventory"]
    assert persistence["qualified_trace"] == assistant["trace"]
    assert census_module.MEI_ENGINE_EXECUTE_ID in persistence["qualified_trace"]
    assert census_module.PRODUCER_ID in persistence["qualified_trace"]
    assert persistence["sink_operations"] == {}
    assert persistence["unresolved_app_callees"] == []
    assert persistence["scan_complete"] is True
    assert "PERSISTENCE" not in assistant["sink_kinds"]
