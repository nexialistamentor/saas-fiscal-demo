"""RED: inert SQLAlchemy declarative model constructors must not stay unresolved."""

from __future__ import annotations


def test_real_inert_declarative_model_constructors_are_not_unresolved_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    result = census_module._background_downstream_inventory(
        modules,
        function_id="app.services.registro_analise_service.executar_e_registrar_analise_xml",
    )

    unresolved = result["unresolved_app_callees"]

    assert "app.models.RelatorioAnalise" not in unresolved
    assert "app.models.UsoPlataforma" not in unresolved
