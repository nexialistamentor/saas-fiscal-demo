from app.l3_enforcement import (
    DecisionRecord,
    ProofSpec,
    RealizationBinding,
    check_r1_provenance_closure,
)


def test_r1_rejeita_proveniencia_da_obrigacao_b_para_obrigacao_a():
    proof_spec_a = ProofSpec(
        proof_spec_id="PS-R1-A-L0080-C0001-0030-AA57826E965D",
        obligation_id="A-L0080-C0001-0030-AA57826E965D",
        obligation_sha256=(
            "AA57826E965DCF70FB44EBF8794F1F7DF96C1DFDA668AE45C9DBB5E0D1EF21D8"
        ),
        decision_atom_ref="app/main.py:ExecutarParsersPayload.dry_run",
        production_entrypoint_ref="app/main.py:admin_executar_parsers",
    )
    realization_a = RealizationBinding(
        proof_spec_id=proof_spec_a.proof_spec_id,
        decision_atom_ref=proof_spec_a.decision_atom_ref,
        production_entrypoint_ref=proof_spec_a.production_entrypoint_ref,
    )
    provenance_b_with_a_binding = DecisionRecord(
        obligation_id="A-L0684-C0001-0025-C3E1D1BDDB7C",
        obligation_sha256=(
            "C3E1D1BDDB7C6504EFF8916383D6232C7742EF338F4264738F8F166B253B451A"
        ),
        proof_spec_id=proof_spec_a.proof_spec_id,
        decision_atom_ref=proof_spec_a.decision_atom_ref,
        production_entrypoint_ref=proof_spec_a.production_entrypoint_ref,
    )

    result = check_r1_provenance_closure(
        target=proof_spec_a,
        realization=realization_a,
        decision_record=provenance_b_with_a_binding,
    )

    assert result.valid is False, "WRONG_OBLIGATION_PROVENANCE_WAS_ACCEPTED"
    assert result.invalid_family == "RUN_INVALID_FOR_OBLIGATION"


def test_r1_rejeita_causal_target_errado_para_obrigacao_a():
    proof_spec_a = ProofSpec(
        proof_spec_id="PS-R1-A-L0080-C0001-0030-AA57826E965D",
        obligation_id="A-L0080-C0001-0030-AA57826E965D",
        obligation_sha256=(
            "AA57826E965DCF70FB44EBF8794F1F7DF96C1DFDA668AE45C9DBB5E0D1EF21D8"
        ),
        decision_atom_ref="app/main.py:ExecutarParsersPayload.dry_run",
        production_entrypoint_ref="app/main.py:admin_executar_parsers",
    )
    realization_with_wrong_causal_target = RealizationBinding(
        proof_spec_id=proof_spec_a.proof_spec_id,
        decision_atom_ref="app/main.py:WRONG_DECISION_ATOM",
        production_entrypoint_ref="app/main.py:WRONG_PRODUCTION_ENTRYPOINT",
    )
    decision_record_with_wrong_causal_target = DecisionRecord(
        obligation_id=proof_spec_a.obligation_id,
        obligation_sha256=proof_spec_a.obligation_sha256,
        proof_spec_id=proof_spec_a.proof_spec_id,
        decision_atom_ref=realization_with_wrong_causal_target.decision_atom_ref,
        production_entrypoint_ref=(
            realization_with_wrong_causal_target.production_entrypoint_ref
        ),
    )

    result = check_r1_provenance_closure(
        target=proof_spec_a,
        realization=realization_with_wrong_causal_target,
        decision_record=decision_record_with_wrong_causal_target,
    )

    assert result.valid is False, "WRONG_CAUSAL_TARGET_WAS_ACCEPTED"
    assert result.invalid_family == "RUN_INVALID_FOR_OBLIGATION"


def test_r1_aceita_proveniencia_exata_da_obrigacao_a():
    proof_spec_a = ProofSpec(
        proof_spec_id="PS-R1-A-L0080-C0001-0030-AA57826E965D",
        obligation_id="A-L0080-C0001-0030-AA57826E965D",
        obligation_sha256=(
            "AA57826E965DCF70FB44EBF8794F1F7DF96C1DFDA668AE45C9DBB5E0D1EF21D8"
        ),
        decision_atom_ref="app/main.py:ExecutarParsersPayload.dry_run",
        production_entrypoint_ref="app/main.py:admin_executar_parsers",
    )
    realization_a = RealizationBinding(
        proof_spec_id=proof_spec_a.proof_spec_id,
        decision_atom_ref=proof_spec_a.decision_atom_ref,
        production_entrypoint_ref=proof_spec_a.production_entrypoint_ref,
    )
    decision_record_a = DecisionRecord(
        obligation_id=proof_spec_a.obligation_id,
        obligation_sha256=proof_spec_a.obligation_sha256,
        proof_spec_id=proof_spec_a.proof_spec_id,
        decision_atom_ref=realization_a.decision_atom_ref,
        production_entrypoint_ref=realization_a.production_entrypoint_ref,
    )

    result = check_r1_provenance_closure(
        target=proof_spec_a,
        realization=realization_a,
        decision_record=decision_record_a,
    )

    assert result.valid is True
    assert result.invalid_family is None

def test_r1_rejeita_hash_da_obrigacao_b_com_id_da_obrigacao_a():
    proof_spec_a = ProofSpec(
        proof_spec_id="PS-R1-A-L0080-C0001-0030-AA57826E965D",
        obligation_id="A-L0080-C0001-0030-AA57826E965D",
        obligation_sha256=(
            "AA57826E965DCF70FB44EBF8794F1F7DF96C1DFDA668AE45C9DBB5E0D1EF21D8"
        ),
        decision_atom_ref="app/main.py:ExecutarParsersPayload.dry_run",
        production_entrypoint_ref="app/main.py:admin_executar_parsers",
    )
    realization_a = RealizationBinding(
        proof_spec_id=proof_spec_a.proof_spec_id,
        decision_atom_ref=proof_spec_a.decision_atom_ref,
        production_entrypoint_ref=proof_spec_a.production_entrypoint_ref,
    )
    decision_record_with_wrong_hash = DecisionRecord(
        obligation_id=proof_spec_a.obligation_id,
        obligation_sha256=(
            "C3E1D1BDDB7C6504EFF8916383D6232C7742EF338F4264738F8F166B253B451A"
        ),
        proof_spec_id=proof_spec_a.proof_spec_id,
        decision_atom_ref=proof_spec_a.decision_atom_ref,
        production_entrypoint_ref=proof_spec_a.production_entrypoint_ref,
    )

    result = check_r1_provenance_closure(
        target=proof_spec_a,
        realization=realization_a,
        decision_record=decision_record_with_wrong_hash,
    )

    assert result.valid is False, "WRONG_OBLIGATION_HASH_WAS_ACCEPTED"
    assert result.invalid_family == "RUN_INVALID_FOR_OBLIGATION"
