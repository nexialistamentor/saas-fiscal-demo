"""
app/agents/engines/agent_erro_operacional.py — ADR-014 B14.3F.

Motor determinístico L3 para AgentErroOperacional.

Recebe somente snapshots soberanos já validados, reconstrói um
EventoOperacional mínimo e executa exclusivamente as nove sentinelas
legadas protegidas. Não chama AgentErroOperacional.run(), padrões
aprendidos, BudgetGuard, LLMRouter ou qualquer provider.

O módulo legado é importado apenas dentro da função principal, depois
da validação do contexto recebida pelo motor.
"""

from __future__ import annotations

from typing import Any

from app.agents.contracts.agent_erro_operacional import (
    INFO_LEGADO_EXACTA,
    MAPA_SENTINELAS_PARA_CODIGOS,
    NOMES_SENTINELAS_CANONICOS,
    PERFIS_DIAGNOSTICOS_CANONICOS,
    SCHEMA_DRIFT_REPRESENTACAO_LEGADA,
    AgentErroDiagnosisPreExecutionError,
    OperationalDiagnosisCode,
    OperationalDiagnosisInternal,
    OperationalDiagnosisPayload,
    OperationalEventSnapshot,
    OperationalGlobalEventSnapshot,
    OperationalLegacyDriftError,
    OperationalTenantEventSnapshot,
)
from app.schemas.evento_operacional import EventoOperacional


_LEGACY_SENTINEL_COUNT = 9
_MISSING = object()


def _raise_legacy_drift() -> None:
    raise OperationalLegacyDriftError() from None


def _validar_contexto_tipado(
    context: OperationalEventSnapshot,
) -> None:
    """Bloqueia chamadas directas com contexto fora dos snapshots fechados."""
    if type(context) not in (
        OperationalGlobalEventSnapshot,
        OperationalTenantEventSnapshot,
    ):
        raise AgentErroDiagnosisPreExecutionError(
            "AG_OPERATIONAL_DIAGNOSIS_CONTEXT_INVALID"
        ) from None


def _validar_superficie_legada(
    legacy_module: Any,
) -> tuple[Any, ...]:
    """
    Valida a superfície protegida na ordem soberana obrigatória.

    A callability é verificada antes de qualquer acesso a __name__.
    Qualquer ausência, divergência ou alteração estrutural produz apenas
    OperationalLegacyDriftError, sem expor valores ou nomes privados.
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
        MAPA_SENTINELAS_PARA_CODIGOS[name]
        for name in names
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
    context: OperationalEventSnapshot,
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
    context: OperationalEventSnapshot,
) -> EventoOperacional:
    """
    Cria a entrada mínima da camada legada.

    Nunca transporta ambiente externo, commit, ficheiro provável,
    payload livre, headers, cookies, query string, body, XML ou traceback.
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


def _texto_nao_branco(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _evidencias_validas(value: object) -> bool:
    if not isinstance(value, (list, tuple)):
        return False

    return bool(value) and all(
        isinstance(item, str) and bool(item.strip())
        for item in value
    )


def _mapear_informacao_em_falta(
    value: object,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        _raise_legacy_drift()

    mapped: list[str] = []

    for item in value:
        if not isinstance(item, str):
            _raise_legacy_drift()

        code = INFO_LEGADO_EXACTA.get(item)

        if code is None:
            _raise_legacy_drift()

        mapped.append(code)

    if len(mapped) != len(set(mapped)):
        _raise_legacy_drift()

    return tuple(mapped)


def projectar_resultado_operacional(
    *,
    diagnostico_codigo: OperationalDiagnosisCode,
    legacy_result: object,
) -> OperationalDiagnosisInternal:
    """Converte um resultado textual legado numa projecção sem textos."""
    profile = PERFIS_DIAGNOSTICOS_CANONICOS[diagnostico_codigo]

    classification = getattr(
        legacy_result,
        "classificacao",
        _MISSING,
    )
    risk = getattr(legacy_result, "risco_patch", _MISSING)

    has_cause = _texto_nao_branco(
        getattr(legacy_result, "causa_provavel", _MISSING)
    )
    has_evidence = _evidencias_validas(
        getattr(legacy_result, "evidencias", _MISSING)
    )
    has_test = _texto_nao_branco(
        getattr(legacy_result, "teste_recomendado", _MISSING)
    )
    has_patch = _texto_nao_branco(
        getattr(legacy_result, "patch_sugerido_texto", _MISSING)
    )
    missing_information = _mapear_informacao_em_falta(
        getattr(legacy_result, "informacao_em_falta", _MISSING)
    )

    if classification != profile.classificacao:
        _raise_legacy_drift()

    if risk != profile.risco_patch:
        _raise_legacy_drift()

    if (
        has_cause is not profile.tem_causa_provavel
        or has_evidence is not profile.tem_evidencias
        or has_test is not profile.tem_teste_recomendado
        or has_patch is not profile.tem_patch_sugerido
    ):
        _raise_legacy_drift()

    if missing_information != profile.informacao_em_falta:
        _raise_legacy_drift()

    return OperationalDiagnosisInternal(
        diagnostico_codigo=diagnostico_codigo,
        classificacao=profile.classificacao,
        risco_patch=profile.risco_patch,
        tem_causa_provavel=profile.tem_causa_provavel,
        tem_evidencias=profile.tem_evidencias,
        tem_teste_recomendado=profile.tem_teste_recomendado,
        tem_patch_sugerido=profile.tem_patch_sugerido,
        informacao_em_falta=profile.informacao_em_falta,
    )


def _projectar_evento_nao_reconhecido() -> OperationalDiagnosisInternal:
    return OperationalDiagnosisInternal(
        diagnostico_codigo=None,
        classificacao=None,
        risco_patch=None,
        tem_causa_provavel=False,
        tem_evidencias=False,
        tem_teste_recomendado=False,
        tem_patch_sugerido=False,
        informacao_em_falta=(),
    )


def construir_payload_diagnostico_operacional(
    *,
    context: OperationalEventSnapshot,
    projection: OperationalDiagnosisInternal,
) -> OperationalDiagnosisPayload:
    """Constrói o payload público exclusivamente a partir da projecção."""
    recognized = projection.diagnostico_codigo is not None

    return OperationalDiagnosisPayload(
        event_id=context.event_id,
        reconhecido=recognized,
        camada_reconhecimento=(
            "sentinela" if recognized else "nao_reconhecido"
        ),
        diagnostico_codigo=projection.diagnostico_codigo,
        classificacao=projection.classificacao,
        risco_patch=projection.risco_patch,
        tem_causa_provavel=projection.tem_causa_provavel,
        tem_evidencias=projection.tem_evidencias,
        tem_teste_recomendado=projection.tem_teste_recomendado,
        tem_patch_sugerido=projection.tem_patch_sugerido,
        informacao_em_falta=projection.informacao_em_falta,
        publication_allowed=False,
        automation_allowed=False,
        requires_human_review=True,
    )


def _reconstruir_projeccao_independente(
    diagnostico_codigo: OperationalDiagnosisCode | None,
) -> OperationalDiagnosisInternal:
    """Reconstrói a projecção sem chamar sentinelas ou o projector principal."""
    if diagnostico_codigo is None:
        return OperationalDiagnosisInternal(
            diagnostico_codigo=None,
            classificacao=None,
            risco_patch=None,
            tem_causa_provavel=False,
            tem_evidencias=False,
            tem_teste_recomendado=False,
            tem_patch_sugerido=False,
            informacao_em_falta=(),
        )

    profile = PERFIS_DIAGNOSTICOS_CANONICOS[diagnostico_codigo]

    return OperationalDiagnosisInternal(
        diagnostico_codigo=diagnostico_codigo,
        classificacao=profile.classificacao,
        risco_patch=profile.risco_patch,
        tem_causa_provavel=profile.tem_causa_provavel,
        tem_evidencias=profile.tem_evidencias,
        tem_teste_recomendado=profile.tem_teste_recomendado,
        tem_patch_sugerido=profile.tem_patch_sugerido,
        informacao_em_falta=profile.informacao_em_falta,
    )


def validate_operational_diagnosis_payload_against_context(
    *,
    context: OperationalEventSnapshot,
    projection: OperationalDiagnosisInternal,
    payload: OperationalDiagnosisPayload,
) -> None:
    """
    Valida projecção e payload por duas reconstruções independentes.

    Não chama sentinelas, motor principal, projector principal,
    construtor principal do payload, agente legado ou funções privadas
    do legado.
    """
    expected_projection = _reconstruir_projeccao_independente(
        projection.diagnostico_codigo
    )

    if (
        projection.model_dump(mode="python")
        != expected_projection.model_dump(mode="python")
    ):
        _raise_legacy_drift()

    recognized = expected_projection.diagnostico_codigo is not None

    expected_payload = OperationalDiagnosisPayload(
        event_id=context.event_id,
        reconhecido=recognized,
        camada_reconhecimento=(
            "sentinela" if recognized else "nao_reconhecido"
        ),
        diagnostico_codigo=expected_projection.diagnostico_codigo,
        classificacao=expected_projection.classificacao,
        risco_patch=expected_projection.risco_patch,
        tem_causa_provavel=expected_projection.tem_causa_provavel,
        tem_evidencias=expected_projection.tem_evidencias,
        tem_teste_recomendado=expected_projection.tem_teste_recomendado,
        tem_patch_sugerido=expected_projection.tem_patch_sugerido,
        informacao_em_falta=expected_projection.informacao_em_falta,
        publication_allowed=False,
        automation_allowed=False,
        requires_human_review=True,
    )

    if (
        payload.model_dump(mode="python")
        != expected_payload.model_dump(mode="python")
    ):
        _raise_legacy_drift()


def executar_agent_erro_operacional_engine(
    context: OperationalEventSnapshot,
) -> OperationalDiagnosisPayload:
    """
    Executa somente as nove sentinelas determinísticas protegidas.

    A ordem é fail-closed: contexto tipado, import tardio, guardas de
    drift, reconstrução mínima, sentinelas, projecção, payload e
    validação independente.
    """
    _validar_contexto_tipado(context)

    from app.agents import agent_erro_operacional as legacy_module

    sentinels = _validar_superficie_legada(legacy_module)
    legacy_event = _reconstruir_evento_legado(context)

    projection: OperationalDiagnosisInternal | None = None

    for sentinel in sentinels:
        legacy_result = sentinel(legacy_event)

        if legacy_result is None:
            continue

        sentinel_name = sentinel.__name__
        diagnosis_code = MAPA_SENTINELAS_PARA_CODIGOS[sentinel_name]
        projection = projectar_resultado_operacional(
            diagnostico_codigo=diagnosis_code,
            legacy_result=legacy_result,
        )
        break

    if projection is None:
        projection = _projectar_evento_nao_reconhecido()

    payload = construir_payload_diagnostico_operacional(
        context=context,
        projection=projection,
    )

    validate_operational_diagnosis_payload_against_context(
        context=context,
        projection=projection,
        payload=payload,
    )

    return payload
