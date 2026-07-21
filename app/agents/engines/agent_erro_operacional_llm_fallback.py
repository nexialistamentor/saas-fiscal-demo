"""
app/agents/engines/agent_erro_operacional_llm_fallback.py — ADR-015 B14.3G.

Motor determinístico L3 do canário de pré-execução do fallback LLM
sobre eventos operacionais.

Recebe apenas o contexto já tipado (OperationalLLMFallbackContext, que
é o próprio OperationalEventSnapshot do B14.3F). Importa tardiamente
app.agents.agent_erro_operacional exclusivamente para ler e executar
_SENTINELAS e verificar _PADROES_APRENDIDOS == []. Nunca chama
AgentErroOperacional.run(), nunca chama _tentar_padrao_aprendido(),
nunca importa BudgetGuard, LLMRouter, providers de LLM ou qualquer
outro agente/adapter/engine.

O papel deste motor é exclusivamente determinar se um evento continua
elegível para o fallback LLM (nenhuma sentinela o reconheceu) — nunca
avalia BudgetPolicy.allow_llm nem PERMITE_CHAMADA_REAL_V1, que são
avaliados pelo adapter depois deste motor devolver a sua resposta.
Este motor nunca contacta a rede, nunca gasta orçamento e nunca
produz um OperationalLLMFallbackPayload — não existe caminho de
sucesso nesta versão.
"""

from __future__ import annotations

from app.agents.contracts.agent_erro_operacional import (
    MAPA_SENTINELAS_PARA_CODIGOS,
    NOMES_SENTINELAS_CANONICOS,
    PERFIS_DIAGNOSTICOS_CANONICOS,
    SCHEMA_DRIFT_REPRESENTACAO_LEGADA,
    OperationalGlobalEventSnapshot,
    OperationalTenantEventSnapshot,
)
from app.agents.contracts.agent_erro_operacional_llm_fallback import (
    AgentErroOperacionalLLMFallbackPreExecutionError,
    OperationalLLMFallbackContext,
    OperationalLLMFallbackLegacyDriftError,
)
from app.schemas.evento_operacional import EventoOperacional

_LEGACY_SENTINEL_COUNT = 9
_MISSING = object()


class OperationalLLMFallbackUnexpectedExecutionError(Exception):
    """
    Sinal interno e opaco do motor.

    Nunca transporta a excepção original, a sua mensagem, os seus
    argumentos ou o seu traceback. O adapter mapeia esta excepção
    para o código público fixo AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR,
    já definido no contrato, sem nunca expor str(exc), repr(exc) ou
    qualquer detalhe interno.
    """

    def __init__(self) -> None:
        super().__init__("execution_error")


def _raise_context_invalid() -> None:
    raise AgentErroOperacionalLLMFallbackPreExecutionError(
        "AG_OPERATIONAL_LLM_FALLBACK_CONTEXT_INVALID"
    ) from None


def _raise_legacy_drift() -> None:
    raise OperationalLLMFallbackLegacyDriftError() from None


def _validar_contexto_tipado(
    context: OperationalLLMFallbackContext,
) -> None:
    """Bloqueia chamadas directas com contexto fora dos snapshots fechados."""
    if type(context) not in (
        OperationalGlobalEventSnapshot,
        OperationalTenantEventSnapshot,
    ):
        _raise_context_invalid()


def _validar_superficie_legada(
    legacy_module: object,
) -> tuple[object, ...]:
    """
    Valida a superfície protegida na ordem soberana obrigatória.

    A callability é verificada antes de qualquer acesso a __name__.
    Qualquer ausência, divergência ou alteração estrutural produz
    apenas OperationalLLMFallbackLegacyDriftError, sem expor valores
    ou nomes privados.
    """
    raw_sentinels = getattr(legacy_module, "_SENTINELAS", _MISSING)

    if raw_sentinels is _MISSING:
        _raise_legacy_drift()

    try:
        sentinels = tuple(raw_sentinels)
    except TypeError:
        _raise_legacy_drift()

    if len(sentinels) != _LEGACY_SENTINEL_COUNT:
        _raise_legacy_drift()

    if not all(callable(sentinel) for sentinel in sentinels):
        _raise_legacy_drift()

    try:
        names = tuple(sentinel.__name__ for sentinel in sentinels)
    except (AttributeError, TypeError):
        _raise_legacy_drift()

    if names != NOMES_SENTINELAS_CANONICOS:
        _raise_legacy_drift()

    map_names = tuple(MAPA_SENTINELAS_PARA_CODIGOS.keys())

    if map_names != names:
        _raise_legacy_drift()

    mapped_codes = tuple(
        MAPA_SENTINELAS_PARA_CODIGOS[name] for name in names
    )

    if len(mapped_codes) != len(set(mapped_codes)):
        _raise_legacy_drift()

    if set(mapped_codes) != set(PERFIS_DIAGNOSTICOS_CANONICOS.keys()):
        _raise_legacy_drift()

    learned_patterns = getattr(
        legacy_module,
        "_PADROES_APRENDIDOS",
        _MISSING,
    )

    if learned_patterns is _MISSING or learned_patterns != []:
        _raise_legacy_drift()

    return sentinels


def _reconstruir_contexto_legado(
    context: OperationalLLMFallbackContext,
) -> dict[str, object]:
    """Reconstrói apenas indicadores nominais fechados para o legado."""
    representations: list[str] = []

    for indicator in context.contexto_indicadores:
        representations.extend(
            SCHEMA_DRIFT_REPRESENTACAO_LEGADA[indicator]
        )

    if not representations:
        return {}

    return {
        "schema_drift_indicators": tuple(representations),
    }


def _reconstruir_evento_legado(
    context: OperationalLLMFallbackContext,
) -> EventoOperacional:
    """
    Cria a entrada mínima da camada legada.

    Nunca transporta ambiente externo real, commit, ficheiro
    provável, payload livre, headers, cookies, query string, body,
    XML ou traceback — apenas os campos tipados já validados no
    snapshot.
    """
    return EventoOperacional(
        tipo=context.tipo,
        origem=context.origem,
        mensagem=context.mensagem,
        endpoint=context.endpoint,
        status_http=context.status_http,
        ambiente="local",
        commit_sha=None,
        ficheiro_provavel=None,
        contexto=_reconstruir_contexto_legado(context),
    )


def executar_agent_erro_operacional_llm_fallback_engine(
    context: OperationalLLMFallbackContext,
) -> bool:
    """
    Recomputa a elegibilidade para o fallback LLM.

    Percorre exclusivamente as nove sentinelas determinísticas
    protegidas, na ordem canónica, até ao primeiro reconhecimento.
    Nunca executa Camada 2 (_tentar_padrao_aprendido), nunca chama
    .run(), nunca importa BudgetGuard, LLMRouter ou qualquer provider.

    Devolve True se nenhuma sentinela reconheceu o evento; devolve
    False no primeiro reconhecimento, tornando o fallback não elegível.

    Levanta AgentErroOperacionalLLMFallbackPreExecutionError se o
    contexto não for um dos dois snapshots fechados, e
    OperationalLLMFallbackLegacyDriftError se a superfície protegida
    divergir do esperado. Qualquer outra excepção inesperada durante
    o import tardio ou a execução das sentinelas é convertida em
    OperationalLLMFallbackUnexpectedExecutionError, sem nunca expor
    str(exc), repr(exc) ou traceback.
    """
    _validar_contexto_tipado(context)

    try:
        import app.agents.agent_erro_operacional as legacy_module

        sentinels = _validar_superficie_legada(legacy_module)
        legacy_event = _reconstruir_evento_legado(context)

        for sentinel in sentinels:
            resultado = sentinel(legacy_event)

            if resultado is not None:
                return False

        return True

    except OperationalLLMFallbackLegacyDriftError:
        raise
    except Exception:
        raise OperationalLLMFallbackUnexpectedExecutionError() from None
