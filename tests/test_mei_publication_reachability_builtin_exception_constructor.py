"""RED: a simple built-in exception subclass must not remain unresolved."""

from __future__ import annotations


def test_real_builtin_exception_constructor_is_not_unresolved_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    result = census_module._background_downstream_inventory(
        modules,
        function_id="app.services.registro_analise_service.executar_e_registrar_analise_xml",
    )

    assert (
        "app.services.tax_engines.base_tax_engine.TempoNormativoAusenteError"
        not in result["unresolved_app_callees"]
    )
    assert "app.database.SessionLocal" in result["unresolved_app_callees"]
