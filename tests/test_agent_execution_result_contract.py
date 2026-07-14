"""
Testes do contrato AgentExecutionResult — ADR-008 B14.0/B14.1.

Prova invariantes internas de escopo, tempo, status, modo, evidências,
metadados LLM, custos, acções, erros e sanitização antes da persistência.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid1, uuid4

import pytest
from pydantic import ValidationError

from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.sanitization import assert_result_sanitized
from app.agents.contracts.shared import (
    AgentAction,
    AgentAlert,
    AgentEvidence,
)


STARTED_AT = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
FINISHED_AT = STARTED_AT + timedelta(seconds=1)


def _payload_base(**overrides: object) -> dict:
    payload: dict = {
        "execution_id": uuid4(),
        "attempt": 1,
        "agent_id": "auditor_fiscal",
        "agent_version": "1.0.0",
        "mission_type": "auditar_documento",
        "mission_id": uuid4(),
        "correlation_id": uuid4(),
        "status": "sucesso",
        "scope": "global",
        "tenant_id": None,
        "started_at": STARTED_AT,
        "finished_at": FINISHED_AT,
        "duration_ms": 1000,
        "mode": "activo",
        "payload_schema": "AgentAuditResult",
    }
    payload.update(overrides)
    return payload


def _action_executed(
    *,
    action_type: str = "recalcular",
) -> AgentAction:
    return AgentAction(
        action_type=action_type,
        target_type="empresa",
        target_id="empresa-001",
        status="executada",
        idempotency_key="a" * 64,
    )


def _action_proposed(
    *,
    action_type: str = "recalcular",
) -> AgentAction:
    return AgentAction(
        action_type=action_type,
        status="proposta",
    )


# ---------------------------------------------------------------------------
# Contrato base
# ---------------------------------------------------------------------------

def test_execution_result_valida_payload_base() -> None:
    result = AgentExecutionResult(**_payload_base())

    assert result.contract_version == "1.0"
    assert result.attempt == 1
    assert result.status == "sucesso"
    assert result.scope == "global"
    assert result.mode == "activo"
    assert result.payload_version == "1.0"
    assert result.payload == {}
    assert result.alerts == []
    assert result.evidence == []
    assert result.actions_proposed == []
    assert result.actions_executed == []


def test_execution_result_proibe_campos_extras() -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(),
            campo_nao_contratado=True,
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "execution_id",
        "mission_id",
        "correlation_id",
    ],
)
def test_execution_result_exige_uuid4(
    field_name: str,
) -> None:
    payload = _payload_base()
    payload[field_name] = uuid1()

    with pytest.raises(ValidationError):
        AgentExecutionResult(**payload)


def test_execution_result_rejeita_contract_version_desconhecida() -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(contract_version="2.0")
        )


def test_execution_result_attempt_exige_minimo_um() -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(attempt=0)
        )


# ---------------------------------------------------------------------------
# Escopo
# ---------------------------------------------------------------------------

def test_scope_global_exige_tenant_ausente() -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(tenant_id=10)
        )


@pytest.mark.parametrize(
    "scope",
    ["tenant", "documento"],
)
def test_scope_tenant_ou_documento_exige_tenant_id(
    scope: str,
) -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(scope=scope)
        )


@pytest.mark.parametrize(
    "scope",
    ["tenant", "documento"],
)
def test_scope_tenant_ou_documento_aceita_tenant_id(
    scope: str,
) -> None:
    result = AgentExecutionResult(
        **_payload_base(
            scope=scope,
            tenant_id=10,
        )
    )

    assert result.scope == scope
    assert result.tenant_id == 10


def test_scope_utilizador_nao_exige_tenant_id() -> None:
    result = AgentExecutionResult(
        **_payload_base(scope="utilizador")
    )

    assert result.scope == "utilizador"
    assert result.tenant_id is None


def test_scope_desconhecido_e_rejeitado() -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(scope="desconhecido")
        )


# ---------------------------------------------------------------------------
# Tempo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field_name",
    ["started_at", "finished_at"],
)
def test_tempo_rejeita_datetime_sem_timezone(
    field_name: str,
) -> None:
    payload = _payload_base()
    payload[field_name] = datetime(2026, 7, 13, 12, 0, 0)

    with pytest.raises(ValidationError):
        AgentExecutionResult(**payload)


@pytest.mark.parametrize(
    "field_name",
    ["started_at", "finished_at"],
)
def test_tempo_rejeita_timezone_nao_utc(
    field_name: str,
) -> None:
    payload = _payload_base()
    payload[field_name] = datetime(
        2026,
        7,
        13,
        9,
        0,
        0,
        tzinfo=timezone(timedelta(hours=-3)),
    )

    with pytest.raises(ValidationError):
        AgentExecutionResult(**payload)


def test_finished_at_nao_pode_anteceder_started_at() -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(
                finished_at=STARTED_AT - timedelta(milliseconds=1),
                duration_ms=0,
            )
        )


def test_duration_ms_exacta_e_aceite() -> None:
    result = AgentExecutionResult(
        **_payload_base(duration_ms=1000)
    )

    assert result.duration_ms == 1000


@pytest.mark.parametrize(
    "duration_ms",
    [999, 1001],
)
def test_duration_ms_aceita_tolerancia_de_um_ms(
    duration_ms: int,
) -> None:
    result = AgentExecutionResult(
        **_payload_base(duration_ms=duration_ms)
    )

    assert result.duration_ms == duration_ms


@pytest.mark.parametrize(
    "duration_ms",
    [998, 1002],
)
def test_duration_ms_rejeita_diferenca_superior_a_um_ms(
    duration_ms: int,
) -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(duration_ms=duration_ms)
        )


def test_duration_ms_rejeita_negativo() -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(duration_ms=-1)
        )


def test_intervalo_zero_aceita_duration_zero() -> None:
    result = AgentExecutionResult(
        **_payload_base(
            finished_at=STARTED_AT,
            duration_ms=0,
        )
    )

    assert result.duration_ms == 0


# ---------------------------------------------------------------------------
# Status, erros e modo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "status",
    [
        "sucesso",
        "bloqueado",
        "pulado",
        "parcial",
    ],
)
def test_status_nao_erro_rejeita_error_code(
    status: str,
) -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(
                status=status,
                error_code="ERRO_INTERNO",
            )
        )


@pytest.mark.parametrize(
    "status",
    [
        "sucesso",
        "bloqueado",
        "pulado",
        "parcial",
    ],
)
def test_status_nao_erro_rejeita_error_message(
    status: str,
) -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(
                status=status,
                error_message="mensagem controlada",
            )
        )


@pytest.mark.parametrize(
    "missing_field",
    ["error_code", "error_message"],
)
def test_status_erro_exige_campos_de_erro(
    missing_field: str,
) -> None:
    values = {
        "status": "erro",
        "error_code": "ERRO_INTERNO",
        "error_message": "Mensagem controlada",
    }
    values[missing_field] = None

    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(**values)
        )


def test_status_erro_aceita_campos_controlados() -> None:
    result = AgentExecutionResult(
        **_payload_base(
            status="erro",
            error_code="ERRO_INTERNO",
            error_message="Mensagem controlada",
            retryable=True,
        )
    )

    assert result.status == "erro"
    assert result.error_code == "ERRO_INTERNO"
    assert result.retryable is True


@pytest.mark.parametrize(
    "status",
    ["erro", "bloqueado", "pulado"],
)
def test_status_sem_execucao_rejeita_actions_executed(
    status: str,
) -> None:
    extra: dict = {}
    if status == "erro":
        extra = {
            "error_code": "ERRO_INTERNO",
            "error_message": "Mensagem controlada",
        }

    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(
                status=status,
                actions_executed=[_action_executed()],
                **extra,
            )
        )


@pytest.mark.parametrize(
    "mode",
    ["sombra", "dry_run"],
)
def test_modo_sem_efeito_rejeita_actions_executed(
    mode: str,
) -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(
                mode=mode,
                actions_executed=[_action_executed()],
            )
        )


def test_modo_activo_aceita_action_executed() -> None:
    action = _action_executed()

    result = AgentExecutionResult(
        **_payload_base(actions_executed=[action])
    )

    assert result.actions_executed == [action]


def test_actions_executed_rejeita_action_proposta() -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(
                actions_executed=[_action_proposed()]
            )
        )


def test_actions_proposed_aceita_action_proposta() -> None:
    action = _action_proposed()

    result = AgentExecutionResult(
        **_payload_base(actions_proposed=[action])
    )

    assert result.actions_proposed == [action]


def test_status_desconhecido_e_rejeitado() -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(status="desconhecido")
        )


def test_modo_desconhecido_e_rejeitado() -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(mode="desconhecido")
        )


# ---------------------------------------------------------------------------
# Evidências
# ---------------------------------------------------------------------------

def test_evidence_ref_existente_e_aceite() -> None:
    evidence = AgentEvidence(
        evidence_type="rule_ref",
        reference="REGRA-001",
    )
    alert = AgentAlert(
        code="ALERTA-001",
        severity="medio",
        message="Alerta controlado",
        evidence_refs=[evidence.evidence_id],
    )

    result = AgentExecutionResult(
        **_payload_base(
            evidence=[evidence],
            alerts=[alert],
        )
    )

    assert result.alerts[0].evidence_refs == [
        evidence.evidence_id
    ]


def test_evidence_ref_ausente_e_rejeitado() -> None:
    alert = AgentAlert(
        code="ALERTA-001",
        severity="medio",
        message="Alerta controlado",
        evidence_refs=[uuid4()],
    )

    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(alerts=[alert])
        )


def test_evidence_refs_comparam_uuid_nativo() -> None:
    evidence_id = uuid4()
    evidence = AgentEvidence(
        evidence_id=evidence_id,
        evidence_type="event_ref",
        reference="EVENTO-001",
    )
    alert = AgentAlert(
        code="ALERTA-001",
        severity="baixo",
        message="Alerta controlado",
        evidence_refs=[evidence_id],
    )

    result = AgentExecutionResult(
        **_payload_base(
            evidence=[evidence],
            alerts=[alert],
        )
    )

    assert result.evidence[0].evidence_id == evidence_id
    assert result.alerts[0].evidence_refs[0] == evidence_id


def test_alert_sem_evidence_refs_e_aceite() -> None:
    alert = AgentAlert(
        code="ALERTA-001",
        severity="informativo",
        message="Alerta controlado",
    )

    result = AgentExecutionResult(
        **_payload_base(alerts=[alert])
    )

    assert result.alerts == [alert]


# ---------------------------------------------------------------------------
# LLM e custos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("provider", "local_model"),
        ("tokens_used", 10),
        ("cost_estimated", Decimal("0.10")),
        ("cost_actual", Decimal("0.08")),
        ("currency", "BRL"),
    ],
)
def test_llm_nao_usado_exige_metadados_vazios(
    field_name: str,
    field_value: object,
) -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(**{field_name: field_value})
        )


def test_llm_usado_exige_provider() -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(llm_used=True)
        )


def test_llm_usado_aceita_provider_sem_custos() -> None:
    result = AgentExecutionResult(
        **_payload_base(
            llm_used=True,
            provider="local_model",
        )
    )

    assert result.llm_used is True
    assert result.provider == "local_model"
    assert result.currency is None


def test_llm_usado_aceita_metadados_completos() -> None:
    result = AgentExecutionResult(
        **_payload_base(
            llm_used=True,
            provider="local_model",
            tokens_used=250,
            cost_estimated=Decimal("0.12"),
            cost_actual=Decimal("0.10"),
            currency="BRL",
        )
    )

    assert result.tokens_used == 250
    assert result.cost_estimated == Decimal("0.12")
    assert result.cost_actual == Decimal("0.10")
    assert result.currency == "BRL"


def test_tokens_used_rejeita_negativo() -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(
                llm_used=True,
                provider="local_model",
                tokens_used=-1,
            )
        )


@pytest.mark.parametrize(
    "field_name",
    ["cost_estimated", "cost_actual"],
)
def test_custos_rejeitam_float(
    field_name: str,
) -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(
                llm_used=True,
                provider="local_model",
                currency="BRL",
                **{field_name: 0.10},
            )
        )


@pytest.mark.parametrize(
    "field_name",
    ["cost_estimated", "cost_actual"],
)
def test_custos_rejeitam_negativo(
    field_name: str,
) -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(
                llm_used=True,
                provider="local_model",
                currency="BRL",
                **{field_name: Decimal("-0.01")},
            )
        )


@pytest.mark.parametrize(
    "field_name",
    ["cost_estimated", "cost_actual"],
)
def test_custo_exige_currency(
    field_name: str,
) -> None:
    with pytest.raises(ValidationError):
        AgentExecutionResult(
            **_payload_base(
                llm_used=True,
                provider="local_model",
                **{field_name: Decimal("0.01")},
            )
        )


def test_custos_zero_com_currency_sao_aceites() -> None:
    result = AgentExecutionResult(
        **_payload_base(
            llm_used=True,
            provider="local_model",
            cost_estimated=Decimal("0"),
            cost_actual=Decimal("0"),
            currency="BRL",
        )
    )

    assert result.cost_actual == Decimal("0")


# ---------------------------------------------------------------------------
# Sanitização antes da persistência
# ---------------------------------------------------------------------------

def test_resultado_limpo_passa_sanitizacao() -> None:
    result = AgentExecutionResult(
        **_payload_base(
            payload={"regra_id": "REGRA-001"},
            alerts=[
                AgentAlert(
                    code="ALERTA-001",
                    severity="baixo",
                    message="Mensagem controlada",
                )
            ],
            evidence=[
                AgentEvidence(
                    evidence_type="rule_ref",
                    reference="REGRA-001",
                )
            ],
            actions_proposed=[_action_proposed()],
        )
    )

    assert_result_sanitized(result.model_dump(mode="json"))


@pytest.mark.parametrize(
    "payload_override",
    [
        {
            "payload": {
                "contacto": "pessoa@example.com",
            }
        },
        {
            "alerts": [
                AgentAlert(
                    code="ALERTA-001",
                    severity="alto",
                    message="Contactar pessoa@example.com",
                )
            ]
        },
        {
            "evidence": [
                AgentEvidence(
                    evidence_type="log_ref",
                    reference=(
                        "Traceback (most recent call last)"
                    ),
                )
            ]
        },
        {
            "actions_proposed": [
                _action_proposed(
                    action_type="enviar para pessoa@example.com"
                )
            ]
        },
    ],
)
def test_resultado_sensivel_e_bloqueado_na_sanitizacao(
    payload_override: dict,
) -> None:
    result = AgentExecutionResult(
        **_payload_base(**payload_override)
    )

    with pytest.raises(ValueError):
        assert_result_sanitized(
            result.model_dump(mode="json")
        )


def test_error_message_sensivel_e_bloqueada_na_sanitizacao() -> None:
    result = AgentExecutionResult(
        **_payload_base(
            status="erro",
            error_code="ERRO_INTERNO",
            error_message="Contactar pessoa@example.com",
        )
    )

    with pytest.raises(ValueError):
        assert_result_sanitized(
            result.model_dump(mode="json")
        )
