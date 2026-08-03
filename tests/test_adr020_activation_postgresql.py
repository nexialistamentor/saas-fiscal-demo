import ast
import copy
import hashlib
import importlib.util
import io
import json
import os
import re
import socket
import subprocess
import time
import uuid
from pathlib import Path

import psycopg
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, insert, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app import models


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "0029_adr020_activation_execution_gate.py"
HISTORICAL = ROOT / "migrations" / "versions" / "0024_adr020_activation_foundation.py"
ATOMIC_REPAIR = ROOT / "migrations" / "versions" / "0028_adr020_atomic_activation_trigger_fix.py"
ATOMIC_REVISION = "0028_adr020_atomic_trigger_fix"
REVISION = "0029_adr020_activation_exec_gate"
FUNCTION = "adr020_validate_activation_execution_decision_bindings"
HISTORICAL_FUNCTION = "adr020_validate_atomic_activation"
TRIGGER = "trg_activation_executions_exact_decision_bindings"
HISTORICAL_TRIGGER = "trg_activation_executions_validate_insert"
BINDINGS = (
    "authority_bindings",
    "policy_bindings",
    "coverage_binding",
    "continuity_binding",
    "precedence_binding",
    "gates_evidence",
)


def _load_migration(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bootstrap_adr020_activation(connection):
    # Exact FK predecessors required by 0024, reduced to the columns and
    # candidate keys that 0024 references. Names and types derive from 0022.
    connection.execute(text("""
        CREATE TABLE policy_versions (
            policy_id varchar(64) NOT NULL,
            policy_version integer NOT NULL,
            policy_hash varchar(64) NOT NULL,
            CONSTRAINT uq_policy_versions_exact_subject
                UNIQUE (policy_id, policy_version, policy_hash)
        );
        CREATE TABLE policy_decisions (
            decision_id varchar(64) PRIMARY KEY
        );
        CREATE TABLE bootstrap_authority_records (
            bootstrap_authority_record_id varchar(64) PRIMARY KEY
        );
        CREATE FUNCTION adr020_reject_append_only_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'ADR-020 append-only table % does not allow %',
                TG_TABLE_NAME,
                TG_OP
                USING ERRCODE = '55000';
        END;
        $$;
        CREATE TABLE alembic_version (
            version_num varchar(32) NOT NULL PRIMARY KEY
        );
        INSERT INTO alembic_version (version_num)
        VALUES ('0023_adr020_coverage');
    """))

    operations = Operations(MigrationContext.configure(connection))
    migration_0024 = _load_migration(HISTORICAL, "test_physical_0024")
    migration_0024.op = operations
    migration_0024.upgrade()
    connection.execute(text("""
        UPDATE alembic_version
        SET version_num = '0024_adr020_activation'
        WHERE version_num = '0023_adr020_coverage'
    """))

    # 0025-0027 are statically audited for non-interference with the two
    # activation tables. This stamp is lineage only, not physical execution.
    connection.execute(text("""
        UPDATE alembic_version
        SET version_num = '0027_adr020_calc_replay'
        WHERE version_num = '0024_adr020_activation'
    """))
    migration_0028 = _load_migration(ATOMIC_REPAIR, "test_physical_0028")
    migration_0028.op = operations
    migration_0028.upgrade()
    connection.execute(text("""
        UPDATE alembic_version
        SET version_num = :atomic_revision
        WHERE version_num = '0027_adr020_calc_replay'
    """), {"atomic_revision": ATOMIC_REVISION})

    migration_0029 = _load_migration(MIGRATION, "test_physical_0029")
    migration_0029.op = operations
    migration_0029.upgrade()
    connection.execute(text("""
        UPDATE alembic_version
        SET version_num = :revision
        WHERE version_num = :atomic_revision
    """), {"revision": REVISION, "atomic_revision": ATOMIC_REVISION})


def _source():
    return MIGRATION.read_text(encoding="utf-8")


def _run(command, **kwargs):
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def postgresql_0029():
    name = f"mission-009a-int10b-{uuid.uuid4().hex[:12]}"
    database = f"adr020_{uuid.uuid4().hex[:12]}"
    password = uuid.uuid4().hex
    port = _free_port()
    container_id = None
    engine = None
    try:
        result = _run([
            "docker", "run", "--detach", "--rm", "--name", name,
            "--label", "mission=MISSION-009A-INTENCAO-10B",
            "-e", "POSTGRES_USER=adr020", "-e", f"POSTGRES_PASSWORD={password}",
            "-e", f"POSTGRES_DB={database}", "-p", f"127.0.0.1:{port}:5432",
            "postgres:16-alpine",
        ])
        container_id = result.stdout.strip()
        url = f"postgresql+psycopg://adr020:{password}@127.0.0.1:{port}/{database}"
        plain_url = f"postgresql://adr020:{password}@127.0.0.1:{port}/{database}"
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            ready = subprocess.run(
                ["docker", "exec", name, "pg_isready", "-U", "adr020", "-d", database],
                text=True, capture_output=True,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise AssertionError("isolated PostgreSQL did not become ready")

        engine = create_engine(url)
        with engine.begin() as connection:
            _bootstrap_adr020_activation(connection)
        env = os.environ.copy()
        env["DATABASE_URL"] = url
        yield {
            "name": name, "container_id": container_id, "database": database,
            "url": url, "plain_url": plain_url, "engine": engine, "env": env,
        }
    finally:
        if engine is not None:
            engine.dispose()
        if container_id is not None:
            subprocess.run(
                ["docker", "rm", "--force", name], text=True, capture_output=True,
                check=False,
            )


def _digest(label):
    return hashlib.sha256(label.encode()).hexdigest()


def _bindings():
    return {
        "authority_bindings": {"roles": ["auditor", "operator"], "source": {"v": 1, "id": "authority"}},
        "policy_bindings": {"policies": [{"version": 3, "id": "p-1"}, {"version": 1, "id": "p-2"}]},
        "coverage_binding": {"domains": ["iva", "irs"], "complete": True},
        "continuity_binding": {"previous": None, "sequence": [1, 2]},
        "precedence_binding": {"order": ["constitution", "law"], "strict": True},
        "gates_evidence": {"checks": [{"passed": True, "name": "integrity"}], "count": 1},
    }


def _decision(suffix=None, bindings=None):
    suffix = suffix or uuid.uuid4().hex
    values = copy.deepcopy(bindings or _bindings())
    values.update({
        "activation_decision_id": f"decision-{suffix}", "decision_action": "activate",
        "decision_outcome": "approved", "authorization_class": "humana_delegada",
        "actor": "integration-auditor", "institutional_role": "fiscal_authority",
        "target_scope": {"country": "PT", "taxes": ["iva", "irs"]},
        "scope_hash": _digest(f"scope-{suffix}"),
        "target_manifest": {"rules": ["r1", "r2"]},
        "target_manifest_hash": _digest(f"manifest-{suffix}"),
        "rationale": "physical PostgreSQL proof", "evidence": {"proof": True},
        "previous_activation_decision_id": None,
        "idempotency_key": f"decision-idem-{suffix}", "record_hash": _digest(f"decision-{suffix}"),
    })
    return values


def _execution(decision, suffix=None):
    suffix = suffix or uuid.uuid4().hex
    values = {key: copy.deepcopy(decision[key]) for key in BINDINGS}
    values.update({
        "activation_execution_id": f"execution-{suffix}",
        "activation_decision_id": decision["activation_decision_id"],
        "activation_decision_record_hash": decision["record_hash"],
        "decision_outcome": "approved", "decision_action": "activate",
        "authorization_class": "humana_delegada", "execution_mode": "manual",
        "state": "pending", "scope_hash": decision["scope_hash"],
        "target_manifest_hash": decision["target_manifest_hash"], "attempt_number": 1,
        "actor_or_worker": "integration-worker", "lease_id": f"lease-{suffix}",
        "fencing_token": 1, "idempotency_key": f"execution-idem-{suffix}",
        "started_at": None, "finished_at": None, "structured_result": None,
        "structured_error": None, "provenance": {"test": "MISSION-009A"},
        "record_hash": _digest(f"execution-{suffix}"),
    })
    return values


def _seed(engine, decision=None):
    decision = decision or _decision()
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationDecision), decision)
    return decision


def _assert_db_rejects(call, engine, execution_id):
    with pytest.raises(DBAPIError) as caught:
        call()
    assert "ADR-020 activation execution bindings diverge" in str(caught.value)
    with engine.connect() as connection:
        count = connection.scalar(text(
            "SELECT count(*) FROM activation_executions WHERE activation_execution_id=:id"
        ), {"id": execution_id})
    assert count == 0


def test_migration_exists_with_sovereign_gate_objects():
    assert MIGRATION.exists(), "prospective migration 0029 is absent"
    source = _source()
    assert FUNCTION in source
    assert TRIGGER in source


def test_exact_revision_lineage_and_postgresql_only_guard():
    source = _source()
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {"revision": REVISION, "down_revision": ATOMIC_REVISION}
    assert len(assignments["revision"]) == 32
    assert 'dialect.name != "postgresql"' in source
    assert "PostgreSQL-only" in source


def test_gate_is_exact_before_insert_and_preserves_historical_trigger():
    source = _source(); lowered = source.lower()
    assert source.count(f"{FUNCTION}()") == 2
    assert source.count(TRIGGER) == 1
    assert re.search(rf"CREATE\s+TRIGGER\s+{TRIGGER}\s+BEFORE\s+INSERT\s+ON\s+activation_executions\s+FOR\s+EACH\s+ROW", source, re.I)
    historical_source = HISTORICAL.read_text(encoding="utf-8")
    assert 'for table in ("activation_executions","activation_generations")' in historical_source
    assert "trg_{table}_validate_insert BEFORE INSERT" in historical_source
    assert "drop trigger" not in lowered


def test_lookup_uses_exact_id_hash_pair_and_six_jsonb_comparisons():
    lowered = _source().lower()
    assert "activation_decision_id = new.activation_decision_id" in lowered
    assert "record_hash = new.activation_decision_record_hash" in lowered
    assert lowered.count("is distinct from") == 6
    for binding in BINDINGS:
        assert f"new.{binding} is distinct from sovereign_decision.{binding}" in lowered
    for floating in ("current", "latest", "newest", "fallback", "order by", "limit 1"):
        assert floating not in lowered
    assert "into strict" in lowered and "no_data_found" in lowered and "too_many_rows" in lowered


def test_upgrade_only_creates_gate_objects_and_downgrade_is_irreversible():
    lowered = _source().lower()
    assert "raise runtimeerror" in lowered and "irreversible" in lowered
    for fragment in ("op.create_table", "op.add_column", "op.alter_column", "op.drop_", "drop function", "drop trigger", "delete from", "update activation_"):
        assert fragment not in lowered


def test_historical_migrations_are_not_reimplemented_or_targeted():
    source = _source().lower()
    assert "0024_adr020_activation_foundation.py" not in source
    assert "alter table" not in source


def test_real_postgresql_revision_functions_and_both_triggers(postgresql_0029):
    engine = postgresql_0029["engine"]
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == REVISION
        assert connection.scalar(text("SELECT to_regprocedure(:name) IS NOT NULL"), {"name": f"{FUNCTION}()"})
        assert connection.scalar(text("SELECT to_regprocedure(:name) IS NOT NULL"), {"name": f"{HISTORICAL_FUNCTION}()"})
        triggers = set(connection.scalars(text("SELECT tgname FROM pg_trigger WHERE tgrelid='activation_executions'::regclass AND NOT tgisinternal")))
    assert {TRIGGER, HISTORICAL_TRIGGER} <= triggers


def test_real_postgresql_downgrade_is_irreversible_and_preserves_objects(postgresql_0029):
    result = subprocess.run(
        ["python", "-m", "alembic", "downgrade", "0027_adr020_calc_replay"],
        cwd=ROOT, env=postgresql_0029["env"], text=True, capture_output=True,
    )
    assert result.returncode != 0
    assert "RuntimeError" in result.stderr and "irreversible" in result.stderr
    with postgresql_0029["engine"].connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == REVISION
        assert connection.scalar(text("SELECT to_regprocedure(:name) IS NOT NULL"), {"name": f"{FUNCTION}()"})
        assert connection.scalar(text("SELECT count(*) FROM pg_trigger WHERE tgname=:name"), {"name": TRIGGER}) == 1
        assert connection.scalar(text("SELECT count(*) FROM pg_trigger WHERE tgname=:name"), {"name": HISTORICAL_TRIGGER}) == 1
        assert connection.scalar(text("SELECT to_regprocedure(:name) IS NOT NULL"), {"name": f"{HISTORICAL_FUNCTION}()"})


def test_exact_bindings_key_order_and_visible_decision_are_accepted(postgresql_0029):
    engine = postgresql_0029["engine"]
    decision = _seed(engine)
    exact = _execution(decision)
    reordered = _execution(decision)
    reordered["authority_bindings"] = {"source": {"id": "authority", "v": 1}, "roles": ["auditor", "operator"]}
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationExecution), [exact, reordered])
    with engine.begin() as connection:
        visible = _decision(); connection.execute(insert(models.ActivationDecision), visible)
        connection.execute(insert(models.ActivationExecution), _execution(visible))


@pytest.mark.parametrize("field", BINDINGS)
def test_each_divergent_binding_is_rejected_and_rolled_back(postgresql_0029, field):
    engine = postgresql_0029["engine"]; decision = _seed(engine); row = _execution(decision)
    row[field] = {"divergent": True}
    _assert_db_rejects(lambda: _connection_insert(engine, row), engine, row["activation_execution_id"])


def _connection_insert(engine, row):
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationExecution), row)


def test_missing_decision_and_wrong_decision_hash_are_rejected(postgresql_0029):
    engine = postgresql_0029["engine"]
    missing_decision = _decision(); missing = _execution(missing_decision)
    with pytest.raises(DBAPIError):
        _connection_insert(engine, missing)
    decision = _seed(engine); wrong = _execution(decision); wrong["activation_decision_record_hash"] = _digest("wrong")
    with pytest.raises(DBAPIError):
        _connection_insert(engine, wrong)


def test_reordered_arrays_and_incompatible_null_are_rejected(postgresql_0029):
    engine = postgresql_0029["engine"]; decision = _seed(engine)
    reordered = _execution(decision); reordered["authority_bindings"]["roles"].reverse()
    _assert_db_rejects(lambda: _connection_insert(engine, reordered), engine, reordered["activation_execution_id"])
    null_row = _execution(decision); null_row["coverage_binding"] = None
    with pytest.raises(DBAPIError):
        _connection_insert(engine, null_row)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM activation_executions WHERE activation_execution_id=:id"), {"id": null_row["activation_execution_id"]}) == 0


def test_unapproved_execution_is_rejected_by_historical_trigger(postgresql_0029):
    engine = postgresql_0029["engine"]
    decision = _seed(engine)
    row = _execution(decision)
    row["decision_outcome"] = "rejected"
    with pytest.raises(DBAPIError, match="only approved decision is executable"):
        _connection_insert(engine, row)
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT count(*) FROM activation_executions WHERE activation_execution_id=:id"
        ), {"id": row["activation_execution_id"]}) == 0


def _orm_object(row):
    return models.ActivationExecution(**copy.deepcopy(row))


@pytest.mark.parametrize("path", [
    "session_add", "bulk_save_objects", "bulk_insert_mappings", "session_execute",
    "connection_execute", "table_insert", "raw_sql",
])
def test_all_sqlalchemy_and_sql_bypasses_accept_exact_and_reject_divergence(postgresql_0029, path):
    engine = postgresql_0029["engine"]; decision = _seed(engine)
    exact = _execution(decision); bad = _execution(decision); bad["policy_bindings"] = {"divergent": True}

    def execute(row):
        if path == "session_add":
            with Session(engine) as session:
                session.add(_orm_object(row)); session.commit()
        elif path == "bulk_save_objects":
            with Session(engine) as session:
                session.bulk_save_objects([_orm_object(row)]); session.commit()
        elif path == "bulk_insert_mappings":
            with Session(engine) as session:
                session.bulk_insert_mappings(models.ActivationExecution, [row]); session.commit()
        elif path == "session_execute":
            with Session(engine) as session:
                session.execute(insert(models.ActivationExecution), [row]); session.commit()
        elif path in {"connection_execute", "table_insert"}:
            with engine.begin() as connection:
                statement = insert(models.ActivationExecution) if path == "connection_execute" else models.ActivationExecution.__table__.insert()
                connection.execute(statement, row)
        else:
            columns = list(row)
            params = {key: json.dumps(value) if key in BINDINGS or key in {"structured_result", "structured_error", "provenance"} and value is not None else value for key, value in row.items()}
            casts = [f"CAST(:{key} AS jsonb)" if key in BINDINGS or key in {"structured_result", "structured_error", "provenance"} and row[key] is not None else f":{key}" for key in columns]
            with engine.begin() as connection:
                connection.execute(text(f"INSERT INTO activation_executions ({','.join(columns)}) VALUES ({','.join(casts)})"), params)

    execute(exact)
    if path == "session_add":
        with pytest.raises((ValueError, DBAPIError)):
            execute(bad)
    else:
        _assert_db_rejects(lambda: execute(bad), engine, bad["activation_execution_id"])


def test_copy_from_accepts_exact_and_trigger_rejects_divergence(postgresql_0029):
    engine = postgresql_0029["engine"]; decision = _seed(engine)
    columns = list(_execution(decision))

    def copy_row(row):
        buffer = io.StringIO()
        encoded = []
        for key in columns:
            value = row[key]
            if value is None:
                encoded.append(r"\N")
            elif key in BINDINGS or key in {"structured_result", "structured_error", "provenance"}:
                encoded.append(json.dumps(value, separators=(",", ":")))
            else:
                encoded.append(str(value))
        buffer.write("\t".join(encoded) + "\n"); buffer.seek(0)
        with psycopg.connect(postgresql_0029["plain_url"]) as connection:
            with connection.cursor() as cursor:
                with cursor.copy(f"COPY activation_executions ({','.join(columns)}) FROM STDIN") as copier:
                    copier.write(buffer.read())

    copy_row(_execution(decision))
    bad = _execution(decision); bad["gates_evidence"] = {"divergent": True}
    with pytest.raises(psycopg.Error, match="bindings diverge"):
        copy_row(bad)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM activation_executions WHERE activation_execution_id=:id"), {"id": bad["activation_execution_id"]}) == 0
