"""RED: static call graph must expose a real transitive ORM persistence sink."""

from __future__ import annotations


def test_real_xml_processing_reaches_document_persistence_sink_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    result = census_module._reachable_orm_persistence_sinks(
        modules,
        function_id="app.xml_service.processar_e_persistir_xml",
    )

    assert result["sink_operations"] == {
        "app.xml_service.persistir_documento_fiscal": [
            "add",
            "flush",
            "add",
            "commit",
        ]
    }
    assert result["unresolved_app_callees"] == []
    assert result["scan_complete"] is True
