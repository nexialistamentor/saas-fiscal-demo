"""RED: a plain app class constructor must not remain unresolved."""

from __future__ import annotations


def test_real_tax_consistency_plain_constructor_is_not_unresolved_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    result = census_module._background_downstream_inventory(
        modules,
        function_id="app.xml_service.processar_e_persistir_xml",
    )

    assert (
        "app.services.tax_consistency.tax_consistency_engine.TaxConsistencyEngine"
        not in result["unresolved_app_callees"]
    )
