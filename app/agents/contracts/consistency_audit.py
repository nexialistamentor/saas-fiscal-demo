"""
app/agents/contracts/consistency_audit.py — ADR-012 B14.3D.

Contratos Pydantic específicos do ConsistencyAuditAgent.
Módulo puro: não importa agentes operacionais, serviços, ORM, BD,
HTTP, filesystem, scheduler, executor ou providers LLM.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)


# ---------------------------------------------------------------------------
# Tipos canónicos
# ---------------------------------------------------------------------------

ConsistencyAuditField = Literal[
    "icms_st_xml",
    "icms_st_motor",
    "mva_xml",
    "mva_motor",
    "base_st_xml",
    "base_st_motor",
]

ConsistencyAuditAlertCode = Literal[
    "ICMS_ST_DIVERGENTE",
    "MVA_DIVERGENTE",
    "BASE_ST_DIVERGENTE",
]

ConsistencyAuditSeverity = Literal["alto"]

ValorComparacao = StrictInt | StrictFloat | None


# ---------------------------------------------------------------------------
# Constantes canónicas imutáveis
# ---------------------------------------------------------------------------

PARES_CANONICOS: tuple[
    tuple[ConsistencyAuditField, ConsistencyAuditField],
    ...,
] = (
    ("icms_st_xml", "icms_st_motor"),
    ("mva_xml", "mva_motor"),
    ("base_st_xml", "base_st_motor"),
)

ORDEM_ALERTAS_CONSISTENCY: tuple[
    ConsistencyAuditAlertCode,
    ...,
] = (
    "ICMS_ST_DIVERGENTE",
    "MVA_DIVERGENTE",
    "BASE_ST_DIVERGENTE",
)

INDICE_ALERTA_CONSISTENCY: Mapping[
    ConsistencyAuditAlertCode,
    int,
] = MappingProxyType(
    {
        codigo: indice
        for indice, codigo in enumerate(ORDEM_ALERTAS_CONSISTENCY)
    }
)

ALERTAS_CONSISTENCY_CANONICOS: Mapping[
    ConsistencyAuditAlertCode,
    tuple[ConsistencyAuditSeverity, str],
] = MappingProxyType(
    {
        "ICMS_ST_DIVERGENTE": (
            "alto",
            (
                "O valor de ICMS-ST declarado no XML diverge do valor "
                "calculado pelo motor fiscal."
            ),
        ),
        "MVA_DIVERGENTE": (
            "alto",
            (
                "A MVA declarada no XML diverge da MVA utilizada "
                "pelo motor fiscal."
            ),
        ),
        "BASE_ST_DIVERGENTE": (
            "alto",
            (
                "A base de cálculo do ICMS-ST declarada no XML diverge "
                "da base calculada pelo motor fiscal."
            ),
        ),
    }
)


# ---------------------------------------------------------------------------
# Contexto
# ---------------------------------------------------------------------------

class ConsistencyAuditContext(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
    )

    empresa_id: StrictInt
    documento_id: StrictInt

    icms_st_xml: ValorComparacao = None
    icms_st_motor: ValorComparacao = None

    mva_xml: ValorComparacao = None
    mva_motor: ValorComparacao = None

    base_st_xml: ValorComparacao = None
    base_st_motor: ValorComparacao = None

    @field_validator(
        "empresa_id",
        "documento_id",
    )
    @classmethod
    def validar_identificador_positivo(
        cls,
        value: int,
    ) -> int:
        if value <= 0:
            raise ValueError(
                "identificador deve ser inteiro positivo"
            )
        return value

    @field_validator(
        "icms_st_xml",
        "icms_st_motor",
        "mva_xml",
        "mva_motor",
        "base_st_xml",
        "base_st_motor",
        mode="before",
    )
    @classmethod
    def rejeitar_coercao_numerica(
        cls,
        value: object,
    ) -> object:
        if value is None:
            return value

        if type(value) not in (int, float):
            raise ValueError(
                "campo de comparação exige int ou float estrito"
            )

        return value

    @model_validator(mode="after")
    def validar_pares(self) -> Self:
        pares_completos = 0

        for campo_xml, campo_motor in PARES_CANONICOS:
            xml_presente = campo_xml in self.model_fields_set
            motor_presente = campo_motor in self.model_fields_set

            if not xml_presente and not motor_presente:
                continue

            if xml_presente != motor_presente:
                raise ValueError(
                    "par de comparação incompleto"
                )

            valor_xml = getattr(self, campo_xml)
            valor_motor = getattr(self, campo_motor)

            if valor_xml is None or valor_motor is None:
                raise ValueError(
                    "par de comparação não admite None explícito"
                )

            for valor in (valor_xml, valor_motor):
                try:
                    convertido = float(valor)
                except (TypeError, ValueError, OverflowError):
                    raise ValueError(
                        "valor não convertível para float"
                    ) from None

                if not math.isfinite(convertido):
                    raise ValueError(
                        "valor de comparação deve ser finito"
                    )

            pares_completos += 1

        if pares_completos == 0:
            raise ValueError(
                "contexto exige pelo menos um par comparável completo"
            )

        return self


# ---------------------------------------------------------------------------
# Alerta canónico
# ---------------------------------------------------------------------------

class ConsistencyAuditAlert(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    codigo: ConsistencyAuditAlertCode
    severidade: ConsistencyAuditSeverity
    mensagem: str

    @model_validator(mode="after")
    def validar_contrato(self) -> Self:
        severidade_esperada, mensagem_esperada = (
            ALERTAS_CONSISTENCY_CANONICOS[self.codigo]
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


def _verificar_ordem_alertas(
    alertas: tuple[ConsistencyAuditAlert, ...],
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
        indice_actual = INDICE_ALERTA_CONSISTENCY[codigo]

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

class ConsistencyAuditPayload(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    analysis_type: Literal[
        "auditoria_consistencia_fiscal"
    ] = "auditoria_consistencia_fiscal"

    schema_type: Literal[
        "ConsistencyAuditPayload"
    ] = "ConsistencyAuditPayload"

    versao: Literal["1.0"] = "1.0"

    empresa_id: StrictInt
    documento_id: StrictInt

    dados_coerentes: StrictBool
    total_alertas: StrictInt
    alertas: tuple[ConsistencyAuditAlert, ...]

    publication_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validar_invariantes(self) -> Self:
        if self.empresa_id <= 0:
            raise ValueError(
                "empresa_id deve ser positivo"
            )

        if self.documento_id <= 0:
            raise ValueError(
                "documento_id deve ser positivo"
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

        if self.dados_coerentes is tem_alertas:
            raise ValueError(
                "dados_coerentes diverge da existência de alertas"
            )

        _verificar_ordem_alertas(self.alertas)
        return self


# ---------------------------------------------------------------------------
# Erros pré-execução
# ---------------------------------------------------------------------------

ConsistencyAuditPreExecutionErrorCode = Literal[
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
    "AG_CONSISTENCY_AUDIT_CONTEXT_INVALID",
]


class ConsistencyAuditPreExecutionError(Exception):
    def __init__(
        self,
        code: ConsistencyAuditPreExecutionErrorCode,
    ) -> None:
        self.code = code
        super().__init__(code)


# ---------------------------------------------------------------------------
# Erros pós-construção
# ---------------------------------------------------------------------------

class ConsistencyAuditResultValidationError(Exception):
    def __init__(self) -> None:
        self.code = "RESULT_MISSION_VALIDATION_FAILED"
        super().__init__(self.code)


class ConsistencyAuditResultSafetyError(Exception):
    def __init__(self) -> None:
        self.code = "RESULT_SANITIZATION_FAILED"
        super().__init__(self.code)
