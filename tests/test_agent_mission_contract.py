"""
Testes do contrato soberano AgentMission — ADR-008 B14.0/B14.1.

A instanciação directa é usada aqui apenas como teste de contrato,
conforme autorização expressa do ADR-008.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid1, uuid4

import pytest
from pydantic import ValidationError

from app.agents.contracts.canonical import (
    build_context_hash,
    build_mission_idempotency_key,
)
from app.agents.contracts.mission import AgentMission
from app.agents.contracts.shared import BudgetPolicy, SourceRef


UTC_NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def _payload_base(**overrides: object) -> dict:
    context = {"evento": "teste", "valor": 10}
    source_request_id = "request-001"

    payload: dict = {
        "mission_id": uuid4(),
        "correlation_id": uuid4(),
        "mission_type": "auditar_documento",
        "target_agent": "auditor_fiscal",
        "context_schema": "AgentAuditContext",
        "output_schema": "AgentAuditResult",
        "scope": "global",
        "requested_by": "system",
        "context": context,
        "context_hash": build_context_hash(context),
        "authority_level": "leitura",
        "execution_mode": "dry_run",
        "source_request_id": source_request_id,
        "idempotency_key": build_mission_idempotency_key(
            mission_type="auditar_documento",
            target_agent="auditor_fiscal",
            scope="global",
            tenant_id=None,
            entity_type=None,
            entity_id=None,
            source_event_id=None,
            schedule_slot=None,
            source_request_id=source_request_id,
            idempotency_reference_at=None,
            contract_version="1.0",
        ),
        "priority": "normal",
        "created_at": UTC_NOW,
    }
    payload.update(overrides)
    return payload


def _recalcular_derivados(payload: dict) -> dict:
    data = dict(payload)
    data["context_hash"] = build_context_hash(data["context"])
    data["idempotency_key"] = build_mission_idempotency_key(
        mission_type=data["mission_type"],
        target_agent=data["target_agent"],
        scope=data["scope"],
        tenant_id=data.get("tenant_id"),
        entity_type=data.get("entity_type"),
        entity_id=data.get("entity_id"),
        source_event_id=data.get("source_event_id"),
        schedule_slot=data.get("schedule_slot"),
        source_request_id=data.get("source_request_id"),
        idempotency_reference_at=data.get(
            "idempotency_reference_at"
        ),
        contract_version=data.get("contract_version", "1.0"),
    )
    return data


# ---------------------------------------------------------------------------
# Contrato base e campos extras
# ---------------------------------------------------------------------------

def test_agent_mission_valida_payload_base() -> None:
    mission = AgentMission(**_payload_base())

    assert mission.contract_version == "1.0"
    assert mission.context_version == "1.0"
    assert mission.output_version == "1.0"
    assert mission.scope == "global"
    assert mission.priority == "normal"
    assert mission.budget_policy == BudgetPolicy()
    assert mission.sources == []


def test_agent_mission_proibe_campos_extras() -> None:
    with pytest.raises(ValidationError):
        AgentMission(
            **_payload_base(),
            campo_nao_contratado=True,
        )


@pytest.mark.parametrize(
    "field_name",
    ["mission_id", "correlation_id"],
)
def test_agent_mission_exige_uuid4(
    field_name: str,
) -> None:
    payload = _payload_base()
    payload[field_name] = uuid1()

    with pytest.raises(ValidationError):
        AgentMission(**payload)


def test_agent_mission_rejeita_contract_version_desconhecida() -> None:
    with pytest.raises(ValidationError):
        AgentMission(
            **_payload_base(contract_version="2.0")
        )


# ---------------------------------------------------------------------------
# Escopo
# ---------------------------------------------------------------------------

def test_scope_global_exige_tenant_ausente() -> None:
    payload = _recalcular_derivados(
        _payload_base(tenant_id=10)
    )

    with pytest.raises(ValidationError):
        AgentMission(**payload)


def test_scope_tenant_exige_tenant_id() -> None:
    payload = _recalcular_derivados(
        _payload_base(scope="tenant")
    )

    with pytest.raises(ValidationError):
        AgentMission(**payload)


def test_scope_tenant_aceita_tenant_id() -> None:
    payload = _recalcular_derivados(
        _payload_base(scope="tenant", tenant_id=10)
    )

    mission = AgentMission(**payload)

    assert mission.scope == "tenant"
    assert mission.tenant_id == 10


@pytest.mark.parametrize(
    "missing_field",
    ["tenant_id", "entity_type", "entity_id"],
)
def test_scope_documento_exige_campos(
    missing_field: str,
) -> None:
    values = {
        "scope": "documento",
        "tenant_id": 10,
        "entity_type": "nfe",
        "entity_id": "doc-001",
    }
    values[missing_field] = None
    payload = _recalcular_derivados(
        _payload_base(**values)
    )

    with pytest.raises(ValidationError):
        AgentMission(**payload)


def test_scope_documento_aceita_campos_completos() -> None:
    payload = _recalcular_derivados(
        _payload_base(
            scope="documento",
            tenant_id=10,
            entity_type="nfe",
            entity_id="doc-001",
        )
    )

    mission = AgentMission(**payload)

    assert mission.scope == "documento"
    assert mission.entity_id == "doc-001"


def test_scope_utilizador_exige_actor_id() -> None:
    payload = _recalcular_derivados(
        _payload_base(scope="utilizador")
    )

    with pytest.raises(ValidationError):
        AgentMission(**payload)


def test_scope_utilizador_aceita_actor_id() -> None:
    payload = _recalcular_derivados(
        _payload_base(
            scope="utilizador",
            actor_id="user-001",
        )
    )

    mission = AgentMission(**payload)

    assert mission.actor_id == "user-001"


# ---------------------------------------------------------------------------
# Origem única
# ---------------------------------------------------------------------------

def test_agent_mission_exige_uma_origem() -> None:
    payload = _payload_base()
    payload["source_request_id"] = None
    payload["idempotency_key"] = "0" * 64

    with pytest.raises(ValidationError):
        AgentMission(**payload)


def test_agent_mission_rejeita_multiplas_origens() -> None:
    payload = _payload_base(
        source_event_id=uuid4(),
    )
    payload["idempotency_key"] = "0" * 64

    with pytest.raises(ValidationError):
        AgentMission(**payload)


def test_parent_mission_id_nao_conta_como_origem() -> None:
    payload = _payload_base(
        parent_mission_id=uuid4(),
    )

    mission = AgentMission(**payload)

    assert mission.parent_mission_id is not None


def test_schedule_slot_vazio_nao_conta_como_origem() -> None:
    payload = _payload_base(
        source_request_id=None,
        schedule_slot="   ",
        idempotency_key="0" * 64,
    )

    with pytest.raises(ValidationError):
        AgentMission(**payload)


def test_source_request_id_e_normalizado() -> None:
    source_request_id = "request-normalizado"
    payload = _payload_base(
        source_request_id=f"  {source_request_id}  ",
    )
    payload["idempotency_key"] = (
        build_mission_idempotency_key(
            mission_type=payload["mission_type"],
            target_agent=payload["target_agent"],
            scope=payload["scope"],
            tenant_id=None,
            entity_type=None,
            entity_id=None,
            source_event_id=None,
            schedule_slot=None,
            source_request_id=source_request_id,
            idempotency_reference_at=None,
            contract_version="1.0",
        )
    )

    mission = AgentMission(**payload)

    assert mission.source_request_id == source_request_id


# ---------------------------------------------------------------------------
# Autoridade e ratificação
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "missing_field",
    [
        "ratification_id",
        "authorized_by",
        "authorization_role",
    ],
)
def test_autoridade_elevada_activa_exige_ratificacao_completa(
    missing_field: str,
) -> None:
    values = {
        "authority_level": "elevada",
        "execution_mode": "activo",
        "ratification_id": "rat-001",
        "authorized_by": "admin-001",
        "authorization_role": "autoridade_final",
    }
    values[missing_field] = None

    with pytest.raises(ValidationError):
        AgentMission(**_payload_base(**values))


def test_autoridade_elevada_activa_aceita_ratificacao_completa() -> None:
    mission = AgentMission(
        **_payload_base(
            authority_level="elevada",
            execution_mode="activo",
            ratification_id="rat-001",
            authorized_by="admin-001",
            authorization_role="autoridade_final",
        )
    )

    assert mission.ratification_id == "rat-001"


@pytest.mark.parametrize(
    "mode",
    ["sombra", "dry_run"],
)
def test_autoridade_elevada_sem_efeito_real_dispensa_ratificacao(
    mode: str,
) -> None:
    mission = AgentMission(
        **_payload_base(
            authority_level="elevada",
            execution_mode=mode,
        )
    )

    assert mission.execution_mode == mode


# ---------------------------------------------------------------------------
# Temporalidade UTC
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field_name",
    [
        "created_at",
        "deadline",
        "reference_at",
        "idempotency_reference_at",
    ],
)
def test_agent_mission_rejeita_datetime_nao_utc(
    field_name: str,
) -> None:
    non_utc = datetime(
        2026,
        7,
        13,
        9,
        0,
        tzinfo=timezone(timedelta(hours=-3)),
    )
    payload = _payload_base(**{field_name: non_utc})
    if field_name == "idempotency_reference_at":
        payload = _recalcular_derivados(payload)

    with pytest.raises(ValidationError):
        AgentMission(**payload)


@pytest.mark.parametrize(
    "field_name",
    [
        "created_at",
        "deadline",
        "reference_at",
        "idempotency_reference_at",
    ],
)
def test_agent_mission_rejeita_datetime_sem_timezone(
    field_name: str,
) -> None:
    naive = datetime(2026, 7, 13, 12, 0)
    payload = _payload_base(**{field_name: naive})
    if field_name == "idempotency_reference_at":
        payload["idempotency_key"] = "0" * 64

    with pytest.raises(ValidationError):
        AgentMission(**payload)


def test_deadline_nao_pode_anteceder_created_at() -> None:
    with pytest.raises(ValidationError):
        AgentMission(
            **_payload_base(
                deadline=UTC_NOW - timedelta(seconds=1)
            )
        )


def test_deadline_igual_created_at_e_permitido() -> None:
    mission = AgentMission(
        **_payload_base(deadline=UTC_NOW)
    )

    assert mission.deadline == mission.created_at


# ---------------------------------------------------------------------------
# Contexto, hash e serialização
# ---------------------------------------------------------------------------

def test_context_hash_correcto_e_aceite() -> None:
    context = {"a": 1, "nested": {"b": "texto"}}
    mission = AgentMission(
        **_payload_base(
            context=context,
            context_hash=build_context_hash(context),
        )
    )

    assert mission.context_hash == build_context_hash(context)


def test_context_hash_incorrecto_e_rejeitado() -> None:
    with pytest.raises(ValidationError):
        AgentMission(
            **_payload_base(context_hash="0" * 64)
        )


def test_contexto_nao_serializavel_e_rejeitado() -> None:
    context = {"valor": object()}

    with pytest.raises((TypeError, ValidationError)):
        AgentMission(
            **_payload_base(
                context=context,
                context_hash="0" * 64,
            )
        )


def test_modelo_nao_executa_sanitizacao_do_contexto() -> None:
    context = {"email": "pessoa@example.com"}
    mission = AgentMission(
        **_payload_base(
            context=context,
            context_hash=build_context_hash(context),
        )
    )

    assert mission.context == context


# ---------------------------------------------------------------------------
# Idempotência
# ---------------------------------------------------------------------------

def test_idempotency_key_correcta_e_aceite() -> None:
    payload = _payload_base()

    mission = AgentMission(**payload)

    assert mission.idempotency_key == payload["idempotency_key"]


def test_idempotency_key_incorrecta_e_rejeitada() -> None:
    with pytest.raises(ValidationError):
        AgentMission(
            **_payload_base(idempotency_key="0" * 64)
        )


def test_reference_at_nao_altera_idempotencia() -> None:
    first = AgentMission(**_payload_base())
    second = AgentMission(
        **_payload_base(
            mission_id=uuid4(),
            correlation_id=uuid4(),
            reference_at=UTC_NOW + timedelta(days=1),
        )
    )

    assert first.idempotency_key == second.idempotency_key


def test_idempotency_reference_at_altera_idempotencia() -> None:
    reference = UTC_NOW + timedelta(days=1)
    payload = _recalcular_derivados(
        _payload_base(
            idempotency_reference_at=reference,
        )
    )

    mission = AgentMission(**payload)

    assert mission.idempotency_reference_at == reference
    assert mission.idempotency_key != _payload_base()["idempotency_key"]


def test_entity_id_numerico_e_textual_produzem_mesma_chave() -> None:
    numeric = _recalcular_derivados(
        _payload_base(
            scope="documento",
            tenant_id=10,
            entity_type="nfe",
            entity_id=123,
        )
    )
    textual = _recalcular_derivados(
        _payload_base(
            scope="documento",
            tenant_id=10,
            entity_type="nfe",
            entity_id="123",
        )
    )

    assert numeric["idempotency_key"] == textual["idempotency_key"]


# ---------------------------------------------------------------------------
# Contratos partilhados
# ---------------------------------------------------------------------------

def test_agent_mission_aceita_budget_policy_valida() -> None:
    policy = BudgetPolicy(
        allow_llm=True,
        allowed_providers=["local_model"],
        max_calls=1,
        max_input_chars=1000,
        max_output_tokens=100,
    )

    mission = AgentMission(
        **_payload_base(budget_policy=policy)
    )

    assert mission.budget_policy == policy


def test_agent_mission_rejeita_budget_policy_incoerente() -> None:
    with pytest.raises(ValidationError):
        AgentMission(
            **_payload_base(
                budget_policy={
                    "allow_llm": False,
                    "max_calls": 1,
                }
            )
        )


def test_agent_mission_aceita_sources_validas_estruturalmente() -> None:
    source = SourceRef(
        fonte_id="fonte-001",
        uso_pretendido="contexto_llm",
    )

    mission = AgentMission(
        **_payload_base(sources=[source])
    )

    assert mission.sources == [source]


def test_modelo_nao_executa_source_authority_guard() -> None:
    source = SourceRef(
        fonte_id="fonte-inexistente",
        uso_pretendido="fundamentar_decisao",
    )

    mission = AgentMission(
        **_payload_base(sources=[source])
    )

    assert mission.sources == [source]
