"""RED: method calls on temporary app class instances must remain visible."""

from __future__ import annotations


def test_temporary_app_class_instance_method_is_visible_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    module = modules["app.routers.st_router"]
    node = module.functions["analise_st_ncm"]

    callees = census_module._direct_callees(module, node)

    assert "app.services.st_service.STAnalyzer.analise_por_ncm" in callees
