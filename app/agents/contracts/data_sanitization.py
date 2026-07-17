"""
app/agents/contracts/data_sanitization.py — ADR-011 B14.3C.

Contratos Pydantic específicos do DataSanitizationAgent.
Módulo puro: não importa agentes operacionais, ORM, BD,
HTTP, serviços ou providers.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


# ---------------------------------------------------------------------------
# Tipos canónicos
# ---------------------------------------------------------------------------

DataSanitizationField = Literal[
    "faturamento",
    "custos",
    "lucro_contabil",
    "lucro",
    "base_calculo",
    "icms_pago",
    "icms_devido",
    "custo_fiscal_entradas",
]

DataSanitizationAlertCode = Literal[
    "CAMPO_NAO_NUMERICO",
    "CAMPO_NEGATIVO",
    "FATURAMENTO_ACIMA_LIMITE",
    "CONTEXTO_SEM_CAMPOS_FISCAIS",
]

DataSanitizationSeverity = Literal[
    "critico",
    "alto",
]

ValorFiscal = (
    StrictInt
    | StrictFloat
    | StrictStr
    | StrictBool
    | None
)


# ---------------------------------------------------------------------------
# Constantes canónicas imutáveis
# ---------------------------------------------------------------------------

CAMPOS_FISCAIS_CANONICOS: tuple[
    DataSanitizationField,
    ...,
] = (
    "faturamento",
    "custos",
    "lucro_contabil",
    "lucro",
    "base_calculo",
    "icms_pago",
    "icms_devido",
    "custo_fiscal_entradas",
)

ORDEM_ALERTAS_POR_CAMPO: tuple[
    DataSanitizationAlertCode,
    ...,
] = (
    "CAMPO_NAO_NUMERICO",
    "CAMPO_NEGATIVO",
    "FATURAMENTO_ACIMA_LIMITE",
)

INDICE_CAMPO: Mapping[DataSanitizationField, int] = MappingProxyType(
    {
        campo: indice
        for indice, campo in enumerate(CAMPOS_FISCAIS_CANONICOS)
    }
)

INDICE_ALERTA: Mapping[DataSanitizationAlertCode, int] = (
    MappingProxyType(
        {
            codigo: indice
            for indice, codigo in enumerate(ORDEM_ALERTAS_POR_CAMPO)
        }
    )
)

LIMITE_FATURAMENTO: float = 1_000_000_000.0

ALERTAS_SANITIZACAO_CANONICOS: Mapping[
    DataSanitizationAlertCode,
    tuple[DataSanitizationSeverity, str],
] = MappingProxyType(
    {
        "CAMPO_NAO_NUMERICO": (
            "critico",
            (
                "O campo fiscal recebido não contém "
                "um valor numérico válido."
            ),
        ),
        "CAMPO_NEGATIVO": (
            "alto",
            "O campo fiscal recebido contém um valor negativo.",
        ),
        "FATURAMENTO_ACIMA_LIMITE": (
            "alto",
            (
                "O faturamento informado excede o limite "
                "de validação configurado."
            ),
        ),
        "CONTEXTO_SEM_CAMPOS_FISCAIS": (
            "critico",
            "Nenhum campo fiscal foi fornecido para sanitização.",
        ),
    }
)


# ---------------------------------------------------------------------------
# Contexto
# ---------------------------------------------------------------------------

class DataSanitizationContext(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
    )

    empresa_id: StrictInt

    faturamento: ValorFiscal = None
    custos: ValorFiscal = None
    lucro_contabil: ValorFiscal = None
    lucro: ValorFiscal = None
    base_calculo: ValorFiscal = None
    icms_pago: ValorFiscal = None
    icms_devido: ValorFiscal = None
    custo_fiscal_entradas: ValorFiscal = None

    @field_validator("empresa_id")
    @classmethod
    def validar_empresa_id(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("empresa_id deve ser positivo")
        return value


# ---------------------------------------------------------------------------
# Alerta canónico
# ---------------------------------------------------------------------------

class DataSanitizationAlert(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    codigo: DataSanitizationAlertCode
    severidade: DataSanitizationSeverity
    campo: DataSanitizationField | None
    mensagem: str

    @model_validator(mode="after")
    def validar_contrato(self) -> Self:
        severidade_esperada, mensagem_esperada = (
            ALERTAS_SANITIZACAO_CANONICOS[self.codigo]
        )

        if self.severidade != severidade_esperada:
            raise ValueError(
                "severidade diverge da tabela canónica"
            )

        if self.mensagem != mensagem_esperada:
            raise ValueError(
                "mensagem diverge da tabela canónica"
            )

        if self.codigo == "CONTEXTO_SEM_CAMPOS_FISCAIS":
            if self.campo is not None:
                raise ValueError(
                    "CONTEXTO_SEM_CAMPOS_FISCAIS não admite campo"
                )
            return self

        if self.campo is None:
            raise ValueError(
                "alerta de campo requer campo nominal"
            )

        if (
            self.codigo == "FATURAMENTO_ACIMA_LIMITE"
            and self.campo != "faturamento"
        ):
            raise ValueError(
                "FATURAMENTO_ACIMA_LIMITE exige "
                "campo='faturamento'"
            )

        return self


def _verificar_ordem_alertas(
    alertas: tuple[DataSanitizationAlert, ...],
) -> None:
    if not alertas:
        return

    alertas_contexto_vazio = tuple(
        alerta
        for alerta in alertas
        if alerta.codigo == "CONTEXTO_SEM_CAMPOS_FISCAIS"
    )

    if alertas_contexto_vazio:
        if len(alertas) != 1:
            raise ValueError(
                "CONTEXTO_SEM_CAMPOS_FISCAIS deve ser "
                "o único alerta"
            )
        return

    chave_anterior: tuple[int, int] | None = None

    for alerta in alertas:
        if alerta.campo is None:
            raise ValueError(
                "alerta de campo requer campo nominal"
            )

        chave_actual = (
            INDICE_CAMPO[alerta.campo],
            INDICE_ALERTA[alerta.codigo],
        )

        if (
            chave_anterior is not None
            and chave_actual <= chave_anterior
        ):
            raise ValueError(
                "alertas fora da ordem canónica"
            )

        chave_anterior = chave_actual


# ---------------------------------------------------------------------------
# Payload nominal
# ---------------------------------------------------------------------------

class DataSanitizationPayload(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    analysis_type: Literal[
        "sanitizacao_contexto_fiscal"
    ] = "sanitizacao_contexto_fiscal"

    schema_type: Literal[
        "DataSanitizationPayload"
    ] = "DataSanitizationPayload"

    versao: Literal["1.0"] = "1.0"

    empresa_id: StrictInt
    contexto_valido: StrictBool
    total_alertas: StrictInt
    alertas: tuple[DataSanitizationAlert, ...]
    publication_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validar_invariantes(self) -> Self:
        if self.empresa_id <= 0:
            raise ValueError(
                "empresa_id deve ser positivo"
            )

        if self.total_alertas < 0:
            raise ValueError(
                "total_alertas não pode ser negativo"
            )

        if self.total_alertas != len(self.alertas):
            raise ValueError(
                "total_alertas diverge do número de alertas"
            )

        tem_alertas = bool(self.alertas)

        if self.contexto_valido is tem_alertas:
            raise ValueError(
                "contexto_valido diverge da existência de alertas"
            )

        pares = tuple(
            (alerta.codigo, alerta.campo)
            for alerta in self.alertas
        )

        if len(pares) != len(set(pares)):
            raise ValueError(
                "alertas contêm entradas duplicadas"
            )

        _verificar_ordem_alertas(self.alertas)
        return self


# ---------------------------------------------------------------------------
# Erros pré-execução
# ---------------------------------------------------------------------------

AdapterDataSanitizacaoPreExecutionErrorCode = Literal[
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
    "MISSION_ACTOR_TENANT_MISMATCH",
    "MISSION_ENTITY_UNSUPPORTED",
    "MISSION_REQUESTED_BY_UNSUPPORTED",
    "MISSION_AUTHORITY_UNSUPPORTED",
    "MISSION_ORIGIN_UNSUPPORTED",
    "MISSION_BUDGET_UNSUPPORTED",
    "MISSION_SOURCES_UNSUPPORTED",
    "AG_DATA_SANITIZATION_CONTEXT_INVALID",
]


class DataSanitizacaoPreExecutionError(Exception):
    def __init__(
        self,
        code: AdapterDataSanitizacaoPreExecutionErrorCode,
    ) -> None:
        self.code = code
        super().__init__(code)


# ---------------------------------------------------------------------------
# Erros pós-construção
# ---------------------------------------------------------------------------

class DataSanitizacaoResultValidationError(Exception):
    def __init__(self) -> None:
        self.code = "RESULT_MISSION_VALIDATION_FAILED"
        super().__init__(self.code)


class DataSanitizacaoResultSafetyError(Exception):
    def __init__(self) -> None:
        self.code = "RESULT_SANITIZATION_FAILED"
        super().__init__(self.code)
