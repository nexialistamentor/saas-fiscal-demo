"""Commit 5 contract: immutable ADR-020 policy authority foundation."""

from pathlib import Path
from types import SimpleNamespace
import re

import pytest
import sqlalchemy as sa
from sqlalchemy import event

import app.models as models


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "0022_adr020_policy_foundation.py"
POLICY_TYPES = {"activation_authority", "automation_envelope", "normative_precedence", "normative_continuity", "coverage_contract"}
DECISION_EVENTS = {"submetida", "auditoria_iniciada", "auditada_favoravelmente", "auditada_desfavoravelmente", "ratificada", "rejeitada", "cancelada"}


def _columns(model):
    return set(model.__table__.columns.keys())


def _checks(model):
    return " ".join(str(item.sqltext) for item in model.__table__.constraints if isinstance(item, sa.CheckConstraint)).lower()


def _source():
    return MIGRATION.read_text(encoding="utf-8")


def test_exact_models_and_tables_exist():
    assert models.PolicyVersion.__tablename__ == "policy_versions"
    assert models.PolicyDecision.__tablename__ == "policy_decisions"
    assert models.BootstrapAuthorityRecord.__tablename__ == "bootstrap_authority_records"


def test_policy_version_has_ratified_minimum_and_no_operational_state():
    fields = _columns(models.PolicyVersion)
    required = {"policy_type", "policy_id", "policy_version", "policy_hash", "domain", "scope", "declared_material_applicability", "modalities", "permitted_authorization_classes", "permitted_execution_modes", "gates", "roles", "segregation_of_duties", "limits", "rules", "exact_references", "origin_evidence", "created_at", "record_hash"}
    forbidden = {"state", "status", "audit_state", "ratification_state", "activation_state", "active", "current_version", "latest_version"}
    assert required <= fields
    assert forbidden.isdisjoint(fields)
    checks = _checks(models.PolicyVersion)
    assert all(value in checks for value in POLICY_TYPES)


def test_policy_identity_and_decision_exact_binding():
    unique_names = {item.name for item in models.PolicyVersion.__table__.constraints if isinstance(item, sa.UniqueConstraint)}
    assert {"uq_policy_versions_identity", "uq_policy_versions_exact_subject", "uq_policy_versions_policy_hash", "uq_policy_versions_record_hash"} <= unique_names
    foreign_keys = {item.name for item in models.PolicyDecision.__table__.constraints if isinstance(item, sa.ForeignKeyConstraint)}
    assert "fk_policy_decisions_exact_policy_version" in foreign_keys
    assert "fk_policy_decisions_previous_decision" in foreign_keys


def test_decision_vocabulary_is_closed_and_record_is_immutable():
    checks = _checks(models.PolicyDecision)
    assert all(value in checks for value in DECISION_EVENTS)
    assert all(value in checks for value in POLICY_TYPES)
    guard = models._adr020_reject_append_only_mutation
    for model in (models.PolicyVersion, models.PolicyDecision, models.BootstrapAuthorityRecord):
        assert event.contains(model, "before_update", guard)
        assert event.contains(model, "before_delete", guard)


def _decision(event_name, role, previous="previous", previous_event=None):
    return SimpleNamespace(decision_id="decision", decision_event=event_name, policy_type="activation_authority", policy_id="policy", policy_version=1, policy_hash="a" * 64, actor="actor", institutional_role=role, evidence={"exact": True}, rationale="express", previous_decision_id=previous, previous_decision_event=previous_event, idempotency_key="key", record_hash="b" * 64)


def test_ratification_without_audit_and_terminal_reopening_are_rejected():
    validator = models._adr020_validate_policy_decision_insert
    with pytest.raises(ValueError, match="predecessor audit chain"):
        validator(None, None, _decision("ratificada", "autoridade_constitucional_final", previous=None))
    with pytest.raises(ValueError, match="terminal"):
        validator(None, None, _decision("ratificada", "autoridade_constitucional_final", previous_event="rejeitada"))
    with pytest.raises(ValueError, match="terminal"):
        validator(None, None, _decision("ratificada", "autoridade_constitucional_final", previous_event="cancelada"))


def _bootstrap(**overrides):
    values = dict(policy_type="activation_authority", policy_id="policy", policy_version=1, policy_hash="a" * 64, domain="irpf", scope={"exact": True}, actor_proponente="proponent", actor_auditor="auditor", independent_audit_result="favoravel", constitutional_authority_declaration="express declaration", actor_ratificador="ratifier", segregation_evidence={"separate": True}, evidence={"exact": True}, validity="valida", submission_mode="manual", audit_mode="manual", ratification_mode="manual", activation_mode="manual", provenance={"exact": True}, record_hash="b" * 64)
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("field,value", [("submission_mode", "automatico"), ("audit_mode", "worker"), ("ratification_mode", "llm"), ("activation_mode", "scheduler")])
def test_bootstrap_is_exclusively_constitutional_and_manual(field, value):
    with pytest.raises(ValueError, match="manual"):
        models._adr020_validate_bootstrap_authority_insert(None, None, _bootstrap(**{field: value}))


def test_bootstrap_requires_favorable_audit_and_segregation():
    with pytest.raises(ValueError, match="favorable"):
        models._adr020_validate_bootstrap_authority_insert(None, None, _bootstrap(independent_audit_result="desfavoravel"))
    with pytest.raises(ValueError, match="segregation"):
        models._adr020_validate_bootstrap_authority_insert(None, None, _bootstrap(actor_auditor="proponent"))


def test_migration_lineage_scope_constraints_and_append_only():
    source = _source()
    lowered = source.lower()
    assert 'revision: str = "0022_adr020_policy"' in source
    assert 'down_revision: str = "0021_adr020_relation_foundation"' in source
    assert re.findall(r'op\.create_table\(\s*["\']([^"\']+)', source) == ["policy_versions", "policy_decisions", "bootstrap_authority_records"]
    for fragment in ("postgresql-only", "jsonb", "adr020_validate_policy_decision_chain", "ratification requires", "terminal decision cannot be reopened", "institutional segregation violation", "before update or delete", "before truncate", "manual", "activation_authority"):
        assert fragment in lowered
    assert "irreversible" in lowered and "raise runtimeerror" in lowered
    assert "op.drop_table" not in lowered


def test_no_implicit_authority_or_later_commit_entities():
    source = (_source() + Path(models.__file__).read_text(encoding="utf-8")).lower()
    assert "current_policy" not in source
    assert "latest_policy" not in source
    for entity in (
        "CalculationBundle",
        "CalculationExecutionRecord",
        "CalculationResultRecord",
        "ReplayExecutionRecord",
        "ReplayVerificationRecord",
    ):
        assert not hasattr(models, entity)
    assert not re.search(
        r"class\s+("
        r"CalculationBundle|CalculationExecutionRecord|"
        r"CalculationResultRecord|ReplayExecutionRecord|"
        r"ReplayVerificationRecord"
        r")\b",
        source,
        re.IGNORECASE,
    )
