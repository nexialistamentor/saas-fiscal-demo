"""
app/agents/contracts/execution_result.py — ADR-008 B14.0/B14.1.

Contrato soberano AgentExecutionResult.
Valida apenas invariantes internas do resultado. A validação cruzada com
AgentMission pertence a app.agents.contracts.validation e será chamada
pelo futuro AgentExecutor.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
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

from app.agents.contracts.shared import (
    AgentAction,
    AgentAlert,
    AgentEvidence,
)


class AgentExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["1.0"] = "1.0"

    execution_id: UUID4
    attempt: int = Field(ge=1)

    agent_id: str
    agent_version: str

    mission_type: str
    mission_id: UUID4
    correlation_id: UUID4

    status: Literal[
        "sucesso",
        "erro",
        "bloqueado",
        "pulado",
        "parcial",
    ]

    scope: Literal[
        "global",
        "tenant",
        "documento",
        "utilizador",
    ]

    tenant_id: int | None = None

    started_at: AwareDatetime
    finished_at: AwareDatetime
    duration_ms: int = Field(ge=0)

    mode: Literal[
        "activo",
        "sombra",
        "dry_run",
    ]

    alerts: list[AgentAlert] = Field(default_factory=list)
    evidence: list[AgentEvidence] = Field(default_factory=list)
    actions_proposed: list[AgentAction] = Field(default_factory=list)
    actions_executed: list[AgentAction] = Field(default_factory=list)

    requires_human_review: bool = False

    payload_schema: str
    payload_version: str = "1.0"
    payload: dict = Field(default_factory=dict)

    llm_used: bool = False
    provider: str | None = None
    tokens_used: int | None = Field(default=None, ge=0)

    cost_estimated: Decimal | None = None
    cost_actual: Decimal | None = None
    currency: str | None = None

    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False

    @field_validator(
        "cost_estimated",
        "cost_actual",
        mode="before",
    )
    @classmethod
    def rejeitar_float_em_custos(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, float):
            raise ValueError(
                "custos devem usar Decimal; float não é permitido"
            )
        return value

    @field_validator(
        "cost_estimated",
        "cost_actual",
    )
    @classmethod
    def validar_custos_nao_negativos(
        cls,
        value: Decimal | None,
    ) -> Decimal | None:
        if value is not None and value < Decimal("0"):
            raise ValueError(
                "custos não podem ser negativos"
            )
        return value

    @model_validator(mode="after")
    def validar_escopo(self) -> Self:
        if self.scope == "global":
            if self.tenant_id is not None:
                raise ValueError(
                    "scope='global' exige tenant_id ausente"
                )
            return self

        if self.scope in {"tenant", "documento"}:
            if self.tenant_id is None:
                raise ValueError(
                    f"scope={self.scope!r} exige tenant_id"
                )

        return self

    @model_validator(mode="after")
    def validar_temporalidade(self) -> Self:
        for nome, valor in (
            ("started_at", self.started_at),
            ("finished_at", self.finished_at),
        ):
            if valor.utcoffset() != timedelta(0):
                raise ValueError(
                    f"{nome} deve estar em UTC"
                )

        if self.finished_at < self.started_at:
            raise ValueError(
                "finished_at não pode ser anterior a started_at"
            )

        intervalo_ms = (
            self.finished_at - self.started_at
        ).total_seconds() * 1000

        if abs(self.duration_ms - intervalo_ms) > 1:
            raise ValueError(
                "duration_ms não corresponde ao intervalo "
                "started_at/finished_at com tolerância de 1 ms"
            )

        return self

    @model_validator(mode="after")
    def validar_status_e_modo(self) -> Self:
        if self.status == "erro":
            if self.error_code is None:
                raise ValueError(
                    "status='erro' exige error_code"
                )
            if self.error_message is None:
                raise ValueError(
                    "status='erro' exige error_message"
                )
            if self.actions_executed:
                raise ValueError(
                    "status='erro' exige actions_executed vazio"
                )
        else:
            if self.error_code is not None:
                raise ValueError(
                    "status diferente de 'erro' exige "
                    "error_code ausente"
                )
            if self.error_message is not None:
                raise ValueError(
                    "status diferente de 'erro' exige "
                    "error_message ausente"
                )

        if (
            self.status in {"bloqueado", "pulado"}
            and self.actions_executed
        ):
            raise ValueError(
                f"status={self.status!r} exige "
                "actions_executed vazio"
            )

        if (
            self.mode in {"sombra", "dry_run"}
            and self.actions_executed
        ):
            raise ValueError(
                f"mode={self.mode!r} exige actions_executed vazio"
            )

        for action in self.actions_executed:
            if action.status != "executada":
                raise ValueError(
                    "actions_executed aceita apenas acções "
                    "com status='executada'"
                )

        return self

    @model_validator(mode="after")
    def validar_referencias_de_evidencia(self) -> Self:
        evidence_ids = {
            item.evidence_id
            for item in self.evidence
        }

        for alert in self.alerts:
            for evidence_ref in alert.evidence_refs:
                if evidence_ref not in evidence_ids:
                    raise ValueError(
                        "AgentAlert.evidence_refs contém ID "
                        "ausente em AgentExecutionResult.evidence"
                    )

        return self

    @model_validator(mode="after")
    def validar_metadados_llm(self) -> Self:
        if not self.llm_used:
            campos = {
                "provider": self.provider,
                "tokens_used": self.tokens_used,
                "cost_estimated": self.cost_estimated,
                "cost_actual": self.cost_actual,
                "currency": self.currency,
            }
            preenchidos = [
                nome
                for nome, valor in campos.items()
                if valor is not None
            ]
            if preenchidos:
                raise ValueError(
                    "llm_used=False exige metadados LLM vazios: "
                    + ", ".join(preenchidos)
                )
            return self

        if self.provider is None:
            raise ValueError(
                "llm_used=True exige provider"
            )

        if (
            self.cost_estimated is not None
            or self.cost_actual is not None
        ) and self.currency is None:
            raise ValueError(
                "currency é obrigatória quando existir custo"
            )

        return self
