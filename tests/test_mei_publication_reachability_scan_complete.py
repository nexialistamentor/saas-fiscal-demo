"""RED: unresolved qualified path evidence must propagate to the Gate A census."""

from __future__ import annotations


def test_assistant_unresolved_persistence_marks_census_incomplete_red(monkeypatch):
    import app.scripts.mei_publication_reachability_census as census_module

    original = census_module._assistant_orm_persistence_inventory

    def unresolved_inventory(modules, *, route_function_id):
        result = original(modules, route_function_id=route_function_id)
        return {
            **result,
            "unresolved_app_callees": ["app.example.unresolved_call"],
            "scan_complete": False,
        }

    monkeypatch.setattr(
        census_module,
        "_assistant_orm_persistence_inventory",
        unresolved_inventory,
    )

    census = census_module.build_census()

    assert census["scan_complete"] is False
    assert census["status"] == "UNRESOLVED"
