"""Commit 7 contract: atomic append-only ADR-020 activation foundation."""
from pathlib import Path
from types import SimpleNamespace
import re
import pytest
import sqlalchemy as sa
from sqlalchemy import event
import app.models as models

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations/versions/0024_adr020_activation_foundation.py"
ENTITIES = (models.PolicyActivationExecution, models.PolicyActivation, models.ActivationDecision, models.ActivationExecution, models.NormativeActivation, models.ActivationGeneration, models.OutboxEventRecord)

def cols(model): return set(model.__table__.columns.keys())
def checks(model): return " ".join(str(x.sqltext) for x in model.__table__.constraints if isinstance(x, sa.CheckConstraint)).lower()
def fks(model): return {x.name for x in model.__table__.constraints if isinstance(x, sa.ForeignKeyConstraint)}
def source(): return MIGRATION.read_text(encoding="utf-8")

def test_seven_exact_models_tables_and_no_automation_envelope_model():
    assert [x.__tablename__ for x in ENTITIES] == ["policy_activation_executions","policy_activations","activation_decisions","activation_executions","normative_activations","activation_generations","outbox_event_records"]
    assert not hasattr(models, "AutomationEnvelope")
    assert "automation_envelope" in checks(models.PolicyVersion)
    assert re.findall(r'op\.create_table\(\s*["\']([^"\']+)', source()) == [x.__tablename__ for x in ENTITIES]

def test_exact_policy_decision_bootstrap_and_delegation_bindings():
    assert {"fk_policy_activation_executions_exact_policy","fk_policy_activation_executions_exact_decision","fk_policy_activation_executions_exact_bootstrap","fk_policy_activation_executions_exact_authority_policy","fk_policy_activation_executions_exact_authority_activation","fk_policy_activation_executions_exact_envelope","fk_policy_activation_executions_exact_envelope_activation"} <= fks(models.PolicyActivationExecution)
    fields = cols(models.PolicyActivationExecution)
    assert {"policy_id","policy_version","policy_hash","policy_decision_id","bootstrap_authority_record_id","bootstrap_authority_record_hash","activation_authority_policy_id","activation_authority_policy_version","activation_authority_policy_hash","activation_authority_policy_activation_id","automation_envelope_id","automation_envelope_version","automation_envelope_hash","automation_envelope_activation_id"} <= fields

def decision(**kw):
    d=dict(activation_decision_id="d",decision_action="activate",decision_outcome="approved",authorization_class="constitucional_reservada",actor="a",institutional_role="autoridade_constitucional_final",target_scope={},scope_hash="a"*64,target_manifest=[{"review_outcome":"validada"}],target_manifest_hash="b"*64,authority_bindings={"bootstrap_authority_record_id":"ba","bootstrap_authority_record_hash":"a"*64},policy_bindings=[{"policy_type":"normative_continuity","policy_id":"nc","policy_version":1,"policy_hash":"b"*64,"policy_activation_id":"nca","policy_activation_record_hash":"c"*64},{"policy_type":"normative_precedence","policy_id":"np","policy_version":1,"policy_hash":"d"*64,"policy_activation_id":"npa","policy_activation_record_hash":"e"*64}],coverage_binding={"coverage_subject_type":"coverage_contract","coverage_contract_id":"cc","contract_version":1,"contract_hash":"f"*64,"coverage_contract_record_id":"ccr","coverage_contract_record_hash":"1"*64},continuity_binding={"continuity_subject_type":"normative_continuity","continuity_policy_id":"nc","continuity_policy_version":1,"continuity_policy_hash":"b"*64,"continuity_policy_activation_id":"nca","continuity_policy_activation_record_hash":"c"*64},precedence_binding={"precedence_subject_type":"normative_precedence","precedence_policy_id":"np","precedence_policy_version":1,"precedence_policy_hash":"d"*64,"precedence_policy_activation_id":"npa","precedence_policy_activation_record_hash":"e"*64},gates_evidence=[{"gate_id":"g","gate_version":1,"gate_hash":"2"*64,"gate_outcome":"approved","evidence_record_id":"er","evidence_record_hash":"3"*64}],rationale="r",evidence={},previous_activation_decision_id=None,idempotency_key="k",record_hash="c"*64); d.update(kw); return SimpleNamespace(**d)

def test_activation_decision_rejeita_bindings_vazios():
    with pytest.raises(ValueError):
        models._adr020_validate_activation_decision_insert(
            None,
            None,
            decision(
                authority_bindings={},
                policy_bindings=[],
                coverage_binding={},
                continuity_binding={},
                precedence_binding={},
                gates_evidence=[],
            ),
        )

def execution(**kw):
    d=dict(activation_execution_id="e",activation_decision_id="d",activation_decision_record_hash="a"*64,decision_outcome="approved",decision_action="activate",authorization_class="constitucional_reservada",execution_mode="manual",state="pending",scope_hash="b"*64,target_manifest_hash="c"*64,attempt_number=1,actor_or_worker="actor",lease_id="l",fencing_token=1,idempotency_key="k",authority_bindings={},policy_bindings=[],coverage_binding={},continuity_binding={},precedence_binding={},gates_evidence=[],started_at=None,finished_at=None,structured_result=None,structured_error=None,provenance={},record_hash="d"*64); d.update(kw); return SimpleNamespace(**d)

def test_approved_and_favorable_review_required_and_terminal_decisions_blocked():
    models._adr020_validate_activation_decision_insert(None,None,decision())
    with pytest.raises(ValueError,match="favorable"): models._adr020_validate_activation_decision_insert(None,None,decision(target_manifest=[{"review_outcome":"rejeitada"}]))
    for outcome in ("rejected","cancelled"):
        with pytest.raises(ValueError,match="cannot be executed"): models._adr020_validate_activation_execution_insert(None,None,execution(decision_outcome=outcome))

def policy_execution(**kw):
    d=dict(policy_activation_execution_id="p",policy_decision_id="pd",policy_type="activation_authority",policy_id="pi",policy_version=1,policy_hash="a"*64,authorization_basis_type="active_policy_chain",authorization_class="humana_delegada",execution_mode="manual",bootstrap_authority_record_id=None,bootstrap_authority_record_hash=None,activation_authority_policy_id="auth",activation_authority_policy_version=1,activation_authority_policy_hash="b"*64,activation_authority_policy_activation_id="pa",automation_envelope_id=None,automation_envelope_version=None,automation_envelope_hash=None,automation_envelope_activation_id=None,attempt_number=1,actor_or_worker="a",lease_id="l",fencing_token=1,idempotency_key="k",state="pendente",started_at=None,finished_at=None,structured_result=None,structured_error=None,provenance={},record_hash="c"*64); d.update(kw); return SimpleNamespace(**d)

def test_delegated_and_automatic_authority_fail_closed():
    with pytest.raises(ValueError,match="superior"): models._adr020_validate_policy_activation_execution_insert(None,None,policy_execution(activation_authority_policy_activation_id=None))
    with pytest.raises(ValueError,match="automation_envelope"): models._adr020_validate_policy_activation_execution_insert(None,None,policy_execution(execution_mode="automatico"))

def test_retry_new_identity_terminal_no_reopening_and_append_only():
    assert "idempotency" in " ".join(x.name or "" for x in models.ActivationExecution.__table__.constraints)
    for entity in ENTITIES:
        assert event.contains(entity,"before_update",models._adr020_reject_append_only_mutation)
        assert event.contains(entity,"before_delete",models._adr020_reject_append_only_mutation)
    with pytest.raises(RuntimeError,match="append-only"): models._adr020_reject_append_only_mutation(None,None,execution(state="completed"))

def test_generation_is_integral_content_addressed_and_normative_activation_insufficient():
    assert {"scope_descriptor","scope_hash","composition_manifest","composition_hash","policy_bindings","coverage_binding","continuity_binding","precedence_binding","gates_evidence","is_complete"} <= cols(models.ActivationGeneration)
    assert "is_complete" not in cols(models.NormativeActivation)
    g=SimpleNamespace(activation_decision_record_hash="a"*64,target_manifest_hash="b"*64,scope_hash="c"*64,composition_hash="d"*64,record_hash="e"*64,is_complete=False,composition_manifest=[],previous_activation_generation_id=None,previous_activation_generation_record_hash=None,authority_bindings={},policy_bindings=[],coverage_binding={},continuity_binding={},precedence_binding={},gates_evidence=[])
    with pytest.raises(ValueError,match="partial generation"): models._adr020_validate_activation_generation_insert(None,None,g)
    g.is_complete=True
    g.composition_manifest=[{"subject_hash":"f"*64}]
    models._adr020_validate_activation_generation_insert(None,None,g)

    g.previous_activation_generation_id="generation-0"
    with pytest.raises(ValueError,match="identity and hash"):
        models._adr020_validate_activation_generation_insert(None,None,g)

    g.previous_activation_generation_id=None
    g.previous_activation_generation_record_hash="f"*64
    with pytest.raises(ValueError,match="identity and hash"):
        models._adr020_validate_activation_generation_insert(None,None,g)

def test_outbox_exact_immutable_contract_has_no_delivery_state():
    required={"outbox_event_id","event_type","activation_execution_id","activation_generation_id","activation_decision_id","scope_hash","composition_hash","payload","payload_hash","provenance","created_at","record_hash"}
    assert cols(models.OutboxEventRecord) == required
    assert {"published","delivered","status"}.isdisjoint(required)

def test_atomicity_lineage_postgresql_jsonb_append_only_and_irreversible():
    s=source(); low=s.lower()
    assert 'revision: str = "0024_adr020_activation"' in s and 'down_revision: str = "0023_adr020_coverage"' in s
    for fragment in ("postgresql-only","jsonb","only approved decision is executable","partial generation forbidden","before update or delete","before truncate","activation_generations","outbox_event_records"): assert fragment in low
    assert "raise runtimeerror" in low and "irreversible" in low and "op.drop_table" not in low

def test_no_floating_resolution_delivery_or_commits_8_to_10():
    model_source=Path(models.__file__).read_text(encoding="utf-8"); combined=(source()+model_source[model_source.index("class PolicyActivationExecution"):]).lower()
    for forbidden in ("current_policy","latest_policy","newest_policy","published = column","delivered = column","dispatcher","scheduler","network"): assert forbidden not in combined
