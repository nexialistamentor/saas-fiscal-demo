"""RED: same-class self.method calls must be visible to the MEI call graph."""

from __future__ import annotations


def test_direct_callees_resolves_real_tax_consistency_self_methods_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    found = census_module._function_node(
        modules,
        "app.services.tax_consistency.tax_consistency_engine.TaxConsistencyEngine.verificar_consistencia",
    )
    assert found is not None
    module, node = found

    assert census_module._direct_callees(module, node) == [
        "app.services.tax_consistency.tax_consistency_engine.TaxConsistencyEngine.verificar_base_st",
        "app.services.tax_consistency.tax_consistency_engine.TaxConsistencyEngine.verificar_icms_st",
        "app.services.tax_consistency.tax_consistency_engine.TaxConsistencyEngine.verificar_mva",
    ]
