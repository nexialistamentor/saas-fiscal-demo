"""RED: distinguish ORM session activity from persistence writes."""

from __future__ import annotations


def test_real_create_analysis_classifies_only_write_relevant_orm_operations_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    operations = census_module._orm_persistence_operations(
        modules,
        function_id="app.services.registro_analise_service.criar_registro_analise",
    )

    assert operations == ["add", "commit"]


def test_real_finalize_analysis_commit_is_persistence_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    operations = census_module._orm_persistence_operations(
        modules,
        function_id="app.services.registro_analise_service.finalizar_registro_analise",
    )

    assert operations == ["commit"]


def test_real_stateless_formalizacao_has_no_orm_persistence_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    operations = census_module._orm_persistence_operations(
        modules,
        function_id="app.routers.formalizacao_router.simular_empresa",
    )

    assert operations == []
