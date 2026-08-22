"""RED: generic persisted report publication may expose MEI results."""

from __future__ import annotations


def test_generic_persisted_report_publication_is_explicitly_unresolved_red():
    from app.scripts.mei_publication_reachability_census import build_census

    census = build_census()
    matches = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/relatorio/{relatorio_id:int}"
    ]

    assert len(matches) == 1
    path = matches[0]

    assert path["function_id"] == "app.routes.relatorio_router.obter_relatorio"
    assert path["mei_reachability"] == "UNRESOLVED_MEI"
    assert path["blocked_before_producer"] is False
    assert path["blocker_code"] == "PERSISTED_MEI_PROVENANCE_UNPROVEN"
    assert path["producer_ids"] == []
    assert "PUBLICATION" in path["sink_kinds"]
    assert path["persistence_source"] == {
        "model": "app.models.RelatorioAnalise",
        "analysis_type_filter": None,
        "may_include_analysis_type": "mei_tax",
        "field": "resultado_json",
        "lineage_proven": False,
    }
    assert census["scan_complete"] is False
    assert census["status"] == "UNRESOLVED"
