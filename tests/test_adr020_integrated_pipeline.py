"""Commit 11: integrated contractual proof of the sovereign ADR-020 pipeline."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import models


ROOT = Path(__file__).resolve().parents[1]
AT = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


def h(label: str) -> str:
    import hashlib

    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def ns(**values):
    return SimpleNamespace(**values)


def exact_policy(label: str) -> dict:
    return {
        "policy_type": label,
        "policy_id": f"policy-{label}",
        "policy_version": 1,
        "policy_hash": h(f"policy-{label}"),
        "policy_activation_id": f"policy-activation-{label}",
        "policy_activation_record_hash": h(f"policy-activation-{label}"),
    }


def sovereign_chain():
    artifact_bytes = b"ADR-020 sovereign normative artifact"
    import hashlib

    artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()
    acquisition_hash = h("acquisition-completed")
    acquisition = ns(
        acquisition_execution_record_id="acquisition-record-3",
        acquisition_execution_id="acquisition-1",
        artifact_reference_record_id="reference-record-1",
        artifact_reference_id="reference-1",
        attempt_number=1,
        execution_event="conclusao",
        projected_state="concluida",
        event_sequence=3,
        previous_acquisition_execution_record_id="acquisition-record-2",
        actor_or_worker="bounded-adapter",
        adapter_version="adapter-1.0.0",
        started_at=AT,
        finished_at=AT,
        structured_result={
            "bytes_received": True,
            "byte_size": len(artifact_bytes),
            "artifact_hash": artifact_hash,
        },
        evidence={},
        provenance={},
        record_hash=acquisition_hash,
    )
    models._adr020_validate_acquisition_execution_insert(None, None, acquisition)

    artifact = ns(
        acquisition_execution_record_id=acquisition.acquisition_execution_record_id,
        acquisition_execution_id=acquisition.acquisition_execution_id,
        acquisition_attempt_number=acquisition.attempt_number,
        acquisition_event=acquisition.execution_event,
        acquisition_state=acquisition.projected_state,
        immutable_bytes=artifact_bytes,
        immutable_location=None,
        byte_size=len(artifact_bytes),
        artifact_hash=artifact_hash,
        record_hash=h("artifact-record"),
    )
    models._adr020_validate_normative_artifact_insert(None, None, artifact)

    receipt = ns(
        sanitized_acquisition_receipt_hash=h("receipt"),
        acquired_content_hash=artifact_hash,
        acquisition_execution_record_hash=acquisition.record_hash,
        credential_use_record_hash=h("credential-use"),
        credential_binding_hash=h("credential-binding"),
        request_contract_hash=h("request-contract"),
        sanitized_request_fingerprint=h("request-fingerprint"),
        sanitized_request_canonicalization_contract_hash=h("request-canonicalization"),
        sanitized_request_manifest={
            "method": "GET",
            "source_identity": "source-001",
            "path": "/normative/artifact",
            "parameter_names": [],
            "parameter_types": {},
            "sanitized_payload_hash": h("sanitized-payload"),
            "request_contract_version": 1,
        },
        sanitized_response_metadata={"media_type": "application/pdf"},
        transport_evidence_manifest=[],
        redaction_manifest=[],
        provenance={},
        record_hash=h("receipt-record"),
    )
    models._adr020_validate_receipt_insert(None, None, receipt)
    sanitization = ns(
        sanitized_acquisition_receipt_hash=receipt.sanitized_acquisition_receipt_hash,
        sanitization_policy_hash=h("sanitization-policy"),
        sanitization_policy_activation_record_hash=h("sanitization-activation"),
        verification_engine_hash=h("sanitization-engine"),
        record_hash=h("sanitization-verification"),
        verification_outcome="verified_sanitized",
        inspected_component_manifest={"complete": True},
        violation_manifest=[],
    )
    models._adr020_validate_sanitization_verification_insert(None, None, sanitization)

    gate_ids = {
        "authenticity": "verification-authenticity",
        "integrity": "verification-integrity",
        "preservation": "verification-preservation",
    }
    extraction = ns(
        extraction_run_record_id="extraction-record-3",
        extraction_run_id="extraction-1",
        normative_artifact_id="artifact-1",
        artifact_hash=artifact.artifact_hash,
        extractor_id="extractor",
        extractor_version="1.0.0",
        parameters_hash=h("parameters"),
        attempt_number=1,
        run_event="conclusao",
        projected_state="concluida",
        event_sequence=3,
        previous_extraction_run_record_id="extraction-record-2",
        authenticity_verification_record_id=gate_ids["authenticity"],
        authenticity_predecessor_type="authenticity",
        authenticity_predecessor_outcome="conclusivo_favoravel",
        integrity_verification_record_id=gate_ids["integrity"],
        integrity_predecessor_type="integrity",
        integrity_predecessor_outcome="conclusivo_favoravel",
        preservation_verification_record_id=gate_ids["preservation"],
        preservation_predecessor_type="preservation",
        preservation_predecessor_outcome="conclusivo_favoravel",
        started_at=AT,
        finished_at=AT,
        occurred_at=AT,
        structured_error=None,
        evidence={"sanitized_receipt_hash": receipt.sanitized_acquisition_receipt_hash},
        provenance={},
        record_hash=h("extraction-run"),
    )
    models._adr020_validate_extraction_run_insert(None, None, extraction)
    extraction_result = ns(
        extraction_run_record_id=extraction.extraction_run_record_id,
        extraction_run_id=extraction.extraction_run_id,
        normative_artifact_id=extraction.normative_artifact_id,
        artifact_hash=extraction.artifact_hash,
        extractor_id=extraction.extractor_id,
        extractor_version=extraction.extractor_version,
        parameters_hash=extraction.parameters_hash,
        attempt_number=extraction.attempt_number,
        run_event=extraction.run_event,
        run_state=extraction.projected_state,
        outcome="conclusivo",
        structured_content={"rules": [{"id": "rule-1"}]},
        evidence={},
        record_hash=h("extraction-result"),
    )
    models._adr020_validate_extraction_result_insert(None, None, extraction_result)

    review = ns(
        subject_id="rule-1",
        subject_version=1,
        subject_hash=h("rule-1-v1"),
        reviewer="independent-reviewer",
        review_event="revisao_concluida",
        outcome="validada",
        evidence={"extraction_result_record_hash": extraction_result.record_hash},
        record_hash=h("rule-review"),
    )
    models._adr020_validate_rule_review_insert(None, None, review)
    decision = ns(
        scope_hash=h("scope"),
        target_manifest_hash=h("target-manifest"),
        record_hash=h("activation-decision"),
        decision_action="activate",
        decision_outcome="approved",
        authority_bindings={
            "bootstrap_authority_record_id": "fixture-bootstrap-authority",
            "bootstrap_authority_record_hash": h("fixture-bootstrap-authority"),
        },
        policy_bindings=[
            exact_policy("normative_continuity"),
            exact_policy("normative_precedence"),
        ],
        coverage_binding={
            "coverage_subject_type": "coverage_contract",
            "coverage_contract_id": "fixture-coverage-contract",
            "contract_version": 1,
            "contract_hash": h("fixture-coverage-contract"),
            "coverage_contract_record_id": "fixture-coverage-contract-record",
            "coverage_contract_record_hash": h("fixture-coverage-contract-record"),
        },
        continuity_binding={
            "continuity_subject_type": "normative_continuity",
            "continuity_policy_id": "policy-normative_continuity",
            "continuity_policy_version": 1,
            "continuity_policy_hash": h("policy-normative_continuity"),
            "continuity_policy_activation_id": "policy-activation-normative_continuity",
            "continuity_policy_activation_record_hash": h("policy-activation-normative_continuity"),
        },
        precedence_binding={
            "precedence_subject_type": "normative_precedence",
            "precedence_policy_id": "policy-normative_precedence",
            "precedence_policy_version": 1,
            "precedence_policy_hash": h("policy-normative_precedence"),
            "precedence_policy_activation_id": "policy-activation-normative_precedence",
            "precedence_policy_activation_record_hash": h("policy-activation-normative_precedence"),
        },
        gates_evidence=[{
            "gate_id": "favorable-rule-review",
            "gate_version": 1,
            "gate_hash": h("favorable-rule-review"),
            "gate_outcome": review.outcome,
            "evidence_record_id": review.subject_id,
            "evidence_record_hash": review.record_hash,
        }],
        target_manifest=[{
            "subject_id": review.subject_id,
            "subject_hash": review.subject_hash,
            "review_record_hash": review.record_hash,
            "review_outcome": review.outcome,
        }],
    )
    models._adr020_validate_activation_decision_insert(None, None, decision)
    execution = ns(
        activation_decision_record_hash=decision.record_hash,
        scope_hash=decision.scope_hash,
        target_manifest_hash=decision.target_manifest_hash,
        record_hash=h("activation-execution"),
        decision_outcome=decision.decision_outcome,
        authorization_class="constitucional_reservada",
        execution_mode="manual",
        attempt_number=1,
        fencing_token=1,
        authority_bindings=decision.authority_bindings,
        policy_bindings=decision.policy_bindings,
        coverage_binding=decision.coverage_binding,
        continuity_binding=decision.continuity_binding,
        precedence_binding=decision.precedence_binding,
        gates_evidence=decision.gates_evidence,
        state="completed",
        finished_at=AT, structured_result={"activation_complete": True},
    )
    models._adr020_validate_activation_execution_insert(None, None, execution)
    generation = ns(
        activation_generation_id="generation-1",
        activation_execution_id="activation-execution-1",
        activation_decision_record_hash=decision.record_hash,
        target_manifest_hash=decision.target_manifest_hash,
        scope_hash=decision.scope_hash,
        composition_hash=h("composition"),
        record_hash=h("generation-record"),
        is_complete=True,
        composition_manifest=[decision.target_manifest[0]],
        previous_activation_generation_id=None,
        previous_activation_generation_record_hash=None,
        authority_bindings=execution.authority_bindings,
        policy_bindings=[], coverage_binding={}, continuity_binding={},
        precedence_binding={}, gates_evidence=[],
    )
    models._adr020_validate_activation_generation_insert(None, None, generation)
    fence = ns(
        scope_hash=generation.scope_hash,
        activation_generation_record_hash=generation.record_hash,
        activation_execution_record_hash=execution.record_hash,
        publisher_lease_record_hash=h("publisher-lease"),
        composition_hash=generation.composition_hash,
        source_event_record_hash=h("source-event"),
        record_hash=h("generation-fence"), generation_sequence=1,
        fencing_token=1, previous_generation_fence_record_id=None,
        previous_generation_fence_record_hash=None,
        activation_generation_is_complete=generation.is_complete,
        activation_execution_state=execution.state,
        activation_execution_id=generation.activation_execution_id,
        activation_generation_execution_id=generation.activation_execution_id,
        activation_generation_scope_hash=generation.scope_hash,
        activation_generation_composition_hash=generation.composition_hash,
    )
    models._adr020_validate_generation_fence_insert(None, None, fence)
    contract = ns(
        consumer_contract_hash=h("consumer-contract"),
        allowed_scope_hash=generation.scope_hash, record_hash=h("contract-record"),
        consumer_contract_version=1, supported_protocol_version=1,
        supported_generation_schema_version=1, consumer_type="replica",
        allowed_scope_descriptor={"scope_hash": generation.scope_hash},
        compatibility_rules={"capabilities": [], "limits": {}, "invariants": []},
        freshness_policy_binding=exact_policy("freshness"),
        security_policy_binding=exact_policy("security"), provenance={},
    )
    models._adr020_validate_consumer_contract_insert(None, None, contract)
    application = ns(
        consumer_application_record_id="application-1", consumer_id="consumer-1",
        replica_id="replica-1", replica_instance_id="replica-instance-1",
        consumer_contract_version=contract.consumer_contract_version,
        consumer_contract_hash=contract.consumer_contract_hash,
        scope_hash=generation.scope_hash, generation_fence_record_id="fence-1",
        generation_fence_record_hash=fence.record_hash,
        activation_generation_id=generation.activation_generation_id,
        activation_generation_record_hash=generation.record_hash,
        composition_hash=generation.composition_hash, record_hash=h("application-record"),
        previous_replica_checkpoint_record_id=None,
        previous_replica_checkpoint_record_hash=None,
        duplicate_of_consumer_application_record_id=None,
        duplicate_of_consumer_application_record_hash=None,
        duplicate_of_replica_checkpoint_record_id=None,
        duplicate_of_replica_checkpoint_record_hash=None,
        attempt_number=1, generation_sequence=fence.generation_sequence,
        fencing_token=fence.fencing_token, application_result="applied",
        finished_at=AT, structured_result={"application_complete": True},
        contract_allowed_scope_hash=contract.allowed_scope_hash,
        fence_scope_hash=fence.scope_hash,
        fence_generation_sequence=fence.generation_sequence,
        fence_fencing_token=fence.fencing_token,
        fence_activation_generation_id=generation.activation_generation_id,
        fence_activation_generation_record_hash=generation.record_hash,
        fence_composition_hash=generation.composition_hash,
    )
    models._adr020_validate_consumer_application_insert(None, None, application)
    checkpoint = ns(**application.__dict__)
    checkpoint.consumer_application_record_hash = application.record_hash
    checkpoint.consumer_application_result = application.application_result
    checkpoint.consumer_application_complete = True
    checkpoint.record_hash = h("checkpoint-record")
    models._adr020_validate_replica_checkpoint_insert(None, None, checkpoint)

    runtime = {
        "runtime_artifact_id": "runtime-1", "runtime_artifact_version": "1.0.0",
        "runtime_artifact_hash": h("runtime"),
        "dependency_manifest": [{"dependency_id": "dep", "dependency_version": "1.2.3", "dependency_hash": h("dep")}],
        "dependency_manifest_hash": h("dependencies"),
        "platform_contract_id": "platform", "platform_contract_version": 1,
        "platform_contract_hash": h("platform"),
    }
    bundle = ns(
        calculation_bundle_schema_version=1, calculation_bundle_hash=h("bundle"),
        scope_hash=generation.scope_hash, generation_fence_record_hash=fence.record_hash,
        generation_sequence=fence.generation_sequence, fencing_token=fence.fencing_token,
        activation_generation_id=generation.activation_generation_id,
        activation_generation_record_hash=generation.record_hash,
        composition_hash=generation.composition_hash,
        consumer_contract_hash=contract.consumer_contract_hash,
        consumer_application_record_id=application.consumer_application_record_id,
        consumer_application_record_hash=application.record_hash,
        replica_checkpoint_record_id="checkpoint-1",
        replica_checkpoint_record_hash=checkpoint.record_hash,
        calculation_subject_reference={"subject_type": "taxpayer", "subject_id": "subject-1", "subject_record_hash": h("subject"), "subject_payload_hash": h("subject-payload")},
        input_snapshot_manifest=[{"input_type": "declaration", "input_id": "input-1", "input_record_hash": h("input"), "input_payload_hash": h("input-payload"), "canonicalization_contract_id": "canonical-input", "canonicalization_contract_version": 1, "canonicalization_contract_hash": h("canonical-input"), "immutable_content_reference": "cas:input", "immutable_content_hash": h("immutable-input")}],
        normative_member_manifest=generation.composition_manifest,
        policy_binding_manifest=[exact_policy("calculation")], coverage_binding={},
        continuity_binding={}, precedence_binding={}, gates_evidence={},
        engine_binding={"engine_artifact_id": "engine-1", "engine_artifact_hash": h("engine")},
        runtime_binding=runtime,
        canonical_serialization_binding={"contract_id": "serialization", "version": 1, "hash": h("serialization")},
        evaluation_instant=AT,
        deterministic_seed_binding={"algorithm": "sha256", "seed": h("seed")},
        provenance={}, record_hash=h("bundle-record"),
    )
    models._adr020_validate_calculation_bundle_insert(None, None, bundle)
    calculation = ns(
        calculation_bundle_hash=bundle.calculation_bundle_hash,
        engine_artifact_hash=bundle.engine_binding["engine_artifact_hash"],
        runtime_artifact_hash=runtime["runtime_artifact_hash"],
        record_hash=h("calculation-execution"), attempt_number=1,
        fencing_token=bundle.fencing_token, state="completed", finished_at=AT,
        structured_result={"calculation_complete": True}, structured_error=None,
        provenance={},
    )
    models._adr020_validate_calculation_execution_insert(None, None, calculation)
    result = ns(
        calculation_execution_record_hash=calculation.record_hash,
        calculation_bundle_id="bundle-1", calculation_bundle_hash=bundle.calculation_bundle_hash,
        result_payload_hash=h("result-payload"), calculation_trace_hash=h("calculation-trace"),
        decision_trace_hash=h("decision-trace"), canonical_result_hash=h("canonical-result"),
        record_hash=h("result-record"), result_schema_version=1,
        result_payload_reference={"cas": h("result-payload")},
        calculation_trace_reference={"cas": h("calculation-trace")},
        decision_trace_reference={"cas": h("decision-trace")}, provenance={},
    )
    models._adr020_validate_calculation_result_insert(None, None, result)
    replay = ns(
        calculation_bundle_hash=bundle.calculation_bundle_hash,
        original_calculation_execution_record_hash=calculation.record_hash,
        original_calculation_result_record_hash=result.record_hash,
        original_canonical_result_hash=result.canonical_result_hash,
        replay_engine_artifact_hash=calculation.engine_artifact_hash,
        replay_runtime_artifact_hash=calculation.runtime_artifact_hash,
        replay_dependency_manifest_hash=runtime["dependency_manifest_hash"],
        replay_platform_contract_hash=runtime["platform_contract_hash"],
        replay_canonical_serialization_contract_hash=bundle.canonical_serialization_binding["hash"],
        replay_deterministic_seed_binding_hash=h("seed-binding"),
        record_hash=h("replay-execution"), attempt_number=1, state="completed",
        finished_at=AT, replay_result_payload_hash=result.result_payload_hash,
        replay_calculation_trace_hash=result.calculation_trace_hash,
        replay_decision_trace_hash=result.decision_trace_hash,
        replay_canonical_result_hash=result.canonical_result_hash,
        replay_evaluation_instant=bundle.evaluation_instant,
        structured_result={"replayed_from_result_hash": result.record_hash},
        structured_error=None, provenance={},
    )
    models._adr020_validate_replay_execution_insert(None, None, replay)
    verification = ns(
        replay_execution_record_hash=replay.record_hash,
        calculation_bundle_hash=bundle.calculation_bundle_hash,
        original_calculation_result_record_hash=result.record_hash,
        original_canonical_result_hash=result.canonical_result_hash,
        replay_canonical_result_hash=replay.replay_canonical_result_hash,
        record_hash=h("replay-verification"), result_payload_match=True,
        calculation_trace_match=True, decision_trace_match=True,
        verification_outcome="match", mismatch_manifest=[], provenance={},
    )
    models._adr020_validate_replay_verification_insert(None, None, verification)
    return locals()


def test_sovereign_pipeline_contracts_end_to_end():
    chain = sovereign_chain()
    assert chain["artifact"].artifact_hash == chain["extraction"].artifact_hash == chain["extraction_result"].artifact_hash
    assert chain["receipt"].acquisition_execution_record_hash == chain["acquisition"].record_hash
    assert chain["review"].evidence["extraction_result_record_hash"] == chain["extraction_result"].record_hash
    assert chain["decision"].target_manifest[0]["review_record_hash"] == chain["review"].record_hash
    assert chain["generation"].activation_decision_record_hash == chain["decision"].record_hash
    assert chain["fence"].activation_generation_record_hash == chain["generation"].record_hash
    assert chain["application"].generation_fence_record_hash == chain["fence"].record_hash
    assert chain["checkpoint"].consumer_application_record_hash == chain["application"].record_hash
    assert chain["bundle"].replica_checkpoint_record_hash == chain["checkpoint"].record_hash
    assert chain["result"].calculation_execution_record_hash == chain["calculation"].record_hash
    assert chain["replay"].original_calculation_result_record_hash == chain["result"].record_hash
    assert chain["verification"].replay_execution_record_hash == chain["replay"].record_hash
    assert chain["replay"].structured_result["replayed_from_result_hash"] == chain["result"].record_hash
    assert chain["result"].record_hash == h("result-record")


def test_divergence_partiality_and_replay_outcomes_fail_closed():
    c = sovereign_chain()
    with pytest.raises(ValueError, match="diverge"):
        models._adr020_validate_generation_fence_insert(None, None, ns(**{**c["fence"].__dict__, "activation_generation_scope_hash": h("other-scope")}))
    with pytest.raises(ValueError, match="stale"):
        models._adr020_validate_generation_fence_insert(None, None, ns(**{**c["fence"].__dict__, "generation_sequence": 2, "fencing_token": 1, "previous_generation_fence_record_id": "fence-0", "previous_generation_fence_record_hash": h("fence-0"), "previous_generation_sequence": 1, "previous_fencing_token": 1}))
    with pytest.raises(ValueError, match="partial application"):
        models._adr020_validate_consumer_application_insert(None, None, ns(**{**c["application"].__dict__, "structured_result": {"application_complete": False}}))
    with pytest.raises(ValueError, match="divergent replica checkpoint"):
        models._adr020_validate_replica_checkpoint_insert(None, None, ns(**{**c["checkpoint"].__dict__, "application_composition_hash": h("other-composition")}))
    with pytest.raises(ValueError, match="completed execution"):
        models._adr020_validate_calculation_result_insert(None, None, ns(**{**c["result"].__dict__, "calculation_execution_state": "running"}))
    with pytest.raises(ValueError, match="partial result"):
        models._adr020_validate_calculation_result_insert(None, None, ns(**{**c["result"].__dict__, "calculation_complete": False}))
    with pytest.raises(ValueError, match="original"):
        models._adr020_validate_replay_execution_insert(None, None, ns(**{**c["replay"].__dict__, "original_bundle_hash": h("other-bundle")}))
    original_hash = c["result"].record_hash
    mismatch = ns(**{**c["verification"].__dict__, "verification_outcome": "mismatch", "replay_canonical_result_hash": h("different-result"), "mismatch_manifest": [{"component": "payload", "evidence_hash": h("difference")} ]})
    models._adr020_validate_replay_verification_insert(None, None, mismatch)
    inconclusive = ns(**{**c["verification"].__dict__, "verification_outcome": "inconclusive", "replay_canonical_result_hash": None, "mismatch_manifest": [{"evidence": "unavailable"}]})
    models._adr020_validate_replay_verification_insert(None, None, inconclusive)
    with pytest.raises(ValueError, match="partial verification"):
        models._adr020_validate_replay_verification_insert(None, None, ns(**{**c["verification"].__dict__, "result_payload_match": False}))
    assert c["result"].record_hash == original_hash


@pytest.mark.parametrize(
    ("evidence", "message"),
    [
        ({"latest": True}, "floating"),
        ({"transport": "https://example.invalid"}, "external transport"),
        ({"clock": "datetime.now()"}, "clock"),
        ({"password": "forbidden"}, "sensitive"),
    ],
)
def test_bundle_rejects_implicit_external_or_floating_authority(evidence, message):
    bundle = sovereign_chain()["bundle"]
    with pytest.raises(ValueError, match=message):
        models._adr020_validate_calculation_bundle_insert(None, None, ns(**{**bundle.__dict__, "gates_evidence": evidence}))


def test_dependencies_are_pinned_and_all_entities_are_append_only():
    c = sovereign_chain()
    dependency = c["bundle"].runtime_binding["dependency_manifest"][0]
    assert dependency.keys() == {"dependency_id", "dependency_version", "dependency_hash"}
    assert dependency["dependency_version"] == "1.2.3"
    append_only = (
        models.AcquisitionExecution, models.SanitizedAcquisitionReceipt,
        models.ExtractionRun, models.ExtractionResult, models.RuleReviewRecord,
        models.ActivationDecision, models.ActivationExecution,
        models.ActivationGeneration, models.GenerationFenceRecord,
        models.ConsumerContractVersion, models.ConsumerApplicationRecord,
        models.ReplicaCheckpointRecord, models.CalculationBundle,
        models.CalculationExecutionRecord, models.CalculationResultRecord,
        models.ReplayExecutionRecord, models.ReplayVerificationRecord,
    )
    for entity in append_only:
        with pytest.raises(RuntimeError, match="append-only"):
            models._adr020_reject_append_only_mutation(None, None, entity())

    sources = [Path(models.__file__)] + sorted((ROOT / "migrations" / "versions").glob("00*_adr020_*.py"))
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in sources)
    for forbidden in ("current_generation", "latest_generation", "newest_generation", "requests.get", "httpx.", "execute_calculation", "execute_replay"):
        assert forbidden not in text
    for operational in (models.ConsumerContractVersion, models.ReplicaCheckpointRecord):
        assert "authority" not in operational.__table__.columns
