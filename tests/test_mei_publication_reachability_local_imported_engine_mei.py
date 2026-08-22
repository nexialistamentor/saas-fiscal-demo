"""RED: a locally imported engine class must not hide a reachable MEI producer."""

from __future__ import annotations


def test_local_imported_insight_engine_exposes_mei_producer_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    result = census_module._background_downstream_inventory(
        modules,
        function_id="app.services.registro_analise_service.executar_e_registrar_analise_xml",
    )

    assert result["unresolved_app_callees"] == []
    assert result["producer_ids"] == [census_module.PRODUCER_ID]
    assert result["downstream_scan_complete"] is True
