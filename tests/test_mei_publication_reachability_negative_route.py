"""RED: a public root with a complete graph and no canonical MEI producer must be classified."""

from __future__ import annotations


def test_real_st_ncm_route_has_no_canonical_mei_producer_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    function_id = "app.routers.st_router.analise_st_ncm"

    result = census_module._default_route_reachability_inventory(
        modules,
        function_id=function_id,
    )

    assert result["mei_reachability"] == "NO_CANONICAL_MEI_PRODUCER"
    assert result["producer_ids"] == []
    assert result["unresolved_app_callees"] == []
    assert result["downstream_scan_complete"] is True


def test_real_st_ncm_route_is_classified_by_build_census_red():
    import app.scripts.mei_publication_reachability_census as census_module

    census = census_module.build_census()
    matches = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/analise-st/ncm/{empresa_id}"
    ]

    assert len(matches) == 1
    path = matches[0]
    assert path["mei_reachability"] == "NO_CANONICAL_MEI_PRODUCER"
    assert path["producer_ids"] == []
    assert path["unresolved_app_callees"] == []
    assert path["downstream_scan_complete"] is True
    assert "/analise-st/ncm/{empresa_id}" not in census["unclassified_entrypoints"]
