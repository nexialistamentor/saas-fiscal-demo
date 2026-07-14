"""
Testes da validação cruzada AgentMission × AgentExecutionResult — ADR-008.

Prova as correspondências obrigatórias, BudgetPolicy verificável e autoridade
mínima das acções executadas. Mantém explícitas as lacunas normativas:
- não existe contador de chamadas para validar BudgetPolicy.max_calls;
- não existe semântica ratificada para comparar agent_version_required.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.validation import (
    validate_result_against_mission,
)
from app.agents.contracts.shared import AgentAction, BudgetPolicy
from app.agents.mission_factory import create_agent_mission


STARTED_AT = datetime(
    2026,
    7,
    13,
    12,
    0,
    0,
    tzinfo=timezone.utc,
)
FINISHED_AT = STARTED_AT + timedelta(seconds=1)


def _mission(**overrides: object):
    kwargs: dict = {
        "mission_type": "auditar_documento",
        "target_agent": "auditor_fiscal",
        "context": {"evento": "teste", "valor": 10},
        "context_schema": "AgentAuditContext",
        "output_schema": "AgentAuditResult",
        "scope": "global",
        "requested_by": "system",
        "authority_level": "leitura",
        "execution_mode": "activo",
        "source_request_id": "request-001",
        "created_at": STARTED_AT,
    }
    kwargs.update(overrides)
    return create_agent_mission(**kwargs)


def _result_for(mission, **overrides: object):
    payload: dict = {
        "execution_id": uuid4(),
        "attempt": 1,
        "agent_id": mission.target_agent,
        "agent_version": "1.0.0",
        "mission_type": mission.mission_type,
        "mission_id": mission.mission_id,
        "correlation_id": mission.correlation_id,
        "status": "sucesso",
        "scope": mission.scope,
        "tenant_id": mission.tenant_id,
        "started_at": STARTED_AT,
        "finished_at": FINISHED_AT,
        "duration_ms": 1000,
        "mode": mission.execution_mode,
        "payload_schema": mission.output_schema,
        "payload_version": mission.output_version,
    }
    payload.update(overrides)
    return AgentExecutionResult(**payload)


def _executed_action() -> AgentAction:
    return AgentAction(
        action_type="recalcular",
        target_type="empresa",
        target_id="empresa-001",
        status="executada",
        idempotency_key="a" * 64,
    )


# ---------------------------------------------------------------------------
# Caminho válido e tipos
# ---------------------------------------------------------------------------

def test_validation_accepts_matching_mission_and_result() -> None:
    mission = _mission()
    result = _result_for(mission)

    assert validate_result_against_mission(mission, result) is None


def test_validation_requires_agent_mission_instance() -> None:
    mission = _mission()
    result = _result_for(mission)

    with pytest.raises(TypeError, match="mission deve ser AgentMission"):
        validate_result_against_mission({}, result)


def test_validation_requires_execution_result_instance() -> None:
    mission = _mission()

    with pytest.raises(
        TypeError,
        match="result deve ser AgentExecutionResult",
    ):
        validate_result_against_mission(mission, {})


# ---------------------------------------------------------------------------
# Nove correspondências obrigatórias missão × resultado
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("field_name", "different_value"),
    [
        ("agent_id", "outro_agente"),
        ("mission_id", uuid4()),
        ("mission_type", "outra_missao"),
        ("correlation_id", uuid4()),
        ("scope", "utilizador"),
        ("mode", "dry_run"),
        ("payload_schema", "OutroSchema"),
        ("payload_version", "2.0"),
    ],
)
def test_validation_rejects_required_field_divergence(
    field_name: str,
    different_value: object,
) -> None:
    mission = _mission()
    result = _result_for(
        mission,
        **{field_name: different_value},
    )

    with pytest.raises(ValueError, match=f"{field_name} divergente"):
        validate_result_against_mission(mission, result)


def test_validation_accepts_matching_tenant_scope() -> None:
    mission = _mission(
        scope="tenant",
        tenant_id=10,
    )
    result = _result_for(mission)

    assert validate_result_against_mission(mission, result) is None


def test_validation_rejects_tenant_divergence() -> None:
    mission = _mission(
        scope="tenant",
        tenant_id=10,
    )
    result = _result_for(
        mission,
        tenant_id=20,
    )

    with pytest.raises(ValueError, match="tenant_id divergente"):
        validate_result_against_mission(mission, result)


# ---------------------------------------------------------------------------
# BudgetPolicy verificável
# ---------------------------------------------------------------------------

def test_validation_llm_not_used_does_not_require_budget() -> None:
    mission = _mission(
        budget_policy=BudgetPolicy(),
    )
    result = _result_for(
        mission,
        llm_used=False,
    )

    assert validate_result_against_mission(mission, result) is None


def test_validation_rejects_llm_when_policy_disallows_it() -> None:
    mission = _mission(
        budget_policy=BudgetPolicy(),
    )
    result = _result_for(
        mission,
        llm_used=True,
        provider="local_model",
    )

    with pytest.raises(
        ValueError,
        match="BudgetPolicy.allow_llm=False",
    ):
        validate_result_against_mission(mission, result)


def test_validation_accepts_authorized_provider() -> None:
    mission = _mission(
        budget_policy=BudgetPolicy(
            allow_llm=True,
            allowed_providers=["local_model"],
            max_calls=1,
            max_input_chars=1000,
            max_output_tokens=200,
            max_cost=Decimal("1.00"),
        ),
    )
    result = _result_for(
        mission,
        llm_used=True,
        provider="local_model",
        tokens_used=200,
        cost_estimated=Decimal("1.00"),
        cost_actual=Decimal("0.75"),
        currency="BRL",
    )

    assert validate_result_against_mission(mission, result) is None


def test_validation_rejects_unauthorized_provider() -> None:
    mission = _mission(
        budget_policy=BudgetPolicy(
            allow_llm=True,
            allowed_providers=["local_model"],
            max_calls=1,
            max_input_chars=1000,
            max_output_tokens=200,
            max_cost=Decimal("1.00"),
        ),
    )
    result = _result_for(
        mission,
        llm_used=True,
        provider="provider_externo",
    )

    with pytest.raises(
        ValueError,
        match="provider não autorizado",
    ):
        validate_result_against_mission(mission, result)


def test_validation_rejects_tokens_above_output_limit() -> None:
    mission = _mission(
        budget_policy=BudgetPolicy(
            allow_llm=True,
            allowed_providers=["local_model"],
            max_calls=1,
            max_input_chars=1000,
            max_output_tokens=200,
            max_cost=Decimal("1.00"),
        ),
    )
    result = _result_for(
        mission,
        llm_used=True,
        provider="local_model",
        tokens_used=201,
    )

    with pytest.raises(
        ValueError,
        match="tokens_used excede",
    ):
        validate_result_against_mission(mission, result)


@pytest.mark.parametrize(
    "field_name",
    ["cost_estimated", "cost_actual"],
)
def test_validation_rejects_cost_above_maximum(
    field_name: str,
) -> None:
    mission = _mission(
        budget_policy=BudgetPolicy(
            allow_llm=True,
            allowed_providers=["local_model"],
            max_calls=1,
            max_input_chars=1000,
            max_output_tokens=200,
            max_cost=Decimal("1.00"),
        ),
    )
    result = _result_for(
        mission,
        llm_used=True,
        provider="local_model",
        currency="BRL",
        **{field_name: Decimal("1.01")},
    )

    with pytest.raises(
        ValueError,
        match=f"{field_name} excede",
    ):
        validate_result_against_mission(mission, result)


def test_validation_accepts_cost_equal_to_maximum() -> None:
    mission = _mission(
        budget_policy=BudgetPolicy(
            allow_llm=True,
            allowed_providers=["local_model"],
            max_calls=1,
            max_input_chars=1000,
            max_output_tokens=200,
            max_cost=Decimal("1.00"),
        ),
    )
    result = _result_for(
        mission,
        llm_used=True,
        provider="local_model",
        cost_actual=Decimal("1.00"),
        currency="BRL",
    )

    assert validate_result_against_mission(mission, result) is None


# ---------------------------------------------------------------------------
# Autoridade das acções executadas
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "authority_level",
    ["leitura", "proposta"],
)
def test_validation_rejects_executed_actions_without_authority(
    authority_level: str,
) -> None:
    mission = _mission(
        authority_level=authority_level,
        execution_mode="activo",
    )
    result = _result_for(
        mission,
        actions_executed=[_executed_action()],
    )

    with pytest.raises(
        ValueError,
        match="authority_level",
    ):
        validate_result_against_mission(mission, result)


def test_validation_accepts_executed_action_with_execution_authority() -> None:
    mission = _mission(
        authority_level="execucao",
        execution_mode="activo",
    )
    result = _result_for(
        mission,
        actions_executed=[_executed_action()],
    )

    assert validate_result_against_mission(mission, result) is None


def test_validation_accepts_executed_action_with_elevated_authority() -> None:
    mission = _mission(
        authority_level="elevada",
        execution_mode="activo",
        ratification_id="rat-001",
        authorized_by="admin-001",
        authorization_role="autoridade_final",
    )
    result = _result_for(
        mission,
        actions_executed=[_executed_action()],
    )

    assert validate_result_against_mission(mission, result) is None


def test_validation_without_executed_actions_does_not_require_authority() -> None:
    mission = _mission(
        authority_level="leitura",
        execution_mode="activo",
    )
    result = _result_for(mission)

    assert validate_result_against_mission(mission, result) is None


# ---------------------------------------------------------------------------
# Lacunas normativas explícitas
# ---------------------------------------------------------------------------

def test_validation_does_not_compare_agent_version_required_yet() -> None:
    mission = _mission(
        agent_version_required="9.9.9",
    )
    result = _result_for(
        mission,
        agent_version="1.0.0",
    )

    # ADR-008 não define semântica de comparação de versões.
    assert validate_result_against_mission(mission, result) is None


def test_validation_has_no_llm_call_counter_contract() -> None:
    mission = _mission(
        budget_policy=BudgetPolicy(
            allow_llm=True,
            allowed_providers=["local_model"],
            max_calls=1,
            max_input_chars=1000,
            max_output_tokens=200,
            max_cost=Decimal("1.00"),
        ),
    )
    result = _result_for(
        mission,
        llm_used=True,
        provider="local_model",
    )

    # AgentExecutionResult não possui campo de contagem de chamadas.
    assert not hasattr(result, "llm_calls")
    assert validate_result_against_mission(mission, result) is None
