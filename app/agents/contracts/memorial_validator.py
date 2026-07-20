"""
app/agents/contracts/memorial_validator.py — ADR-013 B14.3E.

Contratos Pydantic específicos do MemorialValidatorAgent.
Módulo puro: não importa agentes operacionais, serviços, ORM, BD,
HTTP, filesystem, scheduler, executor ou providers LLM.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
)


# ---------------------------------------------------------------------------
# Tipos estritos
# ---------------------------------------------------------------------------


def validar_texto_nao_branco(valor: str) -> str:
    """Rejeita texto vazio ou composto apenas por whitespace, sem normalizar."""
    if not valor.strip():
        raise ValueError("texto obrigatório")
    return valor


TextoNaoBranco = Annotated[
    StrictStr,
    AfterValidator(validar_texto_nao_branco),
]

IdPositivo = Annotated[
    StrictInt,
    Field(gt=0),
]

IntNaoNegativo = Annotated[
    StrictInt,
    Field(ge=0),
]


# ---------------------------------------------------------------------------
# Tipos canónicos
# ---------------------------------------------------------------------------

MemorialAlertCode = Literal[
    "MEMORIAL_RELATORIO_AUSENTE",
    "MEMORIAL_ENGINES_VAZIOS",
    "MEMORIAL_REFERENCIAS_VAZIAS",
    "MEMORIAL_REFERENCIA_INCOMPLETA",
    "MEMORIAL_STATUS_ANALISE",
    "MEMORIAL_CONTAGEM_ALERTAS",
]

MemorialAlertSeverity = Literal[
    "critico",
    "alto",
    "medio",
]


# ---------------------------------------------------------------------------
# Constantes canónicas imutáveis
# ---------------------------------------------------------------------------

LIMIAR_ALERTAS_REVISAO: int = 10

ORDEM_ALERTAS_MEMORIAL: tuple[
    MemorialAlertCode,
    ...,
] = (
    "MEMORIAL_RELATORIO_AUSENTE",
    "MEMORIAL_ENGINES_VAZIOS",
    "MEMORIAL_REFERENCIAS_VAZIAS",
    "MEMORIAL_REFERENCIA_INCOMPLETA",
    "MEMORIAL_STATUS_ANALISE",
    "MEMORIAL_CONTAGEM_ALERTAS",
)

INDICE_ALERTA_MEMORIAL: Mapping[
    MemorialAlertCode,
    int,
] = MappingProxyType(
    {
        codigo: indice
        for indice, codigo in enumerate(ORDEM_ALERTAS_MEMORIAL)
    }
)

ALERTAS_MEMORIAL_CANONICOS: Mapping[
    MemorialAlertCode,
    tuple[MemorialAlertSeverity, str],
] = MappingProxyType(
    {
        "MEMORIAL_RELATORIO_AUSENTE": (
            "critico",
            "Relatório não encontrado no contexto do memorial.",
        ),
        "MEMORIAL_ENGINES_VAZIOS": (
            "alto",
            "Nenhum resultado de engine foi encontrado no memorial.",
        ),
        "MEMORIAL_REFERENCIAS_VAZIAS": (
            "alto",
            "A base normativa do memorial está vazia.",
        ),
        "MEMORIAL_REFERENCIA_INCOMPLETA": (
            "medio",
            "Existe referência legal sem fundamento no memorial.",
        ),
        "MEMORIAL_STATUS_ANALISE": (
            "alto",
            "A análise associada ao memorial apresenta estado de erro.",
        ),
        "MEMORIAL_CONTAGEM_ALERTAS": (
            "medio",
            (
                "O relatório associado ao memorial excede o limiar "
                "de alertas para revisão."
            ),
        ),
    }
)


# ---------------------------------------------------------------------------
# Submodelos do contexto
# ---------------------------------------------------------------------------


class MemorialRelatorioSnapshot(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: IdPositivo
    empresa_id: IdPositivo
    status: TextoNaoBranco
    total_alertas: IntNaoNegativo


class MemorialEngineSnapshot(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    engine_nome: TextoNaoBranco


class MemorialReferenciaSnapshot(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    fundamento: StrictStr | None = None


# ---------------------------------------------------------------------------
# Contexto
# ---------------------------------------------------------------------------


class MemorialValidatorContext(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    empresa_id: IdPositivo
    relatorio_id: IdPositivo

    relatorio: MemorialRelatorioSnapshot | None = None
    engines: tuple[MemorialEngineSnapshot, ...]
    referencias_legais: tuple[MemorialReferenciaSnapshot, ...]

    @model_validator(mode="after")
    def validar_coerencia(self) -> Self:
        if self.relatorio is None:
            return self

        if self.relatorio.id != self.relatorio_id:
            raise ValueError(
                "relatorio.id incompatível com relatorio_id"
            )

        if self.relatorio.empresa_id != self.empresa_id:
            raise ValueError(
                "relatorio.empresa_id incompatível com empresa_id"
            )

        return self


# ---------------------------------------------------------------------------
# Alerta canónico
# ---------------------------------------------------------------------------


class MemorialValidatorAlert(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    codigo: MemorialAlertCode
    severidade: MemorialAlertSeverity
    mensagem: StrictStr

    @model_validator(mode="after")
    def validar_contrato(self) -> Self:
        severidade_esperada, mensagem_esperada = (
            ALERTAS_MEMORIAL_CANONICOS[self.codigo]
        )

        if self.severidade != severidade_esperada:
            raise ValueError(
                "severidade diverge da tabela canónica"
            )

        if self.mensagem != mensagem_esperada:
            raise ValueError(
                "mensagem diverge da tabela canónica"
            )

        return self


def _verificar_ordem_alertas_memorial(
    alertas: tuple[MemorialValidatorAlert, ...],
) -> None:
    codigos = tuple(
        alerta.codigo
        for alerta in alertas
    )

    if len(codigos) != len(set(codigos)):
        raise ValueError(
            "alertas contêm códigos duplicados"
        )

    indice_anterior: int | None = None

    for codigo in codigos:
        indice_actual = INDICE_ALERTA_MEMORIAL[codigo]

        if (
            indice_anterior is not None
            and indice_actual <= indice_anterior
        ):
            raise ValueError(
                "alertas fora da ordem canónica"
            )

        indice_anterior = indice_actual


# ---------------------------------------------------------------------------
# Payload nominal
# ---------------------------------------------------------------------------


class MemorialValidatorPayload(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    analysis_type: Literal[
        "validacao_memorial_fiscal"
    ] = "validacao_memorial_fiscal"

    schema_type: Literal[
        "MemorialValidatorPayload"
    ] = "MemorialValidatorPayload"

    versao: Literal["1.0"] = "1.0"

    empresa_id: IdPositivo
    relatorio_id: IdPositivo

    diagnostico_consistente: StrictBool
    total_alertas: IntNaoNegativo
    alertas: tuple[MemorialValidatorAlert, ...]

    publication_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validar_invariantes(self) -> Self:
        if self.total_alertas != len(self.alertas):
            raise ValueError(
                "total_alertas diverge do número de alertas"
            )

        tem_alertas = bool(self.alertas)

        if self.diagnostico_consistente is tem_alertas:
            raise ValueError(
                "diagnostico_consistente diverge da existência de alertas"
            )

        _verificar_ordem_alertas_memorial(self.alertas)
        return self


# ---------------------------------------------------------------------------
# Erros pré-execução
# ---------------------------------------------------------------------------

MemorialValidatorPreExecutionErrorCode = Literal[
    "MISSION_TARGET_MISMATCH",
    "MISSION_TYPE_UNSUPPORTED",
    "CONTEXT_SCHEMA_UNSUPPORTED",
    "CONTEXT_VERSION_UNSUPPORTED",
    "OUTPUT_SCHEMA_UNSUPPORTED",
    "OUTPUT_VERSION_UNSUPPORTED",
    "MISSION_SCOPE_UNSUPPORTED",
    "MISSION_TENANT_REQUIRED",
    "MISSION_TENANT_UNSUPPORTED",
    "MISSION_ACTOR_UNSUPPORTED",
    "MISSION_ENTITY_UNSUPPORTED",
    "MISSION_REQUESTED_BY_UNSUPPORTED",
    "MISSION_AUTHORITY_UNSUPPORTED",
    "MISSION_ORIGIN_UNSUPPORTED",
    "MISSION_BUDGET_UNSUPPORTED",
    "MISSION_SOURCES_UNSUPPORTED",
    "AG_MEMORIAL_VALIDATOR_CONTEXT_INVALID",
]


class MemorialValidatorPreExecutionError(Exception):
    def __init__(
        self,
        code: MemorialValidatorPreExecutionErrorCode,
    ) -> None:
        self.code = code
        super().__init__(code)


# ---------------------------------------------------------------------------
# Erros pós-construção
# ---------------------------------------------------------------------------


class MemorialValidatorResultValidationError(Exception):
    def __init__(self) -> None:
        self.code = "RESULT_MISSION_VALIDATION_FAILED"
        super().__init__(self.code)


class MemorialValidatorResultSafetyError(Exception):
    def __init__(self) -> None:
        self.code = "RESULT_SANITIZATION_FAILED"
        super().__init__(self.code)
