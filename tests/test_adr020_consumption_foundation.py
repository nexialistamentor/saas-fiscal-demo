from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import models

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "0026_adr020_consumption_foundation.py"
ENTITIES = ("GenerationFenceRecord", "ConsumerContractVersion", "ConsumerApplicationRecord", "ReplicaCheckpointRecord")
TABLES = ("generation_fence_records", "consumer_contract_versions", "consumer_application_records", "replica_checkpoint_records")
H = "a" * 64


def test_four_exact_models_tables():
    assert tuple(getattr(models, name).__tablename__ for name in ENTITIES) == TABLES


def test_migration_lineage_postgresql_jsonb_guards_and_irreversibility():
    source = MIGRATION.read_text(encoding="utf-8")
    lowered = source.lower()
    assert 'revision = "0026_adr020_consumption"' in source
    assert 'down_revision = "0025_adr020_credentials"' in source
    assert source.count("op.create_table(") == 4
    for fragment in ("postgresql-only", "jsonb", "exact integral generation", "stale token", "partial application forbidden", "replica gap or divergence", "before update or delete", "before truncate", "irreversible"):
        assert fragment in lowered
    assert "op.drop_table" not in lowered


def _fence(**changes):
    values = dict(scope_hash=H, activation_generation_record_hash=H, activation_execution_record_hash=H, publisher_lease_record_hash=H, composition_hash=H, source_event_record_hash=H, record_hash=H, generation_sequence=1, fencing_token=1, previous_generation_fence_record_id=None, previous_generation_fence_record_hash=None, activation_generation_is_complete=True, activation_execution_state="completed", activation_execution_id="execution", activation_generation_execution_id="execution", activation_generation_scope_hash=H, activation_generation_composition_hash=H)
    values.update(changes); return SimpleNamespace(**values)


def test_generation_is_integral_exact_contiguous_fenced_and_unforked():
    models._adr020_validate_generation_fence_insert(None, None, _fence())
    with pytest.raises(ValueError, match="incomplete"):
        models._adr020_validate_generation_fence_insert(None, None, _fence(activation_generation_is_complete=False))
    with pytest.raises(ValueError, match="exactly 1"):
        models._adr020_validate_generation_fence_insert(None, None, _fence(generation_sequence=2))
    successor = _fence(generation_sequence=2, fencing_token=2, previous_generation_fence_record_id="f1", previous_generation_fence_record_hash=H, previous_generation_sequence=1, previous_fencing_token=1)
    models._adr020_validate_generation_fence_insert(None, None, successor)
    with pytest.raises(ValueError, match="stale"):
        models._adr020_validate_generation_fence_insert(None, None, _fence(**{**successor.__dict__, "fencing_token": 1}))
    uniques = [tuple(c.columns.keys()) for c in models.GenerationFenceRecord.__table__.constraints if c.__class__.__name__ == "UniqueConstraint"]
    assert ("previous_generation_fence_record_id",) in uniques


def _policy():
    return {"policy_type": "security", "policy_id": "p", "policy_version": 1, "policy_hash": H, "policy_activation_id": "a", "policy_activation_record_hash": H}


def test_contract_is_exact_content_addressed_scoped_and_non_authoritative():
    contract = SimpleNamespace(consumer_contract_hash=H, allowed_scope_hash=H, record_hash=H, consumer_contract_version=1, supported_protocol_version=1, supported_generation_schema_version=1, consumer_type="replica", allowed_scope_descriptor={}, compatibility_rules={"capabilities": [], "limits": {}, "invariants": []}, freshness_policy_binding=_policy(), security_policy_binding=_policy(), provenance={})
    models._adr020_validate_consumer_contract_insert(None, None, contract)
    contract.compatibility_rules = {"latest": True}
    with pytest.raises(ValueError, match="floating"):
        models._adr020_validate_consumer_contract_insert(None, None, contract)
    assert "authority" not in models.ConsumerContractVersion.__table__.columns


def _application(**changes):
    values = dict(consumer_contract_hash=H, scope_hash=H, generation_fence_record_hash=H, activation_generation_record_hash=H, composition_hash=H, record_hash=H, previous_replica_checkpoint_record_id=None, previous_replica_checkpoint_record_hash=None, duplicate_of_consumer_application_record_id=None, duplicate_of_consumer_application_record_hash=None, duplicate_of_replica_checkpoint_record_id=None, duplicate_of_replica_checkpoint_record_hash=None, attempt_number=1, generation_sequence=1, fencing_token=1, application_result="applied", finished_at=datetime.now(timezone.utc), structured_result={"application_complete": True}, consumer_id="c", replica_id="r", replica_instance_id="ri", consumer_contract_version=1, generation_fence_record_id="f", activation_generation_id="g", contract_allowed_scope_hash=H, fence_scope_hash=H, fence_generation_sequence=1, fence_fencing_token=1, fence_activation_generation_id="g", fence_activation_generation_record_hash=H, fence_composition_hash=H)
    values.update(changes); return SimpleNamespace(**values)


def test_application_is_atomic_exact_idempotent_and_retry_is_new_record():
    models._adr020_validate_consumer_application_insert(None, None, _application())
    with pytest.raises(ValueError, match="partial"):
        models._adr020_validate_consumer_application_insert(None, None, _application(structured_result={"application_complete": False}))
    with pytest.raises(ValueError, match="incompatible"):
        models._adr020_validate_consumer_application_insert(None, None, _application(fence_fencing_token=2))
    duplicate = _application(application_result="duplicate_exact", duplicate_of_consumer_application_record_id="old", duplicate_of_consumer_application_record_hash=H, duplicate_of_replica_checkpoint_record_id="cp", duplicate_of_replica_checkpoint_record_hash=H)
    models._adr020_validate_consumer_application_insert(None, None, duplicate)
    assert ("consumer_id", "replica_id", "replica_instance_id", "attempt_number") in [tuple(c.columns.keys()) for c in models.ConsumerApplicationRecord.__table__.constraints if c.__class__.__name__ == "UniqueConstraint"]


def test_replica_checkpoint_requires_exact_integral_application_and_continuity():
    values = {**_application().__dict__, "consumer_application_record_hash": H, "consumer_application_result": "applied", "consumer_application_complete": True, "previous_replica_checkpoint_record_id": None, "previous_replica_checkpoint_record_hash": None}
    models._adr020_validate_replica_checkpoint_insert(None, None, SimpleNamespace(**values))
    with pytest.raises(ValueError, match="integral applied"):
        models._adr020_validate_replica_checkpoint_insert(None, None, SimpleNamespace(**{**values, "consumer_application_result": "failed"}))
    with pytest.raises(ValueError, match="sequence 1"):
        models._adr020_validate_replica_checkpoint_insert(None, None, SimpleNamespace(**{**values, "generation_sequence": 2, "application_generation_sequence": 2}))
    assert "authority" not in models.ReplicaCheckpointRecord.__table__.columns
    assert "activates_content" not in models.ReplicaCheckpointRecord.__table__.columns


def test_append_only_and_no_mutable_or_operational_resolution():
    for entity in ENTITIES:
        with pytest.raises(RuntimeError, match="append-only"):
            models._adr020_reject_append_only_mutation(None, None, getattr(models, entity)())
    source = (MIGRATION.read_text(encoding="utf-8") + Path(models.__file__).read_text(encoding="utf-8")).lower()
    for forbidden in ("current_generation", "latest_generation", "newest_generation", "requests.get", "httpx", "scheduler", "worker endpoint"):
        assert forbidden not in source
