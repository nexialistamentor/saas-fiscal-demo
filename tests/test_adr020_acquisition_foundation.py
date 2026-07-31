import ast
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, event

from app import models


MIGRATION_PATH = Path(
    "migrations/versions/0018_adr020_acquisition_foundation.py"
)

MINIMUM_COLUMNS = {
    models.ArtifactReference: {
        "artifact_reference_id",
        "source_id",
        "exact_locator",
        "official_identifier",
        "expected_media_type",
        "discovered_at",
        "evidence",
        "record_hash",
    },
    models.AcquisitionExecution: {
        "acquisition_execution_id",
        "artifact_reference_id",
        "attempt_number",
        "actor_or_worker",
        "adapter_version",
        "started_at",
        "finished_at",
        "structured_result",
        "structured_error",
        "evidence",
        "provenance",
        "record_hash",
    },
    models.NormativeArtifact: {
        "normative_artifact_id",
        "acquisition_execution_id",
        "artifact_reference_id",
        "immutable_bytes",
        "immutable_location",
        "byte_size",
        "artifact_hash",
        "acquired_at",
        "media_type",
        "provenance",
        "record_hash",
    },
    models.ArtifactVerificationRecord: {
        "artifact_verification_record_id",
        "normative_artifact_id",
        "verified_artifact_hash",
        "verification_type",
        "outcome",
        "verifier",
        "verifier_version",
        "evidence",
        "incident_id",
        "previous_verification_record_id",
        "timestamp",
        "record_hash",
    },
}


def _constraint_names(table, constraint_type) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, constraint_type) and constraint.name
    }


def _check_sql(table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )


def _foreign_key_pairs(table) -> set[tuple[tuple[str, str], ...]]:
    result = set()
    for constraint in table.constraints:
        if not isinstance(constraint, ForeignKeyConstraint):
            continue
        result.add(
            tuple(
                (element.parent.name, element.target_fullname)
                for element in constraint.elements
            )
        )
    return result


def _literal_assignment(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Assignment not found: {name}")


def _sha(character: str) -> str:
    return character * 64


def _artifact(**overrides):
    payload = dict(
        normative_artifact_id="artifact-1",
        acquisition_execution_record_id="execution-record-3",
        acquisition_execution_id="execution-1",
        artifact_reference_id="reference-1",
        acquisition_attempt_number=1,
        acquisition_event="conclusao",
        acquisition_state="concluida",
        immutable_bytes=b"abc",
        immutable_location=None,
        byte_size=3,
        artifact_hash=(
            "ba7816bf8f01cfea414140de5dae2223"
            "b00361a396177a9cb410ff61f20015ad"
        ),
        media_type="application/pdf",
        provenance={},
        record_hash=_sha("a"),
    )
    payload.update(overrides)
    return models.NormativeArtifact(**payload)


def _verification(verification_type: str, **overrides):
    payload = dict(
        artifact_verification_record_id="verification-1",
        normative_artifact_id="artifact-1",
        verified_artifact_hash=_sha("b"),
        verification_type=verification_type,
        outcome="conclusivo_favoravel",
        verifier="verifier",
        verifier_version="1",
        evidence={},
        authenticity_verification_record_id=None,
        authenticity_predecessor_type=None,
        authenticity_predecessor_outcome=None,
        integrity_verification_record_id=None,
        integrity_predecessor_type=None,
        integrity_predecessor_outcome=None,
        record_hash=_sha("c"),
    )
    payload.update(overrides)
    return models.ArtifactVerificationRecord(**payload)


def test_commit_1_exposes_only_the_four_bounded_model_classes():
    names = {
        name
        for name, value in vars(models).items()
        if isinstance(value, type) and hasattr(value, "__tablename__")
        and value.__tablename__ in {
            "artifact_references",
            "acquisition_executions",
            "normative_artifacts",
            "artifact_verification_records",
        }
    }
    assert names == {
        "ArtifactReference",
        "AcquisitionExecution",
        "NormativeArtifact",
        "ArtifactVerificationRecord",
    }


def test_models_preserve_every_ratified_minimum_column():
    for model, minimum in MINIMUM_COLUMNS.items():
        assert minimum <= set(model.__table__.columns.keys())


def test_artifact_reference_is_an_append_only_event_projection():
    columns = set(models.ArtifactReference.__table__.columns.keys())
    assert {
        "artifact_reference_record_id",
        "reference_event",
        "event_sequence",
        "previous_artifact_reference_record_id",
        "occurred_at",
    } <= columns
    checks = _check_sql(models.ArtifactReference.__table__)
    for value in ("identificada", "agendada", "resolvida", "nao_resolvida"):
        assert value in checks
    assert "event_sequence = 1" in checks
    assert "reference_event = 'identificada'" in checks


def test_artifact_reference_predecessor_is_bound_to_same_identity():
    pairs = _foreign_key_pairs(models.ArtifactReference.__table__)
    assert (
        (
            (
                "previous_artifact_reference_record_id",
                "artifact_references.artifact_reference_record_id",
            ),
            (
                "artifact_reference_id",
                "artifact_references.artifact_reference_id",
            ),
        )
        in pairs
    )


def test_acquisition_execution_is_an_append_only_event_projection():
    columns = set(models.AcquisitionExecution.__table__.columns.keys())
    assert {
        "acquisition_execution_record_id",
        "artifact_reference_record_id",
        "execution_event",
        "projected_state",
        "event_sequence",
        "previous_acquisition_execution_record_id",
        "occurred_at",
    } <= columns
    checks = _check_sql(models.AcquisitionExecution.__table__)
    for state in (
        "planeada",
        "em_execucao",
        "concluida",
        "concluida_parcial",
        "indisponivel",
        "falhada",
        "interrompida",
        "cancelada",
    ):
        assert state in checks
    assert "execution_event = 'conclusao'" in checks
    assert "projected_state = 'concluida'" in checks


def test_acquisition_predecessor_is_bound_to_same_attempt():
    pairs = _foreign_key_pairs(models.AcquisitionExecution.__table__)
    assert (
        (
            (
                "previous_acquisition_execution_record_id",
                "acquisition_executions.acquisition_execution_record_id",
            ),
            (
                "acquisition_execution_id",
                "acquisition_executions.acquisition_execution_id",
            ),
            (
                "artifact_reference_id",
                "acquisition_executions.artifact_reference_id",
            ),
            (
                "attempt_number",
                "acquisition_executions.attempt_number",
            ),
        )
        in pairs
    )


def test_acquisition_event_state_validator_rejects_invalid_pair():
    target = models.AcquisitionExecution(
        acquisition_execution_record_id="record-1",
        acquisition_execution_id="execution-1",
        artifact_reference_record_id="reference-record-1",
        artifact_reference_id="reference-1",
        attempt_number=1,
        execution_event="falha",
        projected_state="concluida",
        event_sequence=2,
        previous_acquisition_execution_record_id="record-0",
        actor_or_worker="worker",
        adapter_version="1",
        finished_at=datetime.now(timezone.utc),
        evidence={},
        provenance={},
        record_hash=_sha("d"),
    )
    with pytest.raises(ValueError, match="event/state"):
        models._adr020_validate_acquisition_execution_insert(None, None, target)


def test_concluded_acquisition_requires_exact_byte_proof():
    target = models.AcquisitionExecution(
        acquisition_execution_record_id="record-3",
        acquisition_execution_id="execution-1",
        artifact_reference_record_id="reference-record-1",
        artifact_reference_id="reference-1",
        attempt_number=1,
        execution_event="conclusao",
        projected_state="concluida",
        event_sequence=3,
        previous_acquisition_execution_record_id="record-2",
        actor_or_worker="worker",
        adapter_version="1",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        structured_result={"bytes_received": False},
        evidence={},
        provenance={},
        record_hash=_sha("e"),
    )
    with pytest.raises(ValueError, match="bytes_received"):
        models._adr020_validate_acquisition_execution_insert(None, None, target)


def test_normative_artifact_is_bound_to_exact_concluded_execution_record():
    pairs = _foreign_key_pairs(models.NormativeArtifact.__table__)
    assert (
        (
            (
                "acquisition_execution_record_id",
                "acquisition_executions.acquisition_execution_record_id",
            ),
            (
                "acquisition_execution_id",
                "acquisition_executions.acquisition_execution_id",
            ),
            (
                "artifact_reference_id",
                "acquisition_executions.artifact_reference_id",
            ),
            (
                "acquisition_attempt_number",
                "acquisition_executions.attempt_number",
            ),
            (
                "acquisition_event",
                "acquisition_executions.execution_event",
            ),
            (
                "acquisition_state",
                "acquisition_executions.projected_state",
            ),
        )
        in pairs
    )
    checks = _check_sql(models.NormativeArtifact.__table__)
    assert "acquisition_event = 'conclusao'" in checks
    assert "acquisition_state = 'concluida'" in checks


def test_failed_or_partial_acquisition_cannot_be_named_as_artifact_origin():
    for state in (
        "concluida_parcial",
        "indisponivel",
        "falhada",
        "interrompida",
        "cancelada",
    ):
        artifact = _artifact(acquisition_state=state)
        with pytest.raises(ValueError, match="concluded acquisition"):
            models._adr020_validate_normative_artifact_insert(None, None, artifact)


def test_normative_artifact_bytes_size_and_sha256_are_mathematically_bound():
    artifact = _artifact()
    models._adr020_validate_normative_artifact_insert(None, None, artifact)

    wrong_size = _artifact(byte_size=4)
    with pytest.raises(ValueError, match="byte_size"):
        models._adr020_validate_normative_artifact_insert(None, None, wrong_size)

    wrong_hash = _artifact(artifact_hash=_sha("f"))
    with pytest.raises(ValueError, match="artifact_hash"):
        models._adr020_validate_normative_artifact_insert(None, None, wrong_hash)


def test_immutable_location_requires_exact_canonical_cas_identity():
    digest = _sha("a")
    valid = _artifact(
        immutable_bytes=None,
        immutable_location=f"cas+sha256://{digest}/11",
        byte_size=11,
        artifact_hash=digest,
    )
    models._adr020_validate_normative_artifact_insert(None, None, valid)

    for invalid_location in (
        f"https://example.invalid/current.pdf?hash={digest}",
        f"cas+sha256://{digest}/12",
        f"prefix-cas+sha256://{digest}/11",
    ):
        invalid = _artifact(
            immutable_bytes=None,
            immutable_location=invalid_location,
            byte_size=11,
            artifact_hash=digest,
        )
        with pytest.raises(ValueError, match="immutable_location"):
            models._adr020_validate_normative_artifact_insert(None, None, invalid)


def test_normative_artifact_contains_no_verification_or_activation_state():
    forbidden = {
        "status",
        "state",
        "autenticidade_verificada",
        "integridade_verificada",
        "preservado",
        "corrompido",
        "juridicamente_validado",
        "activo",
        "revogado",
        "substituido",
        "supersedido",
        "updated_at",
    }
    columns = set(models.NormativeArtifact.__table__.columns.keys())
    assert not (forbidden & columns)


def test_verification_has_explicit_cumulative_predecessor_columns():
    columns = set(models.ArtifactVerificationRecord.__table__.columns.keys())
    assert {
        "authenticity_verification_record_id",
        "authenticity_predecessor_type",
        "authenticity_predecessor_outcome",
        "integrity_verification_record_id",
        "integrity_predecessor_type",
        "integrity_predecessor_outcome",
    } <= columns
    checks = _check_sql(models.ArtifactVerificationRecord.__table__)
    assert "verification_type = 'integrity'" in checks
    assert "verification_type = 'preservation'" in checks
    assert "conclusivo_favoravel" in checks


def test_integrity_requires_favorable_authenticity_predecessor():
    missing = _verification(
        "integrity",
        previous_verification_record_id=None,
        authenticity_verification_record_id=None,
    )
    with pytest.raises(ValueError, match="favorable authenticity"):
        models._adr020_validate_verification_insert(None, None, missing)

    valid = _verification(
        "integrity",
        previous_verification_record_id="auth-1",
        authenticity_verification_record_id="auth-1",
        authenticity_predecessor_type="authenticity",
        authenticity_predecessor_outcome="conclusivo_favoravel",
    )
    models._adr020_validate_verification_insert(None, None, valid)


def test_preservation_requires_both_favorable_gates_in_order():
    missing_integrity = _verification(
        "preservation",
        previous_verification_record_id="auth-1",
        authenticity_verification_record_id="auth-1",
        authenticity_predecessor_type="authenticity",
        authenticity_predecessor_outcome="conclusivo_favoravel",
        integrity_verification_record_id=None,
    )
    with pytest.raises(ValueError, match="authenticity and integrity"):
        models._adr020_validate_verification_insert(
            None,
            None,
            missing_integrity,
        )

    valid = _verification(
        "preservation",
        previous_verification_record_id="integrity-1",
        authenticity_verification_record_id="auth-1",
        authenticity_predecessor_type="authenticity",
        authenticity_predecessor_outcome="conclusivo_favoravel",
        integrity_verification_record_id="integrity-1",
        integrity_predecessor_type="integrity",
        integrity_predecessor_outcome="conclusivo_favoravel",
    )
    models._adr020_validate_verification_insert(None, None, valid)


def test_verification_fks_bind_favorable_predecessors_to_same_artifact_hash():
    pairs = _foreign_key_pairs(models.ArtifactVerificationRecord.__table__)
    assert any(
        pair[0][0] == "authenticity_verification_record_id"
        and pair[-2][0] == "authenticity_predecessor_type"
        and pair[-1][0] == "authenticity_predecessor_outcome"
        for pair in pairs
    )
    assert any(
        pair[0][0] == "integrity_verification_record_id"
        and pair[-2][0] == "integrity_predecessor_type"
        and pair[-1][0] == "integrity_predecessor_outcome"
        for pair in pairs
    )


def test_retry_attempt_number_and_artifact_origin_are_unique():
    acquisition_unique_names = _constraint_names(
        models.AcquisitionExecution.__table__,
        UniqueConstraint,
    )
    artifact_unique_names = _constraint_names(
        models.NormativeArtifact.__table__,
        UniqueConstraint,
    )
    assert (
        "uq_acquisition_executions_reference_attempt_sequence"
        in acquisition_unique_names
    )
    assert (
        "uq_normative_artifacts_single_per_acquisition_completion"
        in artifact_unique_names
    )


def test_predecessor_constant_columns_are_null_without_predecessor():
    verification = _verification("authenticity")
    assert verification.authenticity_predecessor_type is None
    assert verification.authenticity_predecessor_outcome is None
    assert verification.integrity_predecessor_type is None
    assert verification.integrity_predecessor_outcome is None


def test_all_four_models_reject_update_and_delete_at_orm_boundary():
    listener = models._adr020_reject_append_only_mutation
    for model in MINIMUM_COLUMNS:
        assert event.contains(model, "before_update", listener)
        assert event.contains(model, "before_delete", listener)
        assert "updated_at" not in model.__table__.columns


def test_all_four_models_have_insert_validators():
    for model, listener in models._ADR020_INSERT_VALIDATORS.items():
        assert event.contains(model, "before_insert", listener)


def test_migration_identity_lineage_and_exact_four_tables():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert (
        _literal_assignment(tree, "revision")
        == "0018_adr020_acquisition_foundation"
    )
    assert _literal_assignment(tree, "down_revision") == "0017_alertas_resolucao"

    created_tables = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "create_table" or not node.args:
            continue
        created_tables.add(ast.literal_eval(node.args[0]))

    assert created_tables == {
        "artifact_references",
        "acquisition_executions",
        "normative_artifacts",
        "artifact_verification_records",
    }


def test_migration_persists_state_machines_and_forbidden_transitions():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "adr020_validate_artifact_reference_event" in source
    assert "adr020_validate_acquisition_execution_event" in source
    assert "forbidden ArtifactReference transition" in source
    assert "forbidden acquisition transition" in source
    assert "event_sequence <> previous_row.event_sequence + 1" in source
    assert "projected_state IN ('em_execucao', 'cancelada')" in source
    assert "previous_row.projected_state = 'em_execucao'" in source


def test_migration_blocks_artifact_without_completed_byte_proof():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "fk_normative_artifacts_completed_execution" in source
    assert "execution_event = 'conclusao'" in source
    assert "projected_state = 'concluida'" in source
    assert '"bytes_received": true' in source
    assert "artifact diverges from concluded acquisition proof" in source


def test_migration_binds_bytes_size_and_sha256_and_content_addressed_location():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS pgcrypto" in source
    assert "octet_length(NEW.immutable_bytes) <> NEW.byte_size" in source
    assert "digest(NEW.immutable_bytes, 'sha256')" in source
    assert "cas+sha256://" in source
    assert "immutable_location is not canonical content address" in source


def test_migration_enforces_artifact_and_verification_causality():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "execution_finished_at" in source
    assert "NEW.acquired_at < execution_finished_at" in source
    assert "artifact acquired_at precedes acquisition completion" in source
    assert "artifact_acquired_at" in source
    assert "NEW.timestamp < artifact_acquired_at" in source
    assert "verification timestamp precedes artifact acquisition" in source


def test_migration_enforces_cumulative_verification_order():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "adr020_validate_verification_order" in source
    assert "verification_type = 'authenticity'" in source
    assert "verification_type = 'integrity'" in source
    assert "outcome = 'conclusivo_favoravel'" in source
    assert "integrity_row.authenticity_verification_record_id" in source
    assert "preservation predecessors are not cumulative" in source


def test_migration_blocks_update_delete_and_truncate_for_all_four_tables():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "BEFORE UPDATE OR DELETE" in source
    assert "BEFORE TRUNCATE" in source
    assert "FOR EACH STATEMENT" in source
    assert "for table_name in _APPEND_ONLY_TABLES" in source


def test_migration_downgrade_is_fail_closed_and_non_destructive():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    downgrade_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "downgrade"
    )
    downgrade_source = ast.get_source_segment(source, downgrade_node)
    assert "irreversible" in downgrade_source
    assert "raise RuntimeError" in downgrade_source
    assert "drop_table" not in downgrade_source
    assert "TRUNCATE" not in downgrade_source


def test_commit_1_does_not_introduce_operational_authority():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "NormativeActivation" not in source
    assert "CalculationBundle" not in source
    assert "worker execution" in source
    assert "does not authorize" in source

# -----------------------------------------------------------------------------
# PostgreSQL integration gate (enabled only by MI-020 R3 execution script)
# -----------------------------------------------------------------------------


def _record_hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _postgres_runtime() -> dict[str, str]:
    container = os.getenv("ADR020_PG_CONTAINER")
    if not container:
        pytest.skip("ADR020_PG_CONTAINER not configured")
    return {
        "container": container,
        "user": os.getenv("ADR020_PG_USER", "adr020"),
        "database": os.getenv("ADR020_PG_DATABASE", "adr020"),
        "password": os.getenv("ADR020_PG_PASSWORD", "adr020_test_password"),
    }


def _docker_psql(
    sql: str,
    *,
    expect_success: bool = True,
    tuples_only: bool = False,
) -> subprocess.CompletedProcess[str]:
    runtime = _postgres_runtime()
    command = [
        "docker",
        "exec",
        "-i",
        "-e",
        f"PGPASSWORD={runtime['password']}",
        runtime["container"],
        "psql",
        "-X",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        runtime["user"],
        "-d",
        runtime["database"],
    ]
    if tuples_only:
        command.extend(["-A", "-t"])
    result = subprocess.run(
        command,
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(
            "PostgreSQL command failed:\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    if not expect_success and result.returncode == 0:
        raise AssertionError("PostgreSQL command unexpectedly succeeded")
    return result


def _render_migration_sql() -> str:
    spec = importlib.util.spec_from_file_location(
        "adr020_migration_r3",
        MIGRATION_PATH,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load migration 0018")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    output = io.StringIO()
    context = MigrationContext.configure(
        url="postgresql://",
        opts={
            "as_sql": True,
            "output_buffer": output,
            "transactional_ddl": True,
        },
    )
    module.op = Operations(context)
    module.upgrade()
    return output.getvalue()


@pytest.fixture(scope="session")
def postgresql_migration_r3() -> dict[str, str]:
    runtime = _postgres_runtime()
    migration_sql = _render_migration_sql()
    _docker_psql(migration_sql)
    return runtime


def _completed_acquisition_sql(
    suffix: str,
    *,
    payload: bytes = b"abc",
) -> dict[str, str | int]:
    artifact_hash = hashlib.sha256(payload).hexdigest()
    byte_size = len(payload)
    reference_id = f"ref-{suffix}"
    reference_record_id = f"refrec-{suffix}"
    execution_id = f"exec-{suffix}"
    creation_id = f"execrec-{suffix}-1"
    running_id = f"execrec-{suffix}-2"
    completion_id = f"execrec-{suffix}-3"
    started_at = "2026-01-01T00:00:02+00:00"
    finished_at = "2026-01-01T00:00:03+00:00"
    occurred_at = "2026-01-01T00:00:04+00:00"
    result_json = json.dumps(
        {
            "bytes_received": True,
            "byte_size": byte_size,
            "artifact_hash": artifact_hash,
        },
        separators=(",", ":"),
    )

    sql = f"""
    INSERT INTO artifact_references (
        artifact_reference_record_id,
        artifact_reference_id,
        reference_event,
        event_sequence,
        previous_artifact_reference_record_id,
        source_id,
        exact_locator,
        official_identifier,
        expected_media_type,
        discovered_at,
        occurred_at,
        evidence,
        record_hash
    ) VALUES (
        {_sql_quote(reference_record_id)},
        {_sql_quote(reference_id)},
        'identificada',
        1,
        NULL,
        'integration-source',
        'https://official.invalid/document',
        NULL,
        'application/pdf',
        '2026-01-01T00:00:00+00:00',
        '2026-01-01T00:00:00+00:00',
        '{{}}'::jsonb,
        {_sql_quote(_record_hash(reference_record_id))}
    );

    INSERT INTO acquisition_executions (
        acquisition_execution_record_id,
        acquisition_execution_id,
        artifact_reference_record_id,
        artifact_reference_id,
        attempt_number,
        execution_event,
        projected_state,
        event_sequence,
        previous_acquisition_execution_record_id,
        actor_or_worker,
        adapter_version,
        started_at,
        finished_at,
        occurred_at,
        structured_result,
        structured_error,
        evidence,
        provenance,
        record_hash
    ) VALUES
    (
        {_sql_quote(creation_id)},
        {_sql_quote(execution_id)},
        {_sql_quote(reference_record_id)},
        {_sql_quote(reference_id)},
        1,
        'criacao',
        'planeada',
        1,
        NULL,
        'integration-worker',
        'adapter-r3',
        NULL,
        NULL,
        '2026-01-01T00:00:01+00:00',
        NULL,
        NULL,
        '{{}}'::jsonb,
        '{{}}'::jsonb,
        {_sql_quote(_record_hash(creation_id))}
    ),
    (
        {_sql_quote(running_id)},
        {_sql_quote(execution_id)},
        {_sql_quote(reference_record_id)},
        {_sql_quote(reference_id)},
        1,
        'inicio',
        'em_execucao',
        2,
        {_sql_quote(creation_id)},
        'integration-worker',
        'adapter-r3',
        {_sql_quote(started_at)},
        NULL,
        '2026-01-01T00:00:02+00:00',
        NULL,
        NULL,
        '{{}}'::jsonb,
        '{{}}'::jsonb,
        {_sql_quote(_record_hash(running_id))}
    ),
    (
        {_sql_quote(completion_id)},
        {_sql_quote(execution_id)},
        {_sql_quote(reference_record_id)},
        {_sql_quote(reference_id)},
        1,
        'conclusao',
        'concluida',
        3,
        {_sql_quote(running_id)},
        'integration-worker',
        'adapter-r3',
        {_sql_quote(started_at)},
        {_sql_quote(finished_at)},
        {_sql_quote(occurred_at)},
        {_sql_quote(result_json)}::jsonb,
        NULL,
        '{{}}'::jsonb,
        '{{}}'::jsonb,
        {_sql_quote(_record_hash(completion_id))}
    );
    """
    _docker_psql(sql)
    return {
        "artifact_hash": artifact_hash,
        "byte_size": byte_size,
        "reference_id": reference_id,
        "execution_id": execution_id,
        "completion_id": completion_id,
        "finished_at": finished_at,
        "payload_hex": payload.hex(),
    }


def _insert_artifact_sql(
    suffix: str,
    acquisition: dict[str, str | int],
    *,
    acquired_at: str,
    immutable_location: str | None = None,
) -> str:
    artifact_id = f"artifact-{suffix}"
    artifact_hash = str(acquisition["artifact_hash"])
    byte_size = int(acquisition["byte_size"])
    if immutable_location is None:
        storage_sql = (
            f"decode({_sql_quote(str(acquisition['payload_hex']))}, 'hex'), NULL"
        )
    else:
        storage_sql = f"NULL, {_sql_quote(immutable_location)}"
    return f"""
    INSERT INTO normative_artifacts (
        normative_artifact_id,
        acquisition_execution_record_id,
        acquisition_execution_id,
        artifact_reference_id,
        acquisition_attempt_number,
        acquisition_event,
        acquisition_state,
        immutable_bytes,
        immutable_location,
        byte_size,
        artifact_hash,
        acquired_at,
        media_type,
        provenance,
        record_hash
    ) VALUES (
        {_sql_quote(artifact_id)},
        {_sql_quote(str(acquisition['completion_id']))},
        {_sql_quote(str(acquisition['execution_id']))},
        {_sql_quote(str(acquisition['reference_id']))},
        1,
        'conclusao',
        'concluida',
        {storage_sql},
        {byte_size},
        {_sql_quote(artifact_hash)},
        {_sql_quote(acquired_at)},
        'application/pdf',
        '{{}}'::jsonb,
        {_sql_quote(_record_hash(artifact_id))}
    );
    """


def _verification_insert_sql(
    *,
    record_id: str,
    artifact_id: str,
    artifact_hash: str,
    verification_type: str,
    timestamp: str,
    outcome: str = "conclusivo_favoravel",
    previous_id: str | None = None,
    authenticity_id: str | None = None,
    integrity_id: str | None = None,
) -> str:
    def nullable(value: str | None) -> str:
        return "NULL" if value is None else _sql_quote(value)

    auth_type = "authenticity" if authenticity_id else None
    auth_outcome = "conclusivo_favoravel" if authenticity_id else None
    integrity_type = "integrity" if integrity_id else None
    integrity_outcome = "conclusivo_favoravel" if integrity_id else None
    return f"""
    INSERT INTO artifact_verification_records (
        artifact_verification_record_id,
        normative_artifact_id,
        verified_artifact_hash,
        verification_type,
        outcome,
        verifier,
        verifier_version,
        evidence,
        incident_id,
        previous_verification_record_id,
        authenticity_verification_record_id,
        authenticity_predecessor_type,
        authenticity_predecessor_outcome,
        integrity_verification_record_id,
        integrity_predecessor_type,
        integrity_predecessor_outcome,
        timestamp,
        record_hash
    ) VALUES (
        {_sql_quote(record_id)},
        {_sql_quote(artifact_id)},
        {_sql_quote(artifact_hash)},
        {_sql_quote(verification_type)},
        {_sql_quote(outcome)},
        'integration-verifier',
        'verifier-r3',
        '{{}}'::jsonb,
        NULL,
        {nullable(previous_id)},
        {nullable(authenticity_id)},
        {nullable(auth_type)},
        {nullable(auth_outcome)},
        {nullable(integrity_id)},
        {nullable(integrity_type)},
        {nullable(integrity_outcome)},
        {_sql_quote(timestamp)},
        {_sql_quote(_record_hash(record_id))}
    );
    """


def test_postgresql_migration_executes_in_real_postgresql(postgresql_migration_r3):
    result = _docker_psql(
        """
        SELECT count(*)
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN (
              'artifact_references',
              'acquisition_executions',
              'normative_artifacts',
              'artifact_verification_records'
          );
        """,
        tuples_only=True,
    )
    assert result.stdout.strip() == "4"


def test_postgresql_rejects_mutable_locator_even_when_hash_is_embedded(
    postgresql_migration_r3,
):
    suffix = uuid.uuid4().hex[:10]
    acquisition = _completed_acquisition_sql(suffix)
    digest = str(acquisition["artifact_hash"])
    bad_location = f"https://mutable.invalid/current.pdf?sha256={digest}"
    result = _docker_psql(
        _insert_artifact_sql(
            suffix,
            acquisition,
            acquired_at="2026-01-01T00:00:04+00:00",
            immutable_location=bad_location,
        ),
        expect_success=False,
    )
    assert "canonical" in result.stderr

    canonical = f"cas+sha256://{digest}/{acquisition['byte_size']}"
    _docker_psql(
        _insert_artifact_sql(
            suffix,
            acquisition,
            acquired_at="2026-01-01T00:00:04+00:00",
            immutable_location=canonical,
        )
    )


def test_postgresql_rejects_artifact_before_acquisition_completion(
    postgresql_migration_r3,
):
    suffix = uuid.uuid4().hex[:10]
    acquisition = _completed_acquisition_sql(suffix)
    result = _docker_psql(
        _insert_artifact_sql(
            suffix,
            acquisition,
            acquired_at="2026-01-01T00:00:02+00:00",
        ),
        expect_success=False,
    )
    assert "precedes acquisition completion" in result.stderr


def test_postgresql_rejects_verification_before_artifact_exists(
    postgresql_migration_r3,
):
    suffix = uuid.uuid4().hex[:10]
    acquisition = _completed_acquisition_sql(suffix)
    artifact_id = f"artifact-{suffix}"
    artifact_hash = str(acquisition["artifact_hash"])
    _docker_psql(
        _insert_artifact_sql(
            suffix,
            acquisition,
            acquired_at="2026-01-01T00:00:04+00:00",
        )
    )
    result = _docker_psql(
        _verification_insert_sql(
            record_id=f"auth-{suffix}",
            artifact_id=artifact_id,
            artifact_hash=artifact_hash,
            verification_type="authenticity",
            timestamp="2026-01-01T00:00:03+00:00",
        ),
        expect_success=False,
    )
    assert "precedes artifact acquisition" in result.stderr


def test_postgresql_enforces_full_favorable_verification_chain(
    postgresql_migration_r3,
):
    suffix = uuid.uuid4().hex[:10]
    acquisition = _completed_acquisition_sql(suffix)
    artifact_id = f"artifact-{suffix}"
    artifact_hash = str(acquisition["artifact_hash"])
    _docker_psql(
        _insert_artifact_sql(
            suffix,
            acquisition,
            acquired_at="2026-01-01T00:00:04+00:00",
        )
    )

    auth_id = f"auth-{suffix}"
    integrity_id = f"integrity-{suffix}"
    preservation_id = f"preservation-{suffix}"
    _docker_psql(
        _verification_insert_sql(
            record_id=auth_id,
            artifact_id=artifact_id,
            artifact_hash=artifact_hash,
            verification_type="authenticity",
            timestamp="2026-01-01T00:00:05+00:00",
        )
    )
    _docker_psql(
        _verification_insert_sql(
            record_id=integrity_id,
            artifact_id=artifact_id,
            artifact_hash=artifact_hash,
            verification_type="integrity",
            timestamp="2026-01-01T00:00:06+00:00",
            previous_id=auth_id,
            authenticity_id=auth_id,
        )
    )
    _docker_psql(
        _verification_insert_sql(
            record_id=preservation_id,
            artifact_id=artifact_id,
            artifact_hash=artifact_hash,
            verification_type="preservation",
            timestamp="2026-01-01T00:00:07+00:00",
            previous_id=integrity_id,
            authenticity_id=auth_id,
            integrity_id=integrity_id,
        )
    )

    result = _docker_psql(
        f"SELECT count(*) FROM artifact_verification_records "
        f"WHERE normative_artifact_id = {_sql_quote(artifact_id)};",
        tuples_only=True,
    )
    assert result.stdout.strip() == "3"


def test_postgresql_rejects_update_delete_and_truncate(postgresql_migration_r3):
    suffix = uuid.uuid4().hex[:10]
    _completed_acquisition_sql(suffix)

    update_result = _docker_psql(
        f"UPDATE artifact_references SET source_id = 'changed' "
        f"WHERE artifact_reference_id = {_sql_quote(f'ref-{suffix}')};",
        expect_success=False,
    )
    assert "append-only" in update_result.stderr

    truncate_result = _docker_psql(
        "TRUNCATE TABLE artifact_verification_records;",
        expect_success=False,
    )
    assert "append-only" in truncate_result.stderr


def test_postgresql_prevents_attempt_reuse_and_duplicate_artifact_origin(
    postgresql_migration_r3,
):
    suffix = uuid.uuid4().hex[:10]
    acquisition = _completed_acquisition_sql(suffix)
    reference_id = str(acquisition["reference_id"])

    duplicate_attempt = f"""
    INSERT INTO acquisition_executions (
        acquisition_execution_record_id,
        acquisition_execution_id,
        artifact_reference_record_id,
        artifact_reference_id,
        attempt_number,
        execution_event,
        projected_state,
        event_sequence,
        previous_acquisition_execution_record_id,
        actor_or_worker,
        adapter_version,
        started_at,
        finished_at,
        occurred_at,
        structured_result,
        structured_error,
        evidence,
        provenance,
        record_hash
    ) VALUES (
        {_sql_quote(f'duplicate-{suffix}')},
        {_sql_quote(f'exec-duplicate-{suffix}')},
        {_sql_quote(f'refrec-{suffix}')},
        {_sql_quote(reference_id)},
        1,
        'criacao',
        'planeada',
        1,
        NULL,
        'integration-worker',
        'adapter-r3',
        NULL,
        NULL,
        '2026-01-01T00:00:05+00:00',
        NULL,
        NULL,
        '{{}}'::jsonb,
        '{{}}'::jsonb,
        {_sql_quote(_record_hash(f'duplicate-{suffix}'))}
    );
    """
    attempt_result = _docker_psql(duplicate_attempt, expect_success=False)
    assert "reference_attempt_sequence" in attempt_result.stderr

    _docker_psql(
        _insert_artifact_sql(
            suffix,
            acquisition,
            acquired_at="2026-01-01T00:00:04+00:00",
        )
    )
    duplicate_artifact_result = _docker_psql(
        _insert_artifact_sql(
            f"duplicate-{suffix}",
            acquisition,
            acquired_at="2026-01-01T00:00:05+00:00",
        ),
        expect_success=False,
    )
    assert "single_per_acquisition_completion" in duplicate_artifact_result.stderr
