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
from app.schemas.adr020_bindings import ADR020BindingsContract


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


def _is_postgresql_unavailable(error):
    sqlstate = error.sqlstate
    return sqlstate is None or sqlstate == "57P03" or sqlstate.startswith("08")


@pytest.fixture(scope="session")
def postgresql_0029():
    name = f"mission-009a-int3a-{uuid.uuid4().hex[:12]}"
    database = f"adr020_{uuid.uuid4().hex[:12]}"
    password = uuid.uuid4().hex
    port = _free_port()
    container_id = None
    engine = None
    readiness_confirmed = False
    try:
        result = _run([
            "docker", "run", "--detach", "--name", name,
            "--label", "mission=MISSION-009A-INTENCAO-3A",
            "-e", "POSTGRES_USER=adr020", "-e", f"POSTGRES_PASSWORD={password}",
            "-e", f"POSTGRES_DB={database}", "-p", f"127.0.0.1:{port}:5432",
            "postgres:16-alpine",
        ])
        container_id = result.stdout.strip()
        url = f"postgresql+psycopg://adr020:{password}@127.0.0.1:{port}/{database}"
        plain_url = f"postgresql://adr020:{password}@127.0.0.1:{port}/{database}"
        deadline = time.monotonic() + 60
        consecutive_connections = 0
        last_unavailable = None
        while time.monotonic() < deadline:
            try:
                with psycopg.connect(plain_url, connect_timeout=2) as connection:
                    assert connection.execute("SELECT 1").fetchone() == (1,)
                consecutive_connections += 1
                if consecutive_connections >= 2:
                    readiness_confirmed = True
                    break
            except psycopg.OperationalError as exc:
                if not _is_postgresql_unavailable(exc):
                    raise
                consecutive_connections = 0
                last_unavailable = exc
            time.sleep(0.25)
        else:
            inspect = subprocess.run(
                ["docker", "inspect", name], text=True, capture_output=True,
                check=False,
            )
            logs = subprocess.run(
                ["docker", "logs", name], text=True, capture_output=True,
                check=False,
            )
            state = subprocess.run(
                [
                    "docker", "inspect", "--format",
                    "status={{.State.Status}} OOMKilled={{.State.OOMKilled}} "
                    "ExitCode={{.State.ExitCode}}",
                    name,
                ],
                text=True, capture_output=True, check=False,
            )
            raise AssertionError(
                "isolated PostgreSQL did not become SQL-ready before deadline\n"
                f"last availability error: {last_unavailable!r}\n"
                f"state: {state.stdout}{state.stderr}\n"
                f"inspect:\n{inspect.stdout}{inspect.stderr}\n"
                f"logs:\n{logs.stdout}{logs.stderr}"
            )

        assert readiness_confirmed
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
        "authority_bindings": {
            "bootstrap_authority_record_id": "bootstrap-authority",
            "bootstrap_authority_record_hash": _digest("bootstrap-authority"),
        },
        "policy_bindings": [
            {
                "policy_type": "normative_continuity",
                "policy_id": "continuity-policy",
                "policy_version": 1,
                "policy_hash": _digest("continuity-policy"),
                "policy_activation_id": "continuity-activation",
                "policy_activation_record_hash": _digest("continuity-activation"),
            },
            {
                "policy_type": "normative_precedence",
                "policy_id": "precedence-policy",
                "policy_version": 1,
                "policy_hash": _digest("precedence-policy"),
                "policy_activation_id": "precedence-activation",
                "policy_activation_record_hash": _digest("precedence-activation"),
            },
        ],
        "coverage_binding": {
            "coverage_subject_type": "coverage_contract",
            "coverage_contract_id": "coverage-contract",
            "contract_version": 1,
            "contract_hash": _digest("coverage-contract"),
            "coverage_contract_record_id": "coverage-record",
            "coverage_contract_record_hash": _digest("coverage-record"),
        },
        "continuity_binding": {
            "continuity_subject_type": "normative_continuity",
            "continuity_policy_id": "continuity-policy",
            "continuity_policy_version": 1,
            "continuity_policy_hash": _digest("continuity-policy"),
            "continuity_policy_activation_id": "continuity-activation",
            "continuity_policy_activation_record_hash": _digest("continuity-activation"),
        },
        "precedence_binding": {
            "precedence_subject_type": "normative_precedence",
            "precedence_policy_id": "precedence-policy",
            "precedence_policy_version": 1,
            "precedence_policy_hash": _digest("precedence-policy"),
            "precedence_policy_activation_id": "precedence-activation",
            "precedence_policy_activation_record_hash": _digest("precedence-activation"),
        },
        "gates_evidence": [
            {
                "gate_id": "integrity-gate",
                "gate_version": 1,
                "gate_hash": _digest("integrity-gate"),
                "gate_outcome": "approved",
                "evidence_record_id": "integrity-evidence",
                "evidence_record_hash": _digest("integrity-evidence"),
            }
        ],
    }


def _divergent_bindings(bindings, field):
    divergent = copy.deepcopy(bindings)
    if field == "authority_bindings":
        divergent[field]["bootstrap_authority_record_id"] = "other-bootstrap-authority"
    elif field == "policy_bindings":
        divergent[field].reverse()
    elif field == "coverage_binding":
        divergent[field]["coverage_contract_record_id"] = "other-coverage-record"
    elif field == "continuity_binding":
        record_hash = _digest("other-continuity-activation")
        divergent[field]["continuity_policy_activation_record_hash"] = record_hash
        divergent["policy_bindings"][0]["policy_activation_record_hash"] = record_hash
    elif field == "precedence_binding":
        record_hash = _digest("other-precedence-activation")
        divergent[field]["precedence_policy_activation_record_hash"] = record_hash
        divergent["policy_bindings"][1]["policy_activation_record_hash"] = record_hash
    else:
        divergent[field][0]["gate_outcome"] = "rejected"
    ADR020BindingsContract.model_validate(divergent, strict=True)
    return divergent


def test_positive_bindings_are_canonical_strict_and_preserve_input():
    payload = _bindings()
    original = copy.deepcopy(payload)
    validated = ADR020BindingsContract.model_validate(payload, strict=True)
    assert payload == original
    assert validated.model_dump() == original
    assert validated.policy_bindings[0].policy_type == "normative_continuity"
    assert validated.policy_bindings[1].policy_type == "normative_precedence"
    assert [gate.gate_id for gate in validated.gates_evidence] == ["integrity-gate"]


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
    reordered["authority_bindings"] = {
        "bootstrap_authority_record_hash": _digest("bootstrap-authority"),
        "bootstrap_authority_record_id": "bootstrap-authority",
    }
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationExecution), [exact, reordered])
    with engine.begin() as connection:
        visible = _decision(); connection.execute(insert(models.ActivationDecision), visible)
        connection.execute(insert(models.ActivationExecution), _execution(visible))


@pytest.mark.parametrize("field", BINDINGS)
def test_each_divergent_binding_is_rejected_and_rolled_back(postgresql_0029, field):
    engine = postgresql_0029["engine"]; decision = _seed(engine); row = _execution(decision)
    divergent = _divergent_bindings(_bindings(), field)
    for binding in BINDINGS:
        row[binding] = divergent[binding]
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
    reordered = _execution(decision); reordered["policy_bindings"].reverse()
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
    exact = _execution(decision); bad = _execution(decision)
    bad["policy_bindings"].reverse()
    ADR020BindingsContract.model_validate(
        {binding: bad[binding] for binding in BINDINGS}, strict=True,
    )

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
    bad = _execution(decision); bad["gates_evidence"][0]["gate_outcome"] = "rejected"
    ADR020BindingsContract.model_validate(
        {binding: bad[binding] for binding in BINDINGS}, strict=True,
    )
    with pytest.raises(psycopg.Error, match="bindings diverge"):
        copy_row(bad)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM activation_executions WHERE activation_execution_id=:id"), {"id": bad["activation_execution_id"]}) == 0
