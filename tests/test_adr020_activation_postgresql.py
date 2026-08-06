import ast
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import bindparam, create_engine, insert, null, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.schemas.adr020_bindings import (
    ADR020BindingsContract,
    ContinuityBinding,
    PolicyBinding,
    PrecedenceBinding,
)


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "0029_adr020_activation_execution_gate.py"
POLICY_BINDING_MIGRATION = ROOT / "migrations" / "versions" / "0030_adr020_policy_binding_gate.py"
BOOTSTRAP_BINDING_MIGRATION = ROOT / "migrations" / "versions" / "0031_adr020_bootstrap_binding_gate.py"
COVERAGE_BINDING_MIGRATION = ROOT / "migrations" / "versions" / "0032_adr020_coverage_binding_gate.py"
CONTINUITY_BINDING_MIGRATION = ROOT / "migrations" / "versions" / "0033_adr020_continuity_binding_gate.py"
PRECEDENCE_BINDING_MIGRATION = ROOT / "migrations" / "versions" / "0034_adr020_precedence_binding_gate.py"
SUBJECT_GATE_MIGRATION = ROOT / "migrations" / "versions" / "0035_adr020_normative_activation_subject_gate.py"
REVIEW_GATE_MIGRATION = ROOT / "migrations" / "versions" / "0036_adr020_normative_activation_review_gate.py"
GENERATION_FK_MIGRATION = ROOT / "migrations" / "versions" / "0037_adr020_activation_generation_fk.py"
GENERATION_EXECUTION_GATE_MIGRATION = ROOT / "migrations" / "versions" / "0038_adr020_normative_activation_generation_execution_gate.py"
GENERATION_DECISION_EXECUTION_FK_MIGRATION = ROOT / "migrations" / "versions" / "0039_adr020_activation_generation_decision_execution_fk.py"
NORMATIVE_GENERATION_DECISION_FK_MIGRATION = ROOT / "migrations" / "versions" / "0040_adr020_norm_gen_decision_fk.py"
NORMATIVE_EXECUTION_DECISION_FK_MIGRATION = ROOT / "migrations" / "versions" / "0041_adr020_norm_exec_dec_fk.py"
RULE_FOUNDATION = ROOT / "migrations" / "versions" / "0020_adr020_rule_foundation.py"
RELATION_FOUNDATION = ROOT / "migrations" / "versions" / "0021_adr020_relation_foundation.py"
POLICY_FOUNDATION = ROOT / "migrations" / "versions" / "0022_adr020_policy_foundation.py"
COVERAGE_FOUNDATION = ROOT / "migrations" / "versions" / "0023_adr020_coverage_foundation.py"
HISTORICAL = ROOT / "migrations" / "versions" / "0024_adr020_activation_foundation.py"
ATOMIC_REPAIR = ROOT / "migrations" / "versions" / "0028_adr020_atomic_activation_trigger_fix.py"
ATOMIC_REVISION = "0028_adr020_atomic_trigger_fix"
REVISION = "0029_adr020_activation_exec_gate"
POLICY_BINDING_REVISION = "0030_adr020_policy_binding_gate"
BOOTSTRAP_BINDING_REVISION = "0031_adr020_bootstrap_binding"
COVERAGE_BINDING_REVISION = "0032_adr020_coverage_gate"
CONTINUITY_BINDING_REVISION = "0033_adr020_continuity_gate"
PRECEDENCE_BINDING_REVISION = "0034_adr020_precedence_gate"
SUBJECT_GATE_REVISION = "0035_adr020_subject_gate"
REVIEW_GATE_REVISION = "0036_adr020_review_gate"
GENERATION_FK_REVISION = "0037_adr020_generation_fk"
GENERATION_EXECUTION_GATE_REVISION = "0038_adr020_generation_exec_gate"
GENERATION_DECISION_EXECUTION_FK_REVISION = "0039_adr020_gen_exec_decision_fk"
NORMATIVE_GENERATION_DECISION_FK_REVISION = "0040_adr020_norm_gen_decision_fk"
NORMATIVE_EXECUTION_DECISION_FK_REVISION = "0041_adr020_norm_exec_dec_fk"
GENERATION_DECISION_EXECUTION_UNIQUE = "uq_activation_executions_exact_decision_binding"
GENERATION_DECISION_EXECUTION_FK = "fk_activation_generations_exact_execution_decision"
NORMATIVE_GENERATION_DECISION_UNIQUE = "uq_activation_generations_generation_exact_decision"
NORMATIVE_GENERATION_DECISION_FK = "fk_normative_activations_generation_exact_decision"
GENERATION_FK = "fk_normative_activations_activation_generation"
GENERATION_EXECUTION_GATE_FUNCTION = "adr020_validate_normative_activation_generation_execution"
GENERATION_EXECUTION_GATE_TRIGGER = "trg_adr020_validate_normative_activation_subject_review_gexec"
GENERATION_EXECUTION_GATE_TOKEN = "ADR020_NORMATIVE_ACTIVATION_GENERATION_EXECUTION_MISMATCH"
REVIEW_GATE_FUNCTION = "adr020_validate_normative_activation_review"
REVIEW_GATE_TRIGGER = "trg_adr020_validate_normative_activation_subject_review"
REVIEW_GATE_TOKEN = "ADR020_NORMATIVE_ACTIVATION_REVIEW_MISMATCH"
SUBJECT_GATE_FUNCTION = "adr020_validate_normative_activation_subject"
SUBJECT_GATE_TRIGGER = "trg_adr020_validate_normative_activation_subject"
SUBJECT_GATE_TOKEN = "ADR020_NORMATIVE_ACTIVATION_SUBJECT_MISMATCH"
BOOTSTRAP_UNIQUE = "uq_bootstrap_authority_records_exact_record"
BOOTSTRAP_FK = "fk_policy_activation_executions_exact_bootstrap_record"
POLICY_BINDING_FUNCTION = "adr020_validate_policy_binding_activations"
POLICY_BINDING_TRIGGER = "trg_adr020_validate_policy_binding_activations"
COVERAGE_BINDING_FUNCTION = "adr020_validate_coverage_binding_contract"
COVERAGE_BINDING_TRIGGER = "trg_adr020_validate_coverage_binding_contract"
COVERAGE_BINDING_TOKEN = "ADR020_COVERAGE_BINDING_CONTRACT_MISMATCH"
CONTINUITY_BINDING_FUNCTION = "adr020_validate_continuity_binding_policy"
CONTINUITY_BINDING_TRIGGER = "trg_adr020_validate_continuity_binding_policy"
CONTINUITY_BINDING_TOKEN = "ADR020_CONTINUITY_BINDING_POLICY_MISMATCH"
PRECEDENCE_BINDING_FUNCTION = "adr020_validate_precedence_binding_policy"
PRECEDENCE_BINDING_TRIGGER = "trg_adr020_validate_precedence_binding_policy"
PRECEDENCE_BINDING_TOKEN = "ADR020_PRECEDENCE_BINDING_POLICY_MISMATCH"
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


def _bootstrap_adr020_activation(
    connection, physical_coverage=False, physical_rule_relation=False,
):
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
    """))

    operations = Operations(MigrationContext.configure(connection))
    if physical_rule_relation:
        connection.execute(text("""
            CREATE TABLE extraction_results (
                extraction_result_id varchar(64) NOT NULL PRIMARY KEY,
                record_hash varchar(64) NOT NULL UNIQUE,
                CONSTRAINT uq_extraction_results_exact
                    UNIQUE (extraction_result_id, record_hash)
            );
            INSERT INTO alembic_version (version_num)
            VALUES ('0019_adr020_extraction');
        """))
        migration_0020 = _load_migration(
            RULE_FOUNDATION, "test_physical_0020_intention_8a",
        )
        migration_0020.op = operations
        migration_0020.upgrade()
        connection.execute(text("""
            UPDATE alembic_version
            SET version_num = '0020_adr020_rule_foundation'
            WHERE version_num = '0019_adr020_extraction'
        """))
        migration_0021 = _load_migration(
            RELATION_FOUNDATION, "test_physical_0021_intention_8a",
        )
        migration_0021.op = operations
        migration_0021.upgrade()
        connection.execute(text("""
            UPDATE alembic_version
            SET version_num = '0021_adr020_relation_foundation'
            WHERE version_num = '0020_adr020_rule_foundation'
        """))
    else:
        connection.execute(text("""
            INSERT INTO alembic_version (version_num)
            VALUES ('0021_adr020_relation_foundation');
        """))

    migration_0022 = _load_migration(POLICY_FOUNDATION, "test_physical_0022")
    migration_0022.op = operations
    migration_0022.upgrade()
    connection.execute(text("""
        UPDATE alembic_version
        SET version_num = '0022_adr020_policy'
        WHERE version_num = '0021_adr020_relation_foundation'
    """))

    if physical_coverage:
        migration_0023 = _load_migration(
            COVERAGE_FOUNDATION, "test_physical_0023_intention_6",
        )
        migration_0023.op = operations
        migration_0023.upgrade()
    # Historical fixtures keep 0023 stamped because their tests do not use
    # coverage objects. Intention 6 opts into the physical upgrade above.
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


def _postgresql_instance(
    target_revision, physical_coverage=False, physical_rule_relation=False,
    stamp_target=True,
):
    intention = (
        "int8a" if physical_rule_relation else
        "int6" if physical_coverage else
        {
            REVISION: "int3a", POLICY_BINDING_REVISION: "int4",
            BOOTSTRAP_BINDING_REVISION: "int5",
        }[target_revision]
    )
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
            _bootstrap_adr020_activation(
                connection, physical_coverage, physical_rule_relation,
            )
            if target_revision in {
                POLICY_BINDING_REVISION, BOOTSTRAP_BINDING_REVISION,
                COVERAGE_BINDING_REVISION, CONTINUITY_BINDING_REVISION,
                PRECEDENCE_BINDING_REVISION, SUBJECT_GATE_REVISION,
                REVIEW_GATE_REVISION, GENERATION_FK_REVISION,
                GENERATION_EXECUTION_GATE_REVISION,
                GENERATION_DECISION_EXECUTION_FK_REVISION,
                NORMATIVE_GENERATION_DECISION_FK_REVISION,
            }:
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
            if target_revision in {
                BOOTSTRAP_BINDING_REVISION, COVERAGE_BINDING_REVISION,
                CONTINUITY_BINDING_REVISION, PRECEDENCE_BINDING_REVISION,
                SUBJECT_GATE_REVISION, REVIEW_GATE_REVISION,
                GENERATION_FK_REVISION, GENERATION_EXECUTION_GATE_REVISION,
                GENERATION_DECISION_EXECUTION_FK_REVISION,
                NORMATIVE_GENERATION_DECISION_FK_REVISION,
            }:
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
            if target_revision in {
                COVERAGE_BINDING_REVISION, CONTINUITY_BINDING_REVISION,
                PRECEDENCE_BINDING_REVISION, SUBJECT_GATE_REVISION,
                REVIEW_GATE_REVISION, GENERATION_FK_REVISION,
                GENERATION_EXECUTION_GATE_REVISION,
                GENERATION_DECISION_EXECUTION_FK_REVISION,
                NORMATIVE_GENERATION_DECISION_FK_REVISION,
            }:
                operations = Operations(MigrationContext.configure(connection))
                migration_0032 = _load_migration(
                    COVERAGE_BINDING_MIGRATION, "test_physical_0032",
                )
                migration_0032.op = operations
                migration_0032.upgrade()
                connection.execute(text("""
                    UPDATE alembic_version
                    SET version_num = :coverage_binding_revision
                    WHERE version_num = :bootstrap_binding_revision
                """), {
                    "coverage_binding_revision": COVERAGE_BINDING_REVISION,
                    "bootstrap_binding_revision": BOOTSTRAP_BINDING_REVISION,
                })
            if target_revision in {
                CONTINUITY_BINDING_REVISION, PRECEDENCE_BINDING_REVISION,
                SUBJECT_GATE_REVISION, REVIEW_GATE_REVISION,
                GENERATION_FK_REVISION, GENERATION_EXECUTION_GATE_REVISION,
                GENERATION_DECISION_EXECUTION_FK_REVISION,
                NORMATIVE_GENERATION_DECISION_FK_REVISION,
            }:
                operations = Operations(MigrationContext.configure(connection))
                migration_0033 = _load_migration(
                    CONTINUITY_BINDING_MIGRATION, "test_physical_0033",
                )
                migration_0033.op = operations
                migration_0033.upgrade()
                connection.execute(text("""
                    UPDATE alembic_version
                    SET version_num = :continuity_binding_revision
                    WHERE version_num = :coverage_binding_revision
                """), {
                    "continuity_binding_revision": CONTINUITY_BINDING_REVISION,
                    "coverage_binding_revision": COVERAGE_BINDING_REVISION,
                })
            if target_revision in {
                PRECEDENCE_BINDING_REVISION, SUBJECT_GATE_REVISION,
                REVIEW_GATE_REVISION, GENERATION_FK_REVISION,
                GENERATION_EXECUTION_GATE_REVISION,
                GENERATION_DECISION_EXECUTION_FK_REVISION,
                NORMATIVE_GENERATION_DECISION_FK_REVISION,
            }:
                operations = Operations(MigrationContext.configure(connection))
                migration_0034 = _load_migration(
                    PRECEDENCE_BINDING_MIGRATION, "test_physical_0034",
                )
                migration_0034.op = operations
                migration_0034.upgrade()
                connection.execute(text("""
                    UPDATE alembic_version
                    SET version_num = :precedence_binding_revision
                    WHERE version_num = :continuity_binding_revision
                """), {
                    "precedence_binding_revision": PRECEDENCE_BINDING_REVISION,
                    "continuity_binding_revision": CONTINUITY_BINDING_REVISION,
                })
            if target_revision in {
                SUBJECT_GATE_REVISION, REVIEW_GATE_REVISION,
                GENERATION_FK_REVISION, GENERATION_EXECUTION_GATE_REVISION,
                GENERATION_DECISION_EXECUTION_FK_REVISION,
                NORMATIVE_GENERATION_DECISION_FK_REVISION,
            }:
                operations = Operations(MigrationContext.configure(connection))
                migration_0035 = _load_migration(
                    SUBJECT_GATE_MIGRATION, "test_physical_0035",
                )
                migration_0035.op = operations
                migration_0035.upgrade()
                connection.execute(text("""
                    UPDATE alembic_version
                    SET version_num = :subject_gate_revision
                    WHERE version_num = :precedence_binding_revision
                """), {
                    "subject_gate_revision": SUBJECT_GATE_REVISION,
                    "precedence_binding_revision": PRECEDENCE_BINDING_REVISION,
                })
            if target_revision in {
                REVIEW_GATE_REVISION, GENERATION_FK_REVISION,
                GENERATION_EXECUTION_GATE_REVISION,
                GENERATION_DECISION_EXECUTION_FK_REVISION,
                NORMATIVE_GENERATION_DECISION_FK_REVISION,
            }:
                operations = Operations(MigrationContext.configure(connection))
                migration_0036 = _load_migration(
                    REVIEW_GATE_MIGRATION, "test_physical_0036",
                )
                migration_0036.op = operations
                migration_0036.upgrade()
                connection.execute(text("""
                    UPDATE alembic_version
                    SET version_num = :review_gate_revision
                    WHERE version_num = :subject_gate_revision
                """), {
                    "review_gate_revision": REVIEW_GATE_REVISION,
                    "subject_gate_revision": SUBJECT_GATE_REVISION,
                })
            if target_revision in {
                GENERATION_FK_REVISION, GENERATION_EXECUTION_GATE_REVISION,
                GENERATION_DECISION_EXECUTION_FK_REVISION,
                NORMATIVE_GENERATION_DECISION_FK_REVISION,
            }:
                operations = Operations(MigrationContext.configure(connection))
                migration_0037 = _load_migration(
                    GENERATION_FK_MIGRATION, "test_physical_0037",
                )
                migration_0037.op = operations
                migration_0037.upgrade()
                connection.execute(text("""
                    UPDATE alembic_version
                    SET version_num = :generation_fk_revision
                    WHERE version_num = :review_gate_revision
                """), {
                    "generation_fk_revision": GENERATION_FK_REVISION,
                    "review_gate_revision": REVIEW_GATE_REVISION,
                })
            if target_revision in {
                GENERATION_EXECUTION_GATE_REVISION,
                GENERATION_DECISION_EXECUTION_FK_REVISION,
                NORMATIVE_GENERATION_DECISION_FK_REVISION,
            }:
                operations = Operations(MigrationContext.configure(connection))
                migration_0038 = _load_migration(
                    GENERATION_EXECUTION_GATE_MIGRATION, "test_physical_0038",
                )
                migration_0038.op = operations
                migration_0038.upgrade()
                connection.execute(text("""
                    UPDATE alembic_version
                    SET version_num = :new WHERE version_num = :old
                """), {
                    "new": GENERATION_EXECUTION_GATE_REVISION,
                    "old": GENERATION_FK_REVISION,
                })
            if target_revision in {
                GENERATION_DECISION_EXECUTION_FK_REVISION,
                NORMATIVE_GENERATION_DECISION_FK_REVISION,
            }:
                operations = Operations(MigrationContext.configure(connection))
                migration_0039 = _load_migration(
                    GENERATION_DECISION_EXECUTION_FK_MIGRATION,
                    "test_physical_0039",
                )
                migration_0039.op = operations
                migration_0039.upgrade()
                connection.execute(text("""
                    UPDATE alembic_version
                    SET version_num = :new WHERE version_num = :old
                """), {
                    "new": GENERATION_DECISION_EXECUTION_FK_REVISION,
                    "old": GENERATION_EXECUTION_GATE_REVISION,
                })
            if target_revision == NORMATIVE_GENERATION_DECISION_FK_REVISION:
                operations = Operations(MigrationContext.configure(connection))
                migration_0040 = _load_migration(
                    NORMATIVE_GENERATION_DECISION_FK_MIGRATION,
                    "test_physical_0040",
                )
                migration_0040.op = operations
                migration_0040.upgrade()
                if stamp_target:
                    connection.execute(text("""
                        UPDATE alembic_version
                        SET version_num = :new WHERE version_num = :old
                    """), {
                        "new": NORMATIVE_GENERATION_DECISION_FK_REVISION,
                        "old": GENERATION_DECISION_EXECUTION_FK_REVISION,
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


@pytest.fixture
def postgresql_intention_6():
    yield from _postgresql_instance(
        COVERAGE_BINDING_REVISION, physical_coverage=True,
    )


@pytest.fixture
def postgresql_intention_6_prospective():
    yield from _postgresql_instance(
        BOOTSTRAP_BINDING_REVISION, physical_coverage=True,
    )


@pytest.fixture
def postgresql_0033():
    yield from _postgresql_instance(
        CONTINUITY_BINDING_REVISION, physical_coverage=True,
    )


@pytest.fixture
def postgresql_0033_prospective():
    yield from _postgresql_instance(
        COVERAGE_BINDING_REVISION, physical_coverage=True,
    )


@pytest.fixture
def postgresql_0034():
    yield from _postgresql_instance(
        PRECEDENCE_BINDING_REVISION, physical_coverage=True,
    )


@pytest.fixture
def postgresql_0034_prospective():
    yield from _postgresql_instance(
        CONTINUITY_BINDING_REVISION, physical_coverage=True,
    )


@pytest.fixture
def postgresql_intention_8a():
    yield from _postgresql_instance(
        SUBJECT_GATE_REVISION,
        physical_coverage=True,
        physical_rule_relation=True,
    )


@pytest.fixture
def postgresql_intention_8a_prospective():
    yield from _postgresql_instance(
        PRECEDENCE_BINDING_REVISION,
        physical_coverage=True,
        physical_rule_relation=True,
    )


@pytest.fixture
def postgresql_intention_8b1():
    yield from _postgresql_instance(
        REVIEW_GATE_REVISION, physical_coverage=True,
        physical_rule_relation=True,
    )


@pytest.fixture
def postgresql_intention_8b1_prospective():
    yield from _postgresql_instance(
        SUBJECT_GATE_REVISION, physical_coverage=True,
        physical_rule_relation=True,
    )


@pytest.fixture
def postgresql_intention_9a():
    yield from _postgresql_instance(
        GENERATION_FK_REVISION, physical_coverage=True,
        physical_rule_relation=True,
    )


@pytest.fixture
def postgresql_intention_9a_prospective():
    yield from _postgresql_instance(
        REVIEW_GATE_REVISION, physical_coverage=True,
        physical_rule_relation=True,
    )


@pytest.fixture
def postgresql_intention_9b1():
    yield from _postgresql_instance(
        GENERATION_EXECUTION_GATE_REVISION, physical_coverage=True,
        physical_rule_relation=True,
    )


@pytest.fixture
def postgresql_intention_9b3(request):
    target_revision = (
        NORMATIVE_GENERATION_DECISION_FK_REVISION
        if request.node.name == (
            "test_normative_activation_rejects_generation_from_"
            "different_exact_decision_via_core"
        )
        else GENERATION_DECISION_EXECUTION_FK_REVISION
    )
    yield from _postgresql_instance(
        target_revision, physical_coverage=True,
        physical_rule_relation=True,
        stamp_target=(
            target_revision != NORMATIVE_GENERATION_DECISION_FK_REVISION
        ),
    )


@pytest.fixture
def postgresql_intention_9b2():
    yield from _postgresql_instance(
        NORMATIVE_GENERATION_DECISION_FK_REVISION, physical_coverage=True,
        physical_rule_relation=True,
    )


@pytest.fixture
def postgresql_intention_9b4(postgresql_intention_9b2):
    engine = postgresql_intention_9b2["engine"]
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        migration_0041 = _load_migration(
            NORMATIVE_EXECUTION_DECISION_FK_MIGRATION,
            "test_physical_0041_intention_9b4",
        )
        migration_0041.op = operations
        migration_0041.upgrade()
        connection.execute(text("""
            UPDATE alembic_version SET version_num=:new WHERE version_num=:old
        """), {
            "new": NORMATIVE_EXECUTION_DECISION_FK_REVISION,
            "old": NORMATIVE_GENERATION_DECISION_FK_REVISION,
        })
    yield postgresql_intention_9b2


@pytest.fixture
def postgresql_intention_9b2_prospective():
    yield from _postgresql_instance(
        GENERATION_DECISION_EXECUTION_FK_REVISION, physical_coverage=True,
        physical_rule_relation=True,
    )


@pytest.fixture
def postgresql_intention_9b1_prospective():
    yield from _postgresql_instance(
        GENERATION_FK_REVISION, physical_coverage=True,
        physical_rule_relation=True,
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


def test_continuity_binding_rejects_divergence_from_exact_policy_binding(
    postgresql_0033,
):
    engine = postgresql_0033["engine"]
    contract_a, contract_b, bindings = _coverage_intention_6_records(
        "continuity-divergence-int7a",
    )
    _set_coverage_binding(bindings, contract_a, contract_a)

    policy_binding_a = bindings["policy_bindings"][0]
    continuity_activation_b = copy.deepcopy(policy_binding_a)
    continuity_activation_b.update({
        "policy_id": "continuity-policy-b-int7a",
        "policy_hash": _digest("continuity-policy-b-int7a"),
        "policy_activation_id": "continuity-activation-b-int7a",
        "policy_activation_record_hash": _digest(
            "continuity-activation-b-int7a",
        ),
    })
    continuity_binding_b = {
        "continuity_subject_type": "normative_continuity",
        "continuity_policy_id": continuity_activation_b["policy_id"],
        "continuity_policy_version": continuity_activation_b["policy_version"],
        "continuity_policy_hash": continuity_activation_b["policy_hash"],
        "continuity_policy_activation_id":
            continuity_activation_b["policy_activation_id"],
        "continuity_policy_activation_record_hash":
            continuity_activation_b["policy_activation_record_hash"],
    }
    bindings["continuity_binding"] = continuity_binding_b

    assert PolicyBinding.model_validate(
        policy_binding_a, strict=True,
    ).model_dump() == policy_binding_a
    assert ContinuityBinding.model_validate(
        continuity_binding_b, strict=True,
    ).model_dump() == continuity_binding_b

    with engine.begin() as connection:
        connection.execute(
            insert(models.CoverageContract), [contract_a, contract_b],
        )
    _materialize_policy_activations(
        engine,
        [*bindings["policy_bindings"], continuity_activation_b],
    )
    with engine.connect() as connection:
        persisted_activations = connection.execute(text("""
            SELECT policy_activation_id, policy_id, policy_version,
                   policy_hash, record_hash
            FROM policy_activations
            WHERE policy_activation_id IN (:activation_a, :activation_b)
            ORDER BY policy_activation_id
        """), {
            "activation_a": policy_binding_a["policy_activation_id"],
            "activation_b": continuity_activation_b["policy_activation_id"],
        }).all()
    assert persisted_activations == sorted([
        (
            policy_binding_a["policy_activation_id"],
            policy_binding_a["policy_id"],
            policy_binding_a["policy_version"],
            policy_binding_a["policy_hash"],
            policy_binding_a["policy_activation_record_hash"],
        ),
        (
            continuity_activation_b["policy_activation_id"],
            continuity_activation_b["policy_id"],
            continuity_activation_b["policy_version"],
            continuity_activation_b["policy_hash"],
            continuity_activation_b["policy_activation_record_hash"],
        ),
    ])

    with pytest.raises(ValidationError) as structural_rejection:
        ADR020BindingsContract.model_validate(bindings, strict=True)
    errors = structural_rejection.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "value_error"
    assert (
        "continuity_binding must match exactly one normative_continuity "
        "policy_binding"
    ) in errors[0]["msg"]

    false_continuity_decision = _decision(
        "continuity-divergence-int7a", bindings,
    )
    with pytest.raises((DBAPIError, IntegrityError)) as caught:
        with engine.begin() as connection:
            connection.execute(
                insert(models.ActivationDecision),
                false_continuity_decision,
            )
    assert caught.value.orig.sqlstate == "23503"
    assert CONTINUITY_BINDING_TOKEN in str(caught.value)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_decisions
            WHERE activation_decision_id = :decision_id
        """), {
            "decision_id": false_continuity_decision["activation_decision_id"],
        }) == 0


def test_precedence_binding_rejects_divergence_from_exact_policy_binding(
    postgresql_0034,
):
    engine = postgresql_0034["engine"]
    contract_a, contract_b, bindings = _coverage_intention_6_records(
        "precedence-divergence-int7b",
    )
    _set_coverage_binding(bindings, contract_a, contract_a)

    policy_binding_a = next(
        binding
        for binding in bindings["policy_bindings"]
        if binding["policy_type"] == "normative_precedence"
    )
    precedence_activation_b = copy.deepcopy(policy_binding_a)
    precedence_activation_b.update({
        "policy_id": "precedence-policy-b-int7b",
        "policy_hash": _digest("precedence-policy-b-int7b"),
        "policy_activation_id": "precedence-activation-b-int7b",
        "policy_activation_record_hash": _digest(
            "precedence-activation-b-int7b",
        ),
    })
    precedence_binding_b = {
        "precedence_subject_type": "normative_precedence",
        "precedence_policy_id": precedence_activation_b["policy_id"],
        "precedence_policy_version": precedence_activation_b["policy_version"],
        "precedence_policy_hash": precedence_activation_b["policy_hash"],
        "precedence_policy_activation_id":
            precedence_activation_b["policy_activation_id"],
        "precedence_policy_activation_record_hash":
            precedence_activation_b["policy_activation_record_hash"],
    }
    bindings["precedence_binding"] = precedence_binding_b

    assert PolicyBinding.model_validate(
        policy_binding_a, strict=True,
    ).model_dump() == policy_binding_a
    assert PrecedenceBinding.model_validate(
        precedence_binding_b, strict=True,
    ).model_dump() == precedence_binding_b

    with engine.begin() as connection:
        connection.execute(
            insert(models.CoverageContract), [contract_a, contract_b],
        )
    _materialize_policy_activations(
        engine,
        [*bindings["policy_bindings"], precedence_activation_b],
    )
    with engine.connect() as connection:
        persisted_activations = connection.execute(text("""
            SELECT policy_activation_id, policy_id, policy_version,
                   policy_hash, record_hash
            FROM policy_activations
            WHERE policy_activation_id IN (:activation_a, :activation_b)
            ORDER BY policy_activation_id
        """), {
            "activation_a": policy_binding_a["policy_activation_id"],
            "activation_b": precedence_activation_b["policy_activation_id"],
        }).all()
    assert persisted_activations == sorted([
        (
            policy_binding_a["policy_activation_id"],
            policy_binding_a["policy_id"],
            policy_binding_a["policy_version"],
            policy_binding_a["policy_hash"],
            policy_binding_a["policy_activation_record_hash"],
        ),
        (
            precedence_activation_b["policy_activation_id"],
            precedence_activation_b["policy_id"],
            precedence_activation_b["policy_version"],
            precedence_activation_b["policy_hash"],
            precedence_activation_b["policy_activation_record_hash"],
        ),
    ])

    with pytest.raises(ValidationError) as structural_rejection:
        ADR020BindingsContract.model_validate(bindings, strict=True)
    errors = structural_rejection.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "value_error"
    assert (
        "precedence_binding must match exactly one normative_precedence "
        "policy_binding"
    ) in errors[0]["msg"]

    false_precedence_decision = _decision(
        "precedence-divergence-int7b", bindings,
    )
    with pytest.raises((DBAPIError, IntegrityError)) as caught:
        with engine.begin() as connection:
            connection.execute(
                insert(models.ActivationDecision),
                false_precedence_decision,
            )
    assert caught.value.orig.sqlstate == "23503"
    assert PRECEDENCE_BINDING_TOKEN in str(caught.value)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_decisions
            WHERE activation_decision_id = :decision_id
        """), {
            "decision_id": false_precedence_decision["activation_decision_id"],
        }) == 0


def _assert_precedence_rejection(engine, decision):
    with pytest.raises((DBAPIError, IntegrityError)) as caught:
        with engine.begin() as connection:
            connection.execute(insert(models.ActivationDecision), decision)
    assert caught.value.orig.sqlstate == "23503"
    assert PRECEDENCE_BINDING_TOKEN in str(caught.value)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_decisions
            WHERE activation_decision_id = :decision_id
        """), {"decision_id": decision["activation_decision_id"]}) == 0


def _precedence_physical_records(engine, suffix):
    contract_a, contract_b, bindings = _coverage_intention_6_records(suffix)
    _set_coverage_binding(bindings, contract_a, contract_a)
    with engine.begin() as connection:
        connection.execute(insert(models.CoverageContract), [contract_a, contract_b])
    return bindings


def test_precedence_binding_accepts_exact_policy_binding(postgresql_0034):
    engine = postgresql_0034["engine"]
    bindings = _precedence_physical_records(engine, "precedence-exact-int7b")
    _materialize_policy_activations(engine, bindings["policy_bindings"])
    assert ADR020BindingsContract.model_validate(
        bindings, strict=True,
    ).model_dump() == bindings
    decision = _decision("precedence-exact-int7b", bindings)
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationDecision), decision)
    with engine.connect() as connection:
        persisted = connection.execute(text("""
            SELECT precedence_binding, continuity_binding,
                   activation_decision_id
            FROM activation_decisions
            WHERE activation_decision_id = :decision_id
        """), {"decision_id": decision["activation_decision_id"]}).one()
    assert persisted == (
        decision["precedence_binding"], decision["continuity_binding"],
        decision["activation_decision_id"],
    )


@pytest.mark.parametrize(
    "case", ("zero_exact", "two_exact", "one_exact_one_other"),
)
def test_precedence_binding_enforces_exact_cumulative_cardinality(
    postgresql_0034, case,
):
    engine = postgresql_0034["engine"]
    bindings = _precedence_physical_records(engine, f"precedence-cardinality-{case}")
    exact = next(
        item for item in bindings["policy_bindings"]
        if item["policy_type"] == "normative_precedence"
    )
    activations = list(bindings["policy_bindings"])
    if case == "zero_exact":
        bindings["precedence_binding"]["precedence_policy_id"] = "absent-policy"
    elif case == "two_exact":
        bindings["policy_bindings"].append(copy.deepcopy(exact))
    else:
        other = copy.deepcopy(exact)
        other.update({
            "policy_id": f"other-precedence-{case}",
            "policy_hash": _digest(f"other-precedence-{case}"),
            "policy_activation_id": f"other-precedence-activation-{case}",
            "policy_activation_record_hash": _digest(
                f"other-precedence-activation-{case}",
            ),
        })
        bindings["policy_bindings"].append(other)
        activations.append(other)
    _materialize_policy_activations(engine, activations)
    decision = _decision(f"precedence-cardinality-{case}", bindings)
    if case == "one_exact_one_other":
        with engine.begin() as connection:
            connection.execute(insert(models.ActivationDecision), decision)
        with engine.connect() as connection:
            assert connection.scalar(text("""
                SELECT count(*) FROM activation_decisions
                WHERE activation_decision_id = :decision_id
            """), {"decision_id": decision["activation_decision_id"]}) == 1
    else:
        _assert_precedence_rejection(engine, decision)


@pytest.mark.parametrize(
    "case",
    (
        "json_null", "array", "string", "wrong_subject_type",
        "missing_policy_id", "missing_policy_version", "missing_policy_hash",
        "missing_activation_id", "missing_activation_record_hash",
        "numeric_policy_id", "text_policy_version", "non_text_policy_hash",
        "numeric_activation_id", "non_text_activation_record_hash",
    ),
)
def test_precedence_binding_rejects_adversarial_jsonb_types(
    postgresql_0034, case,
):
    engine = postgresql_0034["engine"]
    bindings = _precedence_physical_records(engine, f"precedence-{case}")
    exact = next(
        item for item in bindings["policy_bindings"]
        if item["policy_type"] == "normative_precedence"
    )
    precedence = bindings["precedence_binding"]
    if case == "numeric_policy_id":
        exact["policy_id"] = "12345"
        precedence["precedence_policy_id"] = 12345
    elif case == "numeric_activation_id":
        exact["policy_activation_id"] = "67890"
        precedence["precedence_policy_activation_id"] = 67890
    elif case == "non_text_policy_hash":
        exact["policy_hash"] = "1" * 64
        precedence["precedence_policy_hash"] = int("1" * 64)
    elif case == "non_text_activation_record_hash":
        exact["policy_activation_record_hash"] = "2" * 64
        precedence["precedence_policy_activation_record_hash"] = int("2" * 64)
    _materialize_policy_activations(engine, bindings["policy_bindings"])
    if case == "json_null":
        bindings["precedence_binding"] = None
    elif case == "array":
        bindings["precedence_binding"] = []
    elif case == "string":
        bindings["precedence_binding"] = "normative_precedence"
    elif case == "wrong_subject_type":
        precedence["precedence_subject_type"] = "other"
    elif case.startswith("missing_"):
        field = {
            "missing_policy_id": "precedence_policy_id",
            "missing_policy_version": "precedence_policy_version",
            "missing_policy_hash": "precedence_policy_hash",
            "missing_activation_id": "precedence_policy_activation_id",
            "missing_activation_record_hash":
                "precedence_policy_activation_record_hash",
        }[case]
        precedence.pop(field)
    elif case == "text_policy_version":
        precedence["precedence_policy_version"] = "1"
    _assert_precedence_rejection(
        engine, _decision(f"precedence-adversarial-{case}", bindings),
    )


def _assert_continuity_rejection(engine, decision):
    with pytest.raises((DBAPIError, IntegrityError)) as caught:
        with engine.begin() as connection:
            connection.execute(insert(models.ActivationDecision), decision)
    assert caught.value.orig.sqlstate == "23503"
    assert CONTINUITY_BINDING_TOKEN in str(caught.value)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_decisions
            WHERE activation_decision_id = :decision_id
        """), {"decision_id": decision["activation_decision_id"]}) == 0


def _continuity_physical_records(engine, suffix):
    contract_a, contract_b, bindings = _coverage_intention_6_records(suffix)
    _set_coverage_binding(bindings, contract_a, contract_a)
    with engine.begin() as connection:
        connection.execute(insert(models.CoverageContract), [contract_a, contract_b])
    return bindings


def test_continuity_binding_accepts_exact_policy_binding(postgresql_0033):
    engine = postgresql_0033["engine"]
    bindings = _continuity_physical_records(engine, "continuity-exact-int7a")
    _materialize_policy_activations(engine, bindings["policy_bindings"])
    assert ADR020BindingsContract.model_validate(
        bindings, strict=True,
    ).model_dump() == bindings
    decision = _decision("continuity-exact-int7a", bindings)
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationDecision), decision)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_decisions
            WHERE activation_decision_id = :decision_id
        """), {"decision_id": decision["activation_decision_id"]}) == 1


@pytest.mark.parametrize(
    "case", ("zero_exact", "two_exact", "one_exact_one_other"),
)
def test_continuity_binding_enforces_exact_cumulative_cardinality(
    postgresql_0033, case,
):
    engine = postgresql_0033["engine"]
    bindings = _continuity_physical_records(engine, f"cardinality-{case}")
    exact = bindings["policy_bindings"][0]
    activations = list(bindings["policy_bindings"])
    if case == "zero_exact":
        bindings["continuity_binding"]["continuity_policy_id"] = "absent-policy"
    elif case == "two_exact":
        bindings["policy_bindings"].append(copy.deepcopy(exact))
    else:
        other = copy.deepcopy(exact)
        other.update({
            "policy_id": f"other-continuity-{case}",
            "policy_hash": _digest(f"other-continuity-{case}"),
            "policy_activation_id": f"other-continuity-activation-{case}",
            "policy_activation_record_hash": _digest(
                f"other-continuity-activation-{case}",
            ),
        })
        bindings["policy_bindings"].append(other)
        activations.append(other)
    _materialize_policy_activations(engine, activations)
    decision = _decision(f"continuity-cardinality-{case}", bindings)
    if case == "one_exact_one_other":
        with engine.begin() as connection:
            connection.execute(insert(models.ActivationDecision), decision)
        with engine.connect() as connection:
            assert connection.scalar(text("""
                SELECT count(*) FROM activation_decisions
                WHERE activation_decision_id = :decision_id
            """), {"decision_id": decision["activation_decision_id"]}) == 1
    else:
        _assert_continuity_rejection(engine, decision)


@pytest.mark.parametrize(
    "case",
    (
        "json_null", "array", "string", "wrong_subject_type",
        "missing_policy_id", "missing_policy_version", "missing_policy_hash",
        "missing_activation_id", "missing_activation_record_hash",
        "numeric_policy_id", "text_policy_version", "non_text_policy_hash",
        "numeric_activation_id", "non_text_activation_record_hash",
    ),
)
def test_continuity_binding_rejects_adversarial_jsonb_types(
    postgresql_0033, case,
):
    engine = postgresql_0033["engine"]
    bindings = _continuity_physical_records(engine, f"continuity-{case}")
    exact = bindings["policy_bindings"][0]
    if case == "numeric_policy_id":
        exact["policy_id"] = "12345"
        bindings["continuity_binding"]["continuity_policy_id"] = 12345
    elif case == "numeric_activation_id":
        exact["policy_activation_id"] = "67890"
        bindings["continuity_binding"]["continuity_policy_activation_id"] = 67890
    elif case == "non_text_policy_hash":
        exact["policy_hash"] = "1" * 64
        bindings["continuity_binding"]["continuity_policy_hash"] = int("1" * 64)
    elif case == "non_text_activation_record_hash":
        exact["policy_activation_record_hash"] = "2" * 64
        bindings["continuity_binding"][
            "continuity_policy_activation_record_hash"
        ] = int("2" * 64)
    _materialize_policy_activations(engine, bindings["policy_bindings"])
    continuity = bindings["continuity_binding"]
    if case == "json_null":
        bindings["continuity_binding"] = None
    elif case == "array":
        bindings["continuity_binding"] = []
    elif case == "string":
        bindings["continuity_binding"] = "normative_continuity"
    elif case == "wrong_subject_type":
        continuity["continuity_subject_type"] = "other"
    elif case.startswith("missing_"):
        field = {
            "missing_policy_id": "continuity_policy_id",
            "missing_policy_version": "continuity_policy_version",
            "missing_policy_hash": "continuity_policy_hash",
            "missing_activation_id": "continuity_policy_activation_id",
            "missing_activation_record_hash":
                "continuity_policy_activation_record_hash",
        }[case]
        continuity.pop(field)
    elif case == "text_policy_version":
        continuity["continuity_policy_version"] = "1"
    decision = _decision(f"continuity-adversarial-{case}", bindings)
    _assert_continuity_rejection(engine, decision)


def _coverage_intention_6_records(suffix):
    common = {
        "source_id": f"coverage-source-{suffix}", "contract_version": 1,
        "contract_state": "ratificada",
        "effective_from": datetime(2026, 8, 3, tzinfo=timezone.utc),
        "effective_to": None, "timezone": "UTC",
        "expected_calendar": {"frequency": "daily"},
        "publication_schedule": {"hour": 0},
        "delay_windows": {"maximum_minutes": 60},
        "mandatory_sections": ["records"],
        "expected_files_partitions": {"partitions": ["daily"]},
        "pagination": {"mode": "cursor"}, "cursors": {"field": "next_cursor"},
        "empty_response_semantics": {"allowed": True},
        "proven_absence_rules": {"requires_evidence": True},
        "authorized_redirects": [], "media_types": ["application/json"],
        "adapter_id": "coverage-adapter", "compatible_adapter_versions": [1],
        "technical_limits": {"requests_per_minute": 60},
        "retry_policy": {"maximum_attempts": 3},
        "continuity_policy_reference": {"policy_id": f"continuity-{suffix}"},
        "evidence": {"mission": "MISSION-009A-INTENCAO-6"},
        "audit": {"outcome": "favorable"},
        "ratification": {"state": "ratified"},
        "revocation": {"state": "not_revoked"},
    }
    contracts = []
    for label in ("a", "b"):
        contracts.append({
            **common,
            "coverage_contract_record_id": f"coverage-record-{label}-{suffix}",
            "coverage_contract_id": f"coverage-contract-{label}-{suffix}",
            "contract_hash": _digest(f"coverage-contract-{label}-{suffix}"),
            "record_hash": _digest(f"coverage-record-{label}-{suffix}"),
        })
    bindings = _bindings()
    continuity, precedence = bindings["policy_bindings"]
    for label, binding in (("continuity", continuity), ("precedence", precedence)):
        binding.update({
            "policy_id": f"{label}-{suffix}",
            "policy_hash": _digest(f"{label}-{suffix}"),
            "policy_activation_id": f"{label}-activation-{suffix}",
            "policy_activation_record_hash": _digest(f"{label}-activation-{suffix}"),
        })
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
    coverage_policy = {
        "policy_type": "coverage_contract", "policy_id": f"coverage-policy-{suffix}",
        "policy_version": 1, "policy_hash": _digest(f"coverage-policy-{suffix}"),
        "policy_activation_id": f"coverage-activation-{suffix}",
        "policy_activation_record_hash": _digest(f"coverage-activation-{suffix}"),
    }
    bindings["policy_bindings"].append(coverage_policy)
    return contracts[0], contracts[1], bindings


def _set_coverage_binding(bindings, identity_contract, record_contract):
    bindings["coverage_binding"] = {
        "coverage_subject_type": "coverage_contract",
        "coverage_contract_id": identity_contract["coverage_contract_id"],
        "contract_version": identity_contract["contract_version"],
        "contract_hash": identity_contract["contract_hash"],
        "coverage_contract_record_id":
            record_contract["coverage_contract_record_id"],
        "coverage_contract_record_hash": record_contract["record_hash"],
    }


def _assert_coverage_rejection(engine, decision):
    with pytest.raises((DBAPIError, IntegrityError)) as caught:
        with engine.begin() as connection:
            connection.execute(insert(models.ActivationDecision), decision)
    assert caught.value.orig.sqlstate == "23503"
    assert COVERAGE_BINDING_TOKEN in str(caught.value)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_decisions
            WHERE activation_decision_id = :decision_id
        """), {"decision_id": decision["activation_decision_id"]}) == 0


def test_coverage_binding_rejects_contract_identity_and_record_from_different_contracts(
    postgresql_intention_6,
):
    engine = postgresql_intention_6["engine"]
    contract_common = {
        "source_id": "coverage-source",
        "contract_version": 1,
        "contract_state": "ratificada",
        "effective_from": datetime(2026, 8, 3, tzinfo=timezone.utc),
        "effective_to": None,
        "timezone": "UTC",
        "expected_calendar": {"frequency": "daily"},
        "publication_schedule": {"hour": 0},
        "delay_windows": {"maximum_minutes": 60},
        "mandatory_sections": ["records"],
        "expected_files_partitions": {"partitions": ["daily"]},
        "pagination": {"mode": "cursor"},
        "cursors": {"field": "next_cursor"},
        "empty_response_semantics": {"allowed": True},
        "proven_absence_rules": {"requires_evidence": True},
        "authorized_redirects": [],
        "media_types": ["application/json"],
        "adapter_id": "coverage-adapter",
        "compatible_adapter_versions": [1],
        "technical_limits": {"requests_per_minute": 60},
        "retry_policy": {"maximum_attempts": 3},
        "continuity_policy_reference": {"policy_id": "continuity-policy-int6"},
        "evidence": {"mission": "MISSION-009A-INTENCAO-6"},
        "audit": {"outcome": "favorable"},
        "ratification": {"state": "ratified"},
        "revocation": {"state": "not_revoked"},
    }
    contract_a = {
        **contract_common,
        "coverage_contract_record_id": "coverage-record-a",
        "coverage_contract_id": "coverage-contract-a",
        "contract_hash": _digest("coverage-contract-a"),
        "record_hash": _digest("coverage-record-a"),
    }
    contract_b = {
        **contract_common,
        "coverage_contract_record_id": "coverage-record-b",
        "coverage_contract_id": "coverage-contract-b",
        "contract_hash": _digest("coverage-contract-b"),
        "record_hash": _digest("coverage-record-b"),
    }

    bindings = _bindings()
    continuity, precedence = bindings["policy_bindings"]
    continuity.update({
        "policy_id": "continuity-policy-int6",
        "policy_hash": _digest("continuity-policy-int6"),
        "policy_activation_id": "continuity-activation-int6",
        "policy_activation_record_hash": _digest("continuity-activation-int6"),
    })
    precedence.update({
        "policy_id": "precedence-policy-int6",
        "policy_hash": _digest("precedence-policy-int6"),
        "policy_activation_id": "precedence-activation-int6",
        "policy_activation_record_hash": _digest("precedence-activation-int6"),
    })
    coverage_policy = {
        "policy_type": "coverage_contract",
        "policy_id": "coverage-policy-int6",
        "policy_version": 1,
        "policy_hash": _digest("coverage-policy-int6"),
        "policy_activation_id": "coverage-policy-activation-int6",
        "policy_activation_record_hash": _digest(
            "coverage-policy-activation-int6"
        ),
    }
    bindings["policy_bindings"].append(coverage_policy)
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
    bindings["coverage_binding"] = {
        "coverage_subject_type": "coverage_contract",
        "coverage_contract_id": contract_a["coverage_contract_id"],
        "contract_version": contract_a["contract_version"],
        "contract_hash": contract_a["contract_hash"],
        "coverage_contract_record_id": contract_b["coverage_contract_record_id"],
        "coverage_contract_record_hash": contract_b["record_hash"],
    }

    validated = ADR020BindingsContract.model_validate(bindings, strict=True)
    assert validated.model_dump() == bindings
    assert sum(
        binding.policy_type == "coverage_contract"
        for binding in validated.policy_bindings
    ) == 1

    with engine.begin() as connection:
        connection.execute(
            insert(models.CoverageContract), [contract_a, contract_b],
        )
    _materialize_policy_activations(engine, bindings["policy_bindings"])
    with engine.connect() as connection:
        persisted_contracts = connection.execute(text("""
            SELECT coverage_contract_record_id, coverage_contract_id,
                   contract_version, contract_hash, record_hash
            FROM coverage_contracts
            ORDER BY coverage_contract_record_id
        """)).all()
    assert persisted_contracts == [
        (
            contract_a["coverage_contract_record_id"],
            contract_a["coverage_contract_id"],
            contract_a["contract_version"],
            contract_a["contract_hash"],
            contract_a["record_hash"],
        ),
        (
            contract_b["coverage_contract_record_id"],
            contract_b["coverage_contract_id"],
            contract_b["contract_version"],
            contract_b["contract_hash"],
            contract_b["record_hash"],
        ),
    ]

    false_pair_decision = _decision("coverage-false-pair-int6", bindings)
    _assert_coverage_rejection(engine, false_pair_decision)


def test_coverage_binding_accepts_exact_contract_record(postgresql_intention_6):
    engine = postgresql_intention_6["engine"]
    contract_a, contract_b, bindings = _coverage_intention_6_records("positive")
    _set_coverage_binding(bindings, contract_a, contract_a)
    validated = ADR020BindingsContract.model_validate(bindings, strict=True)
    assert validated.model_dump() == bindings
    with engine.begin() as connection:
        connection.execute(insert(models.CoverageContract), [contract_a, contract_b])
    _materialize_policy_activations(engine, bindings["policy_bindings"])
    decision = _decision("coverage-exact-int6", bindings)
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationDecision), decision)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_decisions
            WHERE activation_decision_id = :decision_id
        """), {"decision_id": decision["activation_decision_id"]}) == 1


def test_coverage_binding_gate_is_prospective_and_rejects_new_mismatch(
    postgresql_intention_6_prospective,
):
    engine = postgresql_intention_6_prospective["engine"]
    contract_a, contract_b, bindings = _coverage_intention_6_records("prospective")
    with engine.begin() as connection:
        connection.execute(insert(models.CoverageContract), [contract_a, contract_b])
    _materialize_policy_activations(engine, bindings["policy_bindings"])
    _set_coverage_binding(bindings, contract_a, contract_b)
    historical = _decision("coverage-historical-int6", bindings)
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationDecision), historical)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        migration_0032 = _load_migration(
            COVERAGE_BINDING_MIGRATION, "test_prospective_physical_0032",
        )
        migration_0032.op = operations
        migration_0032.upgrade()
        connection.execute(text("""
            UPDATE alembic_version
            SET version_num = :coverage_revision
            WHERE version_num = :bootstrap_revision
        """), {
            "coverage_revision": COVERAGE_BINDING_REVISION,
            "bootstrap_revision": BOOTSTRAP_BINDING_REVISION,
        })

    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_decisions
            WHERE activation_decision_id = :decision_id
        """), {"decision_id": historical["activation_decision_id"]}) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM pg_proc WHERE proname = :function_name
        """), {"function_name": COVERAGE_BINDING_FUNCTION}) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM pg_trigger WHERE tgname = :trigger_name
        """), {"trigger_name": COVERAGE_BINDING_TRIGGER}) == 1

    mismatch = _decision("coverage-new-mismatch-int6", bindings)
    _assert_coverage_rejection(engine, mismatch)
    _set_coverage_binding(bindings, contract_a, contract_a)
    exact = _decision("coverage-new-exact-int6", bindings)
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationDecision), exact)
    with engine.connect() as connection:
        counts = connection.execute(text("""
            SELECT activation_decision_id FROM activation_decisions
            WHERE activation_decision_id IN (:historical_id, :exact_id)
            ORDER BY activation_decision_id
        """), {
            "historical_id": historical["activation_decision_id"],
            "exact_id": exact["activation_decision_id"],
        }).scalars().all()
    assert counts == sorted([
        historical["activation_decision_id"], exact["activation_decision_id"],
    ])


@pytest.mark.parametrize(
    "case", ("missing_contract", "mixed_contracts", "missing_record_hash", "text_version"),
)
def test_coverage_binding_rejects_fail_closed_forms(postgresql_intention_6, case):
    engine = postgresql_intention_6["engine"]
    contract_a, contract_b, bindings = _coverage_intention_6_records(case)
    with engine.begin() as connection:
        connection.execute(insert(models.CoverageContract), [contract_a, contract_b])
    _materialize_policy_activations(engine, bindings["policy_bindings"])
    _set_coverage_binding(bindings, contract_a, contract_a)
    if case == "missing_contract":
        bindings["coverage_binding"]["coverage_contract_id"] = "absent-contract"
    elif case == "mixed_contracts":
        _set_coverage_binding(bindings, contract_a, contract_b)
    elif case == "missing_record_hash":
        bindings["coverage_binding"].pop("coverage_contract_record_hash")
    else:
        bindings["coverage_binding"]["contract_version"] = "1"
    decision = _decision(f"coverage-fail-closed-{case}", bindings)
    _assert_coverage_rejection(engine, decision)


@pytest.mark.parametrize(
    "case",
    (
        "json_null",
        "array",
        "string",
        "wrong_subject_type",
        "missing_record_id",
        "missing_contract_id",
        "missing_contract_version",
        "missing_contract_hash",
        "missing_record_hash",
        "text_contract_version",
        "numeric_record_id",
        "numeric_contract_id",
        "non_text_contract_hash",
        "non_text_record_hash",
    ),
)
def test_coverage_binding_rejects_adversarial_jsonb_types(
    postgresql_intention_6, case,
):
    engine = postgresql_intention_6["engine"]
    contract_a, contract_b, bindings = _coverage_intention_6_records(
        f"adversarial-{case}"
    )
    if case == "numeric_record_id":
        contract_a["coverage_contract_record_id"] = "12345"
    elif case == "numeric_contract_id":
        contract_a["coverage_contract_id"] = "67890"
    elif case == "non_text_contract_hash":
        contract_a["contract_hash"] = "1" * 64
    elif case == "non_text_record_hash":
        contract_a["record_hash"] = "2" * 64

    with engine.begin() as connection:
        connection.execute(insert(models.CoverageContract), [contract_a, contract_b])
    _materialize_policy_activations(engine, bindings["policy_bindings"])
    _set_coverage_binding(bindings, contract_a, contract_a)

    if case == "json_null":
        bindings["coverage_binding"] = None
    elif case == "array":
        bindings["coverage_binding"] = []
    elif case == "string":
        bindings["coverage_binding"] = "coverage_contract"
    elif case == "wrong_subject_type":
        bindings["coverage_binding"]["coverage_subject_type"] = "other"
    elif case == "missing_record_id":
        bindings["coverage_binding"].pop("coverage_contract_record_id")
    elif case == "missing_contract_id":
        bindings["coverage_binding"].pop("coverage_contract_id")
    elif case == "missing_contract_version":
        bindings["coverage_binding"].pop("contract_version")
    elif case == "missing_contract_hash":
        bindings["coverage_binding"].pop("contract_hash")
    elif case == "missing_record_hash":
        bindings["coverage_binding"].pop("coverage_contract_record_hash")
    elif case == "text_contract_version":
        bindings["coverage_binding"]["contract_version"] = "1"
    elif case == "numeric_record_id":
        bindings["coverage_binding"]["coverage_contract_record_id"] = 12345
    elif case == "numeric_contract_id":
        bindings["coverage_binding"]["coverage_contract_id"] = 67890
    elif case == "non_text_contract_hash":
        bindings["coverage_binding"]["contract_hash"] = int("1" * 64)
    else:
        bindings["coverage_binding"]["coverage_contract_record_hash"] = int(
            "2" * 64
        )

    decision = _decision(f"coverage-adversarial-{case}", bindings)
    _assert_coverage_rejection(engine, decision)


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


def test_continuity_binding_gate_is_prospective_and_rejects_new_divergence(
    postgresql_0033_prospective,
):
    engine = postgresql_0033_prospective["engine"]
    bindings = _continuity_physical_records(engine, "continuity-prospective")
    exact = bindings["policy_bindings"][0]
    other = copy.deepcopy(exact)
    other.update({
        "policy_id": "continuity-policy-prospective-b",
        "policy_hash": _digest("continuity-policy-prospective-b"),
        "policy_activation_id": "continuity-activation-prospective-b",
        "policy_activation_record_hash": _digest(
            "continuity-activation-prospective-b",
        ),
    })
    _materialize_policy_activations(
        engine, [*bindings["policy_bindings"], other],
    )
    bindings["continuity_binding"].update({
        "continuity_policy_id": other["policy_id"],
        "continuity_policy_version": other["policy_version"],
        "continuity_policy_hash": other["policy_hash"],
        "continuity_policy_activation_id": other["policy_activation_id"],
        "continuity_policy_activation_record_hash":
            other["policy_activation_record_hash"],
    })
    historical = _decision("continuity-historical-int7a", bindings)
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationDecision), historical)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        migration_0033 = _load_migration(
            CONTINUITY_BINDING_MIGRATION, "test_prospective_physical_0033",
        )
        migration_0033.op = operations
        migration_0033.upgrade()
        connection.execute(text("""
            UPDATE alembic_version
            SET version_num = :continuity_revision
            WHERE version_num = :coverage_revision
        """), {
            "continuity_revision": CONTINUITY_BINDING_REVISION,
            "coverage_revision": COVERAGE_BINDING_REVISION,
        })

    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_decisions
            WHERE activation_decision_id = :decision_id
        """), {"decision_id": historical["activation_decision_id"]}) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM pg_proc WHERE proname = :function_name
        """), {"function_name": CONTINUITY_BINDING_FUNCTION}) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM pg_trigger WHERE tgname = :trigger_name
        """), {"trigger_name": CONTINUITY_BINDING_TRIGGER}) == 1

    mismatch = _decision("continuity-new-mismatch-int7a", bindings)
    _assert_continuity_rejection(engine, mismatch)
    bindings["continuity_binding"].update({
        "continuity_policy_id": exact["policy_id"],
        "continuity_policy_version": exact["policy_version"],
        "continuity_policy_hash": exact["policy_hash"],
        "continuity_policy_activation_id": exact["policy_activation_id"],
        "continuity_policy_activation_record_hash":
            exact["policy_activation_record_hash"],
    })
    accepted = _decision("continuity-new-exact-int7a", bindings)
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationDecision), accepted)
    with engine.connect() as connection:
        assert connection.execute(text("""
            SELECT activation_decision_id FROM activation_decisions
            WHERE activation_decision_id IN (:historical_id, :accepted_id)
            ORDER BY activation_decision_id
        """), {
            "historical_id": historical["activation_decision_id"],
            "accepted_id": accepted["activation_decision_id"],
        }).scalars().all() == sorted([
            historical["activation_decision_id"],
            accepted["activation_decision_id"],
        ])


def test_continuity_binding_migration_has_exact_static_contract(monkeypatch):
    assert CONTINUITY_BINDING_MIGRATION.exists()
    source = CONTINUITY_BINDING_MIGRATION.read_text(encoding="utf-8")
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
        "revision": CONTINUITY_BINDING_REVISION,
        "down_revision": COVERAGE_BINDING_REVISION,
    }
    assert len(CONTINUITY_BINDING_REVISION) <= 32
    for token in (
        CONTINUITY_BINDING_FUNCTION, CONTINUITY_BINDING_TRIGGER,
        "BEFORE INSERT ON activation_decisions", "FOR EACH ROW",
        "jsonb_array_elements", "SELECT count(*)", "exact_match_count <> 1",
        "23503", CONTINUITY_BINDING_TOKEN,
    ):
        assert token in source
    for field, jsonb_type in (
        ("continuity_subject_type", "string"),
        ("continuity_policy_id", "string"),
        ("continuity_policy_version", "number"),
        ("continuity_policy_hash", "string"),
        ("continuity_policy_activation_id", "string"),
        ("continuity_policy_activation_record_hash", "string"),
    ):
        assert re.search(
            rf"jsonb_typeof\(\s*NEW\.continuity_binding\s*"
            rf"->\s*'{field}'\s*\)\s+IS DISTINCT FROM\s+'{jsonb_type}'",
            source,
        )
    compared_fields = (
        "policy_type", "policy_id", "policy_version", "policy_hash",
        "policy_activation_id", "policy_activation_record_hash",
    )
    for field in compared_fields:
        assert re.search(rf"binding\s*->\s*'{field}'", source)
        assert not re.search(rf"binding\s*->>\s*'{field}'", source)
    assert "policy_bindings) IS DISTINCT FROM 'array'" in source
    assert not re.search(r"\b(update|delete)\b", lowered)
    for forbidden in ("backfill", "precedence", "gates"):
        assert forbidden not in lowered
    assert "raise runtimeerror" in lowered and "irreversible" in lowered

    migration = _load_migration(
        CONTINUITY_BINDING_MIGRATION, "test_0033_non_postgresql_guard",
    )
    class NonPostgresqlOperations:
        def get_bind(self):
            return type("Bind", (), {
                "dialect": type("Dialect", (), {"name": "sqlite"})(),
            })()
    monkeypatch.setattr(migration, "op", NonPostgresqlOperations())
    with pytest.raises(RuntimeError, match="PostgreSQL-only"):
        migration.upgrade()
    with pytest.raises(RuntimeError, match="irreversible"):
        migration.downgrade()


def test_continuity_binding_function_and_trigger_are_physically_installed(
    postgresql_0033,
):
    engine = postgresql_0033["engine"]
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT version_num FROM alembic_version"
        )) == CONTINUITY_BINDING_REVISION
        function_count = connection.scalar(text("""
            SELECT count(*) FROM pg_proc WHERE proname = :function_name
        """), {"function_name": CONTINUITY_BINDING_FUNCTION})
        trigger = connection.execute(text("""
            SELECT t.tgname, t.tgisinternal, t.tgenabled, c.relname,
                   pg_get_triggerdef(t.oid), p.proname
            FROM pg_trigger AS t
            JOIN pg_class AS c ON c.oid = t.tgrelid
            JOIN pg_proc AS p ON p.oid = t.tgfoid
            WHERE t.tgname = :trigger_name
        """), {"trigger_name": CONTINUITY_BINDING_TRIGGER}).one()
    assert function_count == 1
    assert trigger[0:4] == (
        CONTINUITY_BINDING_TRIGGER, False, "O", "activation_decisions",
    )
    assert "BEFORE INSERT" in trigger[4]
    assert trigger[5] == CONTINUITY_BINDING_FUNCTION


def test_precedence_binding_gate_is_prospective_and_rejects_new_divergence(
    postgresql_0034_prospective,
):
    engine = postgresql_0034_prospective["engine"]
    bindings = _precedence_physical_records(engine, "precedence-prospective")
    exact = next(
        item for item in bindings["policy_bindings"]
        if item["policy_type"] == "normative_precedence"
    )
    other = copy.deepcopy(exact)
    other.update({
        "policy_id": "precedence-policy-prospective-b",
        "policy_hash": _digest("precedence-policy-prospective-b"),
        "policy_activation_id": "precedence-activation-prospective-b",
        "policy_activation_record_hash": _digest(
            "precedence-activation-prospective-b",
        ),
    })
    _materialize_policy_activations(engine, [*bindings["policy_bindings"], other])
    bindings["precedence_binding"].update({
        "precedence_policy_id": other["policy_id"],
        "precedence_policy_version": other["policy_version"],
        "precedence_policy_hash": other["policy_hash"],
        "precedence_policy_activation_id": other["policy_activation_id"],
        "precedence_policy_activation_record_hash":
            other["policy_activation_record_hash"],
    })
    historical = _decision("precedence-historical-int7b", bindings)
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationDecision), historical)
        before = connection.execute(text("""
            SELECT activation_decision_id, record_hash
            FROM activation_decisions
            WHERE activation_decision_id = :decision_id
        """), {"decision_id": historical["activation_decision_id"]}).one()

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        migration_0034 = _load_migration(
            PRECEDENCE_BINDING_MIGRATION, "test_prospective_physical_0034",
        )
        migration_0034.op = operations
        migration_0034.upgrade()
        connection.execute(text("""
            UPDATE alembic_version
            SET version_num = :precedence_revision
            WHERE version_num = :continuity_revision
        """), {
            "precedence_revision": PRECEDENCE_BINDING_REVISION,
            "continuity_revision": CONTINUITY_BINDING_REVISION,
        })

    with engine.connect() as connection:
        after = connection.execute(text("""
            SELECT activation_decision_id, record_hash
            FROM activation_decisions
            WHERE activation_decision_id = :decision_id
        """), {"decision_id": historical["activation_decision_id"]}).one()
    assert after == before
    _assert_precedence_rejection(
        engine, _decision("precedence-new-mismatch-int7b", bindings),
    )
    bindings["precedence_binding"].update({
        "precedence_policy_id": exact["policy_id"],
        "precedence_policy_version": exact["policy_version"],
        "precedence_policy_hash": exact["policy_hash"],
        "precedence_policy_activation_id": exact["policy_activation_id"],
        "precedence_policy_activation_record_hash":
            exact["policy_activation_record_hash"],
    })
    accepted = _decision("precedence-new-exact-int7b", bindings)
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationDecision), accepted)
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT count(*) FROM activation_decisions"
        )) == 2


def test_precedence_binding_migration_has_exact_static_contract(monkeypatch):
    assert PRECEDENCE_BINDING_MIGRATION.exists()
    source = PRECEDENCE_BINDING_MIGRATION.read_text(encoding="utf-8")
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
        "revision": PRECEDENCE_BINDING_REVISION,
        "down_revision": CONTINUITY_BINDING_REVISION,
    }
    assert len(PRECEDENCE_BINDING_REVISION) <= 32
    for token in (
        PRECEDENCE_BINDING_FUNCTION, PRECEDENCE_BINDING_TRIGGER,
        "BEFORE INSERT ON activation_decisions", "FOR EACH ROW",
        "jsonb_array_elements", "SELECT count(*)", "exact_match_count <> 1",
        "23503", PRECEDENCE_BINDING_TOKEN,
    ):
        assert token in source
    for field, jsonb_type in (
        ("precedence_subject_type", "string"),
        ("precedence_policy_id", "string"),
        ("precedence_policy_version", "number"),
        ("precedence_policy_hash", "string"),
        ("precedence_policy_activation_id", "string"),
        ("precedence_policy_activation_record_hash", "string"),
    ):
        assert re.search(
            rf"jsonb_typeof\(\s*NEW\.precedence_binding\s*"
            rf"->\s*'{field}'\s*\)\s+IS DISTINCT FROM\s+'{jsonb_type}'",
            source,
        )
    for field in (
        "policy_type", "policy_id", "policy_version", "policy_hash",
        "policy_activation_id", "policy_activation_record_hash",
    ):
        assert re.search(rf"binding\s*->\s*'{field}'", source)
        assert not re.search(rf"binding\s*->>\s*'{field}'", source)
    assert "policy_bindings) IS DISTINCT FROM 'array'" in source
    assert not re.search(r"\b(update|delete)\b", lowered)
    for forbidden in ("backfill", "gates"):
        assert forbidden not in lowered
    assert "continuity" not in lowered.replace(CONTINUITY_BINDING_REVISION, "")
    assert "raise runtimeerror" in lowered and "irreversible" in lowered

    migration = _load_migration(
        PRECEDENCE_BINDING_MIGRATION, "test_0034_non_postgresql_guard",
    )
    class NonPostgresqlOperations:
        def get_bind(self):
            return type("Bind", (), {
                "dialect": type("Dialect", (), {"name": "sqlite"})(),
            })()
    monkeypatch.setattr(migration, "op", NonPostgresqlOperations())
    with pytest.raises(RuntimeError, match="PostgreSQL-only"):
        migration.upgrade()
    with pytest.raises(RuntimeError, match="irreversible"):
        migration.downgrade()


def test_precedence_binding_function_and_trigger_are_physically_installed(
    postgresql_0034,
):
    engine = postgresql_0034["engine"]
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT version_num FROM alembic_version"
        )) == PRECEDENCE_BINDING_REVISION
        assert connection.scalar(text("""
            SELECT count(*) FROM pg_proc WHERE proname = :function_name
        """), {"function_name": PRECEDENCE_BINDING_FUNCTION}) == 1
        trigger = connection.execute(text("""
            SELECT t.tgname, t.tgisinternal, t.tgenabled, c.relname,
                   pg_get_triggerdef(t.oid), p.proname
            FROM pg_trigger AS t
            JOIN pg_class AS c ON c.oid = t.tgrelid
            JOIN pg_proc AS p ON p.oid = t.tgfoid
            WHERE t.tgname = :trigger_name
        """), {"trigger_name": PRECEDENCE_BINDING_TRIGGER}).one()
    assert trigger[0:4] == (
        PRECEDENCE_BINDING_TRIGGER, False, "O", "activation_decisions",
    )
    assert "BEFORE INSERT" in trigger[4]
    assert trigger[5] == PRECEDENCE_BINDING_FUNCTION


@pytest.mark.parametrize(
    "case, expected_token",
    (
        ("continuity_false", CONTINUITY_BINDING_TOKEN),
        ("precedence_false", PRECEDENCE_BINDING_TOKEN),
        ("policy_activation_false", "ADR020_POLICY_BINDING_ACTIVATION_MISMATCH"),
        ("coverage_false", COVERAGE_BINDING_TOKEN),
        ("integrally_exact", None),
    ),
)
def test_binding_triggers_0030_through_0034_coexist(
    postgresql_0034, case, expected_token,
):
    engine = postgresql_0034["engine"]
    bindings = _precedence_physical_records(engine, f"coexist-{case}")
    activations = copy.deepcopy(bindings["policy_bindings"])
    if case == "continuity_false":
        bindings["continuity_binding"][
            "continuity_policy_activation_record_hash"
        ] = _digest("false-continuity")
    elif case == "precedence_false":
        bindings["precedence_binding"][
            "precedence_policy_activation_record_hash"
        ] = _digest("false-precedence")
    elif case == "policy_activation_false":
        precedence = next(
            item for item in bindings["policy_bindings"]
            if item["policy_type"] == "normative_precedence"
        )
        false_hash = _digest("false-policy-activation")
        precedence["policy_activation_record_hash"] = false_hash
        bindings["precedence_binding"][
            "precedence_policy_activation_record_hash"
        ] = false_hash
    elif case == "coverage_false":
        bindings["coverage_binding"][
            "coverage_contract_record_hash"
        ] = _digest("false-coverage")
    _materialize_policy_activations(engine, activations)
    decision = _decision(f"coexist-{case}", bindings)
    if expected_token is None:
        with engine.begin() as connection:
            connection.execute(insert(models.ActivationDecision), decision)
    else:
        with pytest.raises((DBAPIError, IntegrityError)) as caught:
            with engine.begin() as connection:
                connection.execute(insert(models.ActivationDecision), decision)
        assert caught.value.orig.sqlstate == "23503"
        assert expected_token in str(caught.value)
    with engine.connect() as connection:
        triggers = connection.execute(text("""
            SELECT tgname FROM pg_trigger
            WHERE tgrelid = 'activation_decisions'::regclass
              AND NOT tgisinternal
              AND (tgtype & 2) = 2
              AND (tgtype & 4) = 4
            ORDER BY tgname
        """)).scalars().all()
    assert triggers == sorted([
        POLICY_BINDING_TRIGGER, COVERAGE_BINDING_TRIGGER,
        CONTINUITY_BINDING_TRIGGER, PRECEDENCE_BINDING_TRIGGER,
    ])


@pytest.mark.parametrize(
    "value, expected_token",
    (
        (None, "ADR020_POLICY_BINDING_ACTIVATION_MISMATCH"),
        ({}, "ADR020_POLICY_BINDING_ACTIVATION_MISMATCH"),
        ("bindings", "ADR020_POLICY_BINDING_ACTIVATION_MISMATCH"),
        ([], CONTINUITY_BINDING_TOKEN),
    ),
)
def test_policy_bindings_non_array_or_empty_has_canonical_physical_rejection(
    postgresql_0034, value, expected_token,
):
    engine = postgresql_0034["engine"]
    bindings = _precedence_physical_records(
        engine, f"policy-bindings-shape-{type(value).__name__}",
    )
    bindings["policy_bindings"] = value
    decision = _decision(f"policy-bindings-shape-{uuid.uuid4().hex}", bindings)
    with pytest.raises((DBAPIError, IntegrityError)) as caught:
        with engine.begin() as connection:
            connection.execute(insert(models.ActivationDecision), decision)
    assert caught.value.orig.sqlstate == "23503"
    assert expected_token in str(caught.value)
    assert "cannot extract elements" not in str(caught.value).lower()


def test_coverage_binding_migration_has_exact_static_contract(monkeypatch):
    assert COVERAGE_BINDING_MIGRATION.exists()
    source = COVERAGE_BINDING_MIGRATION.read_text(encoding="utf-8")
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
        "revision": COVERAGE_BINDING_REVISION,
        "down_revision": BOOTSTRAP_BINDING_REVISION,
    }
    assert len(COVERAGE_BINDING_REVISION) <= 32
    for token in (
        COVERAGE_BINDING_FUNCTION, COVERAGE_BINDING_TRIGGER,
        "BEFORE INSERT ON activation_decisions", "coverage_contracts",
        "coverage_contract_record_id", "coverage_contract_id", "contract_version",
        "contract_hash", "coverage_contract_record_hash", "record_hash",
        "to_jsonb(coverage_contracts.contract_version)", "23503",
        COVERAGE_BINDING_TOKEN,
    ):
        assert token in source
    assert "NOT EXISTS" in source
    for field, jsonb_type in (
        ("coverage_subject_type", "string"),
        ("coverage_contract_record_id", "string"),
        ("coverage_contract_id", "string"),
        ("contract_version", "number"),
        ("contract_hash", "string"),
        ("coverage_contract_record_hash", "string"),
    ):
        assert re.search(
            rf"jsonb_typeof\(\s*NEW\.coverage_binding\s*->\s*'{field}'\s*\)"
            rf"\s+IS DISTINCT FROM\s+'{jsonb_type}'",
            source,
        )
    assert "policy_versions" not in lowered
    assert "policy_binding" not in lowered
    assert not re.search(r"\b(update|delete)\b", lowered)
    assert "backfill" not in lowered
    assert "raise runtimeerror" in lowered and "irreversible" in lowered

    migration = _load_migration(
        COVERAGE_BINDING_MIGRATION, "test_0032_non_postgresql_guard",
    )
    class NonPostgresqlOperations:
        def get_bind(self):
            return type("Bind", (), {
                "dialect": type("Dialect", (), {"name": "sqlite"})(),
            })()
    monkeypatch.setattr(migration, "op", NonPostgresqlOperations())
    with pytest.raises(RuntimeError, match="PostgreSQL-only"):
        migration.upgrade()
    with pytest.raises(RuntimeError, match="irreversible"):
        migration.downgrade()


def test_coverage_binding_function_and_trigger_are_physically_installed(
    postgresql_intention_6,
):
    engine = postgresql_intention_6["engine"]
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT version_num FROM alembic_version"
        )) == COVERAGE_BINDING_REVISION
        function_count = connection.scalar(text("""
            SELECT count(*) FROM pg_proc WHERE proname = :function_name
        """), {"function_name": COVERAGE_BINDING_FUNCTION})
        trigger = connection.execute(text("""
            SELECT t.tgname, t.tgisinternal, t.tgenabled, c.relname,
                   pg_get_triggerdef(t.oid), p.proname
            FROM pg_trigger AS t
            JOIN pg_class AS c ON c.oid = t.tgrelid
            JOIN pg_proc AS p ON p.oid = t.tgfoid
            WHERE t.tgname = :trigger_name
        """), {"trigger_name": COVERAGE_BINDING_TRIGGER}).one()
    assert function_count == 1
    assert trigger[0:4] == (
        COVERAGE_BINDING_TRIGGER, False, "O", "activation_decisions",
    )
    assert "BEFORE INSERT" in trigger[4]
    assert trigger[5] == COVERAGE_BINDING_FUNCTION


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
        [sys.executable, "-m", "alembic", "downgrade", "0027_adr020_calc_replay"],
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


def test_normative_activation_rejects_mixed_exact_rule_subject_via_core(
    postgresql_intention_8a,
):
    engine = postgresql_intention_8a["engine"]
    suffix = "mixed-exact-rule-subject-int8a"
    extraction_a = {
        "extraction_result_id": f"extraction-a-{suffix}",
        "record_hash": _digest(f"extraction-a-{suffix}"),
    }
    extraction_b = {
        "extraction_result_id": f"extraction-b-{suffix}",
        "record_hash": _digest(f"extraction-b-{suffix}"),
    }

    def rule(label, version, extraction):
        return {
            "rule_version_record_id": f"rule-version-{label}-{suffix}",
            "rule_id": f"rule-{label}-{suffix}",
            "rule_version": version,
            "rule_hash": _digest(f"rule-{label}-{suffix}"),
            "extraction_result_id": extraction["extraction_result_id"],
            "extraction_result_record_hash": extraction["record_hash"],
            "structured_content": {"rule": label, "version": version},
            "declared_material_validity": {"status": "declared"},
            "normative_references": [],
            "exact_precedence_policy_reference": {
                "policy_id": "precedence-policy",
                "policy_version": 1,
                "policy_hash": _digest("precedence-policy"),
            },
            "evidence": {"mission": "MISSION-009A-INTENCAO-8A"},
            "provenance": {"test": suffix},
            "record_hash": _digest(f"rule-record-{label}-{suffix}"),
        }

    rule_a = rule("a", 1, extraction_a)
    rule_b = rule("b", 2, extraction_b)
    review_a = {
        "rule_review_record_id": f"review-a-{suffix}",
        "subject_id": rule_a["rule_id"],
        "subject_version": rule_a["rule_version"],
        "subject_hash": rule_a["rule_hash"],
        "reviewer": "independent-reviewer",
        "review_event": "revisao_concluida",
        "outcome": "validada",
        "evidence": {"mission": "MISSION-009A-INTENCAO-8A"},
        "record_hash": _digest(f"review-a-{suffix}"),
    }
    bindings = _precedence_physical_records(engine, suffix)
    _materialize_policy_activations(engine, bindings["policy_bindings"])
    decision = _decision(suffix, bindings)
    execution = _execution(decision, suffix)

    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO extraction_results (extraction_result_id, record_hash)
            VALUES (:a_id, :a_hash), (:b_id, :b_hash)
        """), {
            "a_id": extraction_a["extraction_result_id"],
            "a_hash": extraction_a["record_hash"],
            "b_id": extraction_b["extraction_result_id"],
            "b_hash": extraction_b["record_hash"],
        })
        connection.execute(insert(models.RuleVersion), [rule_a, rule_b])

    with engine.connect() as connection:
        rule_created_at_a = connection.scalar(text("""
            SELECT created_at FROM rule_versions
            WHERE rule_id=:id AND rule_version=:version AND rule_hash=:hash
        """), {
            "id": rule_a["rule_id"], "version": rule_a["rule_version"],
            "hash": rule_a["rule_hash"],
        })
        assert rule_created_at_a is not None
        assert connection.scalar(text("""
            SELECT count(*) FROM rule_versions
            WHERE rule_id=:id AND rule_version=:version AND rule_hash=:hash
        """), {
            "id": rule_b["rule_id"], "version": rule_b["rule_version"],
            "hash": rule_b["rule_hash"],
        }) == 1

    review_a["timestamp"] = rule_created_at_a + timedelta(microseconds=1)
    with engine.begin() as connection:
        connection.execute(insert(models.RuleReviewRecord), review_a)

    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM rule_review_records
            WHERE rule_review_record_id=:review_id
              AND subject_id=:id AND subject_version=:version
              AND subject_hash=:hash AND review_event='revisao_concluida'
              AND outcome='validada' AND timestamp=:timestamp
        """), {
            "review_id": review_a["rule_review_record_id"],
            "id": rule_a["rule_id"], "version": rule_a["rule_version"],
            "hash": rule_a["rule_hash"], "timestamp": review_a["timestamp"],
        }) == 1

    with engine.begin() as connection:
        connection.execute(insert(models.ActivationDecision), decision)
        connection.execute(insert(models.ActivationExecution), execution)

    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM rule_versions
            WHERE rule_id=:id AND rule_version=:version AND rule_hash=:hash
        """), {
            "id": rule_a["rule_id"], "version": rule_a["rule_version"],
            "hash": rule_a["rule_hash"],
        }) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM rule_versions
            WHERE rule_id=:id AND rule_version=:version AND rule_hash=:hash
        """), {
            "id": rule_b["rule_id"], "version": rule_b["rule_version"],
            "hash": rule_b["rule_hash"],
        }) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM rule_versions
            WHERE rule_id=:id AND rule_version=:version AND rule_hash=:hash
        """), {
            "id": rule_a["rule_id"], "version": rule_b["rule_version"],
            "hash": rule_b["rule_hash"],
        }) == 0

    control_activation = {
        "normative_activation_id": f"activation-control-{suffix}",
        "activation_decision_id": decision["activation_decision_id"],
        "activation_decision_record_hash": decision["record_hash"],
        "activation_execution_id": execution["activation_execution_id"],
        "subject_type": "rule_version", "subject_id": rule_a["rule_id"],
        "subject_version": rule_a["rule_version"],
        "subject_hash": rule_a["rule_hash"],
        "review_record_id": review_a["rule_review_record_id"],
        "review_record_hash": review_a["record_hash"],
        "domain": "fiscal", "modality": "manual",
        "resolver_scope": {"country": "PT", "tax": "iva"},
        "operational_interval": {"from": "2026-08-03T00:00:00Z"},
        "scope_hash": decision["scope_hash"],
        "activation_generation_id": f"generation-{suffix}",
        "activated_at": datetime.now(timezone.utc), "state": "active",
        "technical_actor": "integration-auditor",
        "provenance": {"mission": "MISSION-009A-INTENCAO-8A"},
        "record_hash": _digest(f"activation-control-{suffix}"),
    }
    with engine.begin() as connection:
        connection.execute(insert(models.NormativeActivation), control_activation)
    false_activation = copy.deepcopy(control_activation)
    false_activation.update({
        "normative_activation_id": f"activation-mixed-{suffix}",
        "record_hash": _digest(f"activation-mixed-{suffix}"),
        "subject_id": rule_a["rule_id"],
        "subject_version": rule_b["rule_version"],
        "subject_hash": rule_b["rule_hash"],
    })
    _assert_subject_gate_rejection(engine, false_activation)


def test_normative_activation_rejects_exact_rule_review_from_another_subject_via_core(
    postgresql_intention_8b1,
):
    engine = postgresql_intention_8b1["engine"]
    suffix = "exact-rule-review-another-subject-int8b1"
    extractions = [
        {
            "extraction_result_id": f"extraction-{label}-{suffix}",
            "record_hash": _digest(f"extraction-{label}-{suffix}"),
        }
        for label in ("a", "b")
    ]

    def rule(label, version, extraction):
        return {
            "rule_version_record_id": f"rule-version-{label}-{suffix}",
            "rule_id": f"rule-{label}-{suffix}",
            "rule_version": version,
            "rule_hash": _digest(f"rule-{label}-{suffix}"),
            "extraction_result_id": extraction["extraction_result_id"],
            "extraction_result_record_hash": extraction["record_hash"],
            "structured_content": {"rule": label, "version": version},
            "declared_material_validity": {"status": "declared"},
            "normative_references": [],
            "exact_precedence_policy_reference": {
                "policy_id": "precedence-policy",
                "policy_version": 1,
                "policy_hash": _digest("precedence-policy"),
            },
            "evidence": {"mission": "MISSION-009A-INTENCAO-8B1"},
            "provenance": {"test": suffix},
            "record_hash": _digest(f"rule-record-{label}-{suffix}"),
        }

    rules = [
        rule("a", 1, extractions[0]),
        rule("b", 2, extractions[1]),
    ]
    rule_a, rule_b = rules
    bindings = _precedence_physical_records(engine, suffix)
    _materialize_policy_activations(engine, bindings["policy_bindings"])

    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO extraction_results (extraction_result_id, record_hash)
            VALUES (:a_id, :a_hash), (:b_id, :b_hash)
        """), {
            "a_id": extractions[0]["extraction_result_id"],
            "a_hash": extractions[0]["record_hash"],
            "b_id": extractions[1]["extraction_result_id"],
            "b_hash": extractions[1]["record_hash"],
        })
        connection.execute(insert(models.RuleVersion), rules)

    created_at = []
    with engine.connect() as connection:
        for current_rule in rules:
            exact = connection.execute(text("""
                SELECT rule_id, rule_version, rule_hash, created_at
                FROM rule_versions
                WHERE rule_id=:id AND rule_version=:version AND rule_hash=:hash
            """), {
                "id": current_rule["rule_id"],
                "version": current_rule["rule_version"],
                "hash": current_rule["rule_hash"],
            }).one()
            assert exact[:3] == (
                current_rule["rule_id"], current_rule["rule_version"],
                current_rule["rule_hash"],
            )
            assert exact.created_at is not None
            created_at.append(exact.created_at)

    reviews = []
    for label, current_rule, rule_created_at in zip(
        ("a", "b"), rules, created_at,
    ):
        reviews.append({
            "rule_review_record_id": f"review-{label}-{suffix}",
            "subject_id": current_rule["rule_id"],
            "subject_version": current_rule["rule_version"],
            "subject_hash": current_rule["rule_hash"],
            "reviewer": "independent-reviewer",
            "review_event": "revisao_concluida",
            "outcome": "validada",
            "evidence": {"mission": "MISSION-009A-INTENCAO-8B1"},
            "timestamp": rule_created_at + timedelta(microseconds=1),
            "record_hash": _digest(f"review-{label}-{suffix}"),
        })
    review_a, review_b = reviews
    with engine.begin() as connection:
        connection.execute(insert(models.RuleReviewRecord), reviews)

    decision = _decision(suffix, bindings)
    execution = _execution(decision, suffix)
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationDecision), decision)
        connection.execute(insert(models.ActivationExecution), execution)

    def exact_rule_count(connection, current_rule):
        return connection.scalar(text("""
            SELECT count(*) FROM rule_versions
            WHERE rule_id=:id AND rule_version=:version AND rule_hash=:hash
        """), {
            "id": current_rule["rule_id"],
            "version": current_rule["rule_version"],
            "hash": current_rule["rule_hash"],
        })

    def exact_review_count(connection, review, subject):
        return connection.scalar(text("""
            SELECT count(*) FROM rule_review_records
            WHERE rule_review_record_id=:review_id AND record_hash=:review_hash
              AND subject_id=:id AND subject_version=:version
              AND subject_hash=:hash
        """), {
            "review_id": review["rule_review_record_id"],
            "review_hash": review["record_hash"],
            "id": subject["rule_id"],
            "version": subject["rule_version"],
            "hash": subject["rule_hash"],
        })

    false_activation_id = f"activation-false-{suffix}"
    with engine.connect() as connection:
        assert exact_rule_count(connection, rule_a) == 1
        assert exact_rule_count(connection, rule_b) == 1
        assert exact_review_count(connection, review_a, rule_a) == 1
        assert exact_review_count(connection, review_b, rule_b) == 1
        assert exact_review_count(connection, review_b, rule_a) == 0
        assert connection.scalar(text("""
            SELECT count(*)
            FROM activation_decisions AS decision
            JOIN activation_executions AS execution
              ON execution.activation_decision_id = decision.activation_decision_id
             AND execution.activation_decision_record_hash = decision.record_hash
            WHERE decision.activation_decision_id=:decision_id
              AND decision.record_hash=:decision_hash
              AND decision.decision_action='activate'
              AND decision.decision_outcome='approved'
              AND execution.activation_execution_id=:execution_id
              AND execution.state=:execution_state
        """), {
            "decision_id": decision["activation_decision_id"],
            "decision_hash": decision["record_hash"],
            "execution_id": execution["activation_execution_id"],
            "execution_state": execution["state"],
        }) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM normative_activations
            WHERE normative_activation_id=:activation_id
        """), {"activation_id": false_activation_id}) == 0

    control_activation = {
        "normative_activation_id": f"activation-control-{suffix}",
        "activation_decision_id": decision["activation_decision_id"],
        "activation_decision_record_hash": decision["record_hash"],
        "activation_execution_id": execution["activation_execution_id"],
        "subject_type": "rule_version",
        "subject_id": rule_a["rule_id"],
        "subject_version": rule_a["rule_version"],
        "subject_hash": rule_a["rule_hash"],
        "review_record_id": review_a["rule_review_record_id"],
        "review_record_hash": review_a["record_hash"],
        "domain": "fiscal", "modality": "manual",
        "resolver_scope": {"country": "PT", "tax": "iva"},
        "operational_interval": {"from": "2026-08-03T00:00:00Z"},
        "scope_hash": decision["scope_hash"],
        "activation_generation_id": f"generation-{suffix}",
        "activated_at": datetime.now(timezone.utc), "state": "active",
        "technical_actor": "integration-auditor",
        "provenance": {"mission": "MISSION-009A-INTENCAO-8B1"},
        "record_hash": _digest(f"activation-control-{suffix}"),
    }
    with engine.begin() as connection:
        connection.execute(insert(models.NormativeActivation), control_activation)
    with engine.connect() as connection:
        persisted_control = connection.execute(text("""
            SELECT normative_activation_id, subject_type, subject_id,
                   subject_version, subject_hash, review_record_id,
                   review_record_hash
            FROM normative_activations
            WHERE normative_activation_id=:activation_id
        """), {
            "activation_id": control_activation["normative_activation_id"],
        }).one()
        assert persisted_control == (
            control_activation["normative_activation_id"],
            control_activation["subject_type"], control_activation["subject_id"],
            control_activation["subject_version"],
            control_activation["subject_hash"],
            control_activation["review_record_id"],
            control_activation["review_record_hash"],
        )

    false_activation = copy.deepcopy(control_activation)
    false_activation.update({
        "normative_activation_id": false_activation_id,
        "record_hash": _digest(f"activation-false-{suffix}"),
        "review_record_id": review_b["rule_review_record_id"],
        "review_record_hash": review_b["record_hash"],
    })
    with pytest.raises((DBAPIError, IntegrityError)) as caught:
        with engine.begin() as connection:
            connection.execute(
                insert(models.NormativeActivation),
                false_activation,
            )
            persisted_false = connection.execute(text("""
                SELECT subject_id, subject_version, subject_hash,
                       review_record_id, review_record_hash
                FROM normative_activations
                WHERE normative_activation_id=:activation_id
            """), {"activation_id": false_activation_id}).one()
            assert persisted_false == (
                rule_a["rule_id"], rule_a["rule_version"], rule_a["rule_hash"],
                review_b["rule_review_record_id"], review_b["record_hash"],
            )
    assert caught.value.orig.sqlstate == "23503"
    assert REVIEW_GATE_TOKEN in str(caught.value)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM normative_activations
            WHERE normative_activation_id=:activation_id
        """), {"activation_id": false_activation_id}) == 0


def _intention_8a_context(engine, suffix):
    extractions = [
        {"extraction_result_id": f"extraction-{label}-{suffix}",
         "record_hash": _digest(f"extraction-{label}-{suffix}")}
        for label in ("a", "b")
    ]
    rules = []
    for label, version, extraction in zip(("a", "b"), (1, 2), extractions):
        rules.append({
            "rule_version_record_id": f"rule-version-{label}-{suffix}",
            "rule_id": f"rule-{label}-{suffix}",
            "rule_version": version,
            "rule_hash": _digest(f"rule-{label}-{suffix}"),
            "extraction_result_id": extraction["extraction_result_id"],
            "extraction_result_record_hash": extraction["record_hash"],
            "structured_content": {"rule": label},
            "declared_material_validity": {"status": "declared"},
            "normative_references": [],
            "exact_precedence_policy_reference": {
                "policy_id": "precedence-policy", "policy_version": 1,
                "policy_hash": _digest("precedence-policy"),
            },
            "evidence": {"mission": "MISSION-009A-INTENCAO-8A"},
            "provenance": {"test": suffix},
            "record_hash": _digest(f"rule-record-{label}-{suffix}"),
        })
    relations = []
    for label, version in zip(("a", "b"), (1, 2)):
        relations.append({
            "normative_relation_version_record_id":
                f"relation-version-{label}-{suffix}",
            "normative_relation_id": f"relation-{label}-{suffix}",
            "normative_relation_version": version,
            "normative_relation_hash": _digest(f"relation-{label}-{suffix}"),
            "source_subject_type": "rule_version",
            "source_subject_id": rules[0]["rule_id"],
            "source_subject_version": rules[0]["rule_version"],
            "source_subject_hash": rules[0]["rule_hash"],
            "target_subject_type": "rule_version",
            "target_subject_id": rules[1]["rule_id"],
            "target_subject_version": rules[1]["rule_version"],
            "target_subject_hash": rules[1]["rule_hash"],
            "relation_type": "referencia",
            "declared_material_validity": {"status": "declared"},
            "structured_content": {"relation": label},
            "evidence": {"mission": "MISSION-009A-INTENCAO-8A"},
            "normative_references": [],
            "exact_precedence_policy_reference": {
                "policy_id": "precedence-policy", "policy_version": 1,
                "policy_hash": _digest("precedence-policy"),
            },
            "provenance": {"test": suffix},
            "record_hash": _digest(f"relation-record-{label}-{suffix}"),
        })
    bindings = _precedence_physical_records(engine, suffix)
    _materialize_policy_activations(engine, bindings["policy_bindings"])
    decision = _decision(suffix, bindings)
    execution = _execution(decision, suffix)
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO extraction_results (extraction_result_id, record_hash)
            VALUES (:a_id, :a_hash), (:b_id, :b_hash)
        """), {
            "a_id": extractions[0]["extraction_result_id"],
            "a_hash": extractions[0]["record_hash"],
            "b_id": extractions[1]["extraction_result_id"],
            "b_hash": extractions[1]["record_hash"],
        })
        connection.execute(insert(models.RuleVersion), rules)
        connection.execute(insert(models.NormativeRelationVersion), relations)
    with engine.connect() as connection:
        rule_created = connection.scalar(text("""
            SELECT created_at FROM rule_versions
            WHERE rule_id=:id AND rule_version=:version AND rule_hash=:hash
        """), {"id": rules[0]["rule_id"],
                 "version": rules[0]["rule_version"],
                 "hash": rules[0]["rule_hash"]})
        relation_created = connection.scalar(text("""
            SELECT created_at FROM normative_relation_versions
            WHERE normative_relation_id=:id
              AND normative_relation_version=:version
              AND normative_relation_hash=:hash
        """), {"id": relations[0]["normative_relation_id"],
                 "version": relations[0]["normative_relation_version"],
                 "hash": relations[0]["normative_relation_hash"]})
    rule_review = {
        "rule_review_record_id": f"rule-review-{suffix}",
        "subject_id": rules[0]["rule_id"],
        "subject_version": rules[0]["rule_version"],
        "subject_hash": rules[0]["rule_hash"],
        "reviewer": "independent-reviewer",
        "review_event": "revisao_concluida", "outcome": "validada",
        "evidence": {"mission": "MISSION-009A-INTENCAO-8A"},
        "timestamp": rule_created + timedelta(microseconds=1),
        "record_hash": _digest(f"rule-review-{suffix}"),
    }
    relation_review = {
        "relation_review_record_id": f"relation-review-{suffix}",
        "subject_id": relations[0]["normative_relation_id"],
        "subject_version": relations[0]["normative_relation_version"],
        "subject_hash": relations[0]["normative_relation_hash"],
        "reviewer": "independent-reviewer",
        "review_event": "revisao_concluida", "outcome": "validada",
        "evidence": {"mission": "MISSION-009A-INTENCAO-8A"},
        "timestamp": relation_created + timedelta(microseconds=1),
        "record_hash": _digest(f"relation-review-{suffix}"),
    }
    with engine.begin() as connection:
        connection.execute(insert(models.RuleReviewRecord), rule_review)
        connection.execute(insert(models.RelationReviewRecord), relation_review)
        connection.execute(insert(models.ActivationDecision), decision)
        connection.execute(insert(models.ActivationExecution), execution)
    activation = {
        "normative_activation_id": f"activation-{suffix}",
        "activation_decision_id": decision["activation_decision_id"],
        "activation_decision_record_hash": decision["record_hash"],
        "activation_execution_id": execution["activation_execution_id"],
        "subject_type": "rule_version",
        "subject_id": rules[0]["rule_id"],
        "subject_version": rules[0]["rule_version"],
        "subject_hash": rules[0]["rule_hash"],
        "review_record_id": rule_review["rule_review_record_id"],
        "review_record_hash": rule_review["record_hash"],
        "domain": "fiscal", "modality": "manual",
        "resolver_scope": {"country": "PT"},
        "operational_interval": {"from": "2026-08-03T00:00:00Z"},
        "scope_hash": decision["scope_hash"],
        "activation_generation_id": f"generation-{suffix}",
        "activated_at": datetime.now(timezone.utc), "state": "active",
        "technical_actor": "integration-auditor",
        "provenance": {"mission": "MISSION-009A-INTENCAO-8A"},
        "record_hash": _digest(f"activation-{suffix}"),
    }
    return activation, rules, relations, rule_review, relation_review


def _assert_subject_gate_rejection(engine, activation):
    with pytest.raises((DBAPIError, IntegrityError)) as caught:
        with engine.begin() as connection:
            connection.execute(insert(models.NormativeActivation), activation)
    assert caught.value.orig.sqlstate == "23503"
    assert SUBJECT_GATE_TOKEN in str(caught.value)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM normative_activations
            WHERE normative_activation_id=:activation_id
        """), {"activation_id": activation["normative_activation_id"]}) == 0


def _assert_exact_subject_persisted(engine, activation):
    with engine.begin() as connection:
        connection.execute(insert(models.NormativeActivation), activation)
    with engine.connect() as connection:
        assert connection.execute(text("""
            SELECT subject_type, subject_id, subject_version, subject_hash
            FROM normative_activations
            WHERE normative_activation_id=:activation_id
        """), {"activation_id": activation["normative_activation_id"]}).one() == (
            activation["subject_type"], activation["subject_id"],
            activation["subject_version"], activation["subject_hash"],
        )


def test_normative_activation_accepts_exact_rule_subject_via_core(
    postgresql_intention_8a,
):
    engine = postgresql_intention_8a["engine"]
    activation, _, _, _, _ = _intention_8a_context(engine, "exact-rule-int8a")
    _assert_exact_subject_persisted(engine, activation)


@pytest.mark.parametrize("case", (
    "missing", "divergent_hash", "relation_as_rule", "current", "latest",
    "newest",
))
def test_normative_activation_rejects_false_rule_subject_references(
    postgresql_intention_8a, case,
):
    engine = postgresql_intention_8a["engine"]
    activation, rules, relations, _, _ = _intention_8a_context(
        engine, f"false-rule-{case}-int8a",
    )
    activation["normative_activation_id"] += f"-{case}"
    activation["record_hash"] = _digest(activation["normative_activation_id"])
    if case == "missing":
        activation.update(subject_id="missing-rule", subject_version=99,
                          subject_hash=_digest("missing-rule"))
    elif case == "divergent_hash":
        activation["subject_hash"] = _digest("divergent-rule-hash")
    elif case == "relation_as_rule":
        activation.update(
            subject_id=relations[0]["normative_relation_id"],
            subject_version=relations[0]["normative_relation_version"],
            subject_hash=relations[0]["normative_relation_hash"],
        )
    else:
        activation["subject_id"] = case
    _assert_subject_gate_rejection(engine, activation)


def test_normative_activation_rejects_mixed_exact_relation_subject_via_core(
    postgresql_intention_8a,
):
    engine = postgresql_intention_8a["engine"]
    activation, _, relations, _, review = _intention_8a_context(
        engine, "mixed-relation-int8a",
    )
    activation.update(
        subject_type="normative_relation_version",
        subject_id=relations[0]["normative_relation_id"],
        subject_version=relations[1]["normative_relation_version"],
        subject_hash=relations[1]["normative_relation_hash"],
        review_record_id=review["relation_review_record_id"],
        review_record_hash=review["record_hash"],
    )
    _assert_subject_gate_rejection(engine, activation)


def test_normative_activation_accepts_exact_relation_subject_via_core(
    postgresql_intention_8a,
):
    engine = postgresql_intention_8a["engine"]
    activation, _, relations, _, review = _intention_8a_context(
        engine, "exact-relation-int8a",
    )
    activation.update(
        subject_type="normative_relation_version",
        subject_id=relations[0]["normative_relation_id"],
        subject_version=relations[0]["normative_relation_version"],
        subject_hash=relations[0]["normative_relation_hash"],
        review_record_id=review["relation_review_record_id"],
        review_record_hash=review["record_hash"],
    )
    _assert_exact_subject_persisted(engine, activation)


@pytest.mark.parametrize("case", (
    "missing", "divergent_hash", "rule_as_relation",
))
def test_normative_activation_rejects_false_relation_subject_references(
    postgresql_intention_8a, case,
):
    engine = postgresql_intention_8a["engine"]
    activation, rules, relations, _, review = _intention_8a_context(
        engine, f"false-relation-{case}-int8a",
    )
    activation.update(
        normative_activation_id=f"activation-false-relation-{case}",
        record_hash=_digest(f"activation-false-relation-{case}"),
        subject_type="normative_relation_version",
        subject_id=relations[0]["normative_relation_id"],
        subject_version=relations[0]["normative_relation_version"],
        subject_hash=relations[0]["normative_relation_hash"],
        review_record_id=review["relation_review_record_id"],
        review_record_hash=review["record_hash"],
    )
    if case == "missing":
        activation.update(subject_id="missing-relation", subject_version=99,
                          subject_hash=_digest("missing-relation"))
    elif case == "divergent_hash":
        activation["subject_hash"] = _digest("divergent-relation-hash")
    else:
        activation.update(subject_id=rules[0]["rule_id"],
                          subject_version=rules[0]["rule_version"],
                          subject_hash=rules[0]["rule_hash"])
    _assert_subject_gate_rejection(engine, activation)


def test_normative_activation_subject_gate_is_prospective(
    postgresql_intention_8a_prospective,
):
    engine = postgresql_intention_8a_prospective["engine"]
    activation, rules, _, _, _ = _intention_8a_context(
        engine, "prospective-subject-int8a",
    )
    historical = copy.deepcopy(activation)
    historical.update(
        normative_activation_id="activation-historical-mixed-int8a",
        record_hash=_digest("activation-historical-mixed-int8a"),
        subject_id=rules[0]["rule_id"],
        subject_version=rules[1]["rule_version"],
        subject_hash=rules[1]["rule_hash"],
    )
    with engine.begin() as connection:
        assert connection.scalar(text(
            "SELECT version_num FROM alembic_version"
        )) == PRECEDENCE_BINDING_REVISION
        connection.execute(insert(models.NormativeActivation), historical)
        before = connection.execute(text("""
            SELECT normative_activation_id, record_hash
            FROM normative_activations
            WHERE normative_activation_id=:activation_id
        """), {"activation_id": historical["normative_activation_id"]}).one()
        operations = Operations(MigrationContext.configure(connection))
        migration_0035 = _load_migration(
            SUBJECT_GATE_MIGRATION, "test_prospective_physical_0035",
        )
        migration_0035.op = operations
        migration_0035.upgrade()
        connection.execute(text("""
            UPDATE alembic_version SET version_num=:new_revision
            WHERE version_num=:old_revision
        """), {"new_revision": SUBJECT_GATE_REVISION,
                 "old_revision": PRECEDENCE_BINDING_REVISION})
    with engine.connect() as connection:
        after = connection.execute(text("""
            SELECT normative_activation_id, record_hash
            FROM normative_activations
            WHERE normative_activation_id=:activation_id
        """), {"activation_id": historical["normative_activation_id"]}).one()
        assert after == before
        assert connection.scalar(text("""
            SELECT count(*) FROM pg_proc WHERE proname=:name
        """), {"name": SUBJECT_GATE_FUNCTION}) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM pg_trigger WHERE tgname=:name
        """), {"name": SUBJECT_GATE_TRIGGER}) == 1
    new_false = copy.deepcopy(historical)
    new_false.update(
        normative_activation_id="activation-new-mixed-int8a",
        record_hash=_digest("activation-new-mixed-int8a"),
    )
    _assert_subject_gate_rejection(engine, new_false)
    exact = copy.deepcopy(activation)
    exact.update(normative_activation_id="activation-new-exact-int8a",
                 record_hash=_digest("activation-new-exact-int8a"))
    _assert_exact_subject_persisted(engine, exact)
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT count(*) FROM normative_activations"
        )) == 2
        assert connection.execute(text("""
            SELECT normative_activation_id, record_hash
            FROM normative_activations
            WHERE normative_activation_id=:activation_id
        """), {"activation_id": historical["normative_activation_id"]}).one() == before


def test_normative_activation_subject_gate_migration_has_exact_static_contract(
    monkeypatch,
):
    assert SUBJECT_GATE_MIGRATION.exists()
    source = SUBJECT_GATE_MIGRATION.read_text(encoding="utf-8")
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
        "revision": SUBJECT_GATE_REVISION,
        "down_revision": PRECEDENCE_BINDING_REVISION,
    }
    for token in (
        "PostgreSQL-only", SUBJECT_GATE_FUNCTION, SUBJECT_GATE_TRIGGER,
        "BEFORE INSERT ON normative_activations", "FOR EACH ROW",
        "NEW.subject_type = 'rule_version'",
        "NEW.subject_type = 'normative_relation_version'",
        "rule_id = NEW.subject_id", "rule_version = NEW.subject_version",
        "rule_hash = NEW.subject_hash",
        "normative_relation_id = NEW.subject_id",
        "normative_relation_version = NEW.subject_version",
        "normative_relation_hash = NEW.subject_hash", "SELECT count(*)",
        "exact_match_count <> 1", "23503", SUBJECT_GATE_TOKEN,
    ):
        assert token in source
    assert not re.search(r"\b(update|delete)\b", lowered)
    for forbidden in ("backfill", "review_record", "review_event", "outcome"):
        assert forbidden not in lowered
    assert "raise runtimeerror" in lowered and "irreversible" in lowered

    migration = _load_migration(
        SUBJECT_GATE_MIGRATION, "test_0035_non_postgresql_guard",
    )
    class NonPostgresqlOperations:
        def get_bind(self):
            return type("Bind", (), {
                "dialect": type("Dialect", (), {"name": "sqlite"})(),
            })()
    monkeypatch.setattr(migration, "op", NonPostgresqlOperations())
    with pytest.raises(RuntimeError, match="PostgreSQL-only"):
        migration.upgrade()
    with pytest.raises(RuntimeError, match="irreversible"):
        migration.downgrade()


def test_normative_activation_subject_function_and_trigger_are_physical(
    postgresql_intention_8a,
):
    engine = postgresql_intention_8a["engine"]
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT version_num FROM alembic_version"
        )) == SUBJECT_GATE_REVISION
        assert connection.scalar(text("""
            SELECT count(*) FROM pg_proc WHERE proname=:name
        """), {"name": SUBJECT_GATE_FUNCTION}) == 1
        trigger = connection.execute(text("""
            SELECT t.tgname, t.tgisinternal, t.tgenabled, c.relname,
                   pg_get_triggerdef(t.oid), p.proname
            FROM pg_trigger AS t
            JOIN pg_class AS c ON c.oid=t.tgrelid
            JOIN pg_proc AS p ON p.oid=t.tgfoid
            WHERE t.tgname=:name
        """), {"name": SUBJECT_GATE_TRIGGER}).one()
        append_only = connection.execute(text("""
            SELECT tgname, tgenabled FROM pg_trigger
            WHERE tgrelid='normative_activations'::regclass
              AND tgname IN (
                'trg_normative_activations_append_only_mutation',
                'trg_normative_activations_append_only_truncate'
              )
            ORDER BY tgname
        """)).all()
    assert trigger[0:4] == (
        SUBJECT_GATE_TRIGGER, False, "O", "normative_activations",
    )
    assert "BEFORE INSERT" in trigger[4]
    assert trigger[5] == SUBJECT_GATE_FUNCTION
    assert append_only == [
        ("trg_normative_activations_append_only_mutation", "O"),
        ("trg_normative_activations_append_only_truncate", "O"),
    ]


def _intention_8b1_context(engine, suffix):
    activation, rules, relations, rule_a, relation_a = _intention_8a_context(
        engine, suffix,
    )
    with engine.connect() as connection:
        rule_b_created = connection.scalar(text("""
            SELECT created_at FROM rule_versions
            WHERE rule_id=:id AND rule_version=:version AND rule_hash=:hash
        """), {"id": rules[1]["rule_id"],
                 "version": rules[1]["rule_version"],
                 "hash": rules[1]["rule_hash"]})
        relation_b_created = connection.scalar(text("""
            SELECT created_at FROM normative_relation_versions
            WHERE normative_relation_id=:id
              AND normative_relation_version=:version
              AND normative_relation_hash=:hash
        """), {"id": relations[1]["normative_relation_id"],
                 "version": relations[1]["normative_relation_version"],
                 "hash": relations[1]["normative_relation_hash"]})
    rule_b = {
        "rule_review_record_id": f"rule-review-b-{suffix}",
        "subject_id": rules[1]["rule_id"],
        "subject_version": rules[1]["rule_version"],
        "subject_hash": rules[1]["rule_hash"],
        "reviewer": "independent-reviewer",
        "review_event": "revisao_concluida", "outcome": "validada",
        "evidence": {"mission": "MISSION-009A-INTENCAO-8B1"},
        "timestamp": rule_b_created + timedelta(microseconds=1),
        "record_hash": _digest(f"rule-review-b-{suffix}"),
    }
    relation_b = {
        "relation_review_record_id": f"relation-review-b-{suffix}",
        "subject_id": relations[1]["normative_relation_id"],
        "subject_version": relations[1]["normative_relation_version"],
        "subject_hash": relations[1]["normative_relation_hash"],
        "reviewer": "independent-reviewer",
        "review_event": "revisao_concluida", "outcome": "validada",
        "evidence": {"mission": "MISSION-009A-INTENCAO-8B1"},
        "timestamp": relation_b_created + timedelta(microseconds=1),
        "record_hash": _digest(f"relation-review-b-{suffix}"),
    }
    with engine.begin() as connection:
        connection.execute(insert(models.RuleReviewRecord), rule_b)
        connection.execute(insert(models.RelationReviewRecord), relation_b)
    return activation, rules, relations, (rule_a, rule_b), (relation_a, relation_b)


def _assert_review_gate_rejection(engine, activation):
    with pytest.raises((DBAPIError, IntegrityError)) as caught:
        with engine.begin() as connection:
            connection.execute(insert(models.NormativeActivation), activation)
    assert caught.value.orig.sqlstate == "23503"
    assert REVIEW_GATE_TOKEN in str(caught.value)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM normative_activations
            WHERE normative_activation_id=:activation_id
        """), {"activation_id": activation["normative_activation_id"]}) == 0


def _exact_activation(engine, activation):
    with engine.begin() as connection:
        connection.execute(insert(models.NormativeActivation), activation)
    with engine.connect() as connection:
        return connection.execute(text("""
            SELECT normative_activation_id, subject_type, subject_id,
                   subject_version, subject_hash, review_record_id,
                   review_record_hash
            FROM normative_activations
            WHERE normative_activation_id=:activation_id
        """), {"activation_id": activation["normative_activation_id"]}).one()


def test_normative_activation_accepts_exact_rule_review_for_same_subject_via_core(
    postgresql_intention_8b1,
):
    engine = postgresql_intention_8b1["engine"]
    activation, _, _, _, _ = _intention_8b1_context(engine, "review-rule-ok")
    assert _exact_activation(engine, activation) == tuple(
        activation[key] for key in (
            "normative_activation_id", "subject_type", "subject_id",
            "subject_version", "subject_hash", "review_record_id",
            "review_record_hash",
        )
    )


@pytest.mark.parametrize("case", (
    "missing", "id_with_other_hash", "hash_with_other_id",
    "other_subject", "relation_as_rule",
))
def test_normative_activation_rejects_false_rule_review_references(
    postgresql_intention_8b1, case,
):
    engine = postgresql_intention_8b1["engine"]
    activation, _, _, rules_reviews, relation_reviews = _intention_8b1_context(
        engine, f"review-rule-{case}",
    )
    rule_a, rule_b = rules_reviews
    relation_a, _ = relation_reviews
    activation.update(
        normative_activation_id=f"activation-review-rule-{case}",
        record_hash=_digest(f"activation-review-rule-{case}"),
    )
    if case == "missing":
        activation.update(review_record_id="missing-review",
                          review_record_hash=_digest("missing-review"))
    elif case == "id_with_other_hash":
        activation["review_record_hash"] = rule_b["record_hash"]
    elif case == "hash_with_other_id":
        activation["review_record_id"] = rule_b["rule_review_record_id"]
    elif case == "other_subject":
        activation.update(review_record_id=rule_b["rule_review_record_id"],
                          review_record_hash=rule_b["record_hash"])
    else:
        activation.update(
            review_record_id=relation_a["relation_review_record_id"],
            review_record_hash=relation_a["record_hash"],
        )
    _assert_review_gate_rejection(engine, activation)


def _relation_activation(activation, relations, review, label):
    result = copy.deepcopy(activation)
    result.update(
        normative_activation_id=f"activation-{label}",
        record_hash=_digest(f"activation-{label}"),
        subject_type="normative_relation_version",
        subject_id=relations[0]["normative_relation_id"],
        subject_version=relations[0]["normative_relation_version"],
        subject_hash=relations[0]["normative_relation_hash"],
        review_record_id=review["relation_review_record_id"],
        review_record_hash=review["record_hash"],
    )
    return result


def test_normative_activation_accepts_exact_relation_review_for_same_subject_via_core(
    postgresql_intention_8b1,
):
    engine = postgresql_intention_8b1["engine"]
    activation, _, relations, _, reviews = _intention_8b1_context(
        engine, "review-relation-ok",
    )
    exact = _relation_activation(activation, relations, reviews[0],
                                 "review-relation-ok")
    assert _exact_activation(engine, exact)[0] == exact["normative_activation_id"]


def test_normative_activation_rejects_exact_relation_review_from_another_subject_via_core(
    postgresql_intention_8b1,
):
    engine = postgresql_intention_8b1["engine"]
    activation, _, relations, _, reviews = _intention_8b1_context(
        engine, "review-relation-other-subject",
    )
    false = _relation_activation(activation, relations, reviews[1],
                                 "review-relation-other-subject")
    _assert_review_gate_rejection(engine, false)


@pytest.mark.parametrize("case", (
    "missing", "id_with_other_hash", "hash_with_other_id", "rule_as_relation",
))
def test_normative_activation_rejects_false_relation_review_references(
    postgresql_intention_8b1, case,
):
    engine = postgresql_intention_8b1["engine"]
    activation, _, relations, rule_reviews, relation_reviews = (
        _intention_8b1_context(engine, f"review-relation-{case}")
    )
    relation_a, relation_b = relation_reviews
    false = _relation_activation(activation, relations, relation_a,
                                 f"review-relation-{case}")
    if case == "missing":
        false.update(review_record_id="missing-review",
                     review_record_hash=_digest("missing-relation-review"))
    elif case == "id_with_other_hash":
        false["review_record_hash"] = relation_b["record_hash"]
    elif case == "hash_with_other_id":
        false["review_record_id"] = relation_b["relation_review_record_id"]
    else:
        false.update(review_record_id=rule_reviews[0]["rule_review_record_id"],
                     review_record_hash=rule_reviews[0]["record_hash"])
    _assert_review_gate_rejection(engine, false)


def test_normative_activation_review_gate_dispatches_collisions_by_subject_type(
    postgresql_intention_8b1,
):
    engine = postgresql_intention_8b1["engine"]
    activation, rules, relations, rule_reviews, relation_reviews = (
        _intention_8b1_context(engine, "review-class-collision")
    )
    shared_id = rule_reviews[0]["rule_review_record_id"]
    shared_hash = rule_reviews[0]["record_hash"]
    collision = copy.deepcopy(relation_reviews[0])
    collision.update(relation_review_record_id=shared_id,
                     record_hash=shared_hash)
    with engine.begin() as connection:
        connection.execute(insert(models.RelationReviewRecord), collision)
    # The exact rule row wins only in the rule table despite the collision.
    activation.update(normative_activation_id="activation-rule-collision",
                      record_hash=_digest("activation-rule-collision"))
    assert _exact_activation(engine, activation)[1] == "rule_version"
    # For a relation subject, the same textual pair is resolved only in relation.
    relation = _relation_activation(activation, relations, collision,
                                    "relation-collision")
    assert _exact_activation(engine, relation)[1] == "normative_relation_version"
    # An exact pair present in the opposite class cannot satisfy rule subject B.
    opposite_only = copy.deepcopy(activation)
    opposite_only.update(
        normative_activation_id="activation-opposite-class-only",
        record_hash=_digest("activation-opposite-class-only"),
        subject_id=rules[1]["rule_id"],
        subject_version=rules[1]["rule_version"],
        subject_hash=rules[1]["rule_hash"],
        review_record_id=relation_reviews[0]["relation_review_record_id"],
        review_record_hash=relation_reviews[0]["record_hash"],
    )
    _assert_review_gate_rejection(engine, opposite_only)


def test_normative_activation_review_gate_is_prospective(
    postgresql_intention_8b1_prospective,
):
    engine = postgresql_intention_8b1_prospective["engine"]
    activation, _, _, rule_reviews, _ = _intention_8b1_context(
        engine, "review-prospective",
    )
    historical = copy.deepcopy(activation)
    historical.update(
        normative_activation_id="activation-review-historical-false",
        record_hash=_digest("activation-review-historical-false"),
        review_record_id=rule_reviews[1]["rule_review_record_id"],
        review_record_hash=rule_reviews[1]["record_hash"],
    )
    with engine.begin() as connection:
        assert connection.scalar(text(
            "SELECT version_num FROM alembic_version"
        )) == SUBJECT_GATE_REVISION
        connection.execute(insert(models.NormativeActivation), historical)
        before = connection.execute(text("""
            SELECT normative_activation_id, record_hash, review_record_id,
                   review_record_hash FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": historical["normative_activation_id"]}).one()
        operations = Operations(MigrationContext.configure(connection))
        migration = _load_migration(REVIEW_GATE_MIGRATION,
                                    "test_prospective_physical_0036")
        migration.op = operations
        migration.upgrade()
        connection.execute(text("""
            UPDATE alembic_version SET version_num=:new WHERE version_num=:old
        """), {"new": REVIEW_GATE_REVISION, "old": SUBJECT_GATE_REVISION})
    with engine.connect() as connection:
        assert connection.execute(text("""
            SELECT normative_activation_id, record_hash, review_record_id,
                   review_record_hash FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": historical["normative_activation_id"]}).one() == before
        assert connection.scalar(text(
            "SELECT count(*) FROM pg_proc WHERE proname=:name"
        ), {"name": REVIEW_GATE_FUNCTION}) == 1
        assert connection.scalar(text(
            "SELECT count(*) FROM pg_trigger WHERE tgname=:name"
        ), {"name": REVIEW_GATE_TRIGGER}) == 1
    new_false = copy.deepcopy(historical)
    new_false.update(normative_activation_id="activation-review-new-false",
                     record_hash=_digest("activation-review-new-false"))
    _assert_review_gate_rejection(engine, new_false)
    exact = copy.deepcopy(activation)
    exact.update(normative_activation_id="activation-review-new-exact",
                 record_hash=_digest("activation-review-new-exact"))
    _exact_activation(engine, exact)
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT count(*) FROM normative_activations"
        )) == 2


def test_normative_activation_review_gate_migration_has_exact_static_contract(
    monkeypatch,
):
    source = REVIEW_GATE_MIGRATION.read_text(encoding="utf-8")
    lowered = source.lower()
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body if isinstance(node, ast.Assign)
        and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {"revision": REVIEW_GATE_REVISION,
                           "down_revision": SUBJECT_GATE_REVISION}
    assert len(REVIEW_GATE_REVISION) <= 32
    for token in (
        "PostgreSQL-only", REVIEW_GATE_FUNCTION, REVIEW_GATE_TRIGGER,
        "BEFORE INSERT ON normative_activations", "FOR EACH ROW",
        "NEW.subject_type = 'rule_version'", "rule_review_records",
        "rule_review_record_id = NEW.review_record_id",
        "NEW.subject_type = 'normative_relation_version'",
        "relation_review_records",
        "relation_review_record_id = NEW.review_record_id",
        "record_hash = NEW.review_record_hash", "subject_id = NEW.subject_id",
        "subject_version = NEW.subject_version",
        "subject_hash = NEW.subject_hash", "SELECT count(*)",
        "exact_match_count <> 1", "23503", REVIEW_GATE_TOKEN,
    ):
        assert token in source
    assert not re.search(r"\b(update|delete)\b", lowered)
    for forbidden in (
        "backfill", "review_event", "outcome", "revisao_concluida",
        "validada", "favorabilidade", "activationgeneration",
    ):
        assert forbidden not in lowered
    assert "raise runtimeerror" in lowered and "irreversible" in lowered
    migration = _load_migration(REVIEW_GATE_MIGRATION,
                                "test_0036_non_postgresql_guard")
    class NonPostgresqlOperations:
        def get_bind(self):
            return type("Bind", (), {"dialect": type(
                "Dialect", (), {"name": "sqlite"},
            )()})()
    monkeypatch.setattr(migration, "op", NonPostgresqlOperations())
    with pytest.raises(RuntimeError, match="PostgreSQL-only"):
        migration.upgrade()
    with pytest.raises(RuntimeError, match="irreversible"):
        migration.downgrade()


def test_normative_activation_review_function_and_trigger_are_physical(
    postgresql_intention_8b1,
):
    engine = postgresql_intention_8b1["engine"]
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT version_num FROM alembic_version"
        )) == REVIEW_GATE_REVISION
        assert connection.scalar(text(
            "SELECT count(*) FROM pg_proc WHERE proname=:name"
        ), {"name": REVIEW_GATE_FUNCTION}) == 1
        trigger = connection.execute(text("""
            SELECT t.tgname, t.tgisinternal, t.tgenabled, c.relname,
                   pg_get_triggerdef(t.oid), p.proname
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgname=:name
        """), {"name": REVIEW_GATE_TRIGGER}).one()
        before_insert = connection.execute(text("""
            SELECT tgname FROM pg_trigger
            WHERE tgrelid='normative_activations'::regclass
              AND NOT tgisinternal
              AND (tgtype & 2) = 2 AND (tgtype & 4) = 4
            ORDER BY tgname
        """)).scalars().all()
        append_only = connection.execute(text("""
            SELECT tgname, tgenabled FROM pg_trigger
            WHERE tgrelid='normative_activations'::regclass AND tgname IN (
              'trg_normative_activations_append_only_mutation',
              'trg_normative_activations_append_only_truncate') ORDER BY tgname
        """)).all()
    assert trigger[:4] == (REVIEW_GATE_TRIGGER, False, "O",
                           "normative_activations")
    assert "BEFORE INSERT" in trigger[4] and "FOR EACH ROW" in trigger[4]
    assert trigger[5] == REVIEW_GATE_FUNCTION
    assert before_insert.index(SUBJECT_GATE_TRIGGER) < before_insert.index(
        REVIEW_GATE_TRIGGER,
    )
    assert append_only == [
        ("trg_normative_activations_append_only_mutation", "O"),
        ("trg_normative_activations_append_only_truncate", "O"),
    ]


def test_normative_activation_rejects_missing_activation_generation_via_core(
    postgresql_intention_9a,
):
    engine = postgresql_intention_9a["engine"]
    suffix = "missing-activation-generation-int9a"
    control_activation, rules, _, rule_reviews, _ = _intention_8b1_context(
        engine, suffix,
    )
    subject = rules[0]
    review = rule_reviews[0]

    with engine.connect() as connection:
        decision = connection.execute(text("""
            SELECT activation_decision_id, record_hash, decision_action,
                   decision_outcome, target_manifest_hash, scope_hash,
                   policy_bindings, coverage_binding, continuity_binding,
                   precedence_binding, gates_evidence
            FROM activation_decisions
            WHERE activation_decision_id=:decision_id
              AND record_hash=:decision_hash
        """), {
            "decision_id": control_activation["activation_decision_id"],
            "decision_hash": control_activation["activation_decision_record_hash"],
        }).mappings().one()
        execution = connection.execute(text("""
            SELECT activation_execution_id, activation_decision_id,
                   activation_decision_record_hash, state
            FROM activation_executions
            WHERE activation_execution_id=:execution_id
        """), {
            "execution_id": control_activation["activation_execution_id"],
        }).mappings().one()

    generation = {
        "activation_generation_id": f"generation-{suffix}",
        "previous_activation_generation_id": None,
        "previous_activation_generation_record_hash": None,
        "activation_execution_id": execution["activation_execution_id"],
        "activation_decision_id": decision["activation_decision_id"],
        "activation_decision_record_hash": decision["record_hash"],
        "target_manifest_hash": decision["target_manifest_hash"],
        "scope_descriptor": {"country": "PT", "taxes": ["iva", "irs"]},
        "scope_hash": decision["scope_hash"],
        "composition_manifest": [{
            "subject_type": control_activation["subject_type"],
            "subject_id": subject["rule_id"],
            "subject_version": subject["rule_version"],
            "subject_hash": subject["rule_hash"],
        }],
        "composition_hash": _digest(f"composition-{suffix}"),
        "policy_bindings": decision["policy_bindings"],
        "coverage_binding": decision["coverage_binding"],
        "continuity_binding": decision["continuity_binding"],
        "precedence_binding": decision["precedence_binding"],
        "gates_evidence": decision["gates_evidence"],
        "is_complete": True,
        "effective_from": datetime.now(timezone.utc),
        "provenance": {"mission": "MISSION-009A-INTENCAO-9A"},
        "record_hash": _digest(f"generation-{suffix}"),
    }
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationGeneration), generation)

    control_activation["activation_generation_id"] = generation[
        "activation_generation_id"
    ]
    false_generation_id = f"missing-generation-{suffix}"
    false_activation = copy.deepcopy(control_activation)
    false_activation.update(
        normative_activation_id=f"activation-false-{suffix}",
        record_hash=_digest(f"activation-false-{suffix}"),
        activation_generation_id=false_generation_id,
    )

    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM rule_versions
            WHERE rule_id=:id AND rule_version=:version AND rule_hash=:hash
        """), {"id": subject["rule_id"],
                 "version": subject["rule_version"],
                 "hash": subject["rule_hash"]}) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM rule_review_records
            WHERE rule_review_record_id=:review_id
              AND record_hash=:review_hash AND subject_id=:id
              AND subject_version=:version AND subject_hash=:hash
        """), {"review_id": review["rule_review_record_id"],
                 "review_hash": review["record_hash"],
                 "id": subject["rule_id"],
                 "version": subject["rule_version"],
                 "hash": subject["rule_hash"]}) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_decisions
            WHERE activation_decision_id=:id AND record_hash=:hash
              AND decision_action='activate' AND decision_outcome='approved'
        """), {"id": decision["activation_decision_id"],
                 "hash": decision["record_hash"]}) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_executions
            WHERE activation_execution_id=:execution_id
              AND activation_decision_id=:decision_id
              AND activation_decision_record_hash=:decision_hash
        """), {"execution_id": execution["activation_execution_id"],
                 "decision_id": decision["activation_decision_id"],
                 "decision_hash": decision["record_hash"]}) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_generations
            WHERE activation_generation_id=:generation_id
              AND record_hash=:generation_hash
              AND activation_decision_id=:decision_id
              AND activation_decision_record_hash=:decision_hash
              AND activation_execution_id=:execution_id
              AND scope_hash=:scope_hash
              AND composition_hash=:composition_hash AND is_complete IS TRUE
        """), {"generation_id": generation["activation_generation_id"],
                 "generation_hash": generation["record_hash"],
                 "decision_id": decision["activation_decision_id"],
                 "decision_hash": decision["record_hash"],
                 "execution_id": execution["activation_execution_id"],
                 "scope_hash": generation["scope_hash"],
                 "composition_hash": generation["composition_hash"]}) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_generations
            WHERE activation_generation_id=:generation_id
        """), {"generation_id": false_generation_id}) == 0
        assert connection.scalar(text("""
            SELECT count(*) FROM normative_activations
            WHERE normative_activation_id=:activation_id
        """), {"activation_id": false_activation[
            "normative_activation_id"
        ]}) == 0

    with engine.begin() as connection:
        connection.execute(insert(models.NormativeActivation), control_activation)
    with engine.connect() as connection:
        persisted_control = connection.execute(text("""
            SELECT normative_activation_id, activation_decision_id,
                   activation_decision_record_hash, activation_execution_id,
                   subject_type, subject_id, subject_version, subject_hash,
                   review_record_id, review_record_hash,
                   activation_generation_id, scope_hash, state, record_hash
            FROM normative_activations
            WHERE normative_activation_id=:activation_id
        """), {"activation_id": control_activation[
            "normative_activation_id"
        ]}).one()
        assert persisted_control == tuple(control_activation[key] for key in (
            "normative_activation_id", "activation_decision_id",
            "activation_decision_record_hash", "activation_execution_id",
            "subject_type", "subject_id", "subject_version", "subject_hash",
            "review_record_id", "review_record_hash",
            "activation_generation_id", "scope_hash", "state", "record_hash",
        ))

    with pytest.raises((DBAPIError, IntegrityError)) as raised:
        with engine.begin() as connection:
            connection.execute(insert(models.NormativeActivation), false_activation)
    assert raised.value.orig.sqlstate == "23503"
    assert raised.value.orig.diag.constraint_name == GENERATION_FK
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM normative_activations
            WHERE normative_activation_id=:activation_id
        """), {"activation_id": false_activation[
            "normative_activation_id"
        ]}) == 0


def _intention_9a_context(engine, suffix):
    activation, rules, _, rule_reviews, _ = _intention_8b1_context(
        engine, suffix,
    )
    with engine.connect() as connection:
        decision = connection.execute(text("""
            SELECT activation_decision_id, record_hash, target_manifest_hash,
                   scope_hash, policy_bindings, coverage_binding,
                   continuity_binding, precedence_binding, gates_evidence
            FROM activation_decisions
            WHERE activation_decision_id=:id
        """), {"id": activation["activation_decision_id"]}).mappings().one()
    generation = {
        "activation_generation_id": f"generation-{suffix}",
        "previous_activation_generation_id": None,
        "previous_activation_generation_record_hash": None,
        "activation_execution_id": activation["activation_execution_id"],
        "activation_decision_id": decision["activation_decision_id"],
        "activation_decision_record_hash": decision["record_hash"],
        "target_manifest_hash": decision["target_manifest_hash"],
        "scope_descriptor": {"country": "PT", "taxes": ["iva", "irs"]},
        "scope_hash": decision["scope_hash"],
        "composition_manifest": [{
            "subject_type": activation["subject_type"],
            "subject_id": activation["subject_id"],
            "subject_version": activation["subject_version"],
            "subject_hash": activation["subject_hash"],
        }],
        "composition_hash": _digest(f"composition-{suffix}"),
        "policy_bindings": decision["policy_bindings"],
        "coverage_binding": decision["coverage_binding"],
        "continuity_binding": decision["continuity_binding"],
        "precedence_binding": decision["precedence_binding"],
        "gates_evidence": decision["gates_evidence"],
        "is_complete": True,
        "effective_from": datetime.now(timezone.utc),
        "provenance": {"mission": "MISSION-009A-INTENCAO-9A"},
        "record_hash": _digest(f"generation-{suffix}"),
    }
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationGeneration), generation)
    activation.update(
        normative_activation_id=f"activation-{suffix}",
        activation_generation_id=generation["activation_generation_id"],
        record_hash=_digest(f"activation-{suffix}"),
    )
    return activation, generation, rules[0], rule_reviews[0]


def test_normative_activation_accepts_existing_activation_generation_via_core(
    postgresql_intention_9a,
):
    engine = postgresql_intention_9a["engine"]
    activation, generation, _, _ = _intention_9a_context(
        engine, "existing-generation-int9a",
    )
    with engine.begin() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_generations
            WHERE activation_generation_id=:id
        """), {"id": generation["activation_generation_id"]}) == 1
        connection.execute(insert(models.NormativeActivation), activation)
    columns = tuple(activation)
    with engine.connect() as connection:
        persisted = connection.execute(text(f"""
            SELECT {', '.join(columns)} FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": activation["normative_activation_id"]}).one()
    assert persisted == tuple(activation[column] for column in columns)


def test_normative_activation_rejects_generation_from_another_execution_of_same_decision_via_core(
    postgresql_intention_9b1,
):
    engine = postgresql_intention_9b1["engine"]
    suffix = "generation-another-execution-int9b1"
    control_activation, rules, _, rule_reviews, _ = _intention_8b1_context(
        engine, suffix,
    )
    subject = rules[0]
    review = rule_reviews[0]
    with engine.connect() as connection:
        decision = connection.execute(text("""
            SELECT activation_decision_id, record_hash, decision_action,
                   decision_outcome, target_manifest_hash, scope_hash,
                   authority_bindings, policy_bindings, coverage_binding,
                   continuity_binding, precedence_binding, gates_evidence
            FROM activation_decisions
            WHERE activation_decision_id=:id AND record_hash=:hash
        """), {
            "id": control_activation["activation_decision_id"],
            "hash": control_activation["activation_decision_record_hash"],
        }).mappings().one()

    execution_e1_id = control_activation["activation_execution_id"]
    execution_e2 = _execution(decision, f"e2-{suffix}")
    generation_g1 = {
        "activation_generation_id": f"generation-{suffix}",
        "previous_activation_generation_id": None,
        "previous_activation_generation_record_hash": None,
        "activation_execution_id": execution_e1_id,
        "activation_decision_id": decision["activation_decision_id"],
        "activation_decision_record_hash": decision["record_hash"],
        "target_manifest_hash": decision["target_manifest_hash"],
        "scope_descriptor": {"country": "PT", "taxes": ["iva", "irs"]},
        "scope_hash": decision["scope_hash"],
        "composition_manifest": [{
            "subject_type": control_activation["subject_type"],
            "subject_id": subject["rule_id"],
            "subject_version": subject["rule_version"],
            "subject_hash": subject["rule_hash"],
        }],
        "composition_hash": _digest(f"composition-{suffix}"),
        "policy_bindings": decision["policy_bindings"],
        "coverage_binding": decision["coverage_binding"],
        "continuity_binding": decision["continuity_binding"],
        "precedence_binding": decision["precedence_binding"],
        "gates_evidence": decision["gates_evidence"],
        "is_complete": True,
        "effective_from": datetime.now(timezone.utc),
        "provenance": {"mission": "MISSION-009A-INTENCAO-9B1"},
        "record_hash": _digest(f"generation-{suffix}"),
    }
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationExecution), execution_e2)
        connection.execute(insert(models.ActivationGeneration), generation_g1)

    control_activation.update(
        normative_activation_id=f"activation-control-{suffix}",
        activation_generation_id=generation_g1["activation_generation_id"],
        record_hash=_digest(f"activation-control-{suffix}"),
    )
    false_activation = copy.deepcopy(control_activation)
    false_activation.update(
        normative_activation_id=f"activation-false-{suffix}",
        activation_execution_id=execution_e2["activation_execution_id"],
        record_hash=_digest(f"activation-false-{suffix}"),
    )

    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_decisions
            WHERE activation_decision_id=:id AND record_hash=:hash
              AND decision_action='activate' AND decision_outcome='approved'
        """), {"id": decision["activation_decision_id"],
                 "hash": decision["record_hash"]}) == 1
        executions = connection.execute(text("""
            SELECT activation_execution_id, activation_decision_id,
                   activation_decision_record_hash
            FROM activation_executions
            WHERE activation_execution_id IN (:e1_id, :e2_id)
            ORDER BY activation_execution_id
        """), {"e1_id": execution_e1_id,
                 "e2_id": execution_e2["activation_execution_id"]}).all()
        assert len(executions) == 2
        assert execution_e1_id != execution_e2["activation_execution_id"]
        assert {row[0] for row in executions} == {
            execution_e1_id, execution_e2["activation_execution_id"],
        }
        assert all(row[1:] == (
            decision["activation_decision_id"], decision["record_hash"],
        ) for row in executions)
        assert connection.execute(text("""
            SELECT activation_generation_id, activation_execution_id,
                   activation_decision_id, activation_decision_record_hash
            FROM activation_generations
            WHERE activation_generation_id=:id
        """), {"id": generation_g1["activation_generation_id"]}).one() == (
            generation_g1["activation_generation_id"], execution_e1_id,
            decision["activation_decision_id"], decision["record_hash"],
        )
        assert connection.scalar(text("""
            SELECT count(*) FROM rule_versions
            WHERE rule_id=:id AND rule_version=:version AND rule_hash=:hash
        """), {"id": subject["rule_id"],
                 "version": subject["rule_version"],
                 "hash": subject["rule_hash"]}) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM rule_review_records
            WHERE rule_review_record_id=:review_id AND record_hash=:review_hash
              AND subject_id=:id AND subject_version=:version
              AND subject_hash=:hash
        """), {"review_id": review["rule_review_record_id"],
                 "review_hash": review["record_hash"],
                 "id": subject["rule_id"],
                 "version": subject["rule_version"],
                 "hash": subject["rule_hash"]}) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM normative_activations
            WHERE normative_activation_id IN (:control_id, :false_id)
        """), {"control_id": control_activation["normative_activation_id"],
                 "false_id": false_activation["normative_activation_id"]}) == 0

    with engine.begin() as connection:
        connection.execute(insert(models.NormativeActivation), control_activation)
    control_columns = (
        "normative_activation_id", "activation_decision_id",
        "activation_decision_record_hash", "activation_execution_id",
        "activation_generation_id", "subject_type", "subject_id",
        "subject_version", "subject_hash", "review_record_id",
        "review_record_hash", "scope_hash", "state", "record_hash",
    )
    with engine.connect() as connection:
        persisted_control = connection.execute(text(f"""
            SELECT {', '.join(control_columns)} FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": control_activation["normative_activation_id"]}).one()
        assert persisted_control == tuple(
            control_activation[column] for column in control_columns
        )
        assert persisted_control[3] == execution_e1_id
        assert generation_g1["activation_execution_id"] == execution_e1_id

    with pytest.raises(DBAPIError) as raised:
        with engine.begin() as connection:
            connection.execute(
                insert(models.NormativeActivation),
                false_activation,
            )
            persisted_false = connection.execute(text("""
                SELECT activation_execution_id, activation_generation_id
                FROM normative_activations
                WHERE normative_activation_id=:id
            """), {"id": false_activation["normative_activation_id"]}).one()
            assert persisted_false == (
                execution_e2["activation_execution_id"],
                generation_g1["activation_generation_id"],
            )
    assert raised.value.orig.sqlstate == "23503"
    assert GENERATION_EXECUTION_GATE_TOKEN in str(raised.value.orig)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": false_activation["normative_activation_id"]}) == 0


def test_normative_activation_generation_fk_rejects_missing_id_via_sql(
    postgresql_intention_9a,
):
    engine = postgresql_intention_9a["engine"]
    activation, _, _, _ = _intention_9a_context(engine, "raw-sql-int9a")
    activation["activation_generation_id"] = "missing-generation-raw-sql-int9a"
    table = models.NormativeActivation.__table__
    statement = text(
        f"INSERT INTO normative_activations "
        f"({', '.join(column.name for column in table.columns)}) VALUES "
        f"({', '.join(':' + column.name for column in table.columns)})"
    ).bindparams(*[
        bindparam(column.name, type_=column.type) for column in table.columns
    ])
    with pytest.raises(DBAPIError) as raised:
        with engine.begin() as connection:
            connection.execute(statement, activation)
    assert raised.value.orig.sqlstate == "23503"
    assert raised.value.orig.diag.constraint_name == GENERATION_FK
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": activation["normative_activation_id"]}) == 0


def _intention_9b1_context(engine, suffix):
    activation, generation, _, _ = _intention_9a_context(engine, suffix)
    with engine.connect() as connection:
        decision = connection.execute(text("""
            SELECT activation_decision_id, record_hash, target_manifest_hash,
                   scope_hash, authority_bindings, policy_bindings, coverage_binding,
                   continuity_binding, precedence_binding, gates_evidence
            FROM activation_decisions WHERE activation_decision_id=:id
        """), {"id": activation["activation_decision_id"]}).mappings().one()
    execution_e2 = _execution(decision, f"e2-{suffix}")
    with engine.begin() as connection:
        connection.execute(insert(models.ActivationExecution), execution_e2)
    false_activation = copy.deepcopy(activation)
    false_activation.update(
        normative_activation_id=f"activation-false-{suffix}",
        activation_execution_id=execution_e2["activation_execution_id"],
        record_hash=_digest(f"activation-false-{suffix}"),
    )
    return activation, false_activation, generation, execution_e2


def test_normative_activation_accepts_generation_from_same_execution_via_core(
    postgresql_intention_9b1,
):
    engine = postgresql_intention_9b1["engine"]
    activation, _, generation, _ = _intention_9b1_context(
        engine, "same-execution-int9b1",
    )
    with engine.begin() as connection:
        connection.execute(insert(models.NormativeActivation), activation)
    columns = tuple(activation)
    with engine.connect() as connection:
        persisted = connection.execute(text(f"""
            SELECT {', '.join(columns)} FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": activation["normative_activation_id"]}).one()
    assert persisted == tuple(activation[column] for column in columns)
    assert persisted[columns.index("activation_execution_id")] == generation[
        "activation_execution_id"
    ]
    assert persisted[columns.index("activation_generation_id")] == generation[
        "activation_generation_id"
    ]


def test_normative_activation_generation_execution_gate_rejects_mismatch_via_sql(
    postgresql_intention_9b1,
):
    engine = postgresql_intention_9b1["engine"]
    _, false_activation, _, _ = _intention_9b1_context(
        engine, "raw-sql-int9b1",
    )
    table = models.NormativeActivation.__table__
    statement = text(
        f"INSERT INTO normative_activations "
        f"({', '.join(column.name for column in table.columns)}) VALUES "
        f"({', '.join(':' + column.name for column in table.columns)})"
    ).bindparams(*[
        bindparam(column.name, type_=column.type) for column in table.columns
    ])
    with pytest.raises(DBAPIError) as raised:
        with engine.begin() as connection:
            connection.execute(statement, false_activation)
    assert raised.value.orig.sqlstate == "23503"
    assert GENERATION_EXECUTION_GATE_TOKEN in str(raised.value.orig)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": false_activation["normative_activation_id"]}) == 0


def test_normative_activation_generation_execution_gate_preserves_generation_fk_diagnostic(
    postgresql_intention_9b1,
):
    engine = postgresql_intention_9b1["engine"]
    activation, _, _, _ = _intention_9a_context(engine, "missing-int9b1")
    activation["activation_generation_id"] = "missing-generation-int9b1"
    with pytest.raises(DBAPIError) as raised:
        with engine.begin() as connection:
            connection.execute(insert(models.NormativeActivation), activation)
    assert raised.value.orig.sqlstate == "23503"
    assert raised.value.orig.diag.constraint_name == GENERATION_FK
    assert GENERATION_EXECUTION_GATE_TOKEN not in str(raised.value.orig)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": activation["normative_activation_id"]}) == 0


def test_normative_activation_generation_fk_is_prospective(
    postgresql_intention_9a_prospective,
):
    engine = postgresql_intention_9a_prospective["engine"]
    historical, generation, _, _ = _intention_9a_context(
        engine, "prospective-int9a",
    )
    historical.update(
        normative_activation_id="activation-historical-missing-int9a",
        activation_generation_id="missing-generation-historical-int9a",
        record_hash=_digest("activation-historical-missing-int9a"),
    )
    with engine.begin() as connection:
        assert connection.scalar(text(
            "SELECT version_num FROM alembic_version"
        )) == REVIEW_GATE_REVISION
        connection.execute(insert(models.NormativeActivation), historical)
        before = connection.execute(text("""
            SELECT normative_activation_id, activation_generation_id, record_hash
            FROM normative_activations WHERE normative_activation_id=:id
        """), {"id": historical["normative_activation_id"]}).one()
        operations = Operations(MigrationContext.configure(connection))
        migration = _load_migration(GENERATION_FK_MIGRATION,
                                    "test_prospective_physical_0037")
        migration.op = operations
        migration.upgrade()
        connection.execute(text("""
            UPDATE alembic_version SET version_num=:new WHERE version_num=:old
        """), {"new": GENERATION_FK_REVISION, "old": REVIEW_GATE_REVISION})
    with engine.connect() as connection:
        after = connection.execute(text("""
            SELECT normative_activation_id, activation_generation_id, record_hash
            FROM normative_activations WHERE normative_activation_id=:id
        """), {"id": historical["normative_activation_id"]}).one()
        assert after == before
        assert connection.scalar(text("""
            SELECT convalidated FROM pg_constraint WHERE conname=:name
        """), {"name": GENERATION_FK}) is False
    new_false = copy.deepcopy(historical)
    new_false.update(normative_activation_id="activation-new-missing-int9a",
                     record_hash=_digest("activation-new-missing-int9a"))
    with pytest.raises(DBAPIError) as raised:
        with engine.begin() as connection:
            connection.execute(insert(models.NormativeActivation), new_false)
    assert raised.value.orig.sqlstate == "23503"
    assert raised.value.orig.diag.constraint_name == GENERATION_FK
    exact = copy.deepcopy(historical)
    exact.update(normative_activation_id="activation-new-exact-int9a",
                 activation_generation_id=generation["activation_generation_id"],
                 record_hash=_digest("activation-new-exact-int9a"))
    with engine.begin() as connection:
        connection.execute(insert(models.NormativeActivation), exact)
    with engine.connect() as connection:
        assert connection.execute(text("""
            SELECT normative_activation_id, activation_generation_id, record_hash
            FROM normative_activations WHERE normative_activation_id=:id
        """), {"id": historical["normative_activation_id"]}).one() == before
        assert connection.scalar(text(
            "SELECT count(*) FROM normative_activations"
        )) == 2


def test_normative_activation_generation_fk_migration_has_exact_static_contract(
    monkeypatch,
):
    source = GENERATION_FK_MIGRATION.read_text(encoding="utf-8")
    lowered = source.lower()
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body if isinstance(node, ast.Assign)
        and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {"revision": GENERATION_FK_REVISION,
                           "down_revision": REVIEW_GATE_REVISION}
    assert len(GENERATION_FK_REVISION) <= 32
    for token in (
        "PostgreSQL-only", GENERATION_FK,
        "ALTER TABLE normative_activations",
        "FOREIGN KEY (activation_generation_id)",
        "REFERENCES activation_generations (activation_generation_id)",
        "ON UPDATE RESTRICT", "ON DELETE RESTRICT", "NOT VALID",
    ):
        assert token in source
    assert "validate constraint" not in lowered
    assert "trigger" not in lowered and "plpgsql" not in lowered
    data_sql = re.sub(r"on\s+update\s+restrict", "", lowered)
    assert not re.search(r"\b(update|delete)\s+(?!restrict\b)", data_sql)
    semantic_source = lowered.replace(REVIEW_GATE_REVISION, "")
    for forbidden in (
        "backfill", "activation_decision", "activation_execution", "scope_hash",
        "composition", "review", "subject",
    ):
        assert forbidden not in semantic_source
    assert "raise runtimeerror" in lowered and "irreversible" in lowered
    migration = _load_migration(GENERATION_FK_MIGRATION,
                                "test_0037_non_postgresql_guard")
    class NonPostgresqlOperations:
        def get_bind(self):
            return type("Bind", (), {"dialect": type(
                "Dialect", (), {"name": "sqlite"},
            )()})()
    monkeypatch.setattr(migration, "op", NonPostgresqlOperations())
    with pytest.raises(RuntimeError, match="PostgreSQL-only"):
        migration.upgrade()
    with pytest.raises(RuntimeError, match="irreversible"):
        migration.downgrade()


def test_normative_activation_generation_fk_is_physical(
    postgresql_intention_9a,
):
    engine = postgresql_intention_9a["engine"]
    with engine.connect() as connection:
        constraint = connection.execute(text("""
            SELECT c.conname, c.contype, source.relname, target.relname,
                   source_attribute.attname, target_attribute.attname,
                   c.convalidated, c.condeferrable, c.condeferred,
                   c.confupdtype, c.confdeltype
            FROM pg_constraint c
            JOIN pg_class source ON source.oid=c.conrelid
            JOIN pg_class target ON target.oid=c.confrelid
            JOIN pg_attribute source_attribute
              ON source_attribute.attrelid=c.conrelid
             AND source_attribute.attnum=c.conkey[1]
            JOIN pg_attribute target_attribute
              ON target_attribute.attrelid=c.confrelid
             AND target_attribute.attnum=c.confkey[1]
            WHERE c.conname=:name
        """), {"name": GENERATION_FK}).one()
        triggers = set(connection.execute(text("""
            SELECT tgname FROM pg_trigger
            WHERE tgrelid='normative_activations'::regclass AND NOT tgisinternal
        """)).scalars())
    assert constraint == (
        GENERATION_FK, "f", "normative_activations", "activation_generations",
        "activation_generation_id", "activation_generation_id", False, False,
        False, "r", "r",
    )
    assert {
        SUBJECT_GATE_TRIGGER, REVIEW_GATE_TRIGGER,
        "trg_normative_activations_append_only_mutation",
        "trg_normative_activations_append_only_truncate",
    } <= triggers


def test_normative_activation_generation_execution_gate_is_prospective(
    postgresql_intention_9b1_prospective,
):
    engine = postgresql_intention_9b1_prospective["engine"]
    exact, historical, generation, _ = _intention_9b1_context(
        engine, "prospective-int9b1",
    )
    historical_columns = (
        "normative_activation_id", "activation_execution_id",
        "activation_generation_id", "record_hash",
    )
    with engine.begin() as connection:
        assert connection.scalar(text(
            "SELECT version_num FROM alembic_version"
        )) == GENERATION_FK_REVISION
        connection.execute(insert(models.NormativeActivation), historical)
        before = connection.execute(text(f"""
            SELECT {', '.join(historical_columns)} FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": historical["normative_activation_id"]}).one()
        operations = Operations(MigrationContext.configure(connection))
        migration = _load_migration(
            GENERATION_EXECUTION_GATE_MIGRATION,
            "test_prospective_physical_0038",
        )
        migration.op = operations
        migration.upgrade()
        connection.execute(text("""
            UPDATE alembic_version SET version_num=:new WHERE version_num=:old
        """), {"new": GENERATION_EXECUTION_GATE_REVISION,
                 "old": GENERATION_FK_REVISION})
    with engine.connect() as connection:
        after = connection.execute(text(f"""
            SELECT {', '.join(historical_columns)} FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": historical["normative_activation_id"]}).one()
        assert after == before
        assert connection.scalar(text("""
            SELECT count(*) FROM pg_proc WHERE proname=:name
        """), {"name": GENERATION_EXECUTION_GATE_FUNCTION}) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM pg_trigger WHERE tgname=:name
        """), {"name": GENERATION_EXECUTION_GATE_TRIGGER}) == 1
    new_false = copy.deepcopy(historical)
    new_false.update(normative_activation_id="activation-new-false-int9b1",
                     record_hash=_digest("activation-new-false-int9b1"))
    with pytest.raises(DBAPIError) as raised:
        with engine.begin() as connection:
            connection.execute(insert(models.NormativeActivation), new_false)
    assert raised.value.orig.sqlstate == "23503"
    assert GENERATION_EXECUTION_GATE_TOKEN in str(raised.value.orig)
    exact.update(normative_activation_id="activation-new-exact-int9b1",
                 record_hash=_digest("activation-new-exact-int9b1"))
    with engine.begin() as connection:
        connection.execute(insert(models.NormativeActivation), exact)
    with engine.connect() as connection:
        assert connection.execute(text(f"""
            SELECT {', '.join(historical_columns)} FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": historical["normative_activation_id"]}).one() == before
        assert connection.scalar(text("""
            SELECT count(*) FROM normative_activations
            WHERE activation_generation_id=:id
        """), {"id": generation["activation_generation_id"]}) == 2


def test_normative_activation_generation_execution_gate_has_exact_static_contract(
    monkeypatch,
):
    assert GENERATION_EXECUTION_GATE_TRIGGER == (
        "trg_adr020_validate_normative_activation_subject_review_gexec"
    )
    assert len(GENERATION_EXECUTION_GATE_TRIGGER.encode("utf-8")) <= 63
    source = GENERATION_EXECUTION_GATE_MIGRATION.read_text(encoding="utf-8")
    lowered = source.lower()
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body if isinstance(node, ast.Assign)
        and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {
        "revision": GENERATION_EXECUTION_GATE_REVISION,
        "down_revision": GENERATION_FK_REVISION,
    }
    assert len(GENERATION_EXECUTION_GATE_REVISION) <= 32
    for token in (
        "PostgreSQL-only", GENERATION_EXECUTION_GATE_FUNCTION,
        GENERATION_EXECUTION_GATE_TRIGGER, GENERATION_EXECUTION_GATE_TOKEN,
        "23503", "BEFORE INSERT ON normative_activations", "FOR EACH ROW",
        "FROM activation_generations", "SELECT activation_execution_id",
        "IS DISTINCT FROM NEW.activation_execution_id", "IF NOT FOUND",
        "RETURN NEW", "CREATE OR REPLACE FUNCTION",
    ):
        assert token in source
    semantic_source = lowered
    for value in assignments.values():
        semantic_source = semantic_source.replace(value.lower(), "")
    for forbidden in (
        "activation_decision_id", "activation_decision_record_hash",
        "scope_hash", "composition_hash", "subject_id", "review_record_id",
        "composition_manifest", "backfill", "validate constraint",
    ):
        assert forbidden not in semantic_source
    assert not re.search(r"\b(update|delete)\s+", semantic_source)
    assert "foreign key" not in semantic_source
    assert " unique " not in f" {semantic_source} "
    assert "raise runtimeerror" in lowered and "irreversible" in lowered
    migration = _load_migration(
        GENERATION_EXECUTION_GATE_MIGRATION, "test_0038_non_postgresql_guard",
    )
    class NonPostgresqlOperations:
        def get_bind(self):
            return type("Bind", (), {"dialect": type(
                "Dialect", (), {"name": "sqlite"},
            )()})()
    monkeypatch.setattr(migration, "op", NonPostgresqlOperations())
    with pytest.raises(RuntimeError, match="PostgreSQL-only"):
        migration.upgrade()
    with pytest.raises(RuntimeError, match="irreversible"):
        migration.downgrade()


def test_normative_activation_generation_execution_gate_is_physical(
    postgresql_intention_9b1,
):
    engine = postgresql_intention_9b1["engine"]
    with engine.connect() as connection:
        function_count = connection.scalar(text("""
            SELECT count(*) FROM pg_proc WHERE proname=:name
        """), {"name": GENERATION_EXECUTION_GATE_FUNCTION})
        trigger = connection.execute(text("""
            SELECT t.tgname, t.tgenabled, pg_get_triggerdef(t.oid), p.proname
            FROM pg_trigger t
            JOIN pg_proc p ON p.oid=t.tgfoid
            WHERE t.tgname=:name AND t.tgrelid='normative_activations'::regclass
        """), {"name": GENERATION_EXECUTION_GATE_TRIGGER}).one()
        trigger_names = list(connection.execute(text("""
            SELECT tgname FROM pg_trigger
            WHERE tgrelid='normative_activations'::regclass AND NOT tgisinternal
            ORDER BY tgname
        """)).scalars())
        generation_fk_validated = connection.scalar(text("""
            SELECT convalidated FROM pg_constraint WHERE conname=:name
        """), {"name": GENERATION_FK})
    assert function_count == 1
    assert trigger[0] == GENERATION_EXECUTION_GATE_TRIGGER
    assert trigger[1] == "O"
    assert "BEFORE INSERT ON public.normative_activations FOR EACH ROW" in trigger[2]
    assert trigger[3] == GENERATION_EXECUTION_GATE_FUNCTION
    assert trigger_names.index(SUBJECT_GATE_TRIGGER) < trigger_names.index(
        REVIEW_GATE_TRIGGER
    ) < trigger_names.index(GENERATION_EXECUTION_GATE_TRIGGER)
    assert {
        "trg_normative_activations_append_only_mutation",
        "trg_normative_activations_append_only_truncate",
    } <= set(trigger_names)
    assert generation_fk_validated is False


def test_activation_generation_rejects_execution_from_different_exact_decision_via_core(
    postgresql_intention_9b3,
):
    engine = postgresql_intention_9b3["engine"]
    suffix = "different-exact-decision-int9b3"
    bindings = _precedence_physical_records(engine, suffix)
    _materialize_policy_activations(engine, bindings["policy_bindings"])

    decision_d1 = _decision(f"d1-{suffix}", bindings)
    decision_d2 = copy.deepcopy(decision_d1)
    decision_d2.update({
        "activation_decision_id": f"decision-d2-{suffix}",
        "idempotency_key": f"decision-idem-d2-{suffix}",
        "record_hash": _digest(f"decision-d2-{suffix}"),
    })
    execution_e1 = _execution(decision_d1, f"e1-{suffix}")
    execution_e2 = _execution(decision_d1, f"e2-{suffix}")

    def generation(label, decision, execution):
        return {
            "activation_generation_id": f"generation-{label}-{suffix}",
            "previous_activation_generation_id": None,
            "previous_activation_generation_record_hash": None,
            "activation_execution_id": execution["activation_execution_id"],
            "activation_decision_id": decision["activation_decision_id"],
            "activation_decision_record_hash": decision["record_hash"],
            "target_manifest_hash": decision["target_manifest_hash"],
            "scope_descriptor": {
                "country": "PT", "taxes": ["iva", "irs"], "generation": label,
            },
            "scope_hash": _digest(f"generation-scope-{label}-{suffix}"),
            "composition_manifest": [{
                "subject_type": "rule_version",
                "subject_id": f"rule-{label}-{suffix}",
                "subject_version": 1,
                "subject_hash": _digest(f"rule-{label}-{suffix}"),
            }],
            "composition_hash": _digest(f"composition-{label}-{suffix}"),
            "policy_bindings": decision["policy_bindings"],
            "coverage_binding": decision["coverage_binding"],
            "continuity_binding": decision["continuity_binding"],
            "precedence_binding": decision["precedence_binding"],
            "gates_evidence": decision["gates_evidence"],
            "is_complete": True,
            "effective_from": datetime.now(timezone.utc),
            "provenance": {"mission": "MISSION-009B-INTENCAO-9B3"},
            "record_hash": _digest(f"generation-{label}-{suffix}"),
        }

    generation_control = generation("control", decision_d1, execution_e1)
    generation_false = generation("false", decision_d2, execution_e2)

    with engine.begin() as connection:
        connection.execute(
            insert(models.ActivationDecision), [decision_d1, decision_d2],
        )
        connection.execute(
            insert(models.ActivationExecution), [execution_e1, execution_e2],
        )
        connection.execute(
            insert(models.ActivationGeneration), generation_control,
        )

    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_decisions
            WHERE (activation_decision_id=:d1_id AND record_hash=:d1_hash
                   OR activation_decision_id=:d2_id AND record_hash=:d2_hash)
              AND decision_action='activate' AND decision_outcome='approved'
        """), {
            "d1_id": decision_d1["activation_decision_id"],
            "d1_hash": decision_d1["record_hash"],
            "d2_id": decision_d2["activation_decision_id"],
            "d2_hash": decision_d2["record_hash"],
        }) == 2
        assert decision_d1["activation_decision_id"] != decision_d2[
            "activation_decision_id"
        ]
        assert decision_d1["record_hash"] != decision_d2["record_hash"]
        assert execution_e1["activation_execution_id"] != execution_e2[
            "activation_execution_id"
        ]
        assert all(
            execution["activation_decision_id"]
            == decision_d1["activation_decision_id"]
            and execution["activation_decision_record_hash"]
            == decision_d1["record_hash"]
            for execution in (execution_e1, execution_e2)
        )
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_generations
            WHERE activation_generation_id=:generation_id
              AND activation_execution_id=:execution_id
              AND activation_decision_id=:decision_id
              AND activation_decision_record_hash=:decision_hash
              AND is_complete IS TRUE
        """), {
            "generation_id": generation_control["activation_generation_id"],
            "execution_id": execution_e1["activation_execution_id"],
            "decision_id": decision_d1["activation_decision_id"],
            "decision_hash": decision_d1["record_hash"],
        }) == 1
        assert (
            generation_control["scope_hash"],
            generation_control["composition_hash"],
        ) != (
            generation_false["scope_hash"],
            generation_false["composition_hash"],
        )

    with pytest.raises(DBAPIError):
        with engine.begin() as connection:
            connection.execute(
                insert(models.ActivationGeneration), generation_false,
            )


def test_activation_generation_decision_execution_fk_is_physical_and_not_valid(
    postgresql_intention_9b3, monkeypatch,
):
    source = GENERATION_DECISION_EXECUTION_FK_MIGRATION.read_text(
        encoding="utf-8",
    )
    lowered = source.lower()
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body if isinstance(node, ast.Assign)
        and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {
        "revision": GENERATION_DECISION_EXECUTION_FK_REVISION,
        "down_revision": GENERATION_EXECUTION_GATE_REVISION,
    }

    upgrade = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
    )
    assert isinstance(upgrade.body[0], ast.Assign)
    assert upgrade.body[0].targets[0].id == "bind"
    assert isinstance(upgrade.body[1], ast.If)
    assert ast.unparse(upgrade.body[1].test) == (
        "bind.dialect.name != 'postgresql'"
    )
    assert ast.literal_eval(upgrade.body[1].body[0].exc.args[0]) == (
        "ADR-020 migration 0039 requires PostgreSQL"
    )

    downgrade = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "downgrade"
    )
    assert len(downgrade.body) == 1
    assert isinstance(downgrade.body[0], ast.Raise)
    assert ast.literal_eval(downgrade.body[0].exc.args[0]) == (
        "ADR-020 migration 0039 is irreversible: "
        "exact generation-execution-decision binding cannot be removed"
    )
    for forbidden in (
        "drop", "validate constraint", "create index", "pass", "return",
    ):
        assert not re.search(rf"\b{forbidden}\b", lowered)
    for clause in (
        "MATCH SIMPLE", "ON UPDATE RESTRICT", "ON DELETE RESTRICT",
        "NOT DEFERRABLE", "INITIALLY IMMEDIATE", "NOT VALID",
    ):
        assert clause in source
    assert source.count(GENERATION_DECISION_EXECUTION_UNIQUE) == 1
    assert source.count(GENERATION_DECISION_EXECUTION_FK) == 1

    migration = _load_migration(
        GENERATION_DECISION_EXECUTION_FK_MIGRATION,
        "test_0039_non_postgresql_guard",
    )

    class NonPostgresqlOperations:
        def __init__(self):
            self.ddl_calls = []

        def get_bind(self):
            return type("Bind", (), {"dialect": type(
                "Dialect", (), {"name": "sqlite"},
            )()})()

        def create_unique_constraint(self, *args, **kwargs):
            self.ddl_calls.append((args, kwargs))

        def execute(self, statement):
            self.ddl_calls.append(statement)

    non_postgresql_op = NonPostgresqlOperations()
    monkeypatch.setattr(migration, "op", non_postgresql_op)
    with pytest.raises(RuntimeError) as guard_error:
        migration.upgrade()
    assert str(guard_error.value) == "ADR-020 migration 0039 requires PostgreSQL"
    assert non_postgresql_op.ddl_calls == []
    with pytest.raises(RuntimeError) as downgrade_error:
        migration.downgrade()
    assert str(downgrade_error.value) == (
        "ADR-020 migration 0039 is irreversible: "
        "exact generation-execution-decision binding cannot be removed"
    )

    engine = postgresql_intention_9b3["engine"]
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT version_num FROM alembic_version"
        )) == GENERATION_DECISION_EXECUTION_FK_REVISION
        constraints = connection.execute(text("""
            SELECT c.conname, c.contype, c.convalidated, c.condeferrable,
                   c.condeferred, c.confmatchtype, c.confupdtype, c.confdeltype,
                   pg_get_constraintdef(c.oid),
                   ARRAY(
                       SELECT a.attname
                       FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
                       JOIN pg_attribute a
                         ON a.attrelid=c.conrelid AND a.attnum=k.attnum
                       ORDER BY k.ord
                   ) AS local_columns,
                   ARRAY(
                       SELECT a.attname
                       FROM unnest(c.confkey) WITH ORDINALITY AS k(attnum, ord)
                       JOIN pg_attribute a
                         ON a.attrelid=c.confrelid AND a.attnum=k.attnum
                       ORDER BY k.ord
                   ) AS referenced_columns
            FROM pg_constraint c
            WHERE c.conname IN (:unique_name, :fk_name)
            ORDER BY c.conname
        """), {
            "unique_name": GENERATION_DECISION_EXECUTION_UNIQUE,
            "fk_name": GENERATION_DECISION_EXECUTION_FK,
        }).mappings().all()

    assert len(constraints) == 2
    by_name = {constraint["conname"]: constraint for constraint in constraints}
    unique = by_name[GENERATION_DECISION_EXECUTION_UNIQUE]
    foreign_key = by_name[GENERATION_DECISION_EXECUTION_FK]
    exact_columns = [
        "activation_execution_id",
        "activation_decision_id",
        "activation_decision_record_hash",
    ]
    assert unique["contype"] == "u"
    assert unique["local_columns"] == exact_columns
    assert foreign_key["contype"] == "f"
    assert foreign_key["local_columns"] == exact_columns
    assert foreign_key["referenced_columns"] == exact_columns
    assert foreign_key["convalidated"] is False
    assert foreign_key["condeferrable"] is False
    assert foreign_key["condeferred"] is False
    assert foreign_key["confmatchtype"] == "s"
    assert foreign_key["confupdtype"] == "r"
    assert foreign_key["confdeltype"] == "r"
    definition = foreign_key["pg_get_constraintdef"]
    for clause in (
        "ON UPDATE RESTRICT", "ON DELETE RESTRICT", "NOT VALID",
    ):
        assert clause in definition


def test_activation_generation_decision_execution_fk_is_prospective(
    postgresql_intention_9b1,
):
    engine = postgresql_intention_9b1["engine"]
    suffix = "prospective-9b3"
    bindings = _precedence_physical_records(engine, suffix)
    _materialize_policy_activations(engine, bindings["policy_bindings"])

    decision_d1 = _decision(f"d1-{suffix}", bindings)
    decision_d2 = copy.deepcopy(decision_d1)
    decision_d2.update({
        "activation_decision_id": f"decision-d2-{suffix}",
        "idempotency_key": f"decision-idem-d2-{suffix}",
        "record_hash": _digest(f"decision-d2-{suffix}"),
    })
    executions = {
        label: _execution(decision_d1, f"{label}-{suffix}")
        for label in ("control", "historical", "new-false", "new-coherent")
    }

    def generation(label, decision, execution):
        return {
            "activation_generation_id": f"generation-{label}-{suffix}",
            "previous_activation_generation_id": None,
            "previous_activation_generation_record_hash": None,
            "activation_execution_id": execution["activation_execution_id"],
            "activation_decision_id": decision["activation_decision_id"],
            "activation_decision_record_hash": decision["record_hash"],
            "target_manifest_hash": decision["target_manifest_hash"],
            "scope_descriptor": {"country": "PT", "generation": label},
            "scope_hash": _digest(f"generation-scope-{label}-{suffix}"),
            "composition_manifest": [{
                "subject_type": "rule_version",
                "subject_id": f"rule-{label}-{suffix}",
                "subject_version": 1,
                "subject_hash": _digest(f"rule-{label}-{suffix}"),
            }],
            "composition_hash": _digest(f"composition-{label}-{suffix}"),
            "policy_bindings": decision["policy_bindings"],
            "coverage_binding": decision["coverage_binding"],
            "continuity_binding": decision["continuity_binding"],
            "precedence_binding": decision["precedence_binding"],
            "gates_evidence": decision["gates_evidence"],
            "is_complete": True,
            "effective_from": datetime.now(timezone.utc),
            "provenance": {"mission": "MISSION-010-INTENCAO-9B3"},
            "record_hash": _digest(f"generation-{label}-{suffix}"),
        }

    control = generation("control", decision_d1, executions["control"])
    historical = generation("historical", decision_d2, executions["historical"])
    new_false = generation("new-false", decision_d2, executions["new-false"])
    new_coherent = generation(
        "new-coherent", decision_d1, executions["new-coherent"],
    )

    with engine.begin() as connection:
        assert connection.scalar(text(
            "SELECT version_num FROM alembic_version"
        )) == GENERATION_EXECUTION_GATE_REVISION
        connection.execute(
            insert(models.ActivationDecision), [decision_d1, decision_d2],
        )
        connection.execute(
            insert(models.ActivationExecution), list(executions.values()),
        )
        connection.execute(
            insert(models.ActivationGeneration), [control, historical],
        )
        historical_before = connection.execute(text("""
            SELECT activation_generation_id, activation_execution_id,
                   activation_decision_id, activation_decision_record_hash
            FROM activation_generations
            WHERE activation_generation_id=:generation_id
        """), {"generation_id": historical["activation_generation_id"]}).one()
        operations = Operations(MigrationContext.configure(connection))
        migration = _load_migration(
            GENERATION_DECISION_EXECUTION_FK_MIGRATION,
            "test_prospective_physical_0039",
        )
        migration.op = operations
        migration.upgrade()
        connection.execute(text("""
            UPDATE alembic_version SET version_num=:new WHERE version_num=:old
        """), {
            "new": GENERATION_DECISION_EXECUTION_FK_REVISION,
            "old": GENERATION_EXECUTION_GATE_REVISION,
        })

    with engine.connect() as connection:
        historical_after = connection.execute(text("""
            SELECT activation_generation_id, activation_execution_id,
                   activation_decision_id, activation_decision_record_hash
            FROM activation_generations
            WHERE activation_generation_id=:generation_id
        """), {"generation_id": historical["activation_generation_id"]}).one()
        assert historical_after == historical_before
        assert connection.scalar(text("""
            SELECT convalidated FROM pg_constraint WHERE conname=:name
        """), {"name": GENERATION_DECISION_EXECUTION_FK}) is False

    with pytest.raises(DBAPIError) as exc_info:
        with engine.begin() as connection:
            connection.execute(insert(models.ActivationGeneration), new_false)
    assert exc_info.value.orig.sqlstate == "23503"
    assert exc_info.value.orig.diag.constraint_name == (
        GENERATION_DECISION_EXECUTION_FK
    )

    with engine.begin() as connection:
        connection.execute(insert(models.ActivationGeneration), new_coherent)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM activation_generations
            WHERE activation_generation_id=:generation_id
              AND activation_execution_id=:execution_id
              AND activation_decision_id=:decision_id
              AND activation_decision_record_hash=:decision_hash
        """), {
            "generation_id": new_coherent["activation_generation_id"],
            "execution_id": new_coherent["activation_execution_id"],
            "decision_id": new_coherent["activation_decision_id"],
            "decision_hash": new_coherent["activation_decision_record_hash"],
        }) == 1


def test_normative_activation_rejects_generation_from_different_exact_decision_via_core(
    postgresql_intention_9b3,
):
    engine = postgresql_intention_9b3["engine"]
    suffix = "generation-different-decision-int9b2"
    activation, rules, _, reviews, _ = _intention_8b1_context(engine, suffix)
    with engine.connect() as connection:
        decision_d1 = dict(connection.execute(
            models.ActivationDecision.__table__.select().where(
                models.ActivationDecision.activation_decision_id
                == activation["activation_decision_id"]
            )
        ).mappings().one())

    decision_d2 = copy.deepcopy(decision_d1)
    decision_d2.update(
        activation_decision_id=f"decision-d2-{suffix}",
        idempotency_key=f"decision-idem-d2-{suffix}",
        record_hash=_digest(f"decision-d2-{suffix}"),
    )
    executions = {
        label: _execution(decision_d1, f"{label}-{suffix}")
        for label in ("control", "false")
    }

    def generation(label, subject):
        return {
            "activation_generation_id": f"generation-{label}-{suffix}",
            "previous_activation_generation_id": None,
            "previous_activation_generation_record_hash": None,
            "activation_execution_id": executions[label][
                "activation_execution_id"
            ],
            "activation_decision_id": decision_d1["activation_decision_id"],
            "activation_decision_record_hash": decision_d1["record_hash"],
            "target_manifest_hash": decision_d1["target_manifest_hash"],
            "scope_descriptor": {"country": "PT", "generation": label},
            "scope_hash": _digest(f"generation-scope-{label}-{suffix}"),
            "composition_manifest": [{
                "subject_type": "rule_version",
                "subject_id": subject["rule_id"],
                "subject_version": subject["rule_version"],
                "subject_hash": subject["rule_hash"],
            }],
            "composition_hash": _digest(f"composition-{label}-{suffix}"),
            **{key: decision_d1[key] for key in BINDINGS},
            "is_complete": True,
            "effective_from": datetime.now(timezone.utc),
            "provenance": {"mission": "MISSION-011-INTENCAO-9B2"},
            "record_hash": _digest(f"generation-{label}-{suffix}"),
        }

    generations = {
        label: generation(label, rules[index])
        for index, label in enumerate(("control", "false"))
    }
    control = copy.deepcopy(activation)
    control.update(
        normative_activation_id=f"activation-control-{suffix}",
        activation_execution_id=executions["control"][
            "activation_execution_id"
        ],
        activation_generation_id=generations["control"][
            "activation_generation_id"
        ],
        scope_hash=generations["control"]["scope_hash"],
        record_hash=_digest(f"activation-control-{suffix}"),
    )
    false = copy.deepcopy(control)
    false.update(
        normative_activation_id=f"activation-false-{suffix}",
        activation_decision_id=decision_d2["activation_decision_id"],
        activation_decision_record_hash=decision_d2["record_hash"],
        activation_execution_id=executions["false"][
            "activation_execution_id"
        ],
        activation_generation_id=generations["false"][
            "activation_generation_id"
        ],
        subject_id=rules[1]["rule_id"],
        subject_version=rules[1]["rule_version"],
        subject_hash=rules[1]["rule_hash"],
        review_record_id=reviews[1]["rule_review_record_id"],
        review_record_hash=reviews[1]["record_hash"],
        scope_hash=generations["false"]["scope_hash"],
        record_hash=_digest(f"activation-false-{suffix}"),
    )

    with engine.begin() as connection:
        connection.execute(insert(models.ActivationDecision), decision_d2)
        connection.execute(
            insert(models.ActivationExecution), list(executions.values()),
        )
        connection.execute(
            insert(models.ActivationGeneration), list(generations.values()),
        )

    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT version_num FROM alembic_version"
        )) == GENERATION_DECISION_EXECUTION_FK_REVISION
        for exact_decision in (decision_d1, decision_d2):
            assert connection.scalar(text("""
                SELECT count(*) FROM activation_decisions
                WHERE activation_decision_id=:id AND record_hash=:hash
                  AND decision_action='activate' AND decision_outcome='approved'
            """), {
                "id": exact_decision["activation_decision_id"],
                "hash": exact_decision["record_hash"],
            }) == 1
        for label in ("control", "false"):
            assert connection.scalar(text("""
                SELECT count(*) FROM activation_generations g
                JOIN activation_executions e
                  ON e.activation_execution_id=g.activation_execution_id
                 AND e.activation_decision_id=g.activation_decision_id
                 AND e.activation_decision_record_hash=
                     g.activation_decision_record_hash
                WHERE g.activation_generation_id=:generation_id
                  AND g.activation_decision_id=:decision_id
                  AND g.activation_decision_record_hash=:decision_hash
            """), {
                "generation_id": generations[label]["activation_generation_id"],
                "decision_id": decision_d1["activation_decision_id"],
                "decision_hash": decision_d1["record_hash"],
            }) == 1
        assert connection.scalar(text("""
            SELECT count(*) FROM rule_versions r
            JOIN rule_review_records v
              ON (v.subject_id, v.subject_version, v.subject_hash)
               = (r.rule_id, r.rule_version, r.rule_hash)
            WHERE r.rule_id=:subject_id AND r.rule_version=:subject_version
              AND r.rule_hash=:subject_hash
              AND v.rule_review_record_id=:review_id
              AND v.record_hash=:review_hash
        """), {
            "subject_id": false["subject_id"],
            "subject_version": false["subject_version"],
            "subject_hash": false["subject_hash"],
            "review_id": false["review_record_id"],
            "review_hash": false["review_record_hash"],
        }) == 1

    with engine.begin() as connection:
        connection.execute(insert(models.NormativeActivation), control)
    columns = tuple(control)
    with engine.connect() as connection:
        assert connection.execute(text(f"""
            SELECT {', '.join(columns)} FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": control["normative_activation_id"]}).one() == tuple(
            control[column] for column in columns
        )

    assert false["activation_execution_id"] == generations["false"][
        "activation_execution_id"
    ]
    assert (
        generations["false"]["activation_decision_id"],
        generations["false"]["activation_decision_record_hash"],
    ) == (decision_d1["activation_decision_id"], decision_d1["record_hash"])
    assert (
        false["activation_decision_id"],
        false["activation_decision_record_hash"],
    ) == (decision_d2["activation_decision_id"], decision_d2["record_hash"])
    with pytest.raises(DBAPIError):
        with engine.begin() as connection:
            connection.execute(insert(models.NormativeActivation), false)


def test_normative_activation_has_direct_exact_execution_decision_fk_not_valid(
    postgresql_intention_9b4,
):
    engine = postgresql_intention_9b4["engine"]
    with engine.connect() as connection:
        foreign_key = connection.execute(text("""
            SELECT c.conname, c.contype, c.convalidated, c.condeferrable,
                   c.condeferred, c.confmatchtype, c.confupdtype, c.confdeltype,
                   local_table.relname AS local_table,
                   referenced_table.relname AS referenced_table,
                   referenced_key.relname AS referenced_key,
                   ARRAY(
                       SELECT a.attname
                       FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
                       JOIN pg_attribute a
                         ON a.attrelid=c.conrelid AND a.attnum=k.attnum
                       ORDER BY k.ord
                   ) AS local_columns,
                   ARRAY(
                       SELECT a.attname
                       FROM unnest(c.confkey) WITH ORDINALITY AS k(attnum, ord)
                       JOIN pg_attribute a
                         ON a.attrelid=c.confrelid AND a.attnum=k.attnum
                       ORDER BY k.ord
                   ) AS referenced_columns
            FROM pg_constraint c
            JOIN pg_class local_table ON local_table.oid=c.conrelid
            JOIN pg_class referenced_table ON referenced_table.oid=c.confrelid
            JOIN pg_class referenced_key ON referenced_key.oid=c.conindid
            WHERE c.conname =
                'fk_normative_activations_exact_execution_decision'
        """)).mappings().one_or_none()

    assert foreign_key is not None
    assert foreign_key["conname"] == (
        "fk_normative_activations_exact_execution_decision"
    )
    assert foreign_key["contype"] == "f"
    assert foreign_key["local_table"] == "normative_activations"
    assert foreign_key["referenced_table"] == "activation_executions"
    exact_columns = [
        "activation_execution_id",
        "activation_decision_id",
        "activation_decision_record_hash",
    ]
    assert foreign_key["local_columns"] == exact_columns
    assert foreign_key["referenced_columns"] == exact_columns
    assert foreign_key["confmatchtype"] == "s"
    assert foreign_key["confupdtype"] == "r"
    assert foreign_key["confdeltype"] == "r"
    assert foreign_key["condeferrable"] is False
    assert foreign_key["condeferred"] is False
    assert foreign_key["convalidated"] is False
    assert foreign_key["referenced_key"] == (
        "uq_activation_executions_exact_decision_binding"
    )


def test_normative_generation_decision_fk_is_physical_and_not_valid(
    postgresql_intention_9b2, monkeypatch,
):
    source = NORMATIVE_GENERATION_DECISION_FK_MIGRATION.read_text(
        encoding="utf-8",
    )
    lowered = source.lower()
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body if isinstance(node, ast.Assign)
        and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {
            "revision", "down_revision", "branch_labels", "depends_on",
        }
    }
    assert assignments == {
        "revision": NORMATIVE_GENERATION_DECISION_FK_REVISION,
        "down_revision": GENERATION_DECISION_EXECUTION_FK_REVISION,
        "branch_labels": None,
        "depends_on": None,
    }

    upgrade = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
    )
    assert isinstance(upgrade.body[0], ast.Assign)
    assert upgrade.body[0].targets[0].id == "bind"
    assert isinstance(upgrade.body[1], ast.If)
    assert ast.unparse(upgrade.body[1].test) == (
        "bind.dialect.name != 'postgresql'"
    )
    assert ast.literal_eval(upgrade.body[1].body[0].exc.args[0]) == (
        "ADR-020 migration 0040 requires PostgreSQL"
    )
    assert isinstance(upgrade.body[2], ast.Expr)
    assert ast.unparse(upgrade.body[2].value.func) == (
        "op.create_unique_constraint"
    )
    assert isinstance(upgrade.body[3], ast.Expr)
    assert ast.unparse(upgrade.body[3].value.func) == "op.execute"

    downgrade = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "downgrade"
    )
    assert len(downgrade.body) == 1
    assert isinstance(downgrade.body[0], ast.Raise)
    assert ast.literal_eval(downgrade.body[0].exc.args[0]) == (
        "ADR-020 migration 0040 is irreversible: "
        "exact normative-generation-decision binding cannot be removed"
    )
    for forbidden in (
        "drop", "validate constraint", "create index", "pass", "return",
    ):
        assert not re.search(rf"\b{forbidden}\b", lowered)
    for clause in (
        "MATCH SIMPLE", "ON UPDATE RESTRICT", "ON DELETE RESTRICT",
        "NOT DEFERRABLE", "INITIALLY IMMEDIATE", "NOT VALID",
    ):
        assert clause in source
    assert source.count(NORMATIVE_GENERATION_DECISION_UNIQUE) == 1
    assert source.count(NORMATIVE_GENERATION_DECISION_FK) == 1
    assert "activation_execution_id" not in source
    assert GENERATION_FK not in source

    migration = _load_migration(
        NORMATIVE_GENERATION_DECISION_FK_MIGRATION,
        "test_0040_non_postgresql_guard",
    )

    class NonPostgresqlOperations:
        def __init__(self):
            self.ddl_calls = []

        def get_bind(self):
            return type("Bind", (), {"dialect": type(
                "Dialect", (), {"name": "sqlite"},
            )()})()

        def create_unique_constraint(self, *args, **kwargs):
            self.ddl_calls.append((args, kwargs))

        def execute(self, statement):
            self.ddl_calls.append(statement)

    non_postgresql_op = NonPostgresqlOperations()
    monkeypatch.setattr(migration, "op", non_postgresql_op)
    with pytest.raises(RuntimeError) as guard_error:
        migration.upgrade()
    assert str(guard_error.value) == "ADR-020 migration 0040 requires PostgreSQL"
    assert non_postgresql_op.ddl_calls == []
    with pytest.raises(RuntimeError) as downgrade_error:
        migration.downgrade()
    assert str(downgrade_error.value) == (
        "ADR-020 migration 0040 is irreversible: "
        "exact normative-generation-decision binding cannot be removed"
    )

    engine = postgresql_intention_9b2["engine"]
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT version_num FROM alembic_version"
        )) == NORMATIVE_GENERATION_DECISION_FK_REVISION
        constraints = connection.execute(text("""
            SELECT c.conname, c.contype, c.convalidated, c.condeferrable,
                   c.condeferred, c.confmatchtype, c.confupdtype, c.confdeltype,
                   local_table.relname AS local_table,
                   referenced_table.relname AS referenced_table,
                   ARRAY(
                       SELECT a.attname
                       FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
                       JOIN pg_attribute a
                         ON a.attrelid=c.conrelid AND a.attnum=k.attnum
                       ORDER BY k.ord
                   ) AS local_columns,
                   ARRAY(
                       SELECT a.attname
                       FROM unnest(c.confkey) WITH ORDINALITY AS k(attnum, ord)
                       JOIN pg_attribute a
                         ON a.attrelid=c.confrelid AND a.attnum=k.attnum
                       ORDER BY k.ord
                   ) AS referenced_columns
            FROM pg_constraint c
            JOIN pg_class local_table ON local_table.oid=c.conrelid
            LEFT JOIN pg_class referenced_table
              ON referenced_table.oid=c.confrelid
            WHERE c.conname IN (:unique_name, :composite_fk, :simple_fk)
            ORDER BY c.conname
        """), {
            "unique_name": NORMATIVE_GENERATION_DECISION_UNIQUE,
            "composite_fk": NORMATIVE_GENERATION_DECISION_FK,
            "simple_fk": GENERATION_FK,
        }).mappings().all()

    assert len(constraints) == 3
    by_name = {constraint["conname"]: constraint for constraint in constraints}
    exact_columns = [
        "activation_generation_id",
        "activation_decision_id",
        "activation_decision_record_hash",
    ]
    unique = by_name[NORMATIVE_GENERATION_DECISION_UNIQUE]
    assert unique["contype"] == "u"
    assert unique["local_table"] == "activation_generations"
    assert unique["local_columns"] == exact_columns

    foreign_key = by_name[NORMATIVE_GENERATION_DECISION_FK]
    assert foreign_key["contype"] == "f"
    assert foreign_key["local_table"] == "normative_activations"
    assert foreign_key["referenced_table"] == "activation_generations"
    assert foreign_key["local_columns"] == exact_columns
    assert foreign_key["referenced_columns"] == exact_columns
    assert "activation_execution_id" not in foreign_key["local_columns"]
    assert "activation_execution_id" not in foreign_key["referenced_columns"]
    assert foreign_key["convalidated"] is False
    assert foreign_key["confmatchtype"] == "s"
    assert foreign_key["confupdtype"] == "r"
    assert foreign_key["confdeltype"] == "r"
    assert foreign_key["condeferrable"] is False
    assert foreign_key["condeferred"] is False

    simple_fk = by_name[GENERATION_FK]
    assert simple_fk["contype"] == "f"
    assert simple_fk["local_table"] == "normative_activations"
    assert simple_fk["referenced_table"] == "activation_generations"
    assert simple_fk["local_columns"] == ["activation_generation_id"]
    assert simple_fk["referenced_columns"] == ["activation_generation_id"]


def test_normative_generation_decision_fk_is_prospective(
    postgresql_intention_9b2_prospective,
):
    engine = postgresql_intention_9b2_prospective["engine"]
    suffix = "prospective-9b2"
    activation, rules, _, _, _ = _intention_8b1_context(engine, suffix)
    with engine.connect() as connection:
        decision_d1 = dict(connection.execute(
            models.ActivationDecision.__table__.select().where(
                models.ActivationDecision.activation_decision_id
                == activation["activation_decision_id"]
            )
        ).mappings().one())

    decision_d2 = copy.deepcopy(decision_d1)
    decision_d2.update(
        activation_decision_id=f"decision-d2-{suffix}",
        idempotency_key=f"decision-idem-d2-{suffix}",
        record_hash=_digest(f"decision-d2-{suffix}"),
    )
    activation_execution_id = activation["activation_execution_id"]
    generation = {
        "activation_generation_id": f"generation-{suffix}",
        "previous_activation_generation_id": None,
        "previous_activation_generation_record_hash": None,
        "activation_execution_id": activation_execution_id,
        "activation_decision_id": decision_d1["activation_decision_id"],
        "activation_decision_record_hash": decision_d1["record_hash"],
        "target_manifest_hash": decision_d1["target_manifest_hash"],
        "scope_descriptor": {"country": "PT", "generation": suffix},
        "scope_hash": _digest(f"generation-scope-{suffix}"),
        "composition_manifest": [{
            "subject_type": "rule_version",
            "subject_id": rules[0]["rule_id"],
            "subject_version": rules[0]["rule_version"],
            "subject_hash": rules[0]["rule_hash"],
        }],
        "composition_hash": _digest(f"composition-{suffix}"),
        **{key: decision_d1[key] for key in BINDINGS},
        "is_complete": True,
        "effective_from": datetime.now(timezone.utc),
        "provenance": {"mission": "MISSION-012-INTENCAO-9B2"},
        "record_hash": _digest(f"generation-{suffix}"),
    }
    historical = copy.deepcopy(activation)
    historical.update(
        normative_activation_id=f"activation-historical-{suffix}",
        activation_decision_id=decision_d2["activation_decision_id"],
        activation_decision_record_hash=decision_d2["record_hash"],
        activation_execution_id=activation_execution_id,
        activation_generation_id=generation["activation_generation_id"],
        scope_hash=generation["scope_hash"],
        record_hash=_digest(f"activation-historical-{suffix}"),
    )
    new_false = copy.deepcopy(historical)
    new_false.update(
        normative_activation_id=f"activation-new-false-{suffix}",
        record_hash=_digest(f"activation-new-false-{suffix}"),
    )
    coherent = copy.deepcopy(historical)
    coherent.update(
        normative_activation_id=f"activation-coherent-{suffix}",
        activation_decision_id=decision_d1["activation_decision_id"],
        activation_decision_record_hash=decision_d1["record_hash"],
        record_hash=_digest(f"activation-coherent-{suffix}"),
    )

    with engine.begin() as connection:
        assert connection.scalar(text(
            "SELECT version_num FROM alembic_version"
        )) == GENERATION_DECISION_EXECUTION_FK_REVISION
        connection.execute(insert(models.ActivationDecision), decision_d2)
        connection.execute(insert(models.ActivationGeneration), generation)
        connection.execute(insert(models.NormativeActivation), historical)
        historical_before = connection.execute(text("""
            SELECT activation_generation_id, activation_decision_id,
                   activation_decision_record_hash
            FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": historical["normative_activation_id"]}).one()
        operations = Operations(MigrationContext.configure(connection))
        migration = _load_migration(
            NORMATIVE_GENERATION_DECISION_FK_MIGRATION,
            "test_prospective_physical_0040",
        )
        migration.op = operations
        migration.upgrade()
        connection.execute(text("""
            UPDATE alembic_version SET version_num=:new WHERE version_num=:old
        """), {
            "new": NORMATIVE_GENERATION_DECISION_FK_REVISION,
            "old": GENERATION_DECISION_EXECUTION_FK_REVISION,
        })

    with engine.connect() as connection:
        historical_after = connection.execute(text("""
            SELECT activation_generation_id, activation_decision_id,
                   activation_decision_record_hash
            FROM normative_activations
            WHERE normative_activation_id=:id
        """), {"id": historical["normative_activation_id"]}).one()
        assert historical_after == historical_before
        assert connection.scalar(text("""
            SELECT convalidated FROM pg_constraint WHERE conname=:name
        """), {"name": NORMATIVE_GENERATION_DECISION_FK}) is False

    with engine.begin() as connection:
        connection.execute(insert(models.NormativeActivation), coherent)
    with engine.connect() as connection:
        assert connection.scalar(text("""
            SELECT count(*) FROM normative_activations
            WHERE normative_activation_id=:id
              AND activation_generation_id=:generation_id
              AND activation_decision_id=:decision_id
              AND activation_decision_record_hash=:decision_hash
        """), {
            "id": coherent["normative_activation_id"],
            "generation_id": coherent["activation_generation_id"],
            "decision_id": coherent["activation_decision_id"],
            "decision_hash": coherent["activation_decision_record_hash"],
        }) == 1

    with pytest.raises(DBAPIError) as exc_info:
        with engine.begin() as connection:
            connection.execute(insert(models.NormativeActivation), new_false)
    assert exc_info.value.orig.sqlstate == "23503"
    assert exc_info.value.orig.diag.constraint_name == (
        NORMATIVE_GENERATION_DECISION_FK
    )
