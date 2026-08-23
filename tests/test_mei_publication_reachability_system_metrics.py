from app.scripts import mei_publication_reachability_census as census_module


def test_system_metrics_has_no_canonical_mei_producer_after_dict_reads_qualified():
    census = census_module.build_census()
    path = next(
        item for item in census["paths"]
        if item["entrypoint"] == "/system/metrics"
    )

    assert path["mei_reachability"] == "NO_CANONICAL_MEI_PRODUCER"
    assert path["producer_ids"] == []
    assert path["sink_kinds"] == []
    assert path["unresolved_app_callees"] == []
    assert path["downstream_scan_complete"] is True
