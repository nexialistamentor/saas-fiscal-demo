"""RED: unresolved background reachability must propagate to Gate A status."""

from __future__ import annotations


def test_background_unresolved_propagates_to_global_census_red(monkeypatch):
    import app.scripts.mei_publication_reachability_census as census_module

    monkeypatch.setattr(
        census_module,
        "_fastapi_background_root_inventory",
        lambda modules, *, mounted: [
            {
                "function_id": "app.security.get_usuario_atual",
                "registration_kind": "TEST_REGISTERED_BACKGROUND_ROOT",
            }
        ],
    )
    monkeypatch.setattr(
        census_module,
        "_rq_background_root_inventory",
        lambda modules, *, mounted: [],
    )
    monkeypatch.setattr(
        census_module,
        "_background_downstream_inventory",
        lambda modules, *, function_id: {
            "producer_ids": [],
            "unresolved_app_callees": ["app.synthetic.missing_background_callee"],
            "downstream_scan_complete": False,
        },
    )

    census = census_module.build_census()

    assert census["scan_complete"] is False
    assert census["status"] == "UNRESOLVED"
