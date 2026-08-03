import ast
import copy
from datetime import datetime, timezone
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
from sqlalchemy import create_engine, insert, null, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.schemas.adr020_bindings import ADR020BindingsContract


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "0029_adr020_activation_execution_gate.py"
POLICY_BINDING_MIGRATION = ROOT / "migrations" / "versions" / "0030_adr020_policy_binding_gate.py"
BOOTSTRAP_BINDING_MIGRATION = ROOT / "migrations" / "versions" / "0031_adr020_bootstrap_binding_gate.py"
POLICY_FOUNDATION = ROOT / "migrations" / "versions" / "0022_adr020_policy_foundation.py"
HISTORICAL = ROOT / "migrations" / "versions" / "0024_adr020_activation_foundation.py"
ATOMIC_REPAIR = ROOT / "migrations" / "versions" / "0028_adr020_atomic_activation_trigger_fix.py"
ATOMIC_REVISION = "0028_adr020_atomic_trigger_fix"
REVISION = "0029_adr020_activation_exec_gate"
POLICY_BINDING_REVISION = "0030_adr020_policy_binding_gate"
BOOTSTRAP_BINDING_REVISION = "0031_adr020_bootstrap_binding"
BOOTSTRAP_UNIQUE = "uq_bootstrap_authority_records_exact_record"
BOOTSTRAP_FK = "fk_policy_activation_executions_exact_bootstrap_record"
POLICY_BINDING_FUNCTION = "adr020_validate_policy_binding_activations"
POLICY_BINDING_TRIGGER = "trg_adr020_validate_policy_binding_activations"
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
    # The append-only function is the sole physical predecessor from 0021
    # required by the real 0022 and 0024 upgrades in this isolated bootstrap.
    connection.execute(text("""
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
        VALUES ('0021_adr020_relation_foundation');
    """))

    operations = Operations(MigrationContext.configure(connection))
    migration_0022 = _load_migration(POLICY_FOUNDATION, "test_physical_0022")
    migration_0022.op = operations
    migration_0022.upgrade()
    connection.execute(text("""
        UPDATE alembic_version
        SET version_num = '0022_adr020_policy'
        WHERE version_num = '0021_adr020_relation_foundation'
    """))

    # 0023 is statically audited and stamped because none of its coverage
    # objects is referenced by the tables or binding relation under test.
    connection.execute(text("""
        UPDATE alembic_version
        SET version_num = '0023_adr020_coverage'
        WHERE version_num = '0022_adr020_policy'
    """))

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


def _postgresql_instance(target_revision):
    intention = {REVISION: "int3a", POLICY_BINDING_REVISION: "int4", BOOTSTRAP_BINDING_REVISION: "int5"}[target_revision]
    name = f"mission-009a-{intention}-{uuid.uuid4().hex[:12]}"
    database = f"adr020_{uuid.uuid4().hex[:12]}"
    password = uuid.uuid4().hex
    port = _free_port()
    container_id = None
    engine = None
    readiness_confirmed = False
    try:
        result = _run([
            "docker", "run", "--detach", "--name", name,
            "--label", f"mission=MISSION-009A-{intention.upper()}",
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
            if target_revision in {POLICY_BINDING_REVISION, BOOTSTRAP_BINDING_REVISION}:
                operations = Operations(MigrationContext.configure(connection))
                migration_0030 = _load_migration(
                    POLICY_BINDING_MIGRATION, "test_physical_0030",
                )
                migration_0030.op = operations
                migration_0030.upgrade()
                connection.execute(text("""
                    UPDATE alembic_version
                    SET version_num = :policy_binding_revision
                    WHERE version_num = :revision
                """), {
                    "policy_binding_revision": POLICY_BINDING_REVISION,
                    "revision": REVISION,
                })
            if target_revision == BOOTSTRAP_BINDING_REVISION:
                operations = Operations(MigrationContext.configure(connection))
                migration_0031 = _load_migration(
                    BOOTSTRAP_BINDING_MIGRATION, "test_physical_0031",
                )
                migration_0031.op = operations
                migration_0031.upgrade()
                connection.execute(text("""
                    UPDATE alembic_version
                    SET version_num = :bootstrap_binding_revision
                    WHERE version_num = :policy_binding_revision
                """), {
                    "bootstrap_binding_revision": BOOTSTRAP_BINDING_REVISION,
                    "policy_binding_revision": POLICY_BINDING_REVISION,
                })
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


@pytest.fixture(scope="session")
def postgresql_0029():
    yield from _postgresql_instance(REVISION)


@pytest.fixture(scope="session")
def postgresql_0030():
    yield from _postgresql_instance(POLICY_BINDING_REVISION)


@pytest.fixture(scope="session")
def postgresql_0031():
    yield from _postgresql_instance(BOOTSTRAP_BINDING_REVISION)


@pytest.fixture
def postgresql_0030_prospective():
    yield from _postgresql_instance(POLICY_BINDING_REVISION)


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


def _policy_records(binding, suffix):
    decision_id = f"policy-decision-{suffix}"
    execution_id = f"policy-execution-{suffix}"
    common = {
        key: binding[key]
        for key in ("policy_type", "policy_id", "policy_version", "policy_hash")
    }
    version = {
        "policy_version_record_id": f"policy-version-{suffix}", **common,
        "domain": "fiscal", "scope": {"country": "PT"},
        "declared_material_applicability": {"taxes": ["iva"]},
        "modalities": ["manual"],
        "permitted_authorization_classes": ["humana_delegada"],
        "permitted_execution_modes": ["manual"], "gates": [], "roles": [],
        "segregation_of_duties": {}, "limits": {}, "rules": [],
        "exact_references": [],
        "origin_evidence": {"mission": "MISSION-009A-INTENCAO-4"},
        "record_hash": _digest(f"policy-version-{suffix}"),
    }
    decision = {
        "decision_id": decision_id, "decision_event": "submetida", **common,
        "actor": "policy-proponent", "institutional_role": "proponente_institucional",
        "evidence": {"mission": "MISSION-009A-INTENCAO-4"},
        "rationale": "physical predecessor for exact policy activation",
        "previous_decision_id": None,
        "idempotency_key": f"policy-decision-idempotency-{suffix}",
        "record_hash": _digest(f"policy-decision-{suffix}"),
    }
    execution = {
        "policy_activation_execution_id": execution_id,
        "policy_decision_id": decision_id, **common,
        "authorization_basis_type": "active_policy_chain",
        "authorization_class": "humana_delegada", "execution_mode": "manual",
        "bootstrap_authority_record_id": None,
        "bootstrap_authority_record_hash": None,
        "activation_authority_policy_id": None,
        "activation_authority_policy_version": None,
        "activation_authority_policy_hash": None,
        "activation_authority_policy_activation_id": None,
        "automation_envelope_id": None, "automation_envelope_version": None,
        "automation_envelope_hash": None, "automation_envelope_activation_id": None,
        "attempt_number": 1, "actor_or_worker": "integration-auditor",
        "lease_id": f"policy-lease-{suffix}", "fencing_token": 1,
        "idempotency_key": f"policy-execution-idempotency-{suffix}",
        "state": "concluida", "started_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
        "structured_result": {"activated": True}, "structured_error": None,
        "provenance": {"mission": "MISSION-009A-INTENCAO-4"},
        "record_hash": _digest(f"policy-execution-{suffix}"),
    }
    activation = {
        "policy_activation_id": binding["policy_activation_id"],
        "policy_activation_execution_id": execution_id,
        "policy_decision_id": decision_id, **common,
        "domain": "fiscal", "modality": "manual",
        "operational_interval": {"from": "2026-08-03T00:00:00Z"},
        "activation_generation_id": f"policy-generation-{suffix}",
        "activated_at": datetime.now(timezone.utc), "state": "activa",
        "technical_actor": "integration-auditor",
        "provenance": {"mission": "MISSION-009A-INTENCAO-4"},
        "record_hash": binding["policy_activation_record_hash"],
    }
    return version, decision, execution, activation


def _materialize_policy_activations(engine, bindings):
    records = [
        _policy_records(binding, f"{index}-{uuid.uuid4().hex[:8]}")
        for index, binding in enumerate(bindings)
    ]
    with engine.begin() as connection:
        connection.execute(insert(models.PolicyVersion), [row[0] for row in records])
        connection.execute(insert(models.PolicyDecision), [row[1] for row in records])
        connection.execute(
            insert(models.PolicyActivationExecution), [row[2] for row in records],
        )
        connection.execute(insert(models.PolicyActivation), [row[3] for row in records])


def _bootstrap_rows(suffix):
    policy_hash = _digest(f"bootstrap-policy-{suffix}")
    policy_version = {
        "policy_version_record_id": f"bootstrap-policy-version-{suffix}",
        "policy_type": "activation_authority",
        "policy_id": f"bootstrap-policy-{suffix}",
        "policy_version": 1,
        "policy_hash": policy_hash,
        "domain": "fiscal",
        "scope": {"country": "PT"},
        "declared_material_applicability": {"taxes": ["iva"]},
        "modalities": ["manual"],
        "permitted_authorization_classes": ["constitucional_reservada"],
        "permitted_execution_modes": ["manual"],
        "gates": [],
        "roles": [],
        "segregation_of_duties": {},
        "limits": {},
        "rules": [],
        "exact_references": [],
        "origin_evidence": {"mission": "MISSION-009A-INTENCAO-5"},
        "record_hash": _digest(f"bootstrap-policy-version-{suffix}"),
    }
    policy_decision = {
        "decision_id": f"bootstrap-policy-decision-{suffix}",
        "decision_event": "submetida",
        "policy_type": "activation_authority",
        "policy_id": f"bootstrap-policy-{suffix}",
        "policy_version": 1,
        "policy_hash": policy_hash,
        "actor": "bootstrap-proponent",
        "institutional_role": "proponente_institucional",
        "evidence": {"mission": "MISSION-009A-INTENCAO-5"},
        "rationale": "physical predecessor for bootstrap authority execution",
        "previous_decision_id": None,
        "idempotency_key": f"bootstrap-policy-decision-idempotency-{suffix}",
        "record_hash": _digest(f"bootstrap-policy-decision-{suffix}"),
    }
    bootstrap_common = {
        "policy_type": "activation_authority",
        "policy_id": f"bootstrap-policy-{suffix}",
        "policy_version": 1,
        "policy_hash": policy_hash,
        "domain": "fiscal",
        "scope": {"country": "PT"},
        "actor_proponente": "bootstrap-proponent",
        "actor_auditor": "bootstrap-auditor",
        "independent_audit_result": "favoravel",
        "constitutional_authority_declaration": "constitutional bootstrap authority",
        "actor_ratificador": "bootstrap-ratifier",
        "segregation_evidence": {"actors_are_distinct": True},
        "evidence": {"mission": "MISSION-009A-INTENCAO-5"},
        "validity": "valida",
        "submission_mode": "manual",
        "audit_mode": "manual",
        "ratification_mode": "manual",
        "activation_mode": "manual",
        "provenance": {"mission": "MISSION-009A-INTENCAO-5"},
    }
    bootstrap_a = {
        **bootstrap_common,
        "bootstrap_authority_record_id": f"bootstrap-a-{suffix}",
        "record_hash": _digest(f"bootstrap-a-{suffix}"),
    }
    bootstrap_b = {
        **bootstrap_common,
        "bootstrap_authority_record_id": f"bootstrap-b-{suffix}",
        "record_hash": _digest(f"bootstrap-b-{suffix}"),
    }
    false_pair_row = {
        "policy_activation_execution_id": f"bootstrap-execution-{suffix}",
        "policy_decision_id": f"bootstrap-policy-decision-{suffix}",
        "policy_type": "activation_authority",
        "policy_id": f"bootstrap-policy-{suffix}",
        "policy_version": 1,
        "policy_hash": policy_hash,
        "authorization_basis_type": "bootstrap_authority_record",
        "authorization_class": "constitucional_reservada",
        "execution_mode": "manual",
        "bootstrap_authority_record_id": bootstrap_a["bootstrap_authority_record_id"],
        "bootstrap_authority_record_hash": bootstrap_b["record_hash"],
        "activation_authority_policy_id": None,
        "activation_authority_policy_version": None,
        "activation_authority_policy_hash": None,
        "activation_authority_policy_activation_id": None,
        "automation_envelope_id": None,
        "automation_envelope_version": None,
        "automation_envelope_hash": None,
        "automation_envelope_activation_id": None,
        "attempt_number": 1,
        "actor_or_worker": "integration-auditor",
        "lease_id": f"bootstrap-lease-{suffix}",
        "fencing_token": 1,
        "idempotency_key": f"bootstrap-idempotency-{suffix}",
        "state": "pendente",
        "started_at": None,
        "finished_at": None,
        "structured_result": None,
        "structured_error": None,
        "provenance": {"mission": "MISSION-009A-INTENCAO-5"},
        "record_hash": _digest(f"bootstrap-execution-{suffix}"),
    }
    return policy_version, policy_decision, bootstrap_a, bootstrap_b, false_pair_row


def _seed_bootstrap_rows(engine, suffix):
    rows = _bootstrap_rows(suffix)
    policy_version, policy_decision, bootstrap_a, bootstrap_b, _ = rows

    with engine.begin() as connection:
        connection.execute(insert(models.PolicyVersion), policy_version)
        connection.execute(insert(models.PolicyDecision), policy_decision)
        connection.execute(
            insert(models.BootstrapAuthorityRecord), [bootstrap_a, bootstrap_b],
        )
    return rows


def test_bootstrap_authority_rejects_id_and_record_hash_from_different_records(
    postgresql_0031,
):
    engine = postgresql_0031["engine"]
    _, _, bootstrap_a, bootstrap_b, false_pair_row = _seed_bootstrap_rows(
        engine, "negative",
    )

    with engine.connect() as connection:
        persisted = connection.execute(text("""
            SELECT bootstrap_authority_record_id, record_hash
            FROM bootstrap_authority_records
            ORDER BY bootstrap_authority_record_id
        """)).all()
    assert persisted == [
        (bootstrap_a["bootstrap_authority_record_id"], bootstrap_a["record_hash"]),
        (bootstrap_b["bootstrap_authority_record_id"], bootstrap_b["record_hash"]),
    ]

    with pytest.raises(IntegrityError) as caught:
        with engine.begin() as connection:
            connection.execute(
                insert(models.PolicyActivationExecution),
                false_pair_row,
            )
    assert caught.value.orig.sqlstate == "23503"
    assert (
        getattr(caught.value.orig.diag, "constraint_name", None) == BOOTSTRAP_FK
        or BOOTSTRAP_FK in str(caught.value)
    )
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM policy_activation_executions
            WHERE policy_activation_execution_id = :execution_id
        """), {
            "execution_id": false_pair_row["policy_activation_execution_id"],
        }) == 0


def test_bootstrap_authority_accepts_matching_id_and_record_hash(postgresql_0031):
    engine = postgresql_0031["engine"]
    _, _, bootstrap_a, _, execution = _seed_bootstrap_rows(engine, "positive")
    execution["bootstrap_authority_record_hash"] = bootstrap_a["record_hash"]

    with engine.begin() as connection:
        connection.execute(insert(models.PolicyActivationExecution), execution)
    with engine.connect() as connection:
        persisted = connection.execute(text("""
            SELECT bootstrap_authority_record_id, bootstrap_authority_record_hash
            FROM policy_activation_executions
            WHERE policy_activation_execution_id = :execution_id
        """), {"execution_id": execution["policy_activation_execution_id"]}).one()
    assert persisted == (
        bootstrap_a["bootstrap_authority_record_id"], bootstrap_a["record_hash"],
    )


@pytest.mark.parametrize("fixture_name", ["postgresql_0030", "postgresql_0031"])
@pytest.mark.parametrize(
    ("bootstrap_id", "bootstrap_hash"),
    [
        (None, None),
        ("existing", None),
        (None, "unmatched"),
    ],
    ids=["both-null", "id-without-hash", "hash-without-id"],
)
def test_bootstrap_binding_preserves_match_simple_null_compatibility(
    request, fixture_name, bootstrap_id, bootstrap_hash,
):
    engine = request.getfixturevalue(fixture_name)["engine"]
    revision = "0030" if fixture_name == "postgresql_0030" else "0031"
    suffix = f"null-{revision}-{bootstrap_id}-{bootstrap_hash}"
    _, _, bootstrap_a, _, execution = _seed_bootstrap_rows(engine, suffix)
    execution["bootstrap_authority_record_id"] = (
        bootstrap_a["bootstrap_authority_record_id"]
        if bootstrap_id == "existing" else None
    )
    execution["bootstrap_authority_record_hash"] = (
        _digest(f"unmatched-bootstrap-hash-{suffix}")
        if bootstrap_hash == "unmatched" else None
    )

    with engine.begin() as connection:
        connection.execute(insert(models.PolicyActivationExecution), execution)
    with engine.connect() as connection:
        persisted = connection.execute(text("""
            SELECT bootstrap_authority_record_id, bootstrap_authority_record_hash
            FROM policy_activation_executions
            WHERE policy_activation_execution_id = :execution_id
        """), {"execution_id": execution["policy_activation_execution_id"]}).one()
    assert persisted == (
        execution["bootstrap_authority_record_id"],
        execution["bootstrap_authority_record_hash"],
    )


def test_bootstrap_binding_gate_is_prospective_and_rejects_new_mismatch(
    postgresql_0030_prospective,
):
    engine = postgresql_0030_prospective["engine"]
    _, _, _, _, historical = _seed_bootstrap_rows(engine, "historical")
    with engine.begin() as connection:
        connection.execute(insert(models.PolicyActivationExecution), historical)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM policy_activation_executions
            WHERE policy_activation_execution_id = :execution_id
        """), {"execution_id": historical["policy_activation_execution_id"]}) == 1

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        migration_0031 = _load_migration(
            BOOTSTRAP_BINDING_MIGRATION, "test_prospective_physical_0031",
        )
        migration_0031.op = operations
        migration_0031.upgrade()
        connection.execute(text("""
            UPDATE alembic_version
            SET version_num = :bootstrap_revision
            WHERE version_num = :policy_revision
        """), {
            "bootstrap_revision": BOOTSTRAP_BINDING_REVISION,
            "policy_revision": POLICY_BINDING_REVISION,
        })

    _, _, _, _, new_mismatch = _seed_bootstrap_rows(engine, "prospective")
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT convalidated FROM pg_constraint WHERE conname = :constraint
        """), {"constraint": BOOTSTRAP_FK}) is False
        assert connection.scalar(text("""
            SELECT count(*) FROM policy_activation_executions
            WHERE policy_activation_execution_id = :execution_id
        """), {"execution_id": historical["policy_activation_execution_id"]}) == 1

    with pytest.raises(IntegrityError) as caught:
        with engine.begin() as connection:
            connection.execute(insert(models.PolicyActivationExecution), new_mismatch)
    assert caught.value.orig.sqlstate == "23503"
    assert getattr(caught.value.orig.diag, "constraint_name", None) == BOOTSTRAP_FK
    with engine.connect() as connection:
        counts = connection.execute(text("""
            SELECT policy_activation_execution_id, count(*)
            FROM policy_activation_executions
            WHERE policy_activation_execution_id IN (:historical_id, :new_id)
            GROUP BY policy_activation_execution_id
        """), {
            "historical_id": historical["policy_activation_execution_id"],
            "new_id": new_mismatch["policy_activation_execution_id"],
        }).all()
    assert counts == [(historical["policy_activation_execution_id"], 1)]


def test_policy_binding_rejects_activation_from_different_exact_policy(
    postgresql_0030,
):
    engine = postgresql_0030["engine"]
    bindings = _bindings()
    activation_a = copy.deepcopy(bindings["policy_bindings"][0])
    activation_a.update({
        "policy_id": "policy-a", "policy_hash": _digest("hash-a"),
        "policy_activation_id": "activation-a",
        "policy_activation_record_hash": _digest("activation-record-hash-a"),
    })
    declared_b = copy.deepcopy(activation_a)
    declared_b.update({"policy_id": "policy-b", "policy_hash": _digest("hash-b")})
    _materialize_policy_activations(
        engine, [activation_a, bindings["policy_bindings"][1]],
    )
    version_b = _policy_records(declared_b, f"b-{uuid.uuid4().hex[:8]}")[0]
    with engine.begin() as connection:
        connection.execute(insert(models.PolicyVersion), version_b)

    bindings["policy_bindings"][0] = declared_b
    bindings["continuity_binding"].update({
        "continuity_policy_id": declared_b["policy_id"],
        "continuity_policy_version": declared_b["policy_version"],
        "continuity_policy_hash": declared_b["policy_hash"],
        "continuity_policy_activation_id": declared_b["policy_activation_id"],
        "continuity_policy_activation_record_hash":
            declared_b["policy_activation_record_hash"],
    })
    ADR020BindingsContract.model_validate(bindings, strict=True)
    decision = _decision("mismatched-policy-activation", bindings)

    with pytest.raises(DBAPIError) as caught:
        with engine.begin() as connection:
            connection.execute(insert(models.ActivationDecision), decision)
    assert caught.value.orig.sqlstate == "23503"
    assert "ADR020_POLICY_BINDING_ACTIVATION_MISMATCH" in str(caught.value)


def test_policy_binding_accepts_activation_from_same_exact_policy(postgresql_0030):
    engine = postgresql_0030["engine"]
    bindings = _bindings()
    for index, binding in enumerate(bindings["policy_bindings"]):
        suffix = f"positive-{index}"
        binding.update({
            "policy_id": f"{binding['policy_id']}-{suffix}",
            "policy_hash": _digest(f"policy-{suffix}"),
            "policy_activation_id": f"activation-{suffix}",
            "policy_activation_record_hash": _digest(f"activation-{suffix}"),
        })
    continuity, precedence = bindings["policy_bindings"]
    bindings["continuity_binding"].update({
        "continuity_policy_id": continuity["policy_id"],
        "continuity_policy_hash": continuity["policy_hash"],
        "continuity_policy_activation_id": continuity["policy_activation_id"],
        "continuity_policy_activation_record_hash":
            continuity["policy_activation_record_hash"],
    })
    bindings["precedence_binding"].update({
        "precedence_policy_id": precedence["policy_id"],
        "precedence_policy_hash": precedence["policy_hash"],
        "precedence_policy_activation_id": precedence["policy_activation_id"],
        "precedence_policy_activation_record_hash":
            precedence["policy_activation_record_hash"],
    })
    _materialize_policy_activations(engine, bindings["policy_bindings"])
    ADR020BindingsContract.model_validate(bindings, strict=True)
    decision = _decision("exact-policy-activation", bindings)

    with engine.begin() as connection:
        connection.execute(insert(models.ActivationDecision), decision)
    with engine.connect() as connection:
        persisted = connection.scalar(text("""
            SELECT count(*) FROM activation_decisions
            WHERE activation_decision_id = :decision_id
        """), {"decision_id": decision["activation_decision_id"]})
    assert persisted == 1


@pytest.mark.parametrize(
    "case",
    (
        "sql_null",
        "json_object",
        "empty_array",
        "missing_activation_id",
        "missing_activation_record_hash",
        "non_integer_policy_version",
        "null_policy_version",
        "one_exact_one_divergent",
    ),
)
def test_policy_binding_rejects_invalid_physical_forms(postgresql_0030, case):
    engine = postgresql_0030["engine"]
    bindings = _bindings()
    if case == "one_exact_one_divergent":
        for index, binding in enumerate(bindings["policy_bindings"]):
            binding.update({
                "policy_id": f"multi-binding-policy-{index}",
                "policy_hash": _digest(f"multi-binding-policy-{index}"),
                "policy_activation_id": f"multi-binding-activation-{index}",
                "policy_activation_record_hash": _digest(
                    f"multi-binding-activation-{index}"
                ),
            })
        _materialize_policy_activations(engine, bindings["policy_bindings"])

    if case == "sql_null":
        policy_bindings = null()
    elif case == "json_object":
        policy_bindings = copy.deepcopy(bindings["policy_bindings"][0])
    elif case == "empty_array":
        policy_bindings = []
    else:
        policy_bindings = copy.deepcopy(bindings["policy_bindings"])
        if case == "missing_activation_id":
            policy_bindings[0].pop("policy_activation_id")
        elif case == "missing_activation_record_hash":
            policy_bindings[0].pop("policy_activation_record_hash")
        elif case == "non_integer_policy_version":
            policy_bindings[0]["policy_version"] = "not-an-integer"
        elif case == "null_policy_version":
            policy_bindings[0]["policy_version"] = None
        else:
            policy_bindings[1]["policy_activation_record_hash"] = _digest(
                "divergent-activation-record"
            )

    decision = _decision(f"invalid-{case}")
    decision["policy_bindings"] = policy_bindings
    with pytest.raises(DBAPIError) as caught:
        with engine.begin() as connection:
            connection.execute(insert(models.ActivationDecision), decision)
    assert caught.value.orig.sqlstate == "23503"
    assert "ADR020_POLICY_BINDING_ACTIVATION_MISMATCH" in str(caught.value)
    with engine.connect() as connection:
        persisted = connection.scalar(text("""
            SELECT count(*) FROM activation_decisions
            WHERE activation_decision_id = :decision_id
        """), {"decision_id": decision["activation_decision_id"]})
    assert persisted == 0


def test_bootstrap_binding_migration_has_exact_static_contract(monkeypatch):
    assert BOOTSTRAP_BINDING_MIGRATION.exists()
    source = BOOTSTRAP_BINDING_MIGRATION.read_text(encoding="utf-8")
    lowered = source.lower()
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {
        "revision": BOOTSTRAP_BINDING_REVISION,
        "down_revision": POLICY_BINDING_REVISION,
    }
    assert len(BOOTSTRAP_BINDING_REVISION) <= 32
    assert re.search(
        rf"ALTER\s+TABLE\s+bootstrap_authority_records\s+ADD\s+CONSTRAINT\s+"
        rf"{BOOTSTRAP_UNIQUE}\s+UNIQUE\s*\(\s*bootstrap_authority_record_id\s*,\s*"
        r"record_hash\s*\)", source, re.I,
    )
    assert re.search(
        rf"ALTER\s+TABLE\s+policy_activation_executions\s+ADD\s+CONSTRAINT\s+"
        rf"{BOOTSTRAP_FK}\s+FOREIGN\s+KEY\s*\(\s*"
        r"bootstrap_authority_record_id\s*,\s*bootstrap_authority_record_hash\s*\)"
        r"\s*REFERENCES\s+bootstrap_authority_records\s*\(\s*"
        r"bootstrap_authority_record_id\s*,\s*record_hash\s*\)\s*NOT\s+VALID",
        source, re.I,
    )
    assert "validate constraint" not in lowered
    assert "match full" not in lowered
    assert "not null" not in lowered
    assert not re.search(r"\b(update|delete)\b", lowered)
    assert "backfill" not in lowered
    assert "raise runtimeerror" in lowered and "irreversible" in lowered

    migration = _load_migration(
        BOOTSTRAP_BINDING_MIGRATION, "test_0031_non_postgresql_guard",
    )
    class NonPostgresqlOperations:
        def get_bind(self):
            return type("Bind", (), {"dialect": type("Dialect", (), {"name": "sqlite"})()})()
    monkeypatch.setattr(migration, "op", NonPostgresqlOperations())
    with pytest.raises(RuntimeError, match="PostgreSQL-only"):
        migration.upgrade()
    with pytest.raises(RuntimeError, match="irreversible"):
        migration.downgrade()


def test_bootstrap_binding_constraints_are_physically_installed(postgresql_0031):
    engine = postgresql_0031["engine"]
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == BOOTSTRAP_BINDING_REVISION
        constraints = connection.execute(text("""
            SELECT c.conname, c.contype, c.convalidated,
                   array_agg(source_attribute.attname ORDER BY source_key.ordinality),
                   array_agg(target_attribute.attname ORDER BY source_key.ordinality)
                       FILTER (WHERE target_attribute.attname IS NOT NULL),
                   source_table.relname, target_table.relname
            FROM pg_constraint AS c
            JOIN pg_class AS source_table ON source_table.oid = c.conrelid
            JOIN unnest(c.conkey) WITH ORDINALITY AS source_key(attnum, ordinality)
              ON true
            JOIN pg_attribute AS source_attribute
              ON source_attribute.attrelid = c.conrelid
             AND source_attribute.attnum = source_key.attnum
            LEFT JOIN pg_class AS target_table ON target_table.oid = c.confrelid
            LEFT JOIN unnest(c.confkey) WITH ORDINALITY AS target_key(attnum, ordinality)
              ON target_key.ordinality = source_key.ordinality
            LEFT JOIN pg_attribute AS target_attribute
              ON target_attribute.attrelid = c.confrelid
             AND target_attribute.attnum = target_key.attnum
            WHERE c.conname IN (:unique_name, :fk_name)
            GROUP BY c.conname, c.contype, c.convalidated,
                     source_table.relname, target_table.relname
            ORDER BY c.conname
        """), {"unique_name": BOOTSTRAP_UNIQUE, "fk_name": BOOTSTRAP_FK}).all()
    assert constraints == [
        (
            BOOTSTRAP_FK, "f", False,
            ["bootstrap_authority_record_id", "bootstrap_authority_record_hash"],
            ["bootstrap_authority_record_id", "record_hash"],
            "policy_activation_executions", "bootstrap_authority_records",
        ),
        (
            BOOTSTRAP_UNIQUE, "u", True,
            ["bootstrap_authority_record_id", "record_hash"],
            None, "bootstrap_authority_records", None,
        ),
    ]


def test_policy_binding_migration_has_exact_static_contract():
    assert POLICY_BINDING_MIGRATION.exists()
    source = POLICY_BINDING_MIGRATION.read_text(encoding="utf-8")
    lowered = source.lower()
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {
        "revision": POLICY_BINDING_REVISION,
        "down_revision": REVISION,
    }
    assert len(POLICY_BINDING_REVISION) <= 32
    assert POLICY_BINDING_FUNCTION in source
    assert POLICY_BINDING_TRIGGER in source
    assert re.search(
        rf"CREATE\s+TRIGGER\s+{POLICY_BINDING_TRIGGER}\s+"
        r"BEFORE\s+INSERT\s+ON\s+activation_decisions\s+FOR\s+EACH\s+ROW",
        source, re.I,
    )
    for comparison in (
        "policy_activations.policy_type = binding ->> 'policy_type'",
        "policy_activations.policy_id = binding ->> 'policy_id'",
        "policy_activations.policy_version =",
        "policy_activations.policy_hash = binding ->> 'policy_hash'",
        "policy_activations.policy_activation_id =",
        "policy_activations.record_hash =",
    ):
        assert comparison in lowered
    assert "errcode = '23503'" in lowered
    assert "ADR020_POLICY_BINDING_ACTIVATION_MISMATCH" in source
    assert "raise runtimeerror" in lowered and "irreversible" in lowered
    for forbidden in ("update ", "delete ", "backfill", "alter table"):
        assert forbidden not in lowered


def test_policy_binding_gate_is_physically_installed(postgresql_0030):
    engine = postgresql_0030["engine"]
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == POLICY_BINDING_REVISION
        assert connection.scalar(
            text("SELECT to_regprocedure(:name) IS NOT NULL"),
            {"name": f"{POLICY_BINDING_FUNCTION}()"},
        )
        trigger = connection.execute(text("""
            SELECT event_manipulation, action_timing, event_object_table
            FROM information_schema.triggers
            WHERE trigger_name = :trigger
        """), {"trigger": POLICY_BINDING_TRIGGER}).one()
    assert trigger == ("INSERT", "BEFORE", "activation_decisions")


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
