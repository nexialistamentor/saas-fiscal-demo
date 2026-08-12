"""Prova PostgreSQL real da reconciliacao 0043 de tabela_mva."""

import importlib.util
import socket
import subprocess
import time
import uuid
from pathlib import Path

import psycopg
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_0043 = (
    ROOT
    / "migrations"
    / "versions"
    / "0043_reconcile_tabela_mva_schema.py"
)


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "test_tabela_mva_reconciliation_0043_postgresql",
        MIGRATION_0043,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Nao foi possivel carregar migration 0043")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _is_postgresql_unavailable(error):
    sqlstate = error.sqlstate
    return (
        sqlstate is None
        or sqlstate == "57P03"
        or sqlstate.startswith("08")
    )


@pytest.fixture(scope="module")
def postgresql_0043():
    name = f"mva-reconcile-{uuid.uuid4().hex[:12]}"
    database = f"mva_{uuid.uuid4().hex[:12]}"
    password = uuid.uuid4().hex
    port = _free_port()
    container_id = None
    engine = None

    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "--detach",
                "--name",
                name,
                "--label",
                "mission=SCHEMA-LINEAGE-DRIFT-P0-0043",
                "-e",
                "POSTGRES_USER=mva",
                "-e",
                f"POSTGRES_PASSWORD={password}",
                "-e",
                f"POSTGRES_DB={database}",
                "-p",
                f"127.0.0.1:{port}:5432",
                "postgres:16-alpine",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise AssertionError(
                f"docker run falhou: {result.stderr}"
            )

        container_id = result.stdout.strip()
        plain_url = (
            f"postgresql://mva:{password}"
            f"@127.0.0.1:{port}/{database}"
        )
        url = plain_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

        deadline = time.monotonic() + 60
        consecutive = 0
        last_error = None

        while time.monotonic() < deadline:
            try:
                with psycopg.connect(
                    plain_url,
                    connect_timeout=2,
                ) as conn:
                    assert conn.execute(
                        "SELECT 1"
                    ).fetchone() == (1,)
                consecutive += 1
                if consecutive >= 2:
                    break
            except psycopg.OperationalError as exc:
                if not _is_postgresql_unavailable(exc):
                    raise
                consecutive = 0
                last_error = exc
                time.sleep(0.25)
        else:
            raise AssertionError(
                f"PostgreSQL nao ficou pronto: {last_error!r}"
            )

        engine = create_engine(url)
        yield engine

    finally:
        if engine is not None:
            engine.dispose()
        if container_id is not None:
            subprocess.run(
                ["docker", "rm", "--force", name],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )


def test_postgresql_0043_reconciles_production_minimal_shape(
    postgresql_0043,
):
    engine = postgresql_0043

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tabela_mva"))

        conn.execute(
            text(
                """
                CREATE TABLE tabela_mva (
                    id SERIAL PRIMARY KEY,
                    estado VARCHAR,
                    ncm VARCHAR,
                    mva DOUBLE PRECISION,
                    aliquota_interna DOUBLE PRECISION,
                    vigencia_inicio DATE,
                    vigencia_fim DATE
                )
                """
            )
        )

        inserted_id = conn.execute(
            text(
                """
                INSERT INTO tabela_mva (
                    estado,
                    ncm,
                    mva,
                    aliquota_interna
                )
                VALUES (
                    'SP',
                    '12345678',
                    42.5,
                    18.0
                )
                RETURNING id
                """
            )
        ).scalar_one()

        operations = Operations(
            MigrationContext.configure(conn)
        )
        migration = _load_migration()
        migration.op = operations
        migration.upgrade()

        columns = {
            column["name"]: column["type"]
            for column in inspect(conn).get_columns("tabela_mva")
        }

        assert "fonte_url" not in columns
        assert columns["fonte_legal"].length == 500
        assert columns["nivel_confianca_fonte"].length == 40
        assert columns["url_fonte"].length == 1000
        assert columns["importado_por"].length == 100
        assert "importado_em" in columns

        row = conn.execute(
            text(
                """
                SELECT estado, ncm, mva, aliquota_interna
                FROM tabela_mva
                WHERE id = :id
                """
            ),
            {"id": inserted_id},
        ).one()

        assert row == ("SP", "12345678", 42.5, 18.0)


def test_postgresql_0043_reconciles_legacy_fonte_url_and_preserves_data(
    postgresql_0043,
):
    engine = postgresql_0043

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tabela_mva"))

        conn.execute(
            text(
                """
                CREATE TABLE tabela_mva (
                    id SERIAL PRIMARY KEY,
                    estado VARCHAR,
                    ncm VARCHAR,
                    mva DOUBLE PRECISION,
                    aliquota_interna DOUBLE PRECISION,
                    vigencia_inicio DATE,
                    vigencia_fim DATE,
                    fonte_legal VARCHAR,
                    nivel_confianca_fonte VARCHAR,
                    fonte_url VARCHAR
                )
                """
            )
        )

        conn.execute(
            text(
                """
                INSERT INTO tabela_mva (
                    estado,
                    ncm,
                    mva,
                    aliquota_interna,
                    fonte_legal,
                    nivel_confianca_fonte,
                    fonte_url
                )
                VALUES (
                    'MG',
                    '87654321',
                    55.25,
                    17.0,
                    'Decreto estadual de teste',
                    'alta',
                    'https://legado.exemplo/mva'
                )
                """
            )
        )

        operations = Operations(
            MigrationContext.configure(conn)
        )
        migration = _load_migration()
        migration.op = operations
        migration.upgrade()

        columns = {
            column["name"]: column["type"]
            for column in inspect(conn).get_columns("tabela_mva")
        }

        assert "fonte_url" not in columns
        assert columns["fonte_legal"].length == 500
        assert columns["nivel_confianca_fonte"].length == 40
        assert columns["url_fonte"].length == 1000
        assert columns["importado_por"].length == 100
        assert "importado_em" in columns

        row = conn.execute(
            text(
                """
                SELECT
                    estado,
                    ncm,
                    fonte_legal,
                    nivel_confianca_fonte,
                    url_fonte
                FROM tabela_mva
                WHERE id = 1
                """
            )
        ).one()

        assert row == (
            "MG",
            "87654321",
            "Decreto estadual de teste",
            "alta",
            "https://legado.exemplo/mva",
        )

def test_postgresql_0043_merges_coexisting_urls_and_drops_legacy(
    postgresql_0043,
):
    engine = postgresql_0043

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tabela_mva"))

        conn.execute(
            text(
                """
                CREATE TABLE tabela_mva (
                    id SERIAL PRIMARY KEY,
                    estado VARCHAR,
                    ncm VARCHAR,
                    mva DOUBLE PRECISION,
                    aliquota_interna DOUBLE PRECISION,
                    vigencia_inicio DATE,
                    vigencia_fim DATE,
                    fonte_legal VARCHAR(500),
                    nivel_confianca_fonte VARCHAR(40),
                    fonte_url VARCHAR,
                    url_fonte VARCHAR(1000),
                    importado_em TIMESTAMP,
                    importado_por VARCHAR(100)
                )
                """
            )
        )

        inserted_id = conn.execute(
            text(
                """
                INSERT INTO tabela_mva (
                    estado,
                    ncm,
                    fonte_url,
                    url_fonte
                )
                VALUES (
                    'RJ',
                    '11223344',
                    'https://legado.exemplo/rj',
                    NULL
                )
                RETURNING id
                """
            )
        ).scalar_one()

        operations = Operations(
            MigrationContext.configure(conn)
        )
        migration = _load_migration()
        migration.op = operations
        migration.upgrade()

        columns = {
            column["name"]: column["type"]
            for column in inspect(conn).get_columns("tabela_mva")
        }

        assert "fonte_url" not in columns
        assert columns["url_fonte"].length == 1000

        preserved_url = conn.execute(
            text(
                """
                SELECT url_fonte
                FROM tabela_mva
                WHERE id = :id
                """
            ),
            {"id": inserted_id},
        ).scalar_one()

        assert preserved_url == "https://legado.exemplo/rj"
