"""PostgreSQL 17 lifecycle proof for reconciliation revision 0044."""

import os
import socket
import subprocess
import time
import uuid
import importlib.util
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[1]


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def pg17(monkeypatch_module):
    name = f"pilot-0044-{uuid.uuid4().hex[:10]}"
    password = uuid.uuid4().hex
    port = _free_port()
    result = subprocess.run(
        ["docker", "run", "--detach", "--name", name,
         "-e", "POSTGRES_USER=pilot", "-e", f"POSTGRES_PASSWORD={password}",
         "-e", "POSTGRES_DB=pilot", "-p", f"127.0.0.1:{port}:5432",
         "postgres:17-alpine"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    plain = f"postgresql://pilot:{password}@127.0.0.1:{port}/pilot"
    url = plain.replace("postgresql://", "postgresql+psycopg://", 1)
    try:
        deadline = time.monotonic() + 60
        while True:
            try:
                with psycopg.connect(plain, connect_timeout=2) as connection:
                    assert connection.execute("SHOW server_version_num").fetchone()[0].startswith("17")
                break
            except psycopg.OperationalError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)
        monkeypatch_module.setenv("DATABASE_URL", url)
        yield create_engine(url)
    finally:
        subprocess.run(["docker", "rm", "--force", name], cwd=ROOT,
                       text=True, capture_output=True, check=False)


@pytest.fixture(scope="module")
def monkeypatch_module():
    patch = pytest.MonkeyPatch()
    yield patch
    patch.undo()


def _alembic(revision):
    command.upgrade(Config(str(ROOT / "alembic.ini")), revision)


def _constraint_expression(conn):
    return conn.execute(text("""
        SELECT pg_get_expr(con.conbin, con.conrelid, false)
        FROM pg_constraint AS con
        JOIN pg_class AS rel ON rel.oid = con.conrelid
        WHERE rel.relname = 'usuarios'
          AND con.conname = 'ck_usuarios_role_valido'
          AND con.contype = 'c'
          AND con.convalidated
    """)).scalar_one()


def _migration_role_expression():
    path = ROOT / "migrations" / "versions" / "0044_pilot_schema_blockers.py"
    spec = importlib.util.spec_from_file_location("migration_0044_pg", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._CANONICAL_ROLE_CHECK


def _canonical_state(conn):
    return (
        conn.execute(text("""
            SELECT table_name, column_name, is_nullable, udt_name
            FROM information_schema.columns
            WHERE (table_name, column_name) IN (
                ('usuarios', 'consulta_paga'), ('planos', 'limite_analises'))
            ORDER BY table_name, column_name
        """)).all(),
        _constraint_expression(conn),
    )


def test_pg17_greenfield_0000_to_0044_is_noop_on_baseline_objects(pg17):
    _alembic("0043_reconcile_tabela_mva_schema")
    with pg17.connect() as conn:
        before = _canonical_state(conn)
        # Exact pg_get_expr(..., false) representation produced by baseline 0000.
        assert before[1] == _migration_role_expression()
    _alembic("0044_pilot_schema_blockers")
    with pg17.connect() as conn:
        assert _canonical_state(conn) == before
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0044_pilot_schema_blockers"


def test_pg17_known_0043_drift_repair_downgrade_and_reupgrade(pg17):
    command.downgrade(Config(str(ROOT / "alembic.ini")), "0043_reconcile_tabela_mva_schema")
    with pg17.begin() as conn:
        conn.execute(text("ALTER TABLE usuarios ALTER COLUMN consulta_paga DROP NOT NULL"))
        conn.execute(text("ALTER TABLE planos ALTER COLUMN limite_analises DROP NOT NULL"))
        conn.execute(text("ALTER TABLE usuarios DROP CONSTRAINT ck_usuarios_role_valido"))
        conn.execute(text("INSERT INTO planos (id, nome, limite_cnpjs, limite_analises) VALUES (900044, 'fixture-0044', 2, 77)"))
        conn.execute(text("INSERT INTO usuarios (id, email, hashed_password, plano_id, consulta_paga, role) VALUES (900044, 'fixture0044@example.test', 'hash', 900044, false, 'contador')"))

    _alembic("0044_pilot_schema_blockers")
    with pg17.connect() as conn:
        repaired = _canonical_state(conn)
        assert repaired[0] == [("planos", "limite_analises", "NO", "int4"), ("usuarios", "consulta_paga", "NO", "bool")]
        assert conn.execute(text("SELECT limite_analises FROM planos WHERE id=900044")).scalar_one() == 77
        assert conn.execute(text("SELECT consulta_paga, role FROM usuarios WHERE id=900044")).one() == (False, "contador")

    command.downgrade(Config(str(ROOT / "alembic.ini")), "0043_reconcile_tabela_mva_schema")
    with pg17.connect() as conn:
        assert _canonical_state(conn) == repaired
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0043_reconcile_tabela_mva_schema"

    _alembic("0044_pilot_schema_blockers")
    with pg17.connect() as conn:
        assert _canonical_state(conn) == repaired
