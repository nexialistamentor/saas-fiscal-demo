"""RED: proven SQLAlchemy Column descriptor helpers must not remain unresolved."""

from __future__ import annotations


def test_real_sqlalchemy_column_descriptor_helpers_are_not_unresolved_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    result = census_module._background_downstream_inventory(
        modules,
        function_id="app.services.registro_analise_service.executar_e_registrar_analise_xml",
    )

    unresolved = set(result["unresolved_app_callees"])
    descriptor_targets = {
        "app.models.RelatorioAnalise.id.desc",
        "app.models.TabelaMVA.id.desc",
        "app.models.TabelaMVA.vigencia_fim.is_",
        "app.models.TabelaMVA.vigencia_inicio.desc",
        "app.models.TabelaMVA.vigencia_inicio.is_",
    }

    assert unresolved.isdisjoint(descriptor_targets)
