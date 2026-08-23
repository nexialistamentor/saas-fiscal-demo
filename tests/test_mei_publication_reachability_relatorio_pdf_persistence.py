from app.scripts import mei_publication_reachability_census as census_module


def test_relatorio_pdf_reaches_canonical_mei_only_through_persistence():
    census = census_module.build_census()
    path = next(
        item for item in census["paths"]
        if item["entrypoint"] == "/relatorio/relatorio-pdf"
    )

    assert path["mei_reachability"] == "REACHABLE_MEI"
    assert path["producer_ids"] == [census_module.PRODUCER_ID]

    # executar_analise_xml() does not carry InsightEngine results into the PDF.
    # The canonical MEI sink on this route is the EngineResultado persistence.
    assert set(path["sink_kinds"]) == {"PERSISTENCE"}

    trace = path["trace"]
    assert trace[0] == "app.routes.relatorio_router.relatorio_pdf"
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

    provenance = path["lineage_provenance"]
    assert provenance["persistence_model"] == "app.models.EngineResultado"
    assert provenance["persistence_field"] == "resultado"
    assert "publication_field" not in provenance

    persistence = path["persistence_inventory"]
    assert persistence["scan_complete"] is True
    assert persistence["unresolved_app_callees"] == []

    operations = persistence["sink_operations"].get(
        "app.services.insights_engine.InsightEngine.gerar_insights_empresa"
    )
    assert operations
    assert {"add", "flush", "commit"}.issubset(set(operations))
