"""
app/agents/contracts/mission.py — ADR-008 B14.0/B14.1.

Contrato soberano AgentMission.
O modelo valida invariantes estruturais, temporalidade, hash de contexto
e idempotência. A sanitização e a autoridade das fontes pertencem à
MissionFactory.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    UUID4,
    field_validator,
    model_validator,
)

from app.agents.contracts.canonical import (
    build_context_hash,
    build_mission_idempotency_key,
)
from app.agents.contracts.shared import BudgetPolicy, SourceRef


class AgentMission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["1.0"] = "1.0"

    mission_id: UUID4
    correlation_id: UUID4
    mission_type: str
    target_agent: str

    context_schema: str
    context_version: str = "1.0"
    output_schema: str
    output_version: str = "1.0"

    scope: Literal[
        "global",
        "tenant",
        "documento",
        "utilizador",
    ]
    tenant_id: int | None = None
    actor_id: str | int | None = None
    entity_type: str | None = None
    entity_id: str | int | None = None

    source_event_id: UUID4 | None = None
    schedule_slot: str | None = None
    source_request_id: str | None = None
    parent_mission_id: UUID4 | None = None
    requested_by: Literal[
        "system",
        "user",
        "scheduler",
        "agent",
        "admin",
    ]

    context: dict = Field(default_factory=dict)
    context_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    authority_level: Literal[
        "leitura",
        "proposta",
        "execucao",
        "elevada",
    ]
    execution_mode: Literal[
        "activo",
        "sombra",
        "dry_run",
    ]
    ratification_id: str | None = None
    authorized_by: str | int | None = None
    authorization_role: str | None = None

    idempotency_key: str = Field(pattern=r"^[a-f0-9]{64}$")

    agent_version_required: str | None = None

    priority: Literal[
        "critica",
        "alta",
        "normal",
        "baixa",
    ]
    created_at: AwareDatetime
    deadline: AwareDatetime | None = None
    reference_at: AwareDatetime | None = None
    idempotency_reference_at: AwareDatetime | None = None

    budget_policy: BudgetPolicy = Field(default_factory=BudgetPolicy)
    sources: list[SourceRef] = Field(default_factory=list)

    @field_validator(
        "schedule_slot",
        "source_request_id",
        mode="before",
    )
    @classmethod
    def normalizar_origem_textual(
        cls,
        value: object,
    ) -> object:
        if value is None or not isinstance(value, str):
            return value
        return value.strip() or None

    @model_validator(mode="after")
    def validar_escopo(self) -> Self:
        if self.scope == "global":
            if self.tenant_id is not None:
                raise ValueError(
                    "scope='global' exige tenant_id ausente"
                )
            return self

        if self.scope == "tenant":
            if self.tenant_id is None:
                raise ValueError(
                    "scope='tenant' exige tenant_id"
                )
            return self

        if self.scope == "documento":
            ausentes: list[str] = []
            if self.tenant_id is None:
                ausentes.append("tenant_id")
            if self.entity_type is None:
                ausentes.append("entity_type")
            if self.entity_id is None:
                ausentes.append("entity_id")
            if ausentes:
                raise ValueError(
                    "scope='documento' exige "
                    + ", ".join(ausentes)
                )
            return self

        if self.scope == "utilizador" and self.actor_id is None:
            raise ValueError(
                "scope='utilizador' exige actor_id"
            )

        return self

    @model_validator(mode="after")
    def validar_origem_unica(self) -> Self:
        origens = (
            self.source_event_id,
            self.schedule_slot,
            self.source_request_id,
        )
        quantidade = sum(
            origem is not None
            for origem in origens
        )
        if quantidade != 1:
            raise ValueError(
                "AgentMission exige exactamente uma origem "
                "entre source_event_id, schedule_slot "
                "e source_request_id"
            )
        return self

    @model_validator(mode="after")
    def validar_autoridade(self) -> Self:
        if (
            self.authority_level == "elevada"
            and self.execution_mode == "activo"
        ):
            ausentes: list[str] = []
            if self.ratification_id is None:
                ausentes.append("ratification_id")
            if self.authorized_by is None:
                ausentes.append("authorized_by")
            if self.authorization_role is None:
                ausentes.append("authorization_role")
            if ausentes:
                raise ValueError(
                    "authority_level='elevada' com "
                    "execution_mode='activo' exige "
                    + ", ".join(ausentes)
                )
        return self

    @model_validator(mode="after")
    def validar_temporalidade(self) -> Self:
        campos = {
            "created_at": self.created_at,
            "deadline": self.deadline,
            "reference_at": self.reference_at,
            "idempotency_reference_at": (
                self.idempotency_reference_at
            ),
        }
        for nome, valor in campos.items():
            if (
                valor is not None
                and valor.utcoffset() != timedelta(0)
            ):
                raise ValueError(
                    f"{nome} deve estar em UTC"
                )

        if (
            self.deadline is not None
            and self.deadline < self.created_at
        ):
            raise ValueError(
                "deadline não pode ser anterior a created_at"
            )
        return self

    @model_validator(mode="after")
    def validar_hash_e_idempotencia(self) -> Self:
        context_hash_esperado = build_context_hash(
            self.context
        )
        if self.context_hash != context_hash_esperado:
            raise ValueError(
                "context_hash não corresponde ao contexto"
            )

        idempotency_key_esperada = (
            build_mission_idempotency_key(
                mission_type=self.mission_type,
                target_agent=self.target_agent,
                scope=self.scope,
                tenant_id=self.tenant_id,
                entity_type=self.entity_type,
                entity_id=self.entity_id,
                source_event_id=self.source_event_id,
                schedule_slot=self.schedule_slot,
                source_request_id=self.source_request_id,
                idempotency_reference_at=(
                    self.idempotency_reference_at
                ),
                contract_version=self.contract_version,
            )
        )
        if self.idempotency_key != idempotency_key_esperada:
            raise ValueError(
                "idempotency_key não corresponde à missão"
            )

        return self
