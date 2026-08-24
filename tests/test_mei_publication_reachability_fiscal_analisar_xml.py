from app.scripts import mei_publication_reachability_census as census_module


def test_fiscal_analisar_xml_reaches_canonical_mei_persistence():
    census = census_module.build_census()
    path = next(
        item for item in census["paths"]
        if item["entrypoint"] == "/fiscal/analisar-xml"
    )

    assert path["mei_reachability"] == "REACHABLE_MEI"
    assert path["producer_ids"] == [census_module.PRODUCER_ID]
    assert set(path["sink_kinds"]) == {"PERSISTENCE"}

    trace = path["trace"]
    assert trace[0] == "app.routes.fiscal_router.analisar_xml_fiscal"
    assert "app.routes.fiscal_router._enqueue_or_run_sync" in trace
    assert "app.jobs.analysis_job.processar_xml_job" in trace
    assert (
        "app.services.registro_analise_service."
        "executar_e_registrar_analise_xml"
        in trace
    )
    assert (
        "app.services.insights_engine.InsightEngine.gerar_insights_empresa"
        in trace
    )
    assert census_module.PRODUCER_ID in trace

    assert path["unresolved_app_callees"] == []
    assert path["downstream_scan_complete"] is True

    persistence = path["persistence_inventory"]
    assert persistence["scan_complete"] is True
    assert persistence["unresolved_app_callees"] == []
