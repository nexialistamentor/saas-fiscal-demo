from app.scripts import mei_publication_reachability_census as census_module


def test_auth_register_has_no_canonical_mei_producer_after_qualified_constructors():
    census = census_module.build_census()
    path = next(
        item for item in census["paths"]
        if item["entrypoint"] == "/auth/register"
    )

    assert path["mei_reachability"] == "NO_CANONICAL_MEI_PRODUCER"
    assert path["producer_ids"] == []
    assert path["sink_kinds"] == []
    assert path["unresolved_app_callees"] == []
    assert path["downstream_scan_complete"] is True
