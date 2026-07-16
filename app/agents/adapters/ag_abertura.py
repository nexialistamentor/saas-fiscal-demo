
"""

app/agents/adapters/ag_abertura.py — ADR-009 B14.3A.



Adapter soberano assíncrono para AgAberturaAgent.

Executa em modo sombra ou dry_run. Modo activo produz bloqueio auditável.

Não modifica o agente legado. Não persiste. Não activa LLM, BD, HTTP ou scheduler.

"""



from __future__ import annotations



import time

from collections.abc import Mapping

from datetime import datetime, timedelta, timezone

from uuid import uuid4



from app.agents.ag_abertura_agent import AgAberturaAgent, ag_abertura_agent

from app.agents.contracts.ag_abertura import (

    AgAberturaChecklistItem,

    AgAberturaContext,

    AgAberturaLink,

    AgAberturaPayload,

    AgAberturaPreExecutionError,

    AgAberturaResultSafetyError,

    AgAberturaResultValidationError,

    CommercialDisclosure,

    EXPECTED_LINKS,

    EXPECTED_REVIEW_REASONS,

)

from app.agents.contracts.execution_result import AgentExecutionResult

from app.agents.contracts.mission import AgentMission

from app.agents.contracts.sanitization import assert_result_sanitized

from app.agents.contracts.shared import AgentAlert, BudgetPolicy

from app.agents.contracts.validation import validate_result_against_mission





_TARGET_AGENT = "ag_abertura"

_MISSION_TYPE = "orientar_abertura_empresa"

_CONTEXT_SCHEMA = "ag_abertura.context"

_CONTEXT_VERSION = "1.0"

_OUTPUT_SCHEMA = "ag_abertura.result"

_OUTPUT_VERSION = "1.0"

_AGENT_VERSION = "1.0"





def _validar_fronteira(mission: AgentMission) -> None:

    if mission.target_agent != _TARGET_AGENT:

        raise AgAberturaPreExecutionError("MISSION_TARGET_MISMATCH") from None

    if mission.mission_type != _MISSION_TYPE:

        raise AgAberturaPreExecutionError("MISSION_TYPE_UNSUPPORTED") from None

    if mission.context_schema != _CONTEXT_SCHEMA:

        raise AgAberturaPreExecutionError("CONTEXT_SCHEMA_UNSUPPORTED") from None

    if mission.context_version != _CONTEXT_VERSION:

        raise AgAberturaPreExecutionError("CONTEXT_VERSION_UNSUPPORTED") from None

    if mission.output_schema != _OUTPUT_SCHEMA:

        raise AgAberturaPreExecutionError("OUTPUT_SCHEMA_UNSUPPORTED") from None

    if mission.output_version != _OUTPUT_VERSION:

        raise AgAberturaPreExecutionError("OUTPUT_VERSION_UNSUPPORTED") from None

    if mission.scope != "utilizador" or mission.tenant_id is not None:

        raise AgAberturaPreExecutionError("MISSION_SCOPE_UNSUPPORTED") from None

    actor = mission.actor_id

    if actor is None:

        raise AgAberturaPreExecutionError("MISSION_ACTOR_UNSUPPORTED") from None

    if isinstance(actor, bool):

        raise AgAberturaPreExecutionError("MISSION_ACTOR_UNSUPPORTED") from None

    if isinstance(actor, str) and not actor.strip():

        raise AgAberturaPreExecutionError("MISSION_ACTOR_UNSUPPORTED") from None

    if mission.requested_by not in {"user", "system"}:

        raise AgAberturaPreExecutionError("MISSION_AUTHORITY_UNSUPPORTED") from None

    if mission.authority_level != "leitura":

        raise AgAberturaPreExecutionError("MISSION_AUTHORITY_UNSUPPORTED") from None

    if (

        mission.source_request_id is None

        or not mission.source_request_id.strip()

    ):

        raise AgAberturaPreExecutionError("MISSION_ORIGIN_UNSUPPORTED") from None

    if mission.source_event_id is not None:

        raise AgAberturaPreExecutionError("MISSION_ORIGIN_UNSUPPORTED") from None

    if mission.schedule_slot is not None:

        raise AgAberturaPreExecutionError("MISSION_ORIGIN_UNSUPPORTED") from None

    if mission.budget_policy != BudgetPolicy():

        raise AgAberturaPreExecutionError("MISSION_BUDGET_UNSUPPORTED") from None

    if mission.sources:

        raise AgAberturaPreExecutionError("MISSION_SOURCES_UNSUPPORTED") from None





def _versao_incompativel(mission: AgentMission) -> bool:

    required = mission.agent_version_required

    if required is None:

        return False

    return required != _AGENT_VERSION





def _reconstruir_checklist(

    raw_checklist: list | tuple,

) -> tuple[AgAberturaChecklistItem, ...]:

    items = []

    for item in raw_checklist:

        if not isinstance(item, Mapping):

            raise TypeError("item do checklist nao e Mapping")

        raw = dict(item)

        items.append(

            AgAberturaChecklistItem(

                passo=raw["passo"],

                titulo=raw["titulo"],

                descricao=raw["descricao"],

                link=raw.get("link"),

            )

        )

    return tuple(items)





def _reconstruir_links_uteis() -> tuple[AgAberturaLink, ...]:

    return tuple(

        AgAberturaLink(code=code, url=url)

        for code, url in EXPECTED_LINKS.items()

    )





def _reconstruir_payload(

    legacy_result: dict,

    tipo_contribuinte: str,

) -> dict:

    legacy_payload_raw = legacy_result["payload_estruturado"]

    if not isinstance(legacy_payload_raw, Mapping):

        raise TypeError("payload legado invalido")

    legacy_payload = dict(legacy_payload_raw)



    checklist_raw = legacy_payload["checklist"]

    if not isinstance(checklist_raw, (list, tuple)):

        raise TypeError("checklist legado invalido")

    checklist = _reconstruir_checklist(checklist_raw)



    avisos_raw = legacy_payload["avisos_legais"]

    if not isinstance(avisos_raw, (list, tuple)):

        raise TypeError("avisos_legais legado invalido")

    avisos_legais = tuple(avisos_raw)



    links_uteis = _reconstruir_links_uteis()

    commercial_disclosure = CommercialDisclosure()



    payload_model = AgAberturaPayload(

        resposta=legacy_result["resposta"],

        analysis_type=legacy_result["analysis_type"],

        schema_type=legacy_result["schema_type"],

        versao=legacy_result["versao"],

        tipo_contribuinte=tipo_contribuinte,

        checklist=checklist,

        avisos_legais=avisos_legais,

        links_uteis=links_uteis,

        commercial_disclosure=commercial_disclosure,

        review_reasons=EXPECTED_REVIEW_REASONS,

        publication_allowed=False,

    )



    return payload_model.model_dump(mode="python")





def _construir_resultado(

    *,

    mission: AgentMission,

    status: str,

    started_at: datetime,

    duration_ms: int,

    payload: dict,

    alerts: list[AgentAlert],

    error_code: str | None,

    error_message: str | None,

) -> AgentExecutionResult:

    finished_at = started_at + timedelta(milliseconds=duration_ms)

    return AgentExecutionResult(

        execution_id=uuid4(),

        attempt=1,

        agent_id=_TARGET_AGENT,

        agent_version=_AGENT_VERSION,

        mission_type=mission.mission_type,

        mission_id=mission.mission_id,

        correlation_id=mission.correlation_id,

        status=status,

        scope=mission.scope,

        tenant_id=mission.tenant_id,

        started_at=started_at,

        finished_at=finished_at,

        duration_ms=duration_ms,

        mode=mission.execution_mode,

        alerts=alerts,

        evidence=[],

        actions_proposed=[],

        actions_executed=[],

        requires_human_review=True,

        payload_schema=mission.output_schema,

        payload_version=mission.output_version,

        payload=payload,

        llm_used=False,

        retryable=False,

        error_code=error_code,

        error_message=error_message,

    )





def _finalizar(

    mission: AgentMission,

    result: AgentExecutionResult,

) -> AgentExecutionResult:

    try:

        validate_result_against_mission(mission, result)

    except Exception:

        raise AgAberturaResultValidationError() from None

    try:

        assert_result_sanitized(result.model_dump(mode="json"))

    except Exception:

        raise AgAberturaResultSafetyError() from None

    return result





async def execute_ag_abertura_mission(

    mission: AgentMission,

    agent: AgAberturaAgent = ag_abertura_agent,

) -> AgentExecutionResult:

    """

    Executa a missao AgAberturaAgent em modo sombra ou dry_run.

    Modo activo e versao incompativel produzem bloqueio auditavel.

    Nao modifica o agente legado. Nao persiste. Nao activa LLM, BD ou scheduler.

    """

    _validar_fronteira(mission)



    try:

        context_model = AgAberturaContext(**mission.context)

    except Exception:

        raise AgAberturaPreExecutionError("AG_ABERTURA_CONTEXT_INVALID") from None



    if mission.execution_mode == "activo":

        started_at = datetime.now(timezone.utc)

        tick_start = time.perf_counter_ns()

        tick_end = time.perf_counter_ns()

        duration_ms = max(0, round((tick_end - tick_start) / 1_000_000))

        alert = AgentAlert(

            code="EXECUTION_MODE_NOT_AUTHORIZED",

            severity="alto",

            message="Modo activo não autorizado neste canário.",

            evidence_refs=[],

        )

        result = _construir_resultado(

            mission=mission,

            status="bloqueado",

            started_at=started_at,

            duration_ms=duration_ms,

            payload={},

            alerts=[alert],

            error_code=None,

            error_message=None,

        )

        return _finalizar(mission, result)



    if _versao_incompativel(mission):

        started_at = datetime.now(timezone.utc)

        tick_start = time.perf_counter_ns()

        tick_end = time.perf_counter_ns()

        duration_ms = max(0, round((tick_end - tick_start) / 1_000_000))

        alert = AgentAlert(

            code="AGENT_VERSION_INCOMPATIBLE",

            severity="alto",

            message="Versão do agente incompatível com a missão.",

            evidence_refs=[],

        )

        result = _construir_resultado(

            mission=mission,

            status="bloqueado",

            started_at=started_at,

            duration_ms=duration_ms,

            payload={},

            alerts=[alert],

            error_code=None,

            error_message=None,

        )

        return _finalizar(mission, result)



    started_at = datetime.now(timezone.utc)

    tick_start = time.perf_counter_ns()



    try:

        legacy_result = await agent.run(

            context_model.model_dump(mode="python")

        )

        if not isinstance(legacy_result, Mapping):

            raise TypeError("resultado legado invalido")

        legacy_dict = dict(legacy_result)

        payload_dict = _reconstruir_payload(

            legacy_result=legacy_dict,

            tipo_contribuinte=context_model.tipo_contribuinte,

        )

        tick_end = time.perf_counter_ns()

        duration_ms = max(0, round((tick_end - tick_start) / 1_000_000))

    except Exception:

        tick_end = time.perf_counter_ns()

        duration_ms = max(0, round((tick_end - tick_start) / 1_000_000))

        result = _construir_resultado(

            mission=mission,

            status="erro",

            started_at=started_at,

            duration_ms=duration_ms,

            payload={},

            alerts=[],

            error_code="AG_ABERTURA_EXECUTION_ERROR",

            error_message="Erro interno na execução do agente de abertura",

        )

        return _finalizar(mission, result)



    result = _construir_resultado(

        mission=mission,

        status="sucesso",

        started_at=started_at,

        duration_ms=duration_ms,

        payload=payload_dict,

        alerts=[],

        error_code=None,

        error_message=None,

    )

    return _finalizar(mission, result)
