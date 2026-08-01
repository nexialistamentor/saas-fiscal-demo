import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, event

from app import models


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "migrations"
    / "versions"
    / "0019_adr020_extraction_foundation.py"
)


def _literal_assignment(tree: ast.Module, name: str):
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            return ast.literal_eval(node.value)
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"Assignment {name!r} not found")


def _sha(character: str) -> str:
    return character * 64


def _check_sql(table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )


def _constraint_names(table, constraint_type) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, constraint_type) and constraint.name
    }


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


def _run(**overrides):
    payload = dict(
        extraction_run_record_id="run-record-1",
        extraction_run_id="run-1",
        normative_artifact_id="artifact-1",
        artifact_hash=_sha("a"),
        extractor_id="extractor",
        extractor_version="1",
        parameters_hash=_sha("b"),
        attempt_number=1,
        run_event="criacao",
        projected_state="pendente",
        event_sequence=1,
        previous_extraction_run_record_id=None,
        authenticity_verification_record_id=None,
        authenticity_predecessor_type=None,
        authenticity_predecessor_outcome=None,
        integrity_verification_record_id=None,
        integrity_predecessor_type=None,
        integrity_predecessor_outcome=None,
        preservation_verification_record_id=None,
        preservation_predecessor_type=None,
        preservation_predecessor_outcome=None,
        started_at=None,
        finished_at=None,
        occurred_at=datetime.now(timezone.utc),
        structured_error=None,
        evidence={},
        provenance={},
        record_hash=_sha("c"),
    )
    payload.update(overrides)
    return models.ExtractionRun(**payload)


def _result(**overrides):
    payload = dict(
        extraction_result_id="result-1",
        extraction_run_record_id="run-record-3",
        extraction_run_id="run-1",
        normative_artifact_id="artifact-1",
        artifact_hash=_sha("a"),
        extractor_id="extractor",
        extractor_version="1",
        parameters_hash=_sha("b"),
        attempt_number=1,
        run_event="conclusao",
        run_state="concluida",
        outcome="conclusivo",
        structured_content={"content": "produced"},
        evidence={},
        created_at=datetime.now(timezone.utc),
        record_hash=_sha("d"),
    )
    payload.update(overrides)
    return models.ExtractionResult(**payload)


def test_commit_2_exposes_exact_extraction_models():
    assert models.ExtractionRun.__tablename__ == "extraction_runs"
    assert models.ExtractionResult.__tablename__ == "extraction_results"


def test_extraction_run_contains_identity_projection_and_gate_columns():
    columns = set(models.ExtractionRun.__table__.columns.keys())
    assert {
        "extraction_run_record_id",
        "extraction_run_id",
        "normative_artifact_id",
        "artifact_hash",
        "extractor_id",
        "extractor_version",
        "parameters_hash",
        "attempt_number",
        "run_event",
        "projected_state",
        "event_sequence",
        "previous_extraction_run_record_id",
        "authenticity_verification_record_id",
        "integrity_verification_record_id",
        "preservation_verification_record_id",
        "started_at",
        "finished_at",
        "structured_error",
        "evidence",
        "provenance",
        "record_hash",
    } <= columns


def test_extraction_run_has_its_own_state_machine():
    checks = _check_sql(models.ExtractionRun.__table__)
    for state in (
        "pendente",
        "em_processamento",
        "concluida",
        "falhada",
        "cancelada",
    ):
        assert state in checks
    assert "inconclusiva" not in checks
    assert "run_event = 'criacao'" in checks
    assert "projected_state = 'pendente'" in checks


def test_extraction_run_binds_all_three_favorable_verification_gates():
    pairs = _foreign_key_pairs(models.ExtractionRun.__table__)
    for prefix, expected_type in (
        ("authenticity", "authenticity"),
        ("integrity", "integrity"),
        ("preservation", "preservation"),
    ):
        assert any(
            pair[0][0] == f"{prefix}_verification_record_id"
            and pair[0][1].endswith(
                "artifact_verification_record_id"
            )
            and ("normative_artifact_id", "artifact_verification_records.normative_artifact_id")
            in pair
            and ("artifact_hash", "artifact_verification_records.verified_artifact_hash")
            in pair
            and (
                f"{prefix}_predecessor_type",
                "artifact_verification_records.verification_type",
            )
            in pair
            and (
                f"{prefix}_predecessor_outcome",
                "artifact_verification_records.outcome",
            )
            in pair
            for pair in pairs
        )
        checks = _check_sql(models.ExtractionRun.__table__)
        assert expected_type in checks
    assert "conclusivo_favoravel" in _check_sql(
        models.ExtractionRun.__table__
    )


def test_retry_identity_and_event_sequence_are_unique():
    names = _constraint_names(
        models.ExtractionRun.__table__,
        UniqueConstraint,
    )
    assert "uq_extraction_runs_identity_sequence" in names
    assert "uq_extraction_runs_exact_attempt_sequence" in names


def test_extraction_run_validator_rejects_result_state_as_execution_state():
    target = _run(
        run_event="conclusao",
        projected_state="inconclusiva",
    )
    with pytest.raises(ValueError, match="event/state"):
        models._adr020_validate_extraction_run_insert(
            None,
            None,
            target,
        )


def test_processing_requires_started_at_and_all_favorable_gates():
    target = _run(
        run_event="inicio",
        projected_state="em_processamento",
        event_sequence=2,
        previous_extraction_run_record_id="run-record-1",
        started_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValueError, match="favorable verification gates"):
        models._adr020_validate_extraction_run_insert(
            None,
            None,
            target,
        )


def test_failed_run_requires_structured_error():
    target = _run(
        run_event="falha",
        projected_state="falhada",
        event_sequence=3,
        previous_extraction_run_record_id="run-record-2",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        authenticity_verification_record_id="auth-1",
        authenticity_predecessor_type="authenticity",
        authenticity_predecessor_outcome="conclusivo_favoravel",
        integrity_verification_record_id="integrity-1",
        integrity_predecessor_type="integrity",
        integrity_predecessor_outcome="conclusivo_favoravel",
        preservation_verification_record_id="preservation-1",
        preservation_predecessor_type="preservation",
        preservation_predecessor_outcome="conclusivo_favoravel",
    )
    with pytest.raises(ValueError, match="structured_error"):
        models._adr020_validate_extraction_run_insert(
            None,
            None,
            target,
        )


def test_extraction_result_is_immutable_content_not_execution_state():
    columns = set(models.ExtractionResult.__table__.columns.keys())
    assert {
        "extraction_result_id",
        "extraction_run_record_id",
        "extraction_run_id",
        "normative_artifact_id",
        "artifact_hash",
        "extractor_id",
        "extractor_version",
        "parameters_hash",
        "attempt_number",
        "outcome",
        "structured_content",
        "evidence",
        "created_at",
        "record_hash",
    } <= columns
    assert not (
        {
            "projected_state",
            "status",
            "activation_state",
            "active",
            "updated_at",
        }
        & columns
    )


def test_extraction_result_has_only_ratified_outcomes():
    checks = _check_sql(models.ExtractionResult.__table__)
    assert "conclusivo" in checks
    assert "inconclusivo" in checks
    assert "rejeitado" in checks


def test_result_requires_exact_concluded_run():
    result = _result(run_state="falhada")
    with pytest.raises(ValueError, match="concluded extraction run"):
        models._adr020_validate_extraction_result_insert(
            None,
            None,
            result,
        )


def test_result_cannot_simulate_empty_production():
    result = _result(structured_content={})
    with pytest.raises(ValueError, match="effective structured_content"):
        models._adr020_validate_extraction_result_insert(
            None,
            None,
            result,
        )


def test_commit_2_models_are_append_only_and_have_insert_validators():
    listener = models._adr020_reject_append_only_mutation
    for model in (models.ExtractionRun, models.ExtractionResult):
        assert event.contains(model, "before_update", listener)
        assert event.contains(model, "before_delete", listener)
        assert model in models._ADR020_INSERT_VALIDATORS
        assert event.contains(
            model,
            "before_insert",
            models._ADR020_INSERT_VALIDATORS[model],
        )

def test_migration_0019_identity_lineage_and_exact_two_tables():
    assert MIGRATION_PATH.is_file()

    source = MIGRATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    revision = _literal_assignment(tree, "revision")
    assert revision == "0019_adr020_extraction"
    assert len(revision) <= 32
    assert (
        _literal_assignment(tree, "down_revision")
        == "0018_adr020_acq_foundation"
    )

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
        "extraction_runs",
        "extraction_results",
    }


def test_migration_0019_persists_extraction_state_machine():
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "adr020_validate_extraction_run_event" in source
    assert "forbidden ExtractionRun transition" in source
    assert "event_sequence <> previous_row.event_sequence + 1" in source
    assert "previous_row.projected_state = 'pendente'" in source
    assert "previous_row.projected_state = 'em_processamento'" in source
    assert "em_processamento" in source
    assert "concluida" in source
    assert "falhada" in source
    assert "cancelada" in source


def test_migration_0019_requires_exact_favorable_verification_gates():
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "fk_extraction_runs_authenticity_favorable" in source
    assert "fk_extraction_runs_integrity_favorable" in source
    assert "fk_extraction_runs_preservation_favorable" in source
    assert "verification_type = 'authenticity'" in source
    assert "verification_type = 'integrity'" in source
    assert "verification_type = 'preservation'" in source
    assert "outcome = 'conclusivo_favoravel'" in source
    assert "favorable verification gates" in source


def test_migration_0019_result_requires_effective_concluded_run():
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "fk_extraction_results_concluded_run" in source
    assert "run_event = 'conclusao'" in source
    assert "run_state = 'concluida'" in source
    assert "effective structured_content" in source
    assert "single_per_run_completion" in source


def test_migration_0019_is_postgresql_only_append_only_and_irreversible():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "PostgreSQL-only" in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "BEFORE TRUNCATE" in source
    assert "for table_name in _APPEND_ONLY_TABLES" in source

    downgrade_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "downgrade"
    )
    downgrade_source = ast.get_source_segment(source, downgrade_node)

    assert "irreversible" in downgrade_source
    assert "raise RuntimeError" in downgrade_source
    assert "drop_table" not in downgrade_source
    assert "TRUNCATE" not in downgrade_source
