"""Static MEI call graph contracts for inheritance and executable callees."""

from __future__ import annotations


def test_mei_engine_hierarchy_resolves_inherited_base_method():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    found = census_module._function_node(
        modules,
        census_module.MEI_ENGINE_EXECUTE_ID,
    )
    assert found is not None

    module, _ = found
    inherited_method = census_module._direct_app_base_method(
        module,
        class_name="MEITaxEngine",
        method_name="resolver_ano_referencia",
    )

    assert (
        inherited_method
        == "app.services.tax_engines.base_tax_engine."
        "BaseTaxEngine.resolver_ano_referencia"
    )


def test_mei_engine_execute_uses_mei_temporal_reference_date():
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
        "app.services.tax_engines.mei_temporal.resolver_data_referencia_mei"
        in callees
    )
    assert (
        "app.services.tax_engines.base_tax_engine."
        "BaseTaxEngine.resolver_ano_referencia"
        not in callees
    )
