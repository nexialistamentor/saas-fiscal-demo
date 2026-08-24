"""RED: deprecated MEIEngine must stay inventory-only and delegate to canonical MEITaxEngine."""

from app.scripts.mei_publication_reachability_census import (
    MEI_ENGINE_EXECUTE_ID,
    PRODUCER_ID,
    _class_reachability_inventory,
    _direct_callees,
    _function_node,
    _parse_app,
)


LEGACY_CLASS_ID = "app.services.tax_engines.mei_engine.MEIEngine"
LEGACY_EXECUTE_ID = LEGACY_CLASS_ID + ".execute"


def test_legacy_mei_engine_is_inventory_only_and_uses_canonical_boundary_red():
    modules = _parse_app()

    inventory = _class_reachability_inventory(
        modules,
        class_id=LEGACY_CLASS_ID,
    )
    assert inventory == {
        "class_id": LEGACY_CLASS_ID,
        "present": True,
        "caller_ids": [],
        "reachability": "INVENTORY_ONLY",
    }

    found = _function_node(modules, LEGACY_EXECUTE_ID)
    assert found is not None

    module, node = found
    callees = _direct_callees(module, node)

    assert PRODUCER_ID not in callees
    assert MEI_ENGINE_EXECUTE_ID in callees
