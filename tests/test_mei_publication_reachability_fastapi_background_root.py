"""RED: build_census must detect real FastAPI BackgroundTasks registrations."""

from __future__ import annotations


def test_build_census_detects_real_lote_background_registration_red():
    import app.scripts.mei_publication_reachability_census as census_module

    census = census_module.build_census()
    roots = {
        item["function_id"]: item
        for item in census["background_roots"]
    }

    lote_root = roots["app.routes.lote_router.processar_lote"]

    assert lote_root["present"] is True
    assert lote_root["is_root"] is True
    assert lote_root["registration_ids"] == [
        "app.routes.lote_router.analisar_lote:BackgroundTasks.add_task"
    ]
