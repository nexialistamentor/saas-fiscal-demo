import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.routers.empresa_router import EmpresaCnpjUpdate, completar_cnpj_mei


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations/versions/0054_empresa_cnpj_unique.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "test_migration_0054_module",
        MIGRATION,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Nao foi possivel carregar migration 0054")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_0054_existe_para_fechar_unicidade_cnpj():
    assert MIGRATION.exists(), (
        "0054 ausente: empresas.cnpj continua sem autoridade "
        "de unicidade no banco"
    )


def test_0054_limpa_placeholder_antes_de_criar_unique():
    migration = _load_migration()
    eventos = []

    class Result:
        def scalar_one(self):
            return 0

    class Bind:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, statement, params=None):
            sql = str(statement)

            if "UPDATE empresas" in sql:
                eventos.append(("cleanup", params))
                return Result()

            if "HAVING COUNT(*) > 1" in sql:
                eventos.append(("duplicate_check", None))
                return Result()

            raise AssertionError(f"SQL inesperado: {sql}")

    bind = Bind()

    class FakeOp:
        def get_bind(self):
            return bind

        def create_unique_constraint(self, name, table, columns):
            eventos.append(("unique", name, table, tuple(columns)))

    migration.op = FakeOp()
    migration.upgrade()

    assert eventos == [
        (
            "cleanup",
            {"placeholder": "00000000000000"},
        ),
        ("duplicate_check", None),
        (
            "unique",
            "uq_empresas_cnpj",
            "empresas",
            ("cnpj",),
        ),
    ]


def test_0054_falha_fechado_se_duplicidade_real_restante():
    migration = _load_migration()

    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one(self):
            return self.value

    class Bind:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, statement, params=None):
            sql = str(statement)

            if "UPDATE empresas" in sql:
                return Result(0)

            if "HAVING COUNT(*) > 1" in sql:
                return Result(1)

            raise AssertionError(f"SQL inesperado: {sql}")

    bind = Bind()

    class FakeOp:
        def get_bind(self):
            return bind

        def create_unique_constraint(self, *_args, **_kwargs):
            pytest.fail(
                "UNIQUE nao pode ser criado enquanto houver duplicidade"
            )

    migration.op = FakeOp()

    with pytest.raises(
        RuntimeError,
        match="duplicate non-null empresas.cnpj remain",
    ):
        migration.upgrade()


def test_0054_rejeita_banco_nao_postgresql():
    migration = _load_migration()

    class FakeOp:
        def get_bind(self):
            return SimpleNamespace(
                dialect=SimpleNamespace(name="sqlite")
            )

        def create_unique_constraint(self, *_args, **_kwargs):
            pytest.fail("DDL nao deve ocorrer fora de PostgreSQL")

    migration.op = FakeOp()

    with pytest.raises(RuntimeError, match="0054 requires PostgreSQL"):
        migration.upgrade()


class _FakeQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return None


class _RaceDb:
    def __init__(self):
        self.rollback_called = False

    def query(self, *_args, **_kwargs):
        return _FakeQuery()

    def commit(self):
        raise IntegrityError(
            "unique race",
            params={},
            orig=Exception("duplicate key"),
        )

    def rollback(self):
        self.rollback_called = True

    def refresh(self, *_args, **_kwargs):
        pytest.fail("refresh nao pode ocorrer apos conflito de unicidade")


def test_writer_converte_race_de_unicidade_em_409():
    empresa = SimpleNamespace(
        id=777,
        regime_tributario="mei",
        cnpj=None,
        status_empresa="ativa",
        optante_mei=False,
    )
    db = _RaceDb()

    with pytest.raises(HTTPException) as exc:
        completar_cnpj_mei(
            body=EmpresaCnpjUpdate(cnpj="12345678000190"),
            empresa=empresa,
            db=db,
        )

    assert exc.value.status_code == 409
    assert db.rollback_called is True
