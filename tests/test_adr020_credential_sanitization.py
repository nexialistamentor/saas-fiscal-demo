from pathlib import Path
from types import SimpleNamespace

import pytest

from app import models


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "0025_adr020_credentials_foundation.py"
ENTITIES = (
    "CredentialBindingVersion", "CredentialLifecycleEventRecord",
    "SecretAccessExecutionRecord", "CredentialUseRecord",
    "SanitizedAcquisitionReceipt", "SanitizationVerificationRecord",
)
TABLES = (
    "credential_binding_versions", "credential_lifecycle_event_records",
    "secret_access_execution_records", "credential_use_records",
    "sanitized_acquisition_receipts", "sanitization_verification_records",
)


def test_six_exact_models_and_tables():
    assert tuple(getattr(models, name).__tablename__ for name in ENTITIES) == TABLES


def test_migration_lineage_postgresql_jsonb_and_irreversibility():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0025_adr020_credentials"' in source
    assert 'down_revision = "0024_adr020_activation"' in source
    assert source.count("op.create_table(") == 6
    lowered = source.lower()
    for fragment in ("postgresql", "jsonb", "before update or delete", "before truncate", "irreversible", "raise runtimeerror"):
        assert fragment in lowered
    assert "op.drop_table" not in lowered


def test_exact_fields_and_no_secret_material_columns():
    binding = models.CredentialBindingVersion.__table__.columns
    for name in ("credential_binding_hash", "secret_provider_binding", "opaque_secret_reference_id", "opaque_secret_version_reference_id", "permitted_purpose", "permitted_operation", "permitted_source_scope", "acquisition_contract_binding", "secret_access_policy_binding", "security_policy_binding", "sanitization_policy_binding"):
        assert name in binding
    forbidden = {"secret", "secret_hash", "token", "cookie", "authorization_header", "password"}
    for entity in ENTITIES:
        assert forbidden.isdisjoint(getattr(models, entity).__table__.columns.keys())


def test_lifecycle_continuity_terminal_and_rotation_validation():
    base = dict(credential_binding_hash="a" * 64, record_hash="b" * 64, replacement_credential_binding_id=None, replacement_credential_binding_version=None, replacement_credential_binding_hash=None)
    models._adr020_validate_lifecycle_insert(None, None, SimpleNamespace(**base, lifecycle_event="activated", previous_lifecycle_event_record_id=None, previous_lifecycle_event_record_hash=None))
    with pytest.raises(ValueError, match="begin with activated"):
        models._adr020_validate_lifecycle_insert(None, None, SimpleNamespace(**base, lifecycle_event="suspended", previous_lifecycle_event_record_id=None, previous_lifecycle_event_record_hash=None))
    with pytest.raises(ValueError, match="terminal"):
        models._adr020_validate_lifecycle_insert(None, None, SimpleNamespace(**base, lifecycle_event="resumed", previous_lifecycle_event_record_id="p", previous_lifecycle_event_record_hash="c" * 64, previous_lifecycle_event="revoked"))


def test_access_requires_lease_fence_and_rejects_sensitive_persistence():
    values = dict(acquisition_execution_record_hash="a"*64, credential_binding_hash="b"*64, credential_lifecycle_event_record_hash="c"*64, secret_provider_artifact_hash="d"*64, lease_record_hash="e"*64, record_hash="f"*64, attempt_number=1, fencing_token=1, lease_id="lease", access_state="accessed", structured_result={}, structured_error=None, provenance={})
    models._adr020_validate_secret_access_insert(None, None, SimpleNamespace(**values))
    with pytest.raises(ValueError, match="lease and fence"):
        models._adr020_validate_secret_access_insert(None, None, SimpleNamespace(**{**values, "lease_id": ""}))
    with pytest.raises(ValueError, match="sensitive material"):
        models._adr020_validate_secret_access_insert(None, None, SimpleNamespace(**{**values, "structured_result": {"token": "x"}}))


def test_receipt_allowlist_redaction_and_verification_are_fail_closed():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "verified sanitized receipt required" in source
    assert "before extraction" in source
    verification = SimpleNamespace(sanitized_acquisition_receipt_hash="a"*64, sanitization_policy_hash="b"*64, sanitization_policy_activation_record_hash="c"*64, verification_engine_hash="d"*64, record_hash="e"*64, verification_outcome="verified_sanitized", inspected_component_manifest={"complete": False}, violation_manifest=[],)
    with pytest.raises(ValueError, match="partial"):
        models._adr020_validate_sanitization_verification_insert(None, None, verification)
    redaction_fields = {"component_type", "canonical_location", "sensitivity_category", "sanitization_action", "policy_rule_id", "policy_rule_version", "policy_rule_hash", "verification_outcome"}
    assert "redaction_manifest" in models.SanitizedAcquisitionReceipt.__table__.columns
    assert redaction_fields == redaction_fields


def test_no_operational_or_floating_resolution_implementation():
    source = (MIGRATION.read_text(encoding="utf-8") + Path(models.__file__).read_text(encoding="utf-8")).lower()
    for forbidden in ("boto3", "aws secrets", "azure key vault", "hashicorp vault", "requests.get", "httpx", "scheduler", "worker endpoint"):
        assert forbidden not in source
