"""
app/agents/mission_factory.py — ADR-008 B14.0/B14.1.

Porta obrigatória para criação operacional de AgentMission.
A factory sanitiza o contexto, valida fontes soberanas, valida políticas,
calcula hashes e gera as identidades da missão. Não activa agentes,
scheduler, providers LLM nem efeitos de domínio.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from app.agents.contracts.canonical import (
    build_context_hash,
    build_mission_idempotency_key,
)
from app.agents.contracts.mission import AgentMission
from app.agents.contracts.sanitization import assert_context_sanitized
from app.agents.contracts.shared import BudgetPolicy, SourceRef
from app.schemas.source_authority_schema import SourceAuthorityRequest
from app.services.source_authority_guard import verificar as verificar_fonte


Scope = Literal[
    "global",
    "tenant",
    "documento",
    "utilizador",
]
RequestedBy = Literal[
    "system",
    "user",
    "scheduler",
    "agent",
    "admin",
]
AuthorityLevel = Literal[
    "leitura",
    "proposta",
    "execucao",
    "elevada",
]
ExecutionMode = Literal[
    "activo",
    "sombra",
    "dry_run",
]
Priority = Literal[
    "critica",
    "alta",
    "normal",
    "baixa",
]


def _validar_escopo(
    *,
    scope: Scope,
    tenant_id: int | None,
    actor_id: str | int | None,
    entity_type: str | None,
    entity_id: str | int | None,
) -> None:
    if scope == "global":
        if tenant_id is not None:
            raise ValueError(
                "scope='global' exige tenant_id ausente"
            )
        return

    if scope == "tenant":
        if tenant_id is None:
            raise ValueError(
                "scope='tenant' exige tenant_id"
            )
        return

    if scope == "documento":
        ausentes: list[str] = []
        if tenant_id is None:
            ausentes.append("tenant_id")
        if entity_type is None:
            ausentes.append("entity_type")
        if entity_id is None:
            ausentes.append("entity_id")
        if ausentes:
            raise ValueError(
                "scope='documento' exige "
                + ", ".join(ausentes)
            )
        return

    if scope == "utilizador":
        if actor_id is None:
            raise ValueError(
                "scope='utilizador' exige actor_id"
            )
        return

    raise ValueError(f"scope não reconhecido: {scope!r}")


def _normalizar_budget_policy(
    budget_policy: BudgetPolicy | dict | None,
) -> BudgetPolicy:
    if budget_policy is None:
        return BudgetPolicy()
    return BudgetPolicy.model_validate(budget_policy)


def _normalizar_e_validar_fontes(
    sources: list[SourceRef | dict] | None,
) -> list[SourceRef]:
    fontes = [
        SourceRef.model_validate(source)
        for source in (sources or [])
    ]

    for fonte in fontes:
        request = SourceAuthorityRequest(
            fonte_id=fonte.fonte_id,
            uso_pretendido=fonte.uso_pretendido,
        )
        result = verificar_fonte(request)
        if not result.permitido:
            raise ValueError(
                "SourceAuthorityGuard bloqueou criação da missão: "
                f"fonte_id={fonte.fonte_id!r}; "
                f"uso_pretendido={fonte.uso_pretendido!r}; "
                f"motivo={result.motivo}"
            )

    return fontes


def create_agent_mission(
    *,
    mission_type: str,
    target_agent: str,
    context: dict,
    context_schema: str,
    output_schema: str,
    scope: Scope,
    requested_by: RequestedBy,
    authority_level: AuthorityLevel,
    execution_mode: ExecutionMode,
    source_event_id: UUID | None = None,
    schedule_slot: str | None = None,
    source_request_id: str | None = None,
    context_version: str = "1.0",
    output_version: str = "1.0",
    tenant_id: int | None = None,
    actor_id: str | int | None = None,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    parent_mission_id: UUID | None = None,
    ratification_id: str | None = None,
    authorized_by: str | int | None = None,
    authorization_role: str | None = None,
    agent_version_required: str | None = None,
    priority: Priority = "normal",
    created_at: datetime | None = None,
    deadline: datetime | None = None,
    reference_at: datetime | None = None,
    idempotency_reference_at: datetime | None = None,
    budget_policy: BudgetPolicy | dict | None = None,
    sources: list[SourceRef | dict] | None = None,
    correlation_id: UUID | None = None,
) -> AgentMission:
    """
    Cria uma AgentMission validada pelo caminho operacional obrigatório.

    Não executa a missão e não chama scheduler, AgentExecutor ou LLM.
    """
    _validar_escopo(
        scope=scope,
        tenant_id=tenant_id,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )

    assert_context_sanitized(context)

    fontes_validadas = _normalizar_e_validar_fontes(sources)
    politica_validada = _normalizar_budget_policy(budget_policy)

    context_hash = build_context_hash(context)
    idempotency_key = build_mission_idempotency_key(
        mission_type=mission_type,
        target_agent=target_agent,
        scope=scope,
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        source_event_id=source_event_id,
        schedule_slot=schedule_slot,
        source_request_id=source_request_id,
        idempotency_reference_at=idempotency_reference_at,
        contract_version="1.0",
    )

    return AgentMission(
        contract_version="1.0",
        mission_id=uuid4(),
        correlation_id=correlation_id or uuid4(),
        mission_type=mission_type,
        target_agent=target_agent,
        context_schema=context_schema,
        context_version=context_version,
        output_schema=output_schema,
        output_version=output_version,
        scope=scope,
        tenant_id=tenant_id,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        source_event_id=source_event_id,
        schedule_slot=schedule_slot,
        source_request_id=source_request_id,
        parent_mission_id=parent_mission_id,
        requested_by=requested_by,
        context=context,
        context_hash=context_hash,
        authority_level=authority_level,
        execution_mode=execution_mode,
        ratification_id=ratification_id,
        authorized_by=authorized_by,
        authorization_role=authorization_role,
        idempotency_key=idempotency_key,
        agent_version_required=agent_version_required,
        priority=priority,
        created_at=created_at or datetime.now(timezone.utc),
        deadline=deadline,
        reference_at=reference_at,
        idempotency_reference_at=idempotency_reference_at,
        budget_policy=politica_validada,
        sources=fontes_validadas,
    )
