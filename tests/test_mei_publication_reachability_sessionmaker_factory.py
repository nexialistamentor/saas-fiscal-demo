"""RED: proven SQLAlchemy SessionLocal factory must not remain unresolved."""

from __future__ import annotations

import ast


def _append_models_source(modules, source: str) -> None:
    modules["app.models"].tree.body.extend(ast.parse(source).body)


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


def test_direct_unknown_model_listener_is_fail_closed():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    _append_models_source(
        modules,
        'event.listen(RelatorioAnalise, "before_insert", callback_desconhecido)',
    )

    assert not census_module._is_inert_declarative_model_constructor(
        modules, "app.models.RelatorioAnalise"
    )


def test_global_session_listener_is_fail_closed_for_all_four_targets():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    _append_models_source(
        modules,
        'event.listen(Session, "before_flush", callback_desconhecido)',
    )

    assert not census_module._is_inert_sqlalchemy_sessionmaker_factory(
        modules, "app.database.SessionLocal"
    )
    for model_name in ("EngineResultado", "Insight", "RelatorioAnalise"):
        assert not census_module._is_inert_declarative_model_constructor(
            modules, f"app.models.{model_name}"
        )


def test_global_mapper_listener_is_fail_closed_for_all_four_targets():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    _append_models_source(
        modules,
        'event.listen(Mapper, "before_insert", callback_desconhecido)',
    )

    assert not census_module._is_inert_sqlalchemy_sessionmaker_factory(
        modules, "app.database.SessionLocal"
    )
    for model_name in ("EngineResultado", "Insight", "RelatorioAnalise"):
        assert not census_module._is_inert_declarative_model_constructor(
            modules, f"app.models.{model_name}"
        )
