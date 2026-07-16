"""
app/agents/contracts/ag_abertura.py — ADR-009 B14.3A.

Contratos Pydantic específicos do canário AgAberturaAgent.
Módulo puro: não importa agentes operacionais, ORM, BD, HTTP, serviços ou providers.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)


# ---------------------------------------------------------------------------
# Contexto
# ---------------------------------------------------------------------------

TIPOS_VALIDOS: frozenset[str] = frozenset({
    "mei",
    "me",
    "epp",
    "empresa",
    "ltda",
    "slu",
    "ei",
})


class AgAberturaContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo_contribuinte: str = "mei"

    @field_validator("tipo_contribuinte", mode="before")
    @classmethod
    def validar_tipo(cls, value: object) -> str:
        if value is None:
            raise ValueError("tipo_contribuinte não pode ser None")
        if isinstance(value, bool):
            raise ValueError("tipo_contribuinte deve ser str")
        if not isinstance(value, str):
            raise ValueError("tipo_contribuinte deve ser str")
        normalizado = value.strip().casefold()
        if not normalizado:
            raise ValueError("tipo_contribuinte não pode ser vazio")
        if normalizado not in TIPOS_VALIDOS:
            raise ValueError("tipo_contribuinte não reconhecido")
        return normalizado


# ---------------------------------------------------------------------------
# Checklist
# ---------------------------------------------------------------------------

class AgAberturaChecklistItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    passo: int
    titulo: str
    descricao: str
    link: str | None = None


# ---------------------------------------------------------------------------
# Allowlist soberana de links
# ---------------------------------------------------------------------------

EXPECTED_LINKS: dict[str, str] = {
    "portal_empreendedor": (
        "https://www.gov.br/empresas-e-negocios/pt-br/empreendedor"
    ),
    "redesim": "https://redesim.gov.br",
    "receita_federal": "https://www.gov.br/receitafederal",
}

EXPECTED_LINK_CODES: tuple[str, ...] = tuple(EXPECTED_LINKS)


class AgAberturaLink(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Literal[
        "portal_empreendedor",
        "redesim",
        "receita_federal",
    ]
    url: str

    @model_validator(mode="after")
    def validar_allowlist(self) -> Self:
        if not self.url.startswith("https://"):
            raise ValueError("link deve usar HTTPS")
        if self.url != EXPECTED_LINKS[self.code]:
            raise ValueError("link divergente da allowlist soberana")
        return self


# ---------------------------------------------------------------------------
# Divulgação comercial
# ---------------------------------------------------------------------------

class CommercialDisclosure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform_service_requires_payment: Literal[True] = True
    official_process_cost_separate: Literal[True] = True
    pricing_status: Literal["pendente_ratificacao"] = "pendente_ratificacao"
    pricing_policy_id: None = None
    price_amount: None = None
    currency: Literal["BRL"] = "BRL"
    requires_explicit_consent: Literal[True] = True


# ---------------------------------------------------------------------------
# Razões de revisão
# ---------------------------------------------------------------------------

ReviewReason = Literal[
    "NORMATIVE_SOURCES_MISSING",
    "COMMERCIAL_POLICY_PENDING",
    "TEMPORAL_HARDCODE_PRESENT",
]

EXPECTED_REVIEW_REASONS: tuple[ReviewReason, ...] = (
    "NORMATIVE_SOURCES_MISSING",
    "COMMERCIAL_POLICY_PENDING",
    "TEMPORAL_HARDCODE_PRESENT",
)


# ---------------------------------------------------------------------------
# Payload nominal
# ---------------------------------------------------------------------------

class AgAberturaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    resposta: str
    analysis_type: str
    schema_type: str
    versao: str
    tipo_contribuinte: str

    checklist: tuple[AgAberturaChecklistItem, ...]
    avisos_legais: tuple[str, ...]
    links_uteis: tuple[AgAberturaLink, ...]

    commercial_disclosure: CommercialDisclosure
    review_reasons: tuple[ReviewReason, ...]
    publication_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validar_invariantes_canarios(self) -> Self:
        if self.review_reasons != EXPECTED_REVIEW_REASONS:
            raise ValueError(
                "review_reasons deve conter exactamente as três "
                "razões canónicas, na ordem ratificada"
            )

        codes = tuple(link.code for link in self.links_uteis)
        if codes != EXPECTED_LINK_CODES:
            raise ValueError(
                "links_uteis deve conter exactamente a allowlist "
                "soberana, na ordem canónica"
            )

        return self


# ---------------------------------------------------------------------------
# Erros pré-execução
# ---------------------------------------------------------------------------

AdapterPreExecutionErrorCode = Literal[
    "MISSION_TARGET_MISMATCH",
    "MISSION_TYPE_UNSUPPORTED",
    "CONTEXT_SCHEMA_UNSUPPORTED",
    "CONTEXT_VERSION_UNSUPPORTED",
    "OUTPUT_SCHEMA_UNSUPPORTED",
    "OUTPUT_VERSION_UNSUPPORTED",
    "MISSION_SCOPE_UNSUPPORTED",
    "MISSION_ACTOR_UNSUPPORTED",
    "MISSION_AUTHORITY_UNSUPPORTED",
    "MISSION_ORIGIN_UNSUPPORTED",
    "MISSION_BUDGET_UNSUPPORTED",
    "MISSION_SOURCES_UNSUPPORTED",
    "AG_ABERTURA_CONTEXT_INVALID",
]


class AgAberturaPreExecutionError(Exception):
    def __init__(self, code: AdapterPreExecutionErrorCode) -> None:
        self.code = code
        super().__init__(code)


# ---------------------------------------------------------------------------
# Erros pós-construção
# ---------------------------------------------------------------------------

class AgAberturaResultValidationError(Exception):
    def __init__(self) -> None:
        self.code = "RESULT_MISSION_VALIDATION_FAILED"
        super().__init__(self.code)


class AgAberturaResultSafetyError(Exception):
    def __init__(self) -> None:
        self.code = "RESULT_SANITIZATION_FAILED"
        super().__init__(self.code)
