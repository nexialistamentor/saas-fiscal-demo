"""
Testes dos contratos partilhados soberanos — ADR-008 B14.0.

Prova:
- SourceRef;
- BudgetPolicy e coerência financeira;
- AgentEvidence;
- AgentAlert;
- AgentAction e idempotência;
- campos extras proibidos;
- UUID4 de evidência.
"""

from decimal import Decimal
from uuid import uuid1, uuid4

import pytest
from pydantic import ValidationError

from app.agents.contracts.shared import (
    AgentAction,
    AgentAlert,
    AgentEvidence,
    BudgetPolicy,
    SourceRef,
)


# ---------------------------------------------------------------------------
# SourceRef
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "uso_pretendido",
    [
        "fundamentar_decisao",
        "validar_fato_operacional",
        "apoiar_explicacao_ux",
        "contexto_llm",
    ],
)
def test_source_ref_aceita_usos_normativos(uso_pretendido: str) -> None:
    source = SourceRef(
        fonte_id="fonte-001",
        uso_pretendido=uso_pretendido,
    )

    assert source.fonte_id == "fonte-001"
    assert source.uso_pretendido == uso_pretendido


def test_source_ref_rejeita_uso_desconhecido() -> None:
    with pytest.raises(ValidationError):
        SourceRef(
            fonte_id="fonte-001",
            uso_pretendido="uso_nao_autorizado",
        )


def test_source_ref_exige_fonte_id() -> None:
    with pytest.raises(ValidationError):
        SourceRef(uso_pretendido="contexto_llm")


def test_source_ref_proibe_campos_extras() -> None:
    with pytest.raises(ValidationError):
        SourceRef(
            fonte_id="fonte-001",
            uso_pretendido="contexto_llm",
            extra="proibido",
        )


# ---------------------------------------------------------------------------
# BudgetPolicy
# ---------------------------------------------------------------------------

def test_budget_policy_default_desliga_llm_e_zera_limites() -> None:
    policy = BudgetPolicy()

    assert policy.allow_llm is False
    assert policy.allowed_providers == []
    assert policy.max_calls == 0
    assert policy.max_input_chars == 0
    assert policy.max_output_tokens == 0
    assert policy.max_cost == Decimal("0")
    assert policy.currency == "BRL"
    assert policy.on_unavailable == "deterministic"


def test_budget_policy_listas_default_nao_sao_partilhadas() -> None:
    first = BudgetPolicy()
    second = BudgetPolicy()

    first.allowed_providers.append("local")

    assert second.allowed_providers == []


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("allowed_providers", ["provider"]),
        ("max_calls", 1),
        ("max_input_chars", 1),
        ("max_output_tokens", 1),
        ("max_cost", Decimal("0.01")),
    ],
)
def test_budget_policy_llm_desligado_exige_recursos_zerados(
    field_name: str,
    field_value: object,
) -> None:
    payload = {field_name: field_value}

    with pytest.raises(ValidationError):
        BudgetPolicy(**payload)


def test_budget_policy_llm_ligado_aceita_configuracao_coerente() -> None:
    policy = BudgetPolicy(
        allow_llm=True,
        allowed_providers=["local_model"],
        max_calls=2,
        max_input_chars=5000,
        max_output_tokens=700,
        max_cost=Decimal("1.25"),
        currency="BRL",
        on_unavailable="queue",
    )

    assert policy.allow_llm is True
    assert policy.allowed_providers == ["local_model"]
    assert policy.max_calls == 2
    assert policy.max_input_chars == 5000
    assert policy.max_output_tokens == 700
    assert policy.max_cost == Decimal("1.25")


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("allowed_providers", []),
        ("max_calls", 0),
        ("max_input_chars", 0),
        ("max_output_tokens", 0),
    ],
)
def test_budget_policy_llm_ligado_exige_recursos_positivos(
    field_name: str,
    field_value: object,
) -> None:
    payload = {
        "allow_llm": True,
        "allowed_providers": ["provider"],
        "max_calls": 1,
        "max_input_chars": 1,
        "max_output_tokens": 1,
        field_name: field_value,
    }

    with pytest.raises(ValidationError):
        BudgetPolicy(**payload)


@pytest.mark.parametrize(
    "field_name",
    [
        "max_calls",
        "max_input_chars",
        "max_output_tokens",
    ],
)
def test_budget_policy_rejeita_limite_negativo(field_name: str) -> None:
    with pytest.raises(ValidationError):
        BudgetPolicy(**{field_name: -1})


def test_budget_policy_max_cost_aceita_decimal() -> None:
    policy = BudgetPolicy(
        allow_llm=True,
        allowed_providers=["provider"],
        max_calls=1,
        max_input_chars=1,
        max_output_tokens=1,
        max_cost=Decimal("0.10"),
    )

    assert isinstance(policy.max_cost, Decimal)
    assert policy.max_cost == Decimal("0.10")


def test_budget_policy_max_cost_rejeita_float() -> None:
    with pytest.raises(ValidationError):
        BudgetPolicy(max_cost=0.10)


def test_budget_policy_max_cost_rejeita_negativo() -> None:
    with pytest.raises(ValidationError):
        BudgetPolicy(max_cost=Decimal("-0.01"))


@pytest.mark.parametrize(
    "on_unavailable",
    [
        "deterministic",
        "cache",
        "local_model",
        "queue",
        "human_review",
    ],
)
def test_budget_policy_aceita_fallbacks_normativos(
    on_unavailable: str,
) -> None:
    policy = BudgetPolicy(on_unavailable=on_unavailable)

    assert policy.on_unavailable == on_unavailable


def test_budget_policy_rejeita_fallback_desconhecido() -> None:
    with pytest.raises(ValidationError):
        BudgetPolicy(on_unavailable="provider_externo")


def test_budget_policy_proibe_campos_extras() -> None:
    with pytest.raises(ValidationError):
        BudgetPolicy(extra="proibido")


# ---------------------------------------------------------------------------
# AgentEvidence
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "evidence_type",
    [
        "log_ref",
        "event_ref",
        "document_ref",
        "source_ref",
        "metric_ref",
        "rule_ref",
    ],
)
def test_agent_evidence_aceita_tipos_normativos(
    evidence_type: str,
) -> None:
    evidence = AgentEvidence(
        evidence_type=evidence_type,
        reference="registo-controlado-001",
    )

    assert evidence.evidence_type == evidence_type
    assert evidence.reference == "registo-controlado-001"
    assert evidence.evidence_id.version == 4
    assert evidence.redacted is True


def test_agent_evidence_ids_default_sao_uuid4_unicos() -> None:
    first = AgentEvidence(
        evidence_type="event_ref",
        reference="evento-001",
    )
    second = AgentEvidence(
        evidence_type="event_ref",
        reference="evento-002",
    )

    assert first.evidence_id.version == 4
    assert second.evidence_id.version == 4
    assert first.evidence_id != second.evidence_id


def test_agent_evidence_aceita_uuid4_fornecido() -> None:
    evidence_id = uuid4()

    evidence = AgentEvidence(
        evidence_id=evidence_id,
        evidence_type="rule_ref",
        reference="regra-001",
    )

    assert evidence.evidence_id == evidence_id


def test_agent_evidence_rejeita_uuid_nao_v4() -> None:
    with pytest.raises(ValidationError):
        AgentEvidence(
            evidence_id=uuid1(),
            evidence_type="rule_ref",
            reference="regra-001",
        )


def test_agent_evidence_aceita_sha256_minusculo_valido() -> None:
    digest = "a" * 64

    evidence = AgentEvidence(
        evidence_type="document_ref",
        reference="documento-001",
        sha256=digest,
    )

    assert evidence.sha256 == digest


@pytest.mark.parametrize(
    "digest",
    [
        "a" * 63,
        "a" * 65,
        "A" * 64,
        "g" * 64,
        "",
    ],
)
def test_agent_evidence_rejeita_sha256_invalido(digest: str) -> None:
    with pytest.raises(ValidationError):
        AgentEvidence(
            evidence_type="document_ref",
            reference="documento-001",
            sha256=digest,
        )


def test_agent_evidence_rejeita_tipo_desconhecido() -> None:
    with pytest.raises(ValidationError):
        AgentEvidence(
            evidence_type="conteudo_integral",
            reference="documento-001",
        )


def test_agent_evidence_proibe_campos_extras() -> None:
    with pytest.raises(ValidationError):
        AgentEvidence(
            evidence_type="source_ref",
            reference="fonte-001",
            extra="proibido",
        )


# ---------------------------------------------------------------------------
# AgentAlert
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "severity",
    [
        "critico",
        "alto",
        "medio",
        "baixo",
        "informativo",
    ],
)
def test_agent_alert_aceita_severidades_normativas(
    severity: str,
) -> None:
    alert = AgentAlert(
        code="ALERTA-001",
        severity=severity,
        message="Alerta controlado",
    )

    assert alert.severity == severity
    assert alert.evidence_refs == []


def test_agent_alert_aceita_referencias_uuid4() -> None:
    evidence_id = uuid4()

    alert = AgentAlert(
        code="ALERTA-001",
        severity="alto",
        message="Alerta controlado",
        evidence_refs=[evidence_id],
    )

    assert alert.evidence_refs == [evidence_id]


def test_agent_alert_rejeita_referencia_uuid_nao_v4() -> None:
    with pytest.raises(ValidationError):
        AgentAlert(
            code="ALERTA-001",
            severity="alto",
            message="Alerta controlado",
            evidence_refs=[uuid1()],
        )


def test_agent_alert_listas_default_nao_sao_partilhadas() -> None:
    first = AgentAlert(
        code="ALERTA-001",
        severity="baixo",
        message="Primeiro",
    )
    second = AgentAlert(
        code="ALERTA-002",
        severity="baixo",
        message="Segundo",
    )

    first.evidence_refs.append(uuid4())

    assert second.evidence_refs == []


def test_agent_alert_rejeita_severidade_desconhecida() -> None:
    with pytest.raises(ValidationError):
        AgentAlert(
            code="ALERTA-001",
            severity="urgente",
            message="Alerta controlado",
        )


def test_agent_alert_proibe_campos_extras() -> None:
    with pytest.raises(ValidationError):
        AgentAlert(
            code="ALERTA-001",
            severity="medio",
            message="Alerta controlado",
            extra="proibido",
        )


# ---------------------------------------------------------------------------
# AgentAction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "status",
    [
        "proposta",
        "bloqueada",
    ],
)
def test_agent_action_nao_executada_pode_omitir_chave(
    status: str,
) -> None:
    action = AgentAction(
        action_type="recalcular",
        status=status,
    )

    assert action.status == status
    assert action.idempotency_key is None


def test_agent_action_executada_exige_chave() -> None:
    with pytest.raises(ValidationError):
        AgentAction(
            action_type="recalcular",
            status="executada",
        )


def test_agent_action_executada_aceita_chave_sha256() -> None:
    key = "b" * 64

    action = AgentAction(
        action_type="recalcular",
        target_type="empresa",
        target_id=123,
        status="executada",
        idempotency_key=key,
    )

    assert action.status == "executada"
    assert action.idempotency_key == key
    assert action.target_type == "empresa"
    assert action.target_id == 123


@pytest.mark.parametrize(
    "key",
    [
        "b" * 63,
        "b" * 65,
        "B" * 64,
        "z" * 64,
        "",
    ],
)
def test_agent_action_rejeita_chave_invalida(key: str) -> None:
    with pytest.raises(ValidationError):
        AgentAction(
            action_type="recalcular",
            status="executada",
            idempotency_key=key,
        )


def test_agent_action_aceita_target_id_textual() -> None:
    action = AgentAction(
        action_type="notificar",
        target_type="documento",
        target_id="doc-001",
        status="proposta",
    )

    assert action.target_id == "doc-001"


def test_agent_action_rejeita_status_desconhecido() -> None:
    with pytest.raises(ValidationError):
        AgentAction(
            action_type="recalcular",
            status="dry_run",
        )


def test_agent_action_proibe_campos_extras() -> None:
    with pytest.raises(ValidationError):
        AgentAction(
            action_type="recalcular",
            status="proposta",
            extra="proibido",
        )


# ---------------------------------------------------------------------------
# Defesa comum: extra="forbid"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            SourceRef,
            {
                "fonte_id": "fonte-001",
                "uso_pretendido": "contexto_llm",
            },
        ),
        (BudgetPolicy, {}),
        (
            AgentEvidence,
            {
                "evidence_type": "event_ref",
                "reference": "evento-001",
            },
        ),
        (
            AgentAlert,
            {
                "code": "ALERTA-001",
                "severity": "baixo",
                "message": "Alerta",
            },
        ),
        (
            AgentAction,
            {
                "action_type": "notificar",
                "status": "proposta",
            },
        ),
    ],
)
def test_todos_os_contratos_partilhados_proibem_extra(
    model: type,
    payload: dict,
) -> None:
    with pytest.raises(ValidationError):
        model(**payload, campo_nao_contratado=True)
