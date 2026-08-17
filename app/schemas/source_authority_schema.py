"""
SourceAuthority Schema — contrato do guarda de autoridade de fontes tributárias.
"""

import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.agents.contracts.canonical import canonical_json as _canonical_json
from typing import Literal, Optional


class SourceAuthorityRequest(BaseModel):
    fonte_id: str
    uso_pretendido: Literal[
        "fundamentar_decisao",
        "validar_fato_operacional",
        "apoiar_explicacao_ux",
        "contexto_llm",
    ]


class SourceAuthorityResult(BaseModel):
    permitido: bool
    fonte_id: str
    nome: Optional[str] = None
    tipo: Optional[str] = None
    uso_pretendido: str
    motivo: str
    acao: Optional[str] = None
    pode_fundamentar_decisao: Optional[bool] = None
    pode_validar_fato_operacional: Optional[bool] = None
    pode_ser_usada_por_llm: Optional[bool] = None

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal


_CONSTANTE_ID_PATTERN = re.compile(
    r"^[A-Z][A-Z0-9_]{2,127}$",
    re.ASCII,
)
_DATASET_ID_PATTERN = re.compile(
    r"^[A-Z][A-Z0-9_]{2,127}$",
    re.ASCII,
)
_FONTE_ID_PATTERN = re.compile(
    r"^[A-Z0-9][A-Z0-9-]{2,127}$",
    re.ASCII,
)
_VERSAO_FONTE_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
    re.ASCII,
)
_JURISDICAO_PATTERN = re.compile(
    r"^BR(?:-[A-Z]{2}(?:-[0-9]{7})?)?$",
    re.ASCII,
)
_INVARIANTE_PATTERN = re.compile(
    r"^[A-Z][A-Z0-9_-]{2,127}$",
    re.ASCII,
)


def _validate_normative_text_representation(value: str) -> str:
    if value != unicodedata.normalize("NFKC", value):
        raise ValueError("texto normativo muda sob NFKC")
    if value != value.strip():
        raise ValueError("texto normativo possui whitespace externo")
    if any(
        unicodedata.category(char).startswith("C")
        for char in value
    ):
        raise ValueError("texto normativo possui caractere de controle")
    return value


def _validate_normative_identifier(
    value: str,
    pattern: re.Pattern[str],
) -> str:
    _validate_normative_text_representation(value)
    if pattern.fullmatch(value) is None:
        raise ValueError("gramatica normativa invalida")
    return value


class NormativeBindingUsage(str, Enum):
    diagnostico = "diagnostico"
    estimativa = "estimativa"
    decisao_definitiva = "decisao_definitiva"


class NormativeBindingStatus(str, Enum):
    invalido = "invalido"
    valido_sem_autoridade_decisoria = "valido_sem_autoridade_decisoria"
    valido_com_autoridade_decisoria = "valido_com_autoridade_decisoria"


class NormativeBindingReasonCode(str, Enum):
    CAMPO_OBRIGATORIO_AUSENTE = "CAMPO_OBRIGATORIO_AUSENTE"
    CAMPO_DESCONHECIDO = "CAMPO_DESCONHECIDO"
    ALVO_NORMATIVO_AUSENTE = "ALVO_NORMATIVO_AUSENTE"
    ALVO_NORMATIVO_AMBIGUO = "ALVO_NORMATIVO_AMBIGUO"
    ALVO_FORA_DO_ESCOPO_DA_FONTE = "ALVO_FORA_DO_ESCOPO_DA_FONTE"
    CONTEXTO_INVALIDO = "CONTEXTO_INVALIDO"
    IDENTIFICADOR_INVALIDO = "IDENTIFICADOR_INVALIDO"
    VERSAO_INVALIDA = "VERSAO_INVALIDA"
    VERSAO_FONTE_INCOMPATIVEL = "VERSAO_FONTE_INCOMPATIVEL"
    VIGENCIA_INVALIDA = "VIGENCIA_INVALIDA"
    VIGENCIA_FONTE_INCOMPATIVEL = "VIGENCIA_FONTE_INCOMPATIVEL"
    FORA_DA_VIGENCIA = "FORA_DA_VIGENCIA"
    JURISDICAO_INVALIDA = "JURISDICAO_INVALIDA"
    JURISDICAO_INCOMPATIVEL = "JURISDICAO_INCOMPATIVEL"
    RISCO_INVALIDO = "RISCO_INVALIDO"
    RISCO_FONTE_INCOMPATIVEL = "RISCO_FONTE_INCOMPATIVEL"
    INVARIANTES_INVALIDOS = "INVARIANTES_INVALIDOS"
    BINDING_DUPLICADO = "BINDING_DUPLICADO"
    BINDINGS_CONFLITANTES = "BINDINGS_CONFLITANTES"
    FONTE_INEXISTENTE = "FONTE_INEXISTENTE"
    FONTE_INCOMPLETA = "FONTE_INCOMPLETA"
    FONTE_NAO_AUTORIZADA = "FONTE_NAO_AUTORIZADA"
    DECISAO_DEFINITIVA_BLOQUEADA = "DECISAO_DEFINITIVA_BLOQUEADA"


class NormativeBindingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    constante_id: str
    fonte_id: str
    versao_fonte: str
    vigencia_inicio: date
    vigencia_fim: date | None
    jurisdicao_codigo: str
    risco: Literal["alto", "baixo", "critico", "medio"]
    invariantes: Annotated[
        tuple[str, ...], Field(min_length=1)
    ]

    @field_validator("constante_id")
    @classmethod
    def _validate_constante_id(cls, value: str) -> str:
        return _validate_normative_identifier(
            value, _CONSTANTE_ID_PATTERN
        )

    @field_validator("fonte_id")
    @classmethod
    def _validate_fonte_id(cls, value: str) -> str:
        return _validate_normative_identifier(
            value, _FONTE_ID_PATTERN
        )

    @field_validator("versao_fonte")
    @classmethod
    def _validate_versao_fonte(cls, value: str) -> str:
        return _validate_normative_identifier(
            value, _VERSAO_FONTE_PATTERN
        )

    @field_validator("jurisdicao_codigo")
    @classmethod
    def _validate_jurisdicao_codigo(cls, value: str) -> str:
        return _validate_normative_identifier(
            value, _JURISDICAO_PATTERN
        )

    @field_validator("invariantes")
    @classmethod
    def _validate_invariantes_representation(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for item in value:
            _validate_normative_identifier(
                item, _INVARIANTE_PATTERN
            )
        if len(set(value)) != len(value):
            raise ValueError("invariantes devem ser unicos")
        if value != tuple(sorted(value)):
            raise ValueError("invariantes devem estar ordenados")
        return value

    @field_validator("vigencia_inicio", mode="before")
    @classmethod
    def _validate_vigencia_inicio_iso_string(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, datetime):
            raise ValueError("vigencia_inicio nao aceita datetime")
        if isinstance(value, str) and (
            len(value) != 10
            or value[4] != "-"
            or value[7] != "-"
        ):
            raise ValueError("vigencia_inicio deve usar YYYY-MM-DD")
        return value

    @field_validator("vigencia_fim", mode="before")
    @classmethod
    def _validate_vigencia_fim_iso_string(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, datetime):
            raise ValueError("vigencia_fim nao aceita datetime")
        if isinstance(value, str) and (
            len(value) != 10
            or value[4] != "-"
            or value[7] != "-"
        ):
            raise ValueError("vigencia_fim deve usar YYYY-MM-DD")
        return value


class NormativeDatasetBindingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    fonte_id: str
    versao_fonte: str
    vigencia_inicio: date
    vigencia_fim: date | None
    jurisdicao_codigo: str
    risco: Literal["alto", "baixo", "critico", "medio"]
    invariantes: Annotated[
        tuple[str, ...], Field(min_length=1)
    ]

    @field_validator("dataset_id")
    @classmethod
    def _validate_dataset_id(cls, value: str) -> str:
        return _validate_normative_identifier(
            value, _DATASET_ID_PATTERN
        )

    @field_validator("fonte_id")
    @classmethod
    def _validate_fonte_id(cls, value: str) -> str:
        return _validate_normative_identifier(
            value, _FONTE_ID_PATTERN
        )

    @field_validator("versao_fonte")
    @classmethod
    def _validate_versao_fonte(cls, value: str) -> str:
        return _validate_normative_identifier(
            value, _VERSAO_FONTE_PATTERN
        )

    @field_validator("jurisdicao_codigo")
    @classmethod
    def _validate_jurisdicao_codigo(cls, value: str) -> str:
        return _validate_normative_identifier(
            value, _JURISDICAO_PATTERN
        )

    @field_validator("invariantes")
    @classmethod
    def _validate_invariantes_representation(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for item in value:
            _validate_normative_identifier(
                item, _INVARIANTE_PATTERN
            )
        if len(set(value)) != len(value):
            raise ValueError("invariantes devem ser unicos")
        if value != tuple(sorted(value)):
            raise ValueError("invariantes devem estar ordenados")
        return value

    @field_validator("vigencia_inicio", mode="before")
    @classmethod
    def _validate_vigencia_inicio_iso_string(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, datetime):
            raise ValueError("vigencia_inicio nao aceita datetime")
        if isinstance(value, str) and (
            len(value) != 10
            or value[4] != "-"
            or value[7] != "-"
        ):
            raise ValueError("vigencia_inicio deve usar YYYY-MM-DD")
        return value

    @field_validator("vigencia_fim", mode="before")
    @classmethod
    def _validate_vigencia_fim_iso_string(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, datetime):
            raise ValueError("vigencia_fim nao aceita datetime")
        if isinstance(value, str) and (
            len(value) != 10
            or value[4] != "-"
            or value[7] != "-"
        ):
            raise ValueError("vigencia_fim deve usar YYYY-MM-DD")
        return value


class NormativeBindingContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_referencia: date
    jurisdicao_codigo: str
    uso_solicitado: NormativeBindingUsage

    @field_validator("jurisdicao_codigo")
    @classmethod
    def _validate_jurisdicao_representation(
        cls,
        value: str,
    ) -> str:
        return _validate_normative_identifier(
            value, _JURISDICAO_PATTERN
        )

    @field_validator("data_referencia", mode="before")
    @classmethod
    def _validate_data_referencia_iso_string(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, datetime):
            raise ValueError("data_referencia nao aceita datetime")
        if isinstance(value, str) and (
            len(value) != 10
            or value[4] != "-"
            or value[7] != "-"
        ):
            raise ValueError("data_referencia deve usar YYYY-MM-DD")
        return value


class NormativeBindingBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contexto: NormativeBindingContext
    bindings: Annotated[
        tuple[
            NormativeBindingItem | NormativeDatasetBindingItem,
            ...,
        ],
        Field(min_length=1),
    ]


class NormativeBindingReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: NormativeBindingReasonCode
    binding_index: int | None
    field: str | None

    @field_validator("field")
    @classmethod
    def _validate_reason_field_representation(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return _validate_normative_text_representation(value)


class NormativeBindingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: NormativeBindingStatus
    autorizado_fundamentar_decisao: bool
    reasons: tuple[NormativeBindingReason, ...]
    bindings_validados: Annotated[int, Field(ge=0)]

    def canonical_json(self) -> str:
        return _canonical_json(self)
