from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_0043 = (
    ROOT
    / "migrations"
    / "versions"
    / "0043_reconcile_tabela_mva_schema.py"
)


def test_migration_0043_exists_after_proven_schema_drift():
    assert MIGRATION_0043.exists(), (
        "0043 ausente: tabela_mva continua sem reconciliacao "
        "incremental apos 0042"
    )
import importlib.util
from types import SimpleNamespace

import pytest


def _load_migration_0043():
    spec = importlib.util.spec_from_file_location(
        "test_migration_0043_module",
        MIGRATION_0043,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Nao foi possivel carregar migration 0043")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_0043_rejects_non_postgresql():
    migration = _load_migration_0043()
    migration.op = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(
            dialect=SimpleNamespace(name="sqlite")
        )
    )

    with pytest.raises(
        RuntimeError,
        match="0043 requires PostgreSQL",
    ):
        migration.upgrade()
def test_migration_0043_reconciles_current_production_shape():
    migration = _load_migration_0043()

    existing = {
        "id",
        "estado",
        "ncm",
        "mva",
        "aliquota_interna",
        "vigencia_inicio",
        "vigencia_fim",
    }
    added = []

    class FakeInspector:
        def get_columns(self, table_name):
            assert table_name == "tabela_mva"
            return _typed_columns(migration, existing)

    class FakeOp:
        def get_bind(self):
            return SimpleNamespace(
                dialect=SimpleNamespace(name="postgresql")
            )

        def add_column(self, table_name, column):
            assert table_name == "tabela_mva"
            added.append(
                (
                    column.name,
                    str(column.type),
                    column.nullable,
                )
            )

    migration.op = FakeOp()

    if not hasattr(migration, "sa"):
        pytest.fail(
            "0043 ainda nao importa sqlalchemy para reconciliar tabela_mva"
        )

    original_inspect = migration.sa.inspect
    migration.sa.inspect = lambda _bind: FakeInspector()
    try:
        migration.upgrade()
    finally:
        migration.sa.inspect = original_inspect

    assert added == [
        ("fonte_legal", "VARCHAR(500)", True),
        ("nivel_confianca_fonte", "VARCHAR(40)", True),
        ("url_fonte", "VARCHAR(1000)", True),
        ("importado_em", "DATETIME", True),
        ("importado_por", "VARCHAR(100)", True),
    ]
def test_migration_0043_renames_legacy_fonte_url_without_losing_identity():
    migration = _load_migration_0043()

    existing = {
        "id",
        "estado",
        "ncm",
        "mva",
        "aliquota_interna",
        "vigencia_inicio",
        "vigencia_fim",
        "fonte_legal",
        "nivel_confianca_fonte",
        "fonte_url",
    }
    added = []
    renamed = []

    class FakeInspector:
        def get_columns(self, table_name):
            assert table_name == "tabela_mva"
            return _typed_columns(migration, existing)

    class FakeResult:
        def scalar_one(self):
            return 0

    class FakeBind:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, statement):
            assert "char_length(" in str(statement)
            return FakeResult()

    bind = FakeBind()

    class FakeOp:
        def get_bind(self):
            return bind

        def add_column(self, table_name, column):
            assert table_name == "tabela_mva"
            added.append(column.name)

        def alter_column(
            self,
            table_name,
            column_name,
            *,
            new_column_name,
            **_kwargs,
        ):
            renamed.append(
                (table_name, column_name, new_column_name)
            )

    migration.op = FakeOp()

    original_inspect = migration.sa.inspect
    migration.sa.inspect = lambda _bind: FakeInspector()
    try:
        migration.upgrade()
    finally:
        migration.sa.inspect = original_inspect

    assert renamed == [
        ("tabela_mva", "fonte_url", "url_fonte")
    ]
    assert "url_fonte" not in added
    assert added == [
        "importado_em",
        "importado_por",
    ]
def test_migration_0043_fails_closed_when_legacy_and_canonical_urls_conflict():
    migration = _load_migration_0043()

    existing = {
        "id",
        "estado",
        "ncm",
        "mva",
        "aliquota_interna",
        "vigencia_inicio",
        "vigencia_fim",
        "fonte_legal",
        "nivel_confianca_fonte",
        "fonte_url",
        "url_fonte",
        "importado_em",
        "importado_por",
    }

    class FakeInspector:
        def get_columns(self, table_name):
            assert table_name == "tabela_mva"
            return _typed_columns(migration, existing)

    class FakeResult:
        def __init__(self, value):
            self.value = value

        def scalar_one(self):
            return self.value

    class FakeBind:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, statement):
            sql = str(statement)

            if "char_length(" in sql:
                return FakeResult(0)

            if "IS DISTINCT FROM" in sql:
                return FakeResult(1)

            raise AssertionError(
                f"SQL inesperado no fixture de conflito: {sql}"
            )

    bind = FakeBind()

    class FakeOp:
        def get_bind(self):
            return bind

        def add_column(self, *_args, **_kwargs):
            pytest.fail("nenhuma coluna deveria ser adicionada")

        def alter_column(self, *_args, **_kwargs):
            pytest.fail("nenhum rename deveria ocorrer antes da catraca")

    migration.op = FakeOp()

    original_inspect = migration.sa.inspect
    migration.sa.inspect = lambda _bind: FakeInspector()
    try:
        with pytest.raises(
            RuntimeError,
            match="conflicting fonte_url and url_fonte",
        ):
            migration.upgrade()
    finally:
        migration.sa.inspect = original_inspect
def test_migration_0043_merges_nonconflicting_legacy_url_then_drops_it():
    migration = _load_migration_0043()

    existing = {
        "id",
        "estado",
        "ncm",
        "mva",
        "aliquota_interna",
        "vigencia_inicio",
        "vigencia_fim",
        "fonte_legal",
        "nivel_confianca_fonte",
        "fonte_url",
        "url_fonte",
        "importado_em",
        "importado_por",
    }
    executed = []
    dropped = []

    class FakeInspector:
        def get_columns(self, table_name):
            assert table_name == "tabela_mva"
            return _typed_columns(migration, existing)

    class FakeResult:
        def scalar_one(self):
            return 0

    class FakeBind:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, statement):
            executed.append(str(statement))
            return FakeResult()

    bind = FakeBind()

    class FakeOp:
        def get_bind(self):
            return bind

        def add_column(self, *_args, **_kwargs):
            pytest.fail("nenhuma coluna deveria ser adicionada")

        def alter_column(self, *_args, **_kwargs):
            pytest.fail("nenhum rename deveria ocorrer")

        def drop_column(self, table_name, column_name):
            dropped.append((table_name, column_name))

    migration.op = FakeOp()

    original_inspect = migration.sa.inspect
    migration.sa.inspect = lambda _bind: FakeInspector()
    try:
        migration.upgrade()
    finally:
        migration.sa.inspect = original_inspect

    sql = "\n".join(executed)

    assert "UPDATE tabela_mva" in sql
    assert "url_fonte = fonte_url" in sql
    assert "url_fonte IS NULL" in sql
    assert "fonte_url IS NOT NULL" in sql

    assert dropped == [
        ("tabela_mva", "fonte_url")
    ]
def test_migration_0043_fails_closed_before_narrowing_oversized_values():
    migration = _load_migration_0043()

    columns = [
        {"name": "id", "type": migration.sa.Integer()},
        {"name": "estado", "type": migration.sa.String()},
        {"name": "ncm", "type": migration.sa.String()},
        {"name": "mva", "type": migration.sa.Float()},
        {"name": "aliquota_interna", "type": migration.sa.Float()},
        {"name": "vigencia_inicio", "type": migration.sa.Date()},
        {"name": "vigencia_fim", "type": migration.sa.Date()},
        {"name": "fonte_legal", "type": migration.sa.String()},
        {
            "name": "nivel_confianca_fonte",
            "type": migration.sa.String(),
        },
        {"name": "url_fonte", "type": migration.sa.String()},
        {"name": "importado_em", "type": migration.sa.DateTime()},
        {"name": "importado_por", "type": migration.sa.String(length=100)},
    ]

    class FakeInspector:
        def get_columns(self, table_name):
            assert table_name == "tabela_mva"
            return columns

    class FakeResult:
        def scalar_one(self):
            return 1

    class FakeBind:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, _statement):
            return FakeResult()

    bind = FakeBind()

    class FakeOp:
        def get_bind(self):
            return bind

        def add_column(self, *_args, **_kwargs):
            pytest.fail("nenhuma coluna deveria ser adicionada")

        def alter_column(self, *_args, **_kwargs):
            pytest.fail(
                "nenhum tipo pode ser estreitado antes da catraca"
            )

    migration.op = FakeOp()

    original_inspect = migration.sa.inspect
    migration.sa.inspect = lambda _bind: FakeInspector()
    try:
        with pytest.raises(
            RuntimeError,
            match="values exceed canonical length",
        ):
            migration.upgrade()
    finally:
        migration.sa.inspect = original_inspect


def _typed_columns(migration, names):
    types = {
        "id": migration.sa.Integer(),
        "estado": migration.sa.String(),
        "ncm": migration.sa.String(),
        "mva": migration.sa.Float(),
        "aliquota_interna": migration.sa.Float(),
        "vigencia_inicio": migration.sa.Date(),
        "vigencia_fim": migration.sa.Date(),
        "fonte_legal": migration.sa.String(length=500),
        "nivel_confianca_fonte": migration.sa.String(length=40),
        "fonte_url": migration.sa.String(),
        "url_fonte": migration.sa.String(length=1000),
        "importado_em": migration.sa.DateTime(),
        "importado_por": migration.sa.String(length=100),
    }

    return [
        {
            "name": name,
            "type": types[name],
        }
        for name in sorted(names)
    ]
def test_migration_0043_fails_closed_on_oversized_legacy_fonte_url_before_rename():
    migration = _load_migration_0043()

    existing = {
        "id",
        "estado",
        "ncm",
        "mva",
        "aliquota_interna",
        "vigencia_inicio",
        "vigencia_fim",
        "fonte_legal",
        "nivel_confianca_fonte",
        "fonte_url",
        "importado_em",
        "importado_por",
    }

    class FakeInspector:
        def get_columns(self, table_name):
            assert table_name == "tabela_mva"
            return _typed_columns(migration, existing)

    class FakeResult:
        def scalar_one(self):
            return 1

    class FakeBind:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, _statement):
            return FakeResult()

    bind = FakeBind()

    class FakeOp:
        def get_bind(self):
            return bind

        def add_column(self, *_args, **_kwargs):
            pytest.fail("nenhuma coluna deveria ser adicionada")

        def alter_column(self, *_args, **_kwargs):
            pytest.fail(
                "fonte_url nao pode ser renomeada antes da catraca de tamanho"
            )

    migration.op = FakeOp()

    original_inspect = migration.sa.inspect
    migration.sa.inspect = lambda _bind: FakeInspector()
    try:
        with pytest.raises(
            RuntimeError,
            match="values exceed canonical length",
        ):
            migration.upgrade()
    finally:
        migration.sa.inspect = original_inspect
def test_migration_0043_normalizes_safe_unbounded_canonical_varchars():
    migration = _load_migration_0043()

    columns = [
        {"name": "id", "type": migration.sa.Integer()},
        {"name": "estado", "type": migration.sa.String()},
        {"name": "ncm", "type": migration.sa.String()},
        {"name": "mva", "type": migration.sa.Float()},
        {"name": "aliquota_interna", "type": migration.sa.Float()},
        {"name": "vigencia_inicio", "type": migration.sa.Date()},
        {"name": "vigencia_fim", "type": migration.sa.Date()},
        {"name": "fonte_legal", "type": migration.sa.String()},
        {
            "name": "nivel_confianca_fonte",
            "type": migration.sa.String(),
        },
        {"name": "url_fonte", "type": migration.sa.String()},
        {"name": "importado_em", "type": migration.sa.DateTime()},
        {
            "name": "importado_por",
            "type": migration.sa.String(length=100),
        },
    ]
    altered = []

    class FakeInspector:
        def get_columns(self, table_name):
            assert table_name == "tabela_mva"
            return columns

    class FakeResult:
        def scalar_one(self):
            return 0

    class FakeBind:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, statement):
            assert "char_length(" in str(statement)
            return FakeResult()

    bind = FakeBind()

    class FakeOp:
        def get_bind(self):
            return bind

        def add_column(self, *_args, **_kwargs):
            pytest.fail("nenhuma coluna deveria ser adicionada")

        def alter_column(
            self,
            table_name,
            column_name,
            **kwargs,
        ):
            altered.append(
                (
                    table_name,
                    column_name,
                    str(kwargs.get("type_")),
                )
            )

    migration.op = FakeOp()

    original_inspect = migration.sa.inspect
    migration.sa.inspect = lambda _bind: FakeInspector()
    try:
        migration.upgrade()
    finally:
        migration.sa.inspect = original_inspect

    assert altered == [
        ("tabela_mva", "fonte_legal", "VARCHAR(500)"),
        (
            "tabela_mva",
            "nivel_confianca_fonte",
            "VARCHAR(40)",
        ),
        ("tabela_mva", "url_fonte", "VARCHAR(1000)"),
    ]
def test_migration_0043_renames_legacy_url_with_canonical_length():
    migration = _load_migration_0043()

    existing = {
        "id",
        "estado",
        "ncm",
        "mva",
        "aliquota_interna",
        "vigencia_inicio",
        "vigencia_fim",
        "fonte_legal",
        "nivel_confianca_fonte",
        "fonte_url",
        "importado_em",
        "importado_por",
    }
    altered = []

    class FakeInspector:
        def get_columns(self, table_name):
            assert table_name == "tabela_mva"
            return _typed_columns(migration, existing)

    class FakeResult:
        def scalar_one(self):
            return 0

    class FakeBind:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, statement):
            assert "char_length(fonte_url)" in str(statement)
            return FakeResult()

    bind = FakeBind()

    class FakeOp:
        def get_bind(self):
            return bind

        def add_column(self, *_args, **_kwargs):
            pytest.fail("nenhuma coluna deveria ser adicionada")

        def alter_column(
            self,
            table_name,
            column_name,
            **kwargs,
        ):
            altered.append(
                (
                    table_name,
                    column_name,
                    kwargs.get("new_column_name"),
                    str(kwargs.get("type_")),
                )
            )

    migration.op = FakeOp()

    original_inspect = migration.sa.inspect
    migration.sa.inspect = lambda _bind: FakeInspector()
    try:
        migration.upgrade()
    finally:
        migration.sa.inspect = original_inspect

    legacy_calls = [
        call
        for call in altered
        if call[1] == "fonte_url"
    ]

    assert legacy_calls == [
        (
            "tabela_mva",
            "fonte_url",
            "url_fonte",
            "VARCHAR(1000)",
        )
    ]
