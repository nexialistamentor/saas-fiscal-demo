"""RED: static MEI call graph must resolve inherited app methods."""

from __future__ import annotations


def test_mei_engine_resolves_inherited_base_method_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    found = census_module._function_node(
        modules,
        census_module.MEI_ENGINE_EXECUTE_ID,
    )
    assert found is not None

    module, node = found
    callees = census_module._direct_callees(module, node)

    assert (
        "app.services.tax_engines.base_tax_engine."
        "BaseTaxEngine.resolver_ano_referencia"
        in callees
    )
