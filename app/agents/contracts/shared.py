"""
app/agents/contracts/shared.py — ADR-008 B14.0.

Contratos partilhados soberanos dos agentes.
Módulo puro: não importa agentes, serviços, ORM, BD, HTTP ou providers.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, UUID4, field_validator, model_validator


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fonte_id: str
    uso_pretendido: Literal[
        "fundamentar_decisao",
        "validar_fato_operacional",
        "apoiar_explicacao_ux",
        "contexto_llm",
    ]


class BudgetPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_llm: bool = False
    allowed_providers: list[str] = Field(default_factory=list)
    max_calls: int = Field(default=0, ge=0)
    max_input_chars: int = Field(default=0, ge=0)
    max_output_tokens: int = Field(default=0, ge=0)
    max_cost: Decimal = Decimal("0")
    currency: str = "BRL"
    on_unavailable: Literal[
        "deterministic",
        "cache",
        "local_model",
        "queue",
        "human_review",
    ] = "deterministic"

    @field_validator("max_cost", mode="before")
    @classmethod
    def rejeitar_float_em_max_cost(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("max_cost deve usar Decimal; float não é permitido")
        return value

    @field_validator("max_cost")
    @classmethod
    def validar_max_cost_nao_negativo(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise ValueError("max_cost não pode ser negativo")
        return value

    @model_validator(mode="after")
    def validar_coerencia_llm(self) -> Self:
        if not self.allow_llm:
            if self.allowed_providers:
                raise ValueError("allow_llm=False exige allowed_providers vazio")
            if self.max_calls != 0:
                raise ValueError("allow_llm=False exige max_calls=0")
            if self.max_input_chars != 0:
                raise ValueError("allow_llm=False exige max_input_chars=0")
            if self.max_output_tokens != 0:
                raise ValueError("allow_llm=False exige max_output_tokens=0")
            if self.max_cost != Decimal("0"):
                raise ValueError("allow_llm=False exige max_cost=0")
            return self

        if not self.allowed_providers:
            raise ValueError("allow_llm=True exige allowed_providers não vazio")
        if self.max_calls <= 0:
            raise ValueError("allow_llm=True exige max_calls > 0")
        if self.max_input_chars <= 0:
            raise ValueError("allow_llm=True exige max_input_chars > 0")
        if self.max_output_tokens <= 0:
            raise ValueError("allow_llm=True exige max_output_tokens > 0")
        return self


class AgentEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID4 = Field(default_factory=uuid4)
    evidence_type: Literal[
        "log_ref",
        "event_ref",
        "document_ref",
        "source_ref",
        "metric_ref",
        "rule_ref",
    ]
    reference: str
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    redacted: bool = True


class AgentAlert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal[
        "critico",
        "alto",
        "medio",
        "baixo",
        "informativo",
    ]
    message: str
    evidence_refs: list[UUID4] = Field(default_factory=list)


class AgentAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: str
    target_type: str | None = None
    target_id: str | int | None = None
    status: Literal["proposta", "executada", "bloqueada"]
    idempotency_key: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
    )

    @model_validator(mode="after")
    def validar_idempotencia_da_execucao(self) -> Self:
        if self.status == "executada" and self.idempotency_key is None:
            raise ValueError("status='executada' exige idempotency_key")
        return self
