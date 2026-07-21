"""
app/agents/contracts/agent_erro_operacional.py — ADR-014 B14.3F.

Contratos Pydantic específicos do AgentErroOperacional L3.
Módulo puro: não importa o agente legado, outros agentes, adapters,
engines, readers, serviços, ORM, BD, HTTP, filesystem, scheduler,
registry, executor, BudgetGuard, LLMRouter ou providers LLM.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    UUID4,
    model_validator,
)


# ---------------------------------------------------------------------------
# Expressões canónicas fechadas
# ---------------------------------------------------------------------------

_TIPO_EVENTO_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")

_ORIGEM_OPERACIONAL_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")

_ENDPOINT_TEMPLATE_RE = re.compile(r"^/[A-Za-z0-9/_\-.:{}]*$")

_ATRIBUICAO_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*\s*="
)

_CREDENCIAL_RE = re.compile(
    r"(?i)\b("
    r"password|senha|secret|credential|credencial"
    r"|token|api[_-]?key|authorization|cookie|bearer"
    r")\b"
)

_SQL_PADROES_ESTRUTURAIS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?is)\bselect\b(?:"
        r"\s+(?:\*|[A-Za-z_][A-Za-z0-9_.]*"
        r"(?:\s*,\s*[A-Za-z_][A-Za-z0-9_.]*)*"
        r"|[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\))\s+from\b"
        r"|\s+(?:\d+(?:\.\d+)?|\'(?:\'\'|[^\'])*\'"
        r'|"(?:""|[^"])*")\s*;?\s*$'
        r")"
    ),
    re.compile(r"(?i)\binsert\s+into\b"),
    re.compile(r"(?i)\bupdate\b[\s\S]*?\bset\b"),
    re.compile(r"(?i)\bdelete\s+from\b"),
    re.compile(r"(?i)\bdrop\s+table\b"),
    re.compile(r"(?i)\bcreate\s+table\b"),
    re.compile(r"(?i)\bcreate\s+index\b"),
    re.compile(r"(?i)\balter\s+table\b"),
    re.compile(r"(?i)\btruncate\s+table\b"),
    re.compile(r"(?i)\bmerge\s+into\b"),
    re.compile(r"(?i)\bgrant\b[\s\S]*?\bon\b"),
    re.compile(r"(?i)\brevoke\b[\s\S]*?\bon\b"),
    re.compile(r"(?i)\bexec(?:ute)?\b\s+\w+"),
    re.compile(r"(?i)\bcall\b\s+\w+\s*\("),
    re.compile(r"(?i)\bcopy\b\s+\w+\s+from\b"),
    re.compile(r"(?i)\binformation_schema\b"),
)


def _mensagem_contem_sql(valor: str) -> bool:
    """
    Detecta estruturas reais de comandos SQL, não palavras isoladas.

    Palavras como "from", "where", "join", "update", "call" ou "copy"
    só são consideradas prova de SQL quando aparecem na sintaxe
    estrutural do comando correspondente (ex.: "update ... set",
    "call nome(", "copy tabela from"), nunca isoladamente.
    """
    return any(
        padrao.search(valor) for padrao in _SQL_PADROES_ESTRUTURAIS
    )


_XML_INLINE_RE = re.compile(
    r"<\?xml|<nfeProc|<NFe\b",
    re.IGNORECASE,
)

_TRACEBACK_INLINE_RE = re.compile(
    r"Traceback \(most recent call last\)",
    re.IGNORECASE,
)

_VITE_API_URL_MENCAO_RE = re.compile(
    r"(?i)vite_api_url"
)

MENSAGENS_VITE_API_URL_PERMITIDAS: tuple[str, ...] = (
    "VITE_API_URL não definida no Vercel",
    "variável de ambiente VITE_API_URL ausente",
)



def _mensagem_e_json_estruturado(valor: str) -> bool:
    """
    Detecta corpo HTTP estruturado (objecto ou lista JSON) inteiro
    na mensagem, sem expor o conteúdo desserializado.
    """
    stripped = valor.strip()

    if not stripped or stripped[0] not in "{[":
        return False

    try:
        parsed = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return False

    return isinstance(parsed, (dict, list))


# ---------------------------------------------------------------------------
# Validadores de tipos estritos
# ---------------------------------------------------------------------------


def validar_texto_nao_branco(valor: str) -> str:
    """Rejeita texto vazio ou composto apenas por whitespace, sem normalizar."""
    if not valor.strip():
        raise ValueError("texto obrigatório")
    return valor


def validar_tipo_evento(valor: str) -> str:
    """Rejeita tipo de evento fora do conjunto fechado de caracteres."""
    validar_texto_nao_branco(valor)

    if not _TIPO_EVENTO_RE.fullmatch(valor):
        raise ValueError("tipo com caracteres proibidos")

    return valor


def validar_origem_operacional(valor: str) -> str:
    """Rejeita origem fora do conjunto fechado de caracteres."""
    validar_texto_nao_branco(valor)

    if not _ORIGEM_OPERACIONAL_RE.fullmatch(valor):
        raise ValueError("origem com caracteres proibidos")

    return valor


def validar_mensagem_operacional(valor: str) -> str:
    """
    Rejeita mensagem vazia, branca ou portadora de conteúdo sensível.

    Se "VITE_API_URL" ocorrer na mensagem, sob qualquer capitalização,
    a mensagem inteira deve corresponder exactamente a uma das duas
    formas nominais permitidas — qualquer outra ocorrência é
    rejeitada, incluindo atribuições, valores, dois-pontos, prefixos
    ou sufixos.

    Fora desse caso, qualquer atribuição de variável (mesmo vazia,
    com ou sem espaços em torno de "="), credencial, cabeçalho de
    autorização ou cookie, comando SQL, corpo estruturado em JSON,
    XML bruto ou traceback é rejeitado fail-closed, sem mascarar,
    truncar ou reescrever a entrada.
    """
    validar_texto_nao_branco(valor)

    if _VITE_API_URL_MENCAO_RE.search(valor):
        if valor not in MENSAGENS_VITE_API_URL_PERMITIDAS:
            raise ValueError(
                "menção a VITE_API_URL fora das formas "
                "nominais permitidas"
            )
        return valor

    if _ATRIBUICAO_RE.search(valor):
        raise ValueError(
            "mensagem com atribuição de variável ou valor associado"
        )

    if _CREDENCIAL_RE.search(valor):
        raise ValueError(
            "mensagem com credencial ou cabeçalho sensível"
        )

    if _mensagem_contem_sql(valor):
        raise ValueError("mensagem com comando SQL")

    if _mensagem_e_json_estruturado(valor):
        raise ValueError("mensagem com corpo estruturado em JSON")

    if _XML_INLINE_RE.search(valor):
        raise ValueError("mensagem com XML bruto")

    if _TRACEBACK_INLINE_RE.search(valor):
        raise ValueError("mensagem com traceback")

    return valor


def validar_endpoint_template(valor: str) -> str:
    """Rejeita endpoint absoluto, com traversal ou caracteres proibidos."""
    if "://" in valor:
        raise ValueError("endpoint com esquema proibido")

    if ".." in valor:
        raise ValueError("endpoint com traversal proibido")

    if not _ENDPOINT_TEMPLATE_RE.fullmatch(valor):
        raise ValueError("endpoint com caracteres proibidos")

    return valor


def validar_utc(valor: datetime) -> datetime:
    """Rejeita datetime cujo offset não seja exactamente UTC."""
    if valor.utcoffset() != timedelta(0):
        raise ValueError("deve estar em UTC")
    return valor


# ---------------------------------------------------------------------------
# Tipos estritos
# ---------------------------------------------------------------------------

TipoEvento = Annotated[
    StrictStr,
    Field(min_length=1, max_length=200),
    AfterValidator(validar_tipo_evento),
]

OrigemOperacional = Annotated[
    StrictStr,
    Field(min_length=1, max_length=200),
    AfterValidator(validar_origem_operacional),
]

MensagemOperacional = Annotated[
    StrictStr,
    Field(min_length=1, max_length=2000),
    AfterValidator(validar_mensagem_operacional),
]

EndpointTemplate = Annotated[
    StrictStr,
    Field(min_length=1, max_length=200),
    AfterValidator(validar_endpoint_template),
]

AwareDatetimeUTC = Annotated[
    AwareDatetime,
    AfterValidator(validar_utc),
]

StatusHttp = Annotated[
    StrictInt,
    Field(ge=100, le=599),
]

IdPositivo = Annotated[
    StrictInt,
    Field(gt=0),
]


# ---------------------------------------------------------------------------
# Códigos canónicos
# ---------------------------------------------------------------------------

OperationalDiagnosisCode = Literal[
    "RACE_CONDITION_TERMOS",
    "CTA_LOGIN_CONTEXTO_PERDIDO",
    "VERCEL_ENV_VAZIA",
    "CNAE_SAAS_ERRADO",
    "MEI_LIMITE_EXCEDIDO",
    "FATURAMENTO_ZERO",
    "TEMPO_NORMATIVO_AUSENTE",
    "SCHEMA_DRIFT_UNDEFINED_COLUMN",
    "UPLOAD_XML_500",
]

RiscoPatchCodigo = Literal[
    "baixo",
    "medio",
    "alto",
]

OperationalInfoEmFaltaCodigo = Literal[
    "DATABASE_COLUMNS_STATE_REQUIRED",
    "ALEMBIC_VERSION_REQUIRED",
    "RAILWAY_STACK_TRACE_REQUIRED",
    "EXECUTAR_ANALISE_XML_SOURCE_REQUIRED",
    "LER_XML_UNICO_SOURCE_REQUIRED",
    "SMOKE_XML_REQUIRED",
]

SchemaDriftIndicator = Literal[
    "UNDEFINED_COLUMN",
    "COLUMN_DOES_NOT_EXIST",
    "RELATORIOS_ANALISE_FINGERPRINT_MISSING",
]


# ---------------------------------------------------------------------------
# Sentinelas canónicas
# ---------------------------------------------------------------------------

NOMES_SENTINELAS_CANONICOS: tuple[str, ...] = (
    "_sentinela_race_condition_termos",
    "_sentinela_cta_login_contexto_perdido",
    "_sentinela_vercel_env_vazia",
    "_sentinela_cnae_saas_errado",
    "_sentinela_mei_limite_excedido",
    "_sentinela_faturamento_zero",
    "_sentinela_tempo_normativo_ausente",
    "_sentinela_schema_drift_undefined_column",
    "_sentinela_upload_xml_500",
)

MAPA_SENTINELAS_PARA_CODIGOS: Mapping[
    str,
    OperationalDiagnosisCode,
] = MappingProxyType(
    {
        "_sentinela_race_condition_termos":
            "RACE_CONDITION_TERMOS",
        "_sentinela_cta_login_contexto_perdido":
            "CTA_LOGIN_CONTEXTO_PERDIDO",
        "_sentinela_vercel_env_vazia":
            "VERCEL_ENV_VAZIA",
        "_sentinela_cnae_saas_errado":
            "CNAE_SAAS_ERRADO",
        "_sentinela_mei_limite_excedido":
            "MEI_LIMITE_EXCEDIDO",
        "_sentinela_faturamento_zero":
            "FATURAMENTO_ZERO",
        "_sentinela_tempo_normativo_ausente":
            "TEMPO_NORMATIVO_AUSENTE",
        "_sentinela_schema_drift_undefined_column":
            "SCHEMA_DRIFT_UNDEFINED_COLUMN",
        "_sentinela_upload_xml_500":
            "UPLOAD_XML_500",
    }
)


# ---------------------------------------------------------------------------
# Indicadores tipados de schema drift
# ---------------------------------------------------------------------------

ORDEM_SCHEMA_DRIFT_INDICADORES: tuple[
    SchemaDriftIndicator,
    ...,
] = (
    "UNDEFINED_COLUMN",
    "COLUMN_DOES_NOT_EXIST",
    "RELATORIOS_ANALISE_FINGERPRINT_MISSING",
)

_INDICE_SCHEMA_DRIFT: Mapping[
    SchemaDriftIndicator,
    int,
] = MappingProxyType(
    {
        indicador: indice
        for indice, indicador in enumerate(
            ORDEM_SCHEMA_DRIFT_INDICADORES
        )
    }
)

SCHEMA_DRIFT_REPRESENTACAO_LEGADA: Mapping[
    SchemaDriftIndicator,
    tuple[str, ...],
] = MappingProxyType(
    {
        "UNDEFINED_COLUMN": (
            "undefinedcolumn",
        ),
        "COLUMN_DOES_NOT_EXIST": (
            "column tabela.coluna does not exist",
        ),
        "RELATORIOS_ANALISE_FINGERPRINT_MISSING": (
            "relatorios_analise.fingerprint",
        ),
    }
)


def validar_contexto_indicadores(
    valor: tuple[SchemaDriftIndicator, ...],
) -> tuple[SchemaDriftIndicator, ...]:
    """Rejeita excesso, duplicação ou ordem não canónica de indicadores."""
    if len(valor) > len(ORDEM_SCHEMA_DRIFT_INDICADORES):
        raise ValueError(
            "indicadores excedem o máximo permitido"
        )

    if len(valor) != len(set(valor)):
        raise ValueError("indicadores duplicados")

    indice_anterior: int | None = None

    for indicador in valor:
        indice_actual = _INDICE_SCHEMA_DRIFT[indicador]

        if (
            indice_anterior is not None
            and indice_actual <= indice_anterior
        ):
            raise ValueError(
                "indicadores fora da ordem canónica"
            )

        indice_anterior = indice_actual

    return valor


ContextoIndicadores = Annotated[
    tuple[SchemaDriftIndicator, ...],
    AfterValidator(validar_contexto_indicadores),
]


# ---------------------------------------------------------------------------
# Informação em falta tipada
# ---------------------------------------------------------------------------

ORDEM_INFO_EM_FALTA: tuple[
    OperationalInfoEmFaltaCodigo,
    ...,
] = (
    "DATABASE_COLUMNS_STATE_REQUIRED",
    "ALEMBIC_VERSION_REQUIRED",
    "RAILWAY_STACK_TRACE_REQUIRED",
    "EXECUTAR_ANALISE_XML_SOURCE_REQUIRED",
    "LER_XML_UNICO_SOURCE_REQUIRED",
    "SMOKE_XML_REQUIRED",
)

_INDICE_INFO_EM_FALTA: Mapping[
    OperationalInfoEmFaltaCodigo,
    int,
] = MappingProxyType(
    {
        codigo: indice
        for indice, codigo in enumerate(ORDEM_INFO_EM_FALTA)
    }
)

INFO_LEGADO_EXACTA: Mapping[
    str,
    OperationalInfoEmFaltaCodigo,
] = MappingProxyType(
    {
        "colunas reais de tabela em producao":
            "DATABASE_COLUMNS_STATE_REQUIRED",

        "colunas reais de tabela afectada em producao":
            "DATABASE_COLUMNS_STATE_REQUIRED",

        "valor actual de alembic_version em producao":
            "ALEMBIC_VERSION_REQUIRED",

        "stack trace Railway":
            "RAILWAY_STACK_TRACE_REQUIRED",

        "corpo de executar_analise_xml":
            "EXECUTAR_ANALISE_XML_SOURCE_REQUIRED",

        "corpo de ler_xml_unico":
            "LER_XML_UNICO_SOURCE_REQUIRED",

        "XML completo usado no smoke":
            "SMOKE_XML_REQUIRED",
    }
)


def _verificar_ordem_info_em_falta(
    codigos: tuple[OperationalInfoEmFaltaCodigo, ...],
) -> None:
    if len(codigos) != len(set(codigos)):
        raise ValueError(
            "informação em falta contém códigos duplicados"
        )

    indice_anterior: int | None = None

    for codigo in codigos:
        indice_actual = _INDICE_INFO_EM_FALTA[codigo]

        if (
            indice_anterior is not None
            and indice_actual <= indice_anterior
        ):
            raise ValueError(
                "informação em falta fora da ordem canónica"
            )

        indice_anterior = indice_actual


# ---------------------------------------------------------------------------
# Perfis canónicos profundamente imutáveis
# ---------------------------------------------------------------------------


class OperationalDiagnosisProfile(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    classificacao: Literal["P0"]
    risco_patch: RiscoPatchCodigo

    tem_causa_provavel: Literal[True]
    tem_evidencias: Literal[True]
    tem_teste_recomendado: Literal[True]
    tem_patch_sugerido: Literal[True]

    informacao_em_falta: tuple[
        OperationalInfoEmFaltaCodigo, ...
    ]


PERFIS_DIAGNOSTICOS_CANONICOS: Mapping[
    OperationalDiagnosisCode,
    OperationalDiagnosisProfile,
] = MappingProxyType(
    {
        "RACE_CONDITION_TERMOS":
            OperationalDiagnosisProfile(
                classificacao="P0",
                risco_patch="baixo",
                tem_causa_provavel=True,
                tem_evidencias=True,
                tem_teste_recomendado=True,
                tem_patch_sugerido=True,
                informacao_em_falta=(),
            ),

        "CTA_LOGIN_CONTEXTO_PERDIDO":
            OperationalDiagnosisProfile(
                classificacao="P0",
                risco_patch="baixo",
                tem_causa_provavel=True,
                tem_evidencias=True,
                tem_teste_recomendado=True,
                tem_patch_sugerido=True,
                informacao_em_falta=(),
            ),

        "VERCEL_ENV_VAZIA":
            OperationalDiagnosisProfile(
                classificacao="P0",
                risco_patch="baixo",
                tem_causa_provavel=True,
                tem_evidencias=True,
                tem_teste_recomendado=True,
                tem_patch_sugerido=True,
                informacao_em_falta=(),
            ),

        "CNAE_SAAS_ERRADO":
            OperationalDiagnosisProfile(
                classificacao="P0",
                risco_patch="medio",
                tem_causa_provavel=True,
                tem_evidencias=True,
                tem_teste_recomendado=True,
                tem_patch_sugerido=True,
                informacao_em_falta=(),
            ),

        "MEI_LIMITE_EXCEDIDO":
            OperationalDiagnosisProfile(
                classificacao="P0",
                risco_patch="medio",
                tem_causa_provavel=True,
                tem_evidencias=True,
                tem_teste_recomendado=True,
                tem_patch_sugerido=True,
                informacao_em_falta=(),
            ),

        "FATURAMENTO_ZERO":
            OperationalDiagnosisProfile(
                classificacao="P0",
                risco_patch="baixo",
                tem_causa_provavel=True,
                tem_evidencias=True,
                tem_teste_recomendado=True,
                tem_patch_sugerido=True,
                informacao_em_falta=(),
            ),

        "TEMPO_NORMATIVO_AUSENTE":
            OperationalDiagnosisProfile(
                classificacao="P0",
                risco_patch="medio",
                tem_causa_provavel=True,
                tem_evidencias=True,
                tem_teste_recomendado=True,
                tem_patch_sugerido=True,
                informacao_em_falta=(),
            ),

        "SCHEMA_DRIFT_UNDEFINED_COLUMN":
            OperationalDiagnosisProfile(
                classificacao="P0",
                risco_patch="medio",
                tem_causa_provavel=True,
                tem_evidencias=True,
                tem_teste_recomendado=True,
                tem_patch_sugerido=True,
                informacao_em_falta=(
                    "DATABASE_COLUMNS_STATE_REQUIRED",
                    "ALEMBIC_VERSION_REQUIRED",
                ),
            ),

        "UPLOAD_XML_500":
            OperationalDiagnosisProfile(
                classificacao="P0",
                risco_patch="baixo",
                tem_causa_provavel=True,
                tem_evidencias=True,
                tem_teste_recomendado=True,
                tem_patch_sugerido=True,
                informacao_em_falta=(
                    "RAILWAY_STACK_TRACE_REQUIRED",
                    "EXECUTAR_ANALISE_XML_SOURCE_REQUIRED",
                    "LER_XML_UNICO_SOURCE_REQUIRED",
                    "SMOKE_XML_REQUIRED",
                ),
            ),
    }
)

MAPA_CODIGOS_PARA_INFO_EM_FALTA: Mapping[
    OperationalDiagnosisCode,
    tuple[OperationalInfoEmFaltaCodigo, ...],
] = MappingProxyType(
    {
        codigo: perfil.informacao_em_falta
        for codigo, perfil in (
            PERFIS_DIAGNOSTICOS_CANONICOS.items()
        )
    }
)


# ---------------------------------------------------------------------------
# Snapshots tipados
# ---------------------------------------------------------------------------


class OperationalGlobalEventSnapshot(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    event_id: UUID4
    occurred_at: AwareDatetimeUTC

    scope: Literal["global"]
    tenant_id: None = None

    tipo: TipoEvento
    origem: OrigemOperacional
    mensagem: MensagemOperacional
    endpoint: EndpointTemplate | None = None
    status_http: StatusHttp | None = None

    contexto_indicadores: ContextoIndicadores = ()


class OperationalTenantEventSnapshot(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    event_id: UUID4
    occurred_at: AwareDatetimeUTC

    scope: Literal["tenant"]
    tenant_id: IdPositivo

    tipo: TipoEvento
    origem: OrigemOperacional
    mensagem: MensagemOperacional
    endpoint: EndpointTemplate | None = None
    status_http: StatusHttp | None = None

    contexto_indicadores: ContextoIndicadores = ()


OperationalEventSnapshot = Annotated[
    OperationalGlobalEventSnapshot
    | OperationalTenantEventSnapshot,
    Field(discriminator="scope"),
]


# ---------------------------------------------------------------------------
# Coerência canónica do diagnóstico
# ---------------------------------------------------------------------------


def _validar_coerencia_perfil(
    *,
    diagnostico_codigo: OperationalDiagnosisCode | None,
    classificacao: Literal["P0"] | None,
    risco_patch: RiscoPatchCodigo | None,
    tem_causa_provavel: bool,
    tem_evidencias: bool,
    tem_teste_recomendado: bool,
    tem_patch_sugerido: bool,
    informacao_em_falta: tuple[
        OperationalInfoEmFaltaCodigo, ...
    ],
) -> None:
    """
    Impede estados contraditórios entre o código de diagnóstico, o
    perfil canónico e a informação em falta, sem transportar valores
    recebidos nas mensagens.

    diagnostico_codigo=None representa o estado não reconhecido: exige
    classificacao, risco_patch, flags e informacao_em_falta vazios.
    diagnostico_codigo definido exige correspondência integral com
    PERFIS_DIAGNOSTICOS_CANONICOS.
    """
    _verificar_ordem_info_em_falta(informacao_em_falta)

    if diagnostico_codigo is None:
        if classificacao is not None:
            raise ValueError(
                "ausência de diagnóstico não admite classificação"
            )

        if risco_patch is not None:
            raise ValueError(
                "ausência de diagnóstico não admite risco"
            )

        if (
            tem_causa_provavel
            or tem_evidencias
            or tem_teste_recomendado
            or tem_patch_sugerido
        ):
            raise ValueError(
                "ausência de diagnóstico exige flags falsos"
            )

        if informacao_em_falta != ():
            raise ValueError(
                "ausência de diagnóstico exige "
                "informação em falta vazia"
            )

        return

    if diagnostico_codigo not in PERFIS_DIAGNOSTICOS_CANONICOS:
        raise ValueError(
            "código de diagnóstico fora do mapa canónico"
        )

    perfil = PERFIS_DIAGNOSTICOS_CANONICOS[diagnostico_codigo]

    if classificacao != perfil.classificacao:
        raise ValueError(
            "classificação diverge do perfil canónico"
        )

    if risco_patch != perfil.risco_patch:
        raise ValueError(
            "risco diverge do perfil canónico"
        )

    if not (
        tem_causa_provavel
        and tem_evidencias
        and tem_teste_recomendado
        and tem_patch_sugerido
    ):
        raise ValueError(
            "flags divergem do perfil canónico"
        )

    if informacao_em_falta != perfil.informacao_em_falta:
        raise ValueError(
            "informação em falta diverge do perfil canónico"
        )


# ---------------------------------------------------------------------------
# Projecção interna sanitizada
# ---------------------------------------------------------------------------


class OperationalDiagnosisInternal(BaseModel):
    """
    Projecção interna do resultado das sentinelas.

    Contém somente código de diagnóstico, classificação, risco, flags
    e informação em falta — reconhecimento e camada de reconhecimento
    pertencem exclusivamente ao payload público.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    diagnostico_codigo: OperationalDiagnosisCode | None
    classificacao: Literal["P0"] | None
    risco_patch: RiscoPatchCodigo | None

    tem_causa_provavel: StrictBool
    tem_evidencias: StrictBool
    tem_teste_recomendado: StrictBool
    tem_patch_sugerido: StrictBool

    informacao_em_falta: tuple[
        OperationalInfoEmFaltaCodigo, ...
    ]

    @model_validator(mode="after")
    def validar_coerencia(self) -> Self:
        _validar_coerencia_perfil(
            diagnostico_codigo=self.diagnostico_codigo,
            classificacao=self.classificacao,
            risco_patch=self.risco_patch,
            tem_causa_provavel=self.tem_causa_provavel,
            tem_evidencias=self.tem_evidencias,
            tem_teste_recomendado=self.tem_teste_recomendado,
            tem_patch_sugerido=self.tem_patch_sugerido,
            informacao_em_falta=self.informacao_em_falta,
        )
        return self


# ---------------------------------------------------------------------------
# Payload público
# ---------------------------------------------------------------------------


class OperationalDiagnosisPayload(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    event_id: UUID4

    reconhecido: StrictBool

    camada_reconhecimento: Literal[
        "sentinela",
        "nao_reconhecido",
    ]

    diagnostico_codigo: OperationalDiagnosisCode | None
    classificacao: Literal["P0"] | None
    risco_patch: RiscoPatchCodigo | None

    tem_causa_provavel: StrictBool
    tem_evidencias: StrictBool
    tem_teste_recomendado: StrictBool
    tem_patch_sugerido: StrictBool

    informacao_em_falta: tuple[
        OperationalInfoEmFaltaCodigo, ...
    ]

    publication_allowed: Literal[False] = False
    automation_allowed: Literal[False] = False
    requires_human_review: Literal[True] = True

    @model_validator(mode="after")
    def validar_coerencia(self) -> Self:
        if self.reconhecido:
            if self.camada_reconhecimento != "sentinela":
                raise ValueError(
                    "camada de reconhecimento indevida "
                    "para evento reconhecido"
                )

            if self.diagnostico_codigo is None:
                raise ValueError(
                    "evento reconhecido exige "
                    "código de diagnóstico"
                )
        else:
            if self.camada_reconhecimento != "nao_reconhecido":
                raise ValueError(
                    "camada de reconhecimento indevida "
                    "para evento não reconhecido"
                )

            if self.diagnostico_codigo is not None:
                raise ValueError(
                    "evento não reconhecido não admite "
                    "código de diagnóstico"
                )

        _validar_coerencia_perfil(
            diagnostico_codigo=self.diagnostico_codigo,
            classificacao=self.classificacao,
            risco_patch=self.risco_patch,
            tem_causa_provavel=self.tem_causa_provavel,
            tem_evidencias=self.tem_evidencias,
            tem_teste_recomendado=self.tem_teste_recomendado,
            tem_patch_sugerido=self.tem_patch_sugerido,
            informacao_em_falta=self.informacao_em_falta,
        )
        return self


# ---------------------------------------------------------------------------
# Erros pré-execução
# ---------------------------------------------------------------------------

AgentErroDiagnosisPreExecutionErrorCode = Literal[
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
    "MISSION_ENVELOPE_UNSUPPORTED",
    "MISSION_PRIORITY_UNSUPPORTED",
    "MISSION_REFERENCE_AT_REQUIRED",
    "MISSION_TEMPORALITY_UNSUPPORTED",
    "AG_OPERATIONAL_DIAGNOSIS_CONTEXT_INVALID",
]

_MENSAGEM_PRE_EXECUCAO_GENERICA = (
    "A missão de diagnóstico operacional recebida não é "
    "compatível com este agente."
)

_MENSAGEM_CONTEXTO_INVALIDO = (
    "Não foi possível validar o contexto do evento "
    "operacional recebido."
)


class AgentErroDiagnosisPreExecutionError(Exception):
    def __init__(
        self,
        code: AgentErroDiagnosisPreExecutionErrorCode,
    ) -> None:
        self.code = code
        self.public_message = (
            _MENSAGEM_CONTEXTO_INVALIDO
            if code == "AG_OPERATIONAL_DIAGNOSIS_CONTEXT_INVALID"
            else _MENSAGEM_PRE_EXECUCAO_GENERICA
        )
        super().__init__(code)


# ---------------------------------------------------------------------------
# Erro de drift do legado
# ---------------------------------------------------------------------------


class OperationalLegacyDriftError(Exception):
    def __init__(self) -> None:
        self.code = "AG_OPERATIONAL_DIAGNOSIS_LEGACY_DRIFT"
        self.public_message = (
            "O motor de diagnóstico detectou uma divergência "
            "no legado protegido."
        )
        super().__init__(self.code)


# ---------------------------------------------------------------------------
# Erros pós-construção
# ---------------------------------------------------------------------------


class AgentErroDiagnosisResultValidationError(Exception):
    def __init__(self) -> None:
        self.code = "RESULT_MISSION_VALIDATION_FAILED"
        super().__init__(self.code)


class AgentErroDiagnosisResultSafetyError(Exception):
    def __init__(self) -> None:
        self.code = "RESULT_SANITIZATION_FAILED"
        super().__init__(self.code)