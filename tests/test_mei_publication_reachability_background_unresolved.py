"""RED: unresolved background reachability must propagate to Gate A status."""

from __future__ import annotations


def test_background_unresolved_propagates_to_global_census_red(monkeypatch):
    import app.scripts.mei_publication_reachability_census as census_module

    target_root = "app.routes.lote_router.processar_lote"
    original_background_downstream = (
        census_module._background_downstream_inventory
    )

    def synthetic_background_downstream(
        modules,
        *,
        function_id,
    ):
        if function_id == target_root:
            return {
                "producer_ids": [],
                "unresolved_app_callees": [
                    "app.synthetic.missing_background_callee"
                ],
                "downstream_scan_complete": False,
            }

        return original_background_downstream(
            modules,
            function_id=function_id,
        )

    monkeypatch.setattr(
        census_module,
        "_background_downstream_inventory",
        synthetic_background_downstream,
    )

    census = census_module.build_census()

    roots = [
        item
        for item in census["background_roots"]
        if item["function_id"] == target_root
    ]

    assert len(roots) == 1
    assert roots[0]["is_root"] is True
    assert roots[0]["downstream_scan_complete"] is False
    assert roots[0]["unresolved_app_callees"] == [
        "app.synthetic.missing_background_callee"
    ]

    assert census["scan_complete"] is False
    assert census["status"] == "UNRESOLVED"
