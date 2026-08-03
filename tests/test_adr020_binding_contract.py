import pytest
from pydantic import ValidationError

from app.schemas.adr020_bindings import ADR020BindingsContract


def _gates_evidence() -> list[dict[str, object]]:
    return [
        {
            "gate_id": "gate-001",
            "gate_version": 1,
            "gate_hash": "4" * 64,
            "gate_outcome": "passed",
            "evidence_record_id": "gate-evidence-record-001",
            "evidence_record_hash": "5" * 64,
        }
    ]


def _policy_bindings() -> list[dict[str, object]]:
    return [
        {
            "policy_type": "normative_precedence",
            "policy_id": "normative-precedence-policy-001",
            "policy_version": 1,
            "policy_hash": "d" * 64,
            "policy_activation_id": "policy-activation-001",
            "policy_activation_record_hash": "e" * 64,
        },
        {
            "policy_type": "normative_continuity",
            "policy_id": "normative-continuity-policy-001",
            "policy_version": 1,
            "policy_hash": "2" * 64,
            "policy_activation_id": "continuity-activation-001",
            "policy_activation_record_hash": "3" * 64,
        }
    ]


def _coverage_binding() -> dict[str, object]:
    return {
        "coverage_subject_type": "coverage_contract",
        "coverage_contract_id": "coverage-contract-001",
        "contract_version": 1,
        "contract_hash": "f" * 64,
        "coverage_contract_record_id": "coverage-contract-record-001",
        "coverage_contract_record_hash": "1" * 64,
    }


def _continuity_binding() -> dict[str, object]:
    return {
        "continuity_subject_type": "normative_continuity",
        "continuity_policy_id": "normative-continuity-policy-001",
        "continuity_policy_version": 1,
        "continuity_policy_hash": "2" * 64,
        "continuity_policy_activation_id": "continuity-activation-001",
        "continuity_policy_activation_record_hash": "3" * 64,
    }


def _precedence_binding() -> dict[str, object]:
    return {
        "precedence_subject_type": "normative_precedence",
        "precedence_policy_id": "normative-precedence-policy-001",
        "precedence_policy_version": 1,
        "precedence_policy_hash": "d" * 64,
        "precedence_policy_activation_id": "policy-activation-001",
        "precedence_policy_activation_record_hash": "e" * 64,
    }


@pytest.mark.parametrize(
    ("field", "empty_value"),
    [
        ("authority_bindings", {}),
        ("policy_bindings", []),
        ("coverage_binding", {}),
        ("continuity_binding", {}),
        ("precedence_binding", {}),
        ("gates_evidence", []),
    ],
)
def test_adr020_bindings_contract_rejeita_estruturas_vazias(field, empty_value):
    payload = {
        "authority_bindings": {
            "bootstrap_authority_record_id": "bootstrap-authority-001",
            "bootstrap_authority_record_hash": "a" * 64,
        },
        "policy_bindings": _policy_bindings(),
        "coverage_binding": _coverage_binding(),
        "continuity_binding": _continuity_binding(),
        "precedence_binding": _precedence_binding(),
        "gates_evidence": _gates_evidence(),
    }
    payload[field] = empty_value

    with pytest.raises(Exception):
        ADR020BindingsContract(**payload)


def test_authority_bindings_rejeita_mapa_sem_identidade_soberana():
    payload = {
        "authority_bindings": {"authority": "binding"},
        "policy_bindings": _policy_bindings(),
        "coverage_binding": _coverage_binding(),
        "continuity_binding": _continuity_binding(),
        "precedence_binding": _precedence_binding(),
        "gates_evidence": _gates_evidence(),
    }

    with pytest.raises(ValidationError):
        ADR020BindingsContract(**payload)


def test_continuity_binding_rejeita_placeholder_sem_identidade_soberana():
    payload = {
        "authority_bindings": {
            "bootstrap_authority_record_id": "bootstrap-authority-001",
            "bootstrap_authority_record_hash": "a" * 64,
        },
        "policy_bindings": _policy_bindings(),
        "coverage_binding": _coverage_binding(),
        "continuity_binding": {"continuity": "binding"},
        "precedence_binding": _precedence_binding(),
        "gates_evidence": _gates_evidence(),
    }

    with pytest.raises(ValidationError):
        ADR020BindingsContract(**payload)


def test_precedence_binding_rejeita_placeholder_sem_identidade_soberana():
    payload = {
        "authority_bindings": {
            "bootstrap_authority_record_id": "bootstrap-authority-001",
            "bootstrap_authority_record_hash": "a" * 64,
        },
        "policy_bindings": _policy_bindings(),
        "coverage_binding": _coverage_binding(),
        "continuity_binding": _continuity_binding(),
        "precedence_binding": {"precedence": "binding"},
        "gates_evidence": _gates_evidence(),
    }

    with pytest.raises(ValidationError):
        ADR020BindingsContract(**payload)


def test_gates_evidence_rejeita_placeholder_sem_evidencia_estruturada():
    payload = {
        "authority_bindings": {
            "bootstrap_authority_record_id": "bootstrap-authority-001",
            "bootstrap_authority_record_hash": "a" * 64,
        },
        "policy_bindings": _policy_bindings(),
        "coverage_binding": _coverage_binding(),
        "continuity_binding": _continuity_binding(),
        "precedence_binding": _precedence_binding(),
        "gates_evidence": ["gate_evidence"],
    }

    with pytest.raises(ValidationError):
        ADR020BindingsContract(**payload)


def test_gates_evidence_aceita_elemento_estruturado_exacto():
    result = ADR020BindingsContract(
        authority_bindings={
            "bootstrap_authority_record_id": "bootstrap-authority-001",
            "bootstrap_authority_record_hash": "a" * 64,
        },
        policy_bindings=_policy_bindings(),
        coverage_binding=_coverage_binding(),
        continuity_binding=_continuity_binding(),
        precedence_binding=_precedence_binding(),
        gates_evidence=[
            {
                "gate_id": "gate-001",
                "gate_version": 1,
                "gate_hash": "4" * 64,
                "gate_outcome": "passed",
                "evidence_record_id": "gate-evidence-record-001",
                "evidence_record_hash": "5" * 64,
            }
        ],
    )

    assert result.gates_evidence[0].gate_id == "gate-001"
    assert result.gates_evidence[0].gate_version == 1
    assert result.gates_evidence[0].gate_outcome == "passed"
    assert (
        result.gates_evidence[0].evidence_record_id
        == "gate-evidence-record-001"
    )


def test_gates_evidence_rejeita_campo_extra():
    gates_evidence = _gates_evidence()
    gates_evidence[0]["source"] = "nao-ratificado"

    with pytest.raises(ValidationError) as exc_info:
        ADR020BindingsContract(
            authority_bindings={
                "bootstrap_authority_record_id": "bootstrap-authority-001",
                "bootstrap_authority_record_hash": "a" * 64,
            },
            policy_bindings=_policy_bindings(),
            coverage_binding=_coverage_binding(),
            continuity_binding=_continuity_binding(),
            precedence_binding=_precedence_binding(),
            gates_evidence=gates_evidence,
        )

    errors = exc_info.value.errors()

    assert any(
        error["loc"] == ("gates_evidence", 0, "source")
        and error["type"] == "extra_forbidden"
        for error in errors
    )


def test_authority_bindings_aceita_cadeia_politica_activa_exacta():
    result = ADR020BindingsContract(
        authority_bindings={
            "activation_authority_policy_id": "activation-authority-policy-001",
            "activation_authority_policy_version": 1,
            "activation_authority_policy_hash": "b" * 64,
            "activation_authority_policy_activation_id": "authority-activation-001",
        },
        policy_bindings=_policy_bindings(),
        coverage_binding=_coverage_binding(),
        continuity_binding=_continuity_binding(),
        precedence_binding=_precedence_binding(),
        gates_evidence=_gates_evidence(),
    )

    assert result.authority_bindings.activation_authority_policy_version == 1


def test_authority_bindings_aceita_autoridade_automatica_delegada_exacta():
    result = ADR020BindingsContract(
        authority_bindings={
            "activation_authority_policy_id": "activation-authority-policy-001",
            "activation_authority_policy_version": 1,
            "activation_authority_policy_hash": "b" * 64,
            "activation_authority_policy_activation_id": "authority-activation-001",
            "automation_envelope_id": "automation-envelope-001",
            "automation_envelope_version": 1,
            "automation_envelope_hash": "c" * 64,
            "automation_envelope_activation_id": "envelope-activation-001",
        },
        policy_bindings=_policy_bindings(),
        coverage_binding=_coverage_binding(),
        continuity_binding=_continuity_binding(),
        precedence_binding=_precedence_binding(),
        gates_evidence=_gates_evidence(),
    )

    assert result.authority_bindings.activation_authority_policy_version == 1
    assert result.authority_bindings.automation_envelope_version == 1


def test_authority_bindings_aceita_bootstrap_automatico_exacto():
    result = ADR020BindingsContract(
        authority_bindings={
            "bootstrap_authority_record_id": "bootstrap-authority-001",
            "bootstrap_authority_record_hash": "a" * 64,
            "automation_envelope_id": "automation-envelope-001",
            "automation_envelope_version": 1,
            "automation_envelope_hash": "c" * 64,
            "automation_envelope_activation_id": "envelope-activation-001",
        },
        policy_bindings=_policy_bindings(),
        coverage_binding=_coverage_binding(),
        continuity_binding=_continuity_binding(),
        precedence_binding=_precedence_binding(),
        gates_evidence=_gates_evidence(),
    )

    assert result.authority_bindings.bootstrap_authority_record_id == (
        "bootstrap-authority-001"
    )
    assert result.authority_bindings.automation_envelope_version == 1


def test_policy_bindings_aceita_policy_version_e_activation_exactas():
    result = ADR020BindingsContract(
        authority_bindings={
            "bootstrap_authority_record_id": "bootstrap-authority-001",
            "bootstrap_authority_record_hash": "a" * 64,
        },
        policy_bindings=_policy_bindings(),
        coverage_binding=_coverage_binding(),
        continuity_binding=_continuity_binding(),
        precedence_binding=_precedence_binding(),
        gates_evidence=_gates_evidence(),
    )

    assert result.policy_bindings[0].policy_type == "normative_precedence"
    assert result.policy_bindings[0].policy_version == 1
    assert (
        result.policy_bindings[0].policy_activation_id == "policy-activation-001"
    )


def test_coverage_binding_aceita_coverage_contract_exacto():
    result = ADR020BindingsContract(
        authority_bindings={
            "bootstrap_authority_record_id": "bootstrap-authority-001",
            "bootstrap_authority_record_hash": "a" * 64,
        },
        policy_bindings=_policy_bindings(),
        coverage_binding={
            "coverage_subject_type": "coverage_contract",
            "coverage_contract_id": "coverage-contract-001",
            "contract_version": 1,
            "contract_hash": "f" * 64,
            "coverage_contract_record_id": "coverage-contract-record-001",
            "coverage_contract_record_hash": "1" * 64,
        },
        continuity_binding=_continuity_binding(),
        precedence_binding=_precedence_binding(),
        gates_evidence=_gates_evidence(),
    )

    assert result.coverage_binding.coverage_subject_type == "coverage_contract"
    assert result.coverage_binding.contract_version == 1
    assert (
        result.coverage_binding.coverage_contract_record_id
        == "coverage-contract-record-001"
    )


def test_continuity_binding_aceita_politica_e_activacao_exactas():
    result = ADR020BindingsContract(
        authority_bindings={
            "bootstrap_authority_record_id": "bootstrap-authority-001",
            "bootstrap_authority_record_hash": "a" * 64,
        },
        policy_bindings=_policy_bindings(),
        coverage_binding=_coverage_binding(),
        continuity_binding={
            "continuity_subject_type": "normative_continuity",
            "continuity_policy_id": "normative-continuity-policy-001",
            "continuity_policy_version": 1,
            "continuity_policy_hash": "2" * 64,
            "continuity_policy_activation_id": "continuity-activation-001",
            "continuity_policy_activation_record_hash": "3" * 64,
        },
        precedence_binding=_precedence_binding(),
        gates_evidence=_gates_evidence(),
    )

    assert (
        result.continuity_binding.continuity_subject_type
        == "normative_continuity"
    )
    assert result.continuity_binding.continuity_policy_version == 1
    assert (
        result.continuity_binding.continuity_policy_activation_id
        == "continuity-activation-001"
    )


def test_continuity_binding_rejeita_zero_policy_bindings_correspondentes():
    policy_bindings = [
        policy
        for policy in _policy_bindings()
        if policy["policy_type"] != "normative_continuity"
    ]

    with pytest.raises(
        ValidationError,
        match=(
            "continuity_binding must match exactly one "
            "normative_continuity policy_binding"
        ),
    ):
        ADR020BindingsContract(
            authority_bindings={
                "bootstrap_authority_record_id": "bootstrap-authority-001",
                "bootstrap_authority_record_hash": "a" * 64,
            },
            policy_bindings=policy_bindings,
            coverage_binding=_coverage_binding(),
            continuity_binding=_continuity_binding(),
            precedence_binding=_precedence_binding(),
            gates_evidence=_gates_evidence(),
        )


def test_continuity_binding_rejeita_multiplos_policy_bindings_correspondentes():
    policy_bindings = _policy_bindings()
    duplicate = next(
        policy.copy()
        for policy in policy_bindings
        if policy["policy_type"] == "normative_continuity"
    )
    policy_bindings.append(duplicate)

    with pytest.raises(
        ValidationError,
        match=(
            "continuity_binding must match exactly one "
            "normative_continuity policy_binding"
        ),
    ):
        ADR020BindingsContract(
            authority_bindings={
                "bootstrap_authority_record_id": "bootstrap-authority-001",
                "bootstrap_authority_record_hash": "a" * 64,
            },
            policy_bindings=policy_bindings,
            coverage_binding=_coverage_binding(),
            continuity_binding=_continuity_binding(),
            precedence_binding=_precedence_binding(),
            gates_evidence=_gates_evidence(),
        )


def test_precedence_binding_rejeita_zero_policy_bindings_correspondentes():
    policy_bindings = [
        policy
        for policy in _policy_bindings()
        if policy["policy_type"] != "normative_precedence"
    ]

    with pytest.raises(
        ValidationError,
        match=(
            "precedence_binding must match exactly one "
            "normative_precedence policy_binding"
        ),
    ):
        ADR020BindingsContract(
            authority_bindings={
                "bootstrap_authority_record_id": "bootstrap-authority-001",
                "bootstrap_authority_record_hash": "a" * 64,
            },
            policy_bindings=policy_bindings,
            coverage_binding=_coverage_binding(),
            continuity_binding=_continuity_binding(),
            precedence_binding=_precedence_binding(),
            gates_evidence=_gates_evidence(),
        )


def test_precedence_binding_rejeita_multiplos_policy_bindings_correspondentes():
    policy_bindings = _policy_bindings()
    duplicate = next(
        policy.copy()
        for policy in policy_bindings
        if policy["policy_type"] == "normative_precedence"
    )
    policy_bindings.append(duplicate)

    with pytest.raises(
        ValidationError,
        match=(
            "precedence_binding must match exactly one "
            "normative_precedence policy_binding"
        ),
    ):
        ADR020BindingsContract(
            authority_bindings={
                "bootstrap_authority_record_id": "bootstrap-authority-001",
                "bootstrap_authority_record_hash": "a" * 64,
            },
            policy_bindings=policy_bindings,
            coverage_binding=_coverage_binding(),
            continuity_binding=_continuity_binding(),
            precedence_binding=_precedence_binding(),
            gates_evidence=_gates_evidence(),
        )


def test_precedence_binding_aceita_politica_e_activacao_exactas():
    result = ADR020BindingsContract(
        authority_bindings={
            "bootstrap_authority_record_id": "bootstrap-authority-001",
            "bootstrap_authority_record_hash": "a" * 64,
        },
        policy_bindings=_policy_bindings(),
        coverage_binding=_coverage_binding(),
        continuity_binding=_continuity_binding(),
        precedence_binding={
            "precedence_subject_type": "normative_precedence",
            "precedence_policy_id": "normative-precedence-policy-001",
            "precedence_policy_version": 1,
            "precedence_policy_hash": "d" * 64,
            "precedence_policy_activation_id": "policy-activation-001",
            "precedence_policy_activation_record_hash": "e" * 64,
        },
        gates_evidence=_gates_evidence(),
    )

    assert (
        result.precedence_binding.precedence_subject_type
        == "normative_precedence"
    )
    assert result.precedence_binding.precedence_policy_version == 1
    assert (
        result.precedence_binding.precedence_policy_activation_id
        == "policy-activation-001"
    )


@pytest.mark.parametrize(
    "hash_field",
    [
        "gate_hash",
        "evidence_record_hash",
    ],
)
def test_gates_evidence_rejeita_hash_uppercase(hash_field):
    gates_evidence = _gates_evidence()
    gates_evidence[0][hash_field] = "A" * 64

    with pytest.raises(ValidationError) as exc_info:
        ADR020BindingsContract(
            authority_bindings={
                "bootstrap_authority_record_id": "bootstrap-authority-001",
                "bootstrap_authority_record_hash": "a" * 64,
            },
            policy_bindings=_policy_bindings(),
            coverage_binding=_coverage_binding(),
            continuity_binding=_continuity_binding(),
            precedence_binding=_precedence_binding(),
            gates_evidence=gates_evidence,
        )

    errors = exc_info.value.errors()

    assert any(
        error["loc"] == ("gates_evidence", 0, hash_field)
        and error["type"] == "string_pattern_mismatch"
        for error in errors
    )
