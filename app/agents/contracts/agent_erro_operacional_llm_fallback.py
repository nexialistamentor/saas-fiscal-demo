"""
app/agents/contracts/agent_erro_operacional_llm_fallback.py — ADR-015 B14.3G.

Contratos Pydantic específicos do canário de pré-execução do fallback
LLM sobre eventos operacionais (v1).

Módulo puro: não importa o agente legado, o motor/adapter/engine do
B14.3F, outros agentes, adapters, engines, readers, serviços, ORM, BD,
HTTP, filesystem, scheduler, registry, executor, BudgetGuard, LLMRouter,
providers de LLM ou qualquer submódulo de app.services.llm_providers.

O contexto desta missão é o próprio OperationalEventSnapshot do B14.3F
— importado, nunca duplicado, nunca envolvido num novo tipo. Isto
preserva context.event_id e a coerência
mission.source_event_id == context.event_id exactamente como no B14.3F.

PERMITE_CHAMADA_REAL_V1 não é campo de nenhum modelo — é uma constante
de módulo desta versão do contrato, permanentemente falsa. Não é
alterada por nenhuma missão, chamador ou configuração de ambiente. A
activação de chamada real exige nova ADR, novo agent_version e nova
fallback_policy_version — nunca uma subida de context_version, que
mede o schema do OperationalEventSnapshot, não a autoridade de rede
do agente.
"""

from __future__ import annotations

import unicodedata
from typing import Annotated, Final, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    UUID4,
    model_validator,
)

from app.agents.contracts.agent_erro_operacional import (
    OperationalEventSnapshot,
)


# ---------------------------------------------------------------------------
# Alias directo — nenhum wrapper, nenhum modelo, nenhuma validação nova
# ---------------------------------------------------------------------------

OperationalLLMFallbackContext = OperationalEventSnapshot


# ---------------------------------------------------------------------------
# Constante permanente da versão (nunca campo de missão, contexto ou modelo)
# ---------------------------------------------------------------------------

PERMITE_CHAMADA_REAL_V1: Final[Literal[False]] = False


# ---------------------------------------------------------------------------
# Texto de conteúdo LLM
# ---------------------------------------------------------------------------

_LIMITE_CARACTERES_POR_CAMPO = 500
_LIMITE_CARACTERES_AGREGADO = 1200


def validar_texto_conteudo_llm(valor: str) -> str:
    """
    Rejeita texto vazio ou em branco, e qualquer carácter Unicode da
    categoria de controlo (Cc) excepto '\\n'. Nunca normaliza nem
    trunca — rejeição integral ou aceitação integral.
    """
    if not valor.strip():
        raise ValueError(
            "campo de conteúdo não pode ser vazio nem branco quando presente"
        )

    for caracter in valor:
        if caracter == "\n":
            continue
        if unicodedata.category(caracter) == "Cc":
            raise ValueError(
                "campo de conteúdo contém carácter de controlo proibido"
            )

    return valor


TextoConteudoLLM = Annotated[
    StrictStr,
    Field(max_length=_LIMITE_CARACTERES_POR_CAMPO),
    AfterValidator(validar_texto_conteudo_llm),
]


def _validar_conteudo_llm(
    *,
    hipotese_operacional: str | None,
    informacao_adicional_necessaria: str | None,
    recomendacao_de_investigacao: str | None,
) -> None:
    """
    Impõe as duas regras partilhadas por Output e Payload: pelo menos
    um campo preenchido, e o agregado dos campos preenchidos dentro
    do limite de 1200 caracteres. Independente de qualquer estimativa
    de tokens.
    """
    campos = (
        hipotese_operacional,
        informacao_adicional_necessaria,
        recomendacao_de_investigacao,
    )

    if all(campo is None for campo in campos):
        raise ValueError(
            "pelo menos um campo de conteúdo deve estar preenchido"
        )

    agregado = sum(len(campo) for campo in campos if campo is not None)

    if agregado > _LIMITE_CARACTERES_AGREGADO:
        raise ValueError(
            "soma dos campos de conteúdo excede o limite agregado de "
            f"{_LIMITE_CARACTERES_AGREGADO} caracteres"
        )


# ---------------------------------------------------------------------------
# Output estrito do provider (nunca o payload público)
# ---------------------------------------------------------------------------


class OperationalLLMFallbackOutput(BaseModel):
    """
    Único schema em que o output do LLM seria interpretado, numa
    futura activação. Não contém event_id, linhagem, autoridade ou
    metadados de execução — só os três campos de conteúdo. Nenhum
    campo é obrigatório individualmente (evita forçar o modelo a
    inventar conteúdo); pelo menos um tem de estar preenchido.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    hipotese_operacional: TextoConteudoLLM | None = None
    informacao_adicional_necessaria: TextoConteudoLLM | None = None
    recomendacao_de_investigacao: TextoConteudoLLM | None = None

    @model_validator(mode="after")
    def validar_conteudo(self) -> Self:
        _validar_conteudo_llm(
            hipotese_operacional=self.hipotese_operacional,
            informacao_adicional_necessaria=(
                self.informacao_adicional_necessaria
            ),
            recomendacao_de_investigacao=self.recomendacao_de_investigacao,
        )
        return self


# ---------------------------------------------------------------------------
# Payload público — ratificado na v1, reservado a um futuro caminho de sucesso
# ---------------------------------------------------------------------------


class OperationalLLMFallbackPayload(BaseModel):
    """
    Contrato ratificado agora; nenhum AgentExecutionResult de B14.3G
    v1 contém este payload (não existe caminho de sucesso nesta
    versão). Quando uma futura ADR autorizar chamada real, o adapter
    montará este payload deterministicamente — o provider nunca
    controla event_id, linhagem ou os três flags de autoridade.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    event_id: UUID4

    hipotese_operacional: TextoConteudoLLM | None = None
    informacao_adicional_necessaria: TextoConteudoLLM | None = None
    recomendacao_de_investigacao: TextoConteudoLLM | None = None

    publication_allowed: Literal[False] = False
    automation_allowed: Literal[False] = False
    requires_human_review: Literal[True] = True

    @model_validator(mode="after")
    def validar_conteudo(self) -> Self:
        _validar_conteudo_llm(
            hipotese_operacional=self.hipotese_operacional,
            informacao_adicional_necessaria=(
                self.informacao_adicional_necessaria
            ),
            recomendacao_de_investigacao=self.recomendacao_de_investigacao,
        )
        return self


# ---------------------------------------------------------------------------
# Erros de pré-execução (paridade exacta de 21 com o B14.3F)
# ---------------------------------------------------------------------------

AgentErroOperacionalLLMFallbackPreExecutionErrorCode = Literal[
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
    "AG_OPERATIONAL_LLM_FALLBACK_CONTEXT_INVALID",
]

_MENSAGEM_PRE_EXECUCAO_GENERICA = (
    "A missão de diagnóstico operacional recebida não é "
    "compatível com este agente."
)

_MENSAGEM_CONTEXTO_INVALIDO = (
    "Não foi possível validar o contexto do evento "
    "operacional recebido."
)


class AgentErroOperacionalLLMFallbackPreExecutionError(Exception):
    def __init__(
        self,
        code: AgentErroOperacionalLLMFallbackPreExecutionErrorCode,
    ) -> None:
        self.code = code
        self.public_message = (
            _MENSAGEM_CONTEXTO_INVALIDO
            if code == "AG_OPERATIONAL_LLM_FALLBACK_CONTEXT_INVALID"
            else _MENSAGEM_PRE_EXECUCAO_GENERICA
        )
        super().__init__(code)


# ---------------------------------------------------------------------------
# Códigos e mensagens operacionais
#
# Usados directamente pelo adapter para construir um AgentExecutionResult
# com status="bloqueado" (como alerts) ou status="erro" (como error_code
# + error_message) — nunca são excepções de pré-execução. Definidos aqui,
# em vez de no adapter, para que engine/adapter/testes nunca dupliquem
# ou divirjam nestes valores.
# ---------------------------------------------------------------------------

AGENT_VERSION_INCOMPATIBLE = "AGENT_VERSION_INCOMPATIBLE"
AGENT_VERSION_INCOMPATIBLE_MESSAGE = (
    "A versão requerida pela missão não é compatível com o agente "
    "de fallback LLM operacional."
)

EXECUTION_MODE_NOT_AUTHORIZED = "EXECUTION_MODE_NOT_AUTHORIZED"
EXECUTION_MODE_NOT_AUTHORIZED_MESSAGE = (
    "O modo de execução solicitado não está autorizado para o agente "
    "de fallback LLM operacional."
)

AG_OPERATIONAL_LLM_FALLBACK_NOT_ELIGIBLE = (
    "AG_OPERATIONAL_LLM_FALLBACK_NOT_ELIGIBLE"
)
AG_OPERATIONAL_LLM_FALLBACK_NOT_ELIGIBLE_MESSAGE = (
    "O evento foi reconhecido por uma sentinela determinística; "
    "o fallback LLM não é aplicável."
)

AG_OPERATIONAL_LLM_FALLBACK_BUDGET_NOT_AUTHORIZED = (
    "AG_OPERATIONAL_LLM_FALLBACK_BUDGET_NOT_AUTHORIZED"
)
AG_OPERATIONAL_LLM_FALLBACK_BUDGET_NOT_AUTHORIZED_MESSAGE = (
    "A missão não está autorizada a utilizar LLM."
)

AG_OPERATIONAL_LLM_FALLBACK_REAL_CALL_NOT_ENABLED = (
    "AG_OPERATIONAL_LLM_FALLBACK_REAL_CALL_NOT_ENABLED"
)
AG_OPERATIONAL_LLM_FALLBACK_REAL_CALL_NOT_ENABLED_MESSAGE = (
    "A chamada real a um provedor LLM não está activada nesta "
    "versão do agente."
)

AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR = (
    "AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR"
)
AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR_MESSAGE = (
    "Não foi possível concluir a verificação de elegibilidade "
    "para o fallback LLM operacional."
)


# ---------------------------------------------------------------------------
# Erro de drift do legado
# ---------------------------------------------------------------------------


class OperationalLLMFallbackLegacyDriftError(Exception):
    def __init__(self) -> None:
        self.code = "AG_OPERATIONAL_LLM_FALLBACK_LEGACY_DRIFT"
        self.public_message = (
            "O motor de fallback LLM detectou uma divergência "
            "no legado protegido."
        )
        super().__init__(self.code)


# ---------------------------------------------------------------------------
# Erros pós-construção (namespace único)
# ---------------------------------------------------------------------------


class AgentErroOperacionalLLMFallbackResultValidationError(Exception):
    def __init__(self) -> None:
        self.code = "AG_OPERATIONAL_LLM_FALLBACK_RESULT_VALIDATION_FAILED"
        self.public_message = (
            "O resultado da missão de fallback LLM não corresponde "
            "à missão originante."
        )
        super().__init__(self.code)


class AgentErroOperacionalLLMFallbackResultSafetyError(Exception):
    def __init__(self) -> None:
        self.code = "AG_OPERATIONAL_LLM_FALLBACK_RESULT_SANITIZATION_FAILED"
        self.public_message = (
            "O resultado da missão de fallback LLM não passou "
            "na sanitização soberana."
        )
        super().__init__(self.code)
