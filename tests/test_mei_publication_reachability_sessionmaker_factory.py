"""RED: proven SQLAlchemy SessionLocal factory must not remain unresolved."""

from __future__ import annotations


def test_real_sessionmaker_factory_is_not_unresolved_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    result = census_module._background_downstream_inventory(
        modules,
        function_id="app.services.registro_analise_service.executar_e_registrar_analise_xml",
    )

    unresolved = set(result["unresolved_app_callees"])

    assert "app.database.SessionLocal" not in unresolved
    assert result["producer_ids"] == [census_module.PRODUCER_ID]
    assert result["downstream_scan_complete"] is True
