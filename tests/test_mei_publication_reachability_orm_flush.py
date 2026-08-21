"""RED: real ORM flush/rollback semantics must be explicit before persistence reachability."""

from __future__ import annotations


def test_real_document_persistence_exposes_flush_and_rollback_session_ops_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    operations = census_module._orm_session_operations(
        modules,
        function_id="app.xml_service.persistir_documento_fiscal",
    )

    assert operations == ["add", "flush", "rollback", "add", "commit"]


def test_real_document_persistence_treats_flush_as_write_not_rollback_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    operations = census_module._orm_persistence_operations(
        modules,
        function_id="app.xml_service.persistir_documento_fiscal",
    )

    assert operations == ["add", "flush", "add", "commit"]
