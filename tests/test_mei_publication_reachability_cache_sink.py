"""RED: the real Assistant MEI path must expose its cache sink."""

from __future__ import annotations


def test_real_assistant_mei_path_reports_reachable_cache_sink_red():
    from app.scripts.mei_publication_reachability_census import build_census

    census = build_census()
    matches = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/perguntar"
    ]
    assert len(matches) == 1

    path = matches[0]
    assert path["mei_reachability"] == "REACHABLE_MEI"
    assert (
        "app.services.tax_engines.mei_constants.calcular_das_mei"
        in path["producer_ids"]
    )
    assert "CACHE" in path["sink_kinds"]
