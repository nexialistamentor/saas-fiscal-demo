"""Real repository proof: deprecated MEIEngine must stay inventory-only."""

from __future__ import annotations


def test_real_deprecated_mei_engine_has_no_static_constructor_callers():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    result = census_module._class_reachability_inventory(
        modules,
        class_id="app.services.tax_engines.mei_engine.MEIEngine",
    )

    assert result == {
        "class_id": "app.services.tax_engines.mei_engine.MEIEngine",
        "present": True,
        "caller_ids": [],
        "reachability": "INVENTORY_ONLY",
    }
