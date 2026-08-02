from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import models

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "0027_adr020_calculation_replay.py"
H = "a" * 64
ENTITIES = ("CalculationBundle", "CalculationExecutionRecord", "CalculationResultRecord", "ReplayExecutionRecord", "ReplayVerificationRecord")
TABLES = ("calculation_bundles", "calculation_execution_records", "calculation_result_records", "replay_execution_records", "replay_verification_records")


def test_five_exact_models_tables_and_lineage():
    assert tuple(getattr(models, name).__tablename__ for name in ENTITIES) == TABLES
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0027_adr020_calc_replay"' in source
    assert 'down_revision = "0026_adr020_consumption"' in source
    assert source.count("op.create_table(") == 5
    lowered = source.lower()
    for fragment in ("postgresql-only", "jsonb", "before update or delete", "before truncate", "partial verification cannot be match", "irreversible"):
        assert fragment in lowered
    assert "op.drop_table" not in lowered


def _input():
    return {"input_type": "declaration", "input_id": "i", "input_record_hash": H, "input_payload_hash": H, "canonicalization_contract_id": "c", "canonicalization_contract_version": 1, "canonicalization_contract_hash": H, "immutable_content_reference": "cas:a", "immutable_content_hash": H}


def _runtime():
    return {"runtime_artifact_id": "r", "runtime_artifact_version": "1", "runtime_artifact_hash": H, "dependency_manifest": [{"dependency_id": "d", "dependency_version": "1", "dependency_hash": H}], "dependency_manifest_hash": H, "platform_contract_id": "p", "platform_contract_version": 1, "platform_contract_hash": H}


def _bundle(**changes):
    values = dict(calculation_bundle_schema_version=1, calculation_bundle_hash=H, scope_hash=H, generation_fence_record_hash=H, generation_sequence=1, fencing_token=1, activation_generation_id="g", activation_generation_record_hash=H, composition_hash=H, consumer_contract_hash=H, consumer_application_record_hash=H, replica_checkpoint_record_hash=H, calculation_subject_reference={"subject_type": "taxpayer", "subject_id": "s", "subject_record_hash": H, "subject_payload_hash": H}, input_snapshot_manifest=[_input()], normative_member_manifest=[], policy_binding_manifest=[], coverage_binding={}, continuity_binding={}, precedence_binding={}, gates_evidence={}, engine_binding={"engine_artifact_id": "e", "engine_artifact_hash": H}, runtime_binding=_runtime(), canonical_serialization_binding={"contract_id": "s", "version": 1, "hash": H}, evaluation_instant=datetime(2026, 1, 1, tzinfo=timezone.utc), deterministic_seed_binding={"algorithm": "none", "seed": "not_applicable"}, provenance={}, record_hash=H, consumer_application_record_id="a", replica_checkpoint_record_id="r")
    values.update(changes); return SimpleNamespace(**values)


def test_bundle_is_content_addressed_exact_and_fail_closed():
    models._adr020_validate_calculation_bundle_insert(None, None, _bundle())
    for change, message in (({"fence_generation_sequence": 2}, "divergent"), ({"activation_generation_is_complete": False}, "integral"), ({"consumer_application_result": "pending"}, "terminal"), ({"input_snapshot_manifest": []}, "inputs")):
        with pytest.raises(ValueError, match=message): models._adr020_validate_calculation_bundle_insert(None, None, _bundle(**change))
    for value, message in (({"latest": True}, "floating"), ({"url": "https://example.invalid"}, "external transport"), ({"clock": "datetime.now()"}, "clock"), ({"Authorization": "x"}, "sensitive")):
        with pytest.raises(ValueError, match=message): models._adr020_validate_calculation_bundle_insert(None, None, _bundle(gates_evidence=value))


def _execution(**changes):
    values = dict(calculation_bundle_hash=H, engine_artifact_hash=H, runtime_artifact_hash=H, record_hash=H, attempt_number=1, fencing_token=1, state="completed", finished_at=datetime.now(timezone.utc), structured_result={"calculation_complete": True}, structured_error=None, provenance={})
    values.update(changes); return SimpleNamespace(**values)


def test_execution_exact_terminal_retry_and_partial_blocked():
    models._adr020_validate_calculation_execution_insert(None, None, _execution())
    with pytest.raises(ValueError, match="exact bundle"): models._adr020_validate_calculation_execution_insert(None, None, _execution(exact_bundle_hash="b" * 64))
    with pytest.raises(ValueError, match="partial"): models._adr020_validate_calculation_execution_insert(None, None, _execution(structured_result={"calculation_complete": False}))
    assert ("calculation_bundle_id", "attempt_number") in [tuple(c.columns.keys()) for c in models.CalculationExecutionRecord.__table__.constraints if c.__class__.__name__ == "UniqueConstraint"]


def _result(**changes):
    values = dict(calculation_execution_record_hash=H, calculation_bundle_id="b", calculation_bundle_hash=H, result_payload_hash=H, calculation_trace_hash=H, decision_trace_hash=H, canonical_result_hash=H, record_hash=H, result_schema_version=1, result_payload_reference={}, calculation_trace_reference={}, decision_trace_reference={}, provenance={})
    values.update(changes); return SimpleNamespace(**values)


def test_result_requires_completed_exact_atomic_execution():
    models._adr020_validate_calculation_result_insert(None, None, _result())
    with pytest.raises(ValueError, match="completed"): models._adr020_validate_calculation_result_insert(None, None, _result(calculation_execution_state="running"))
    with pytest.raises(ValueError, match="partial"): models._adr020_validate_calculation_result_insert(None, None, _result(calculation_complete=False))


def _replay(**changes):
    values = dict(calculation_bundle_hash=H, original_calculation_execution_record_hash=H, original_calculation_result_record_hash=H, original_canonical_result_hash=H, replay_engine_artifact_hash=H, replay_runtime_artifact_hash=H, replay_dependency_manifest_hash=H, replay_platform_contract_hash=H, replay_canonical_serialization_contract_hash=H, replay_deterministic_seed_binding_hash=H, record_hash=H, attempt_number=1, state="completed", finished_at=datetime.now(timezone.utc), replay_result_payload_hash=H, replay_calculation_trace_hash=H, replay_decision_trace_hash=H, replay_canonical_result_hash=H, replay_evaluation_instant=datetime(2026, 1, 1, tzinfo=timezone.utc), structured_result={}, structured_error=None, provenance={})
    values.update(changes); return SimpleNamespace(**values)


def test_replay_uses_original_state_and_retry_is_new_record():
    models._adr020_validate_replay_execution_insert(None, None, _replay())
    with pytest.raises(ValueError, match="original"): models._adr020_validate_replay_execution_insert(None, None, _replay(original_bundle_hash="b" * 64))
    with pytest.raises(ValueError, match="current state"): models._adr020_validate_replay_execution_insert(None, None, _replay(structured_result={"current": True}))
    assert ("original_calculation_result_record_id", "attempt_number") in [tuple(c.columns.keys()) for c in models.ReplayExecutionRecord.__table__.constraints if c.__class__.__name__ == "UniqueConstraint"]


def _verification(**changes):
    values = dict(replay_execution_record_hash=H, calculation_bundle_hash=H, original_calculation_result_record_hash=H, original_canonical_result_hash=H, replay_canonical_result_hash=H, record_hash=H, result_payload_match=True, calculation_trace_match=True, decision_trace_match=True, verification_outcome="match", mismatch_manifest=[], provenance={})
    values.update(changes); return SimpleNamespace(**values)


def test_verification_closed_outcomes_and_evidence():
    models._adr020_validate_replay_verification_insert(None, None, _verification())
    with pytest.raises(ValueError, match="partial"): models._adr020_validate_replay_verification_insert(None, None, _verification(result_payload_match=False))
    models._adr020_validate_replay_verification_insert(None, None, _verification(verification_outcome="mismatch", replay_canonical_result_hash="b" * 64, mismatch_manifest=[{"component_type": "payload", "evidence_hash": H}]))
    models._adr020_validate_replay_verification_insert(None, None, _verification(verification_outcome="inconclusive", replay_canonical_result_hash=None, mismatch_manifest=[{"evidence": "unavailable"}]))


def test_append_only_and_no_operational_surface():
    for entity in ENTITIES:
        with pytest.raises(RuntimeError, match="append-only"): models._adr020_reject_append_only_mutation(None, None, getattr(models, entity)())
    source = (MIGRATION.read_text(encoding="utf-8") + Path(models.__file__).read_text(encoding="utf-8")).lower()
    for forbidden in ("requests.get", "httpx.", "def endpoint", "def worker", "def scheduler", "execute_calculation", "execute_replay"):
        assert forbidden not in source
