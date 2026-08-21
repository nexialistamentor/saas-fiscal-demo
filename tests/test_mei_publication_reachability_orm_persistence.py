"""RED: reachability scanner must recognize real ORM session operations."""

from __future__ import annotations


def test_real_registro_analise_create_exposes_orm_session_operations_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    operations = census_module._orm_session_operations(
        modules,
        function_id=(
            "app.services.registro_analise_service.criar_registro_analise"
        ),
    )

    assert operations == ["add", "commit", "refresh"]


def test_real_stateless_formalizacao_has_no_orm_session_operations_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    operations = census_module._orm_session_operations(
        modules,
        function_id="app.routers.formalizacao_router.simular_empresa",
    )

    assert operations == []
