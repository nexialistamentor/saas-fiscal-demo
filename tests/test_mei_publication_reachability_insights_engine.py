from app.scripts import mei_publication_reachability_census as census_module


def test_insights_route_carries_mei_publication_and_persistence_evidence():
    census = census_module.build_census()
    path = next(
        item for item in census["paths"]
        if item["entrypoint"] == "/insights/{empresa_id}"
    )

    assert path["mei_reachability"] == "REACHABLE_MEI"
    assert path["producer_ids"] == [census_module.PRODUCER_ID]
    assert set(path["sink_kinds"]) == {"PUBLICATION", "PERSISTENCE"}

    persistence = path["persistence_inventory"]
    assert persistence["scan_complete"] is True
    assert persistence["unresolved_app_callees"] == []

    operations = persistence["sink_operations"].get(
        "app.services.insights_engine.InsightEngine.gerar_insights_empresa"
    )
    assert operations
    assert {"add", "flush", "commit"}.issubset(set(operations))
