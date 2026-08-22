"""RED: build_census must detect the real mounted fiscal RQ registration."""

from __future__ import annotations


def test_build_census_detects_real_fiscal_rq_registration_red():
    import app.scripts.mei_publication_reachability_census as census_module

    census = census_module.build_census()
    roots = {
        item["function_id"]: item
        for item in census["background_roots"]
    }

    rq_root = roots["app.jobs.analysis_job.processar_xml_job"]

    assert rq_root["present"] is True
    assert rq_root["is_root"] is True
    assert rq_root["reachability"] == "REGISTERED_BACKGROUND_ROOT"
    assert rq_root["registration_ids"] == [
        "app.routes.fiscal_router.analisar_xml_fiscal"
        "->app.routes.fiscal_router._enqueue_or_run_sync:RQ.Queue.enqueue"
    ]
    assert rq_root["producer_ids"] == [census_module.PRODUCER_ID]
    assert rq_root["unresolved_app_callees"] == []
    assert rq_root["downstream_scan_complete"] is True
