"""RED: local instance method calls must be visible to the MEI call graph."""

from __future__ import annotations


def test_direct_callees_resolves_real_local_instance_method_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    found = census_module._function_node(
        modules,
        "app.xml_service.processar_e_persistir_xml",
    )
    assert found is not None
    module, node = found

    callees = census_module._direct_callees(module, node)
    assert (
        "app.services.tax_consistency.tax_consistency_engine.TaxConsistencyEngine"
        in callees
    )
    assert (
        "app.services.tax_consistency.tax_consistency_engine.TaxConsistencyEngine.verificar_consistencia"
        in callees
    )
