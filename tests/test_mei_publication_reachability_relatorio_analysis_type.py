from app.scripts import mei_publication_reachability_census as census_module


def test_relatorio_analysis_type_carries_insightengine_mei_sinks():
    census = census_module.build_census()
    path = next(
        item for item in census["paths"]
        if item["entrypoint"] == "/relatorio/{analysis_type}"
    )

    assert path["mei_reachability"] == "REACHABLE_MEI"
    assert path["producer_ids"] == [census_module.PRODUCER_ID]
    assert set(path["sink_kinds"]) == {"PUBLICATION", "PERSISTENCE"}

    assert path["trace"][0] == (
        "app.routes.relatorio_router.obter_relatorio_por_tipo"
    )
    assert (
        "app.services.insights_engine.InsightEngine.gerar_insights_empresa"
        in path["trace"]
    )
    assert census_module.PRODUCER_ID in path["trace"]

    provenance = path["lineage_provenance"]
    assert provenance["analysis_type_branch"] == "tax_recovery"
    assert provenance["publication_field"] == "relatorio"

    persistence = path["persistence_inventory"]
    assert persistence["scan_complete"] is True
    assert persistence["unresolved_app_callees"] == []

    operations = persistence["sink_operations"].get(
        "app.services.insights_engine.InsightEngine.gerar_insights_empresa"
    )
    assert operations
    assert {"add", "flush", "commit"}.issubset(set(operations))
