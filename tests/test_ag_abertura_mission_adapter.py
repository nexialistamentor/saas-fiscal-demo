
"""

tests/test_ag_abertura_mission_adapter.py — ADR-009 B14.3A.



Cenários contratuais do adapter soberano AgAberturaAgent.

"""



from __future__ import annotations



import ast

import copy

import hashlib

import os

from datetime import datetime, timezone

from decimal import Decimal

from unittest.mock import AsyncMock, patch

from uuid import uuid4



import pytest

from pydantic import ValidationError



from app.agents.adapters.ag_abertura import execute_ag_abertura_mission

from app.agents.contracts.ag_abertura import (

    AgAberturaLink,

    AgAberturaPayload,

    AgAberturaPreExecutionError,

    AgAberturaResultSafetyError,

    AgAberturaResultValidationError,

    CommercialDisclosure,

    EXPECTED_LINKS,

    EXPECTED_LINK_CODES,

    EXPECTED_REVIEW_REASONS,

)

from app.agents.contracts.shared import BudgetPolicy, SourceRef

from app.agents.mission_factory import create_agent_mission



_CREATED_AT = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)



_LEGACY_MEI = {

    "resposta": "**Como abrir MEI em 2026**\n\nSiga o checklist:",

    "requires_payment": False,

    "analysis_type": "abertura_empresa",

    "schema_type": "HowTo",

    "versao": "1.0",

    "payload_estruturado": {

        "tipo_contribuinte": "mei",

        "checklist": [

            {

                "passo": 1,

                "titulo": "Verificar CPF",

                "descricao": "CPF regular.",

                "link": "https://www.gov.br/receitafederal",

            },

        ],

        "avisos_legais": [

            "Este guia nao substitui a consulta a um contador.",

        ],

        "links_uteis": {

            "portal_empreendedor": "https://www.gov.br/empresas-e-negocios/pt-br/empreendedor",

            "redesim": "https://redesim.gov.br",

            "receita_federal": "https://www.gov.br/receitafederal",

        },

    },

}



_LEGACY_EPP = {

    "resposta": "**Como abrir uma empresa (ME/EPP)**\n\nProcesso via REDESIM:",

    "requires_payment": False,

    "analysis_type": "abertura_empresa",

    "schema_type": "HowTo",

    "versao": "1.0",

    "payload_estruturado": {

        "tipo_contribuinte": "epp",

        "checklist": [

            {

                "passo": 1,

                "titulo": "Definir responsabilidade contabil",

                "descricao": "Contador pode ser recomendado.",

                "link": None,

            },

        ],

        "avisos_legais": [

            "Verifique requisitos especificos do seu municipio.",

        ],

        "links_uteis": {

            "portal_empreendedor": "https://www.gov.br/empresas-e-negocios/pt-br/empreendedor",

            "redesim": "https://redesim.gov.br",

            "receita_federal": "https://www.gov.br/receitafederal",

        },

    },

}





def _missao(**overrides):

    kwargs = {

        "mission_type": "orientar_abertura_empresa",

        "target_agent": "ag_abertura",

        "context": {"tipo_contribuinte": "mei"},

        "context_schema": "ag_abertura.context",

        "context_version": "1.0",

        "output_schema": "ag_abertura.result",

        "output_version": "1.0",

        "scope": "utilizador",

        "actor_id": "user-001",

        "requested_by": "user",

        "authority_level": "leitura",

        "execution_mode": "sombra",

        "source_request_id": "req-001",

        "created_at": _CREATED_AT,

    }

    kwargs.update(overrides)

    return create_agent_mission(**kwargs)





def _fake_agent(return_value):

    agent = AsyncMock()

    agent.run = AsyncMock(return_value=return_value)

    return agent





def _links_canonicos():

    return tuple(

        AgAberturaLink(code=c, url=u)

        for c, u in EXPECTED_LINKS.items()

    )





def _payload_base(**overrides):

    kwargs = dict(

        resposta="r",

        analysis_type="abertura_empresa",

        schema_type="HowTo",

        versao="1.0",

        tipo_contribuinte="mei",

        checklist=(),

        avisos_legais=(),

        links_uteis=_links_canonicos(),

        commercial_disclosure=CommercialDisclosure(),

        review_reasons=EXPECTED_REVIEW_REASONS,

        publication_allowed=False,

    )

    kwargs.update(overrides)

    return kwargs





def _assert_matriz_comum_sem_llm(result) -> None:

    assert result.attempt == 1

    assert result.retryable is False

    assert result.requires_human_review is True

    assert result.llm_used is False

    assert result.provider is None

    assert result.tokens_used is None

    assert result.cost_estimated is None

    assert result.cost_actual is None

    assert result.currency is None

    assert result.evidence == []

    assert result.actions_proposed == []

    assert result.actions_executed == []

    assert result.payload_schema == "ag_abertura.result"

    assert result.payload_version == "1.0"





def test_missao_criada_por_factory():

    mission = _missao()

    assert mission.target_agent == "ag_abertura"





@pytest.mark.asyncio

async def test_adapter_e_assincrono():

    import inspect

    assert inspect.iscoroutinefunction(execute_ag_abertura_mission)





@pytest.mark.asyncio

async def test_target_divergente():

    mission = _missao().model_copy(update={"target_agent": "outro_agente"})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_TARGET_MISMATCH"





@pytest.mark.asyncio

async def test_mission_type_divergente():

    mission = _missao().model_copy(update={"mission_type": "outra_missao"})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_TYPE_UNSUPPORTED"





@pytest.mark.asyncio

async def test_context_schema_divergente():

    mission = _missao().model_copy(update={"context_schema": "outro.context"})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "CONTEXT_SCHEMA_UNSUPPORTED"





@pytest.mark.asyncio

async def test_context_version_divergente():

    mission = _missao().model_copy(update={"context_version": "2.0"})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "CONTEXT_VERSION_UNSUPPORTED"





@pytest.mark.asyncio

async def test_output_schema_divergente():

    mission = _missao().model_copy(update={"output_schema": "outro.result"})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "OUTPUT_SCHEMA_UNSUPPORTED"





@pytest.mark.asyncio

async def test_output_version_divergente():

    mission = _missao().model_copy(update={"output_version": "2.0"})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "OUTPUT_VERSION_UNSUPPORTED"





@pytest.mark.asyncio

async def test_scope_divergente():

    mission = _missao().model_copy(update={"scope": "global"})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_SCOPE_UNSUPPORTED"





@pytest.mark.asyncio

async def test_tenant_id_presente():

    mission = _missao().model_copy(update={"tenant_id": 1})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_SCOPE_UNSUPPORTED"





@pytest.mark.asyncio

async def test_authority_level_divergente():

    mission = _missao().model_copy(update={"authority_level": "proposta"})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_AUTHORITY_UNSUPPORTED"





@pytest.mark.asyncio

async def test_requested_by_divergente():

    mission = _missao().model_copy(update={"requested_by": "scheduler"})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_AUTHORITY_UNSUPPORTED"





@pytest.mark.asyncio

async def test_actor_none():

    mission = _missao().model_copy(update={"actor_id": None})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_ACTOR_UNSUPPORTED"





@pytest.mark.asyncio

async def test_actor_booleano():

    mission = _missao().model_copy(update={"actor_id": True})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_ACTOR_UNSUPPORTED"





@pytest.mark.asyncio

async def test_actor_string_vazia():

    mission = _missao().model_copy(update={"actor_id": ""})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_ACTOR_UNSUPPORTED"





@pytest.mark.asyncio

async def test_actor_string_espacos():

    mission = _missao().model_copy(update={"actor_id": "   "})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_ACTOR_UNSUPPORTED"





@pytest.mark.asyncio

async def test_actor_string_valida():

    mission = _missao(actor_id="user-abc")

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "sucesso"





@pytest.mark.asyncio

async def test_actor_inteiro_nao_booleano():

    mission = _missao(actor_id=42)

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "sucesso"





@pytest.mark.asyncio

async def test_source_request_id_ausente():

    mission = _missao().model_copy(update={"source_request_id": None})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_ORIGIN_UNSUPPORTED"





@pytest.mark.asyncio

async def test_source_request_id_vazio():

    mission = _missao().model_copy(update={"source_request_id": ""})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_ORIGIN_UNSUPPORTED"





@pytest.mark.asyncio

async def test_source_request_id_espacos():

    mission = _missao().model_copy(update={"source_request_id": "   "})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_ORIGIN_UNSUPPORTED"





@pytest.mark.asyncio

async def test_source_event_id_presente():

    mission = _missao().model_copy(update={"source_event_id": uuid4()})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_ORIGIN_UNSUPPORTED"





@pytest.mark.asyncio

async def test_schedule_slot_presente():

    mission = _missao().model_copy(update={"schedule_slot": "slot-abc"})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_ORIGIN_UNSUPPORTED"





@pytest.mark.asyncio

async def test_budget_divergente():

    mission = _missao(

        budget_policy=BudgetPolicy(

            allow_llm=True,

            allowed_providers=["local"],

            max_calls=1,

            max_input_chars=100,

            max_output_tokens=100,

            max_cost=Decimal("1.00"),

        )

    )

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_BUDGET_UNSUPPORTED"





@pytest.mark.asyncio

async def test_allowed_providers_nao_vazio():

    budget_divergente = _missao().budget_policy.model_copy(

        update={"allowed_providers": ["local"]}

    )

    mission = _missao().model_copy(update={"budget_policy": budget_divergente})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_BUDGET_UNSUPPORTED"





@pytest.mark.asyncio

async def test_sources_nao_vazio():

    mission = _missao().model_copy(update={

        "sources": [SourceRef(fonte_id="lei-123", uso_pretendido="apoiar_explicacao_ux")]

    })

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "MISSION_SOURCES_UNSUPPORTED"





@pytest.mark.parametrize("valor_invalido", [None, 123, "", "   ", "sa", "corporation"])

@pytest.mark.asyncio

async def test_contexto_tipo_invalido(valor_invalido):

    mission = _missao(context={"tipo_contribuinte": valor_invalido})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "AG_ABERTURA_CONTEXT_INVALID"





@pytest.mark.asyncio

async def test_contexto_campo_extra():

    mission = _missao(context={"tipo_contribuinte": "mei", "campo_extra": "x"})

    with pytest.raises(AgAberturaPreExecutionError) as exc_info:

        await execute_ag_abertura_mission(mission)

    assert exc_info.value.code == "AG_ABERTURA_CONTEXT_INVALID"





@pytest.mark.asyncio

async def test_contexto_normalizacao():

    mission = _missao(context={"tipo_contribuinte": " MEI "})

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "sucesso"

    assert result.payload["tipo_contribuinte"] == "mei"





@pytest.mark.asyncio

async def test_adapter_passa_dict_ao_legado():

    mission = _missao(context={"tipo_contribuinte": "mei"})

    agent = _fake_agent(_LEGACY_MEI)

    await execute_ag_abertura_mission(mission, agent=agent)

    call_args = agent.run.call_args[0][0]

    assert isinstance(call_args, dict)

    assert call_args["tipo_contribuinte"] == "mei"





@pytest.mark.asyncio

async def test_nominal_sombra():

    mission = _missao(execution_mode="sombra")

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "sucesso"

    assert result.mode == "sombra"





@pytest.mark.asyncio

async def test_nominal_dry_run():

    mission = _missao(execution_mode="dry_run")

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "sucesso"

    assert result.mode == "dry_run"





@pytest.mark.asyncio

async def test_nominal_run_chamado_uma_vez():

    mission = _missao()

    agent = _fake_agent(_LEGACY_MEI)

    await execute_ag_abertura_mission(mission, agent=agent)

    agent.run.assert_awaited_once()





@pytest.mark.asyncio

async def test_nominal_attempt_retryable():

    mission = _missao()

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.attempt == 1

    assert result.retryable is False





@pytest.mark.asyncio

async def test_nominal_requires_human_review():

    mission = _missao()

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.requires_human_review is True





@pytest.mark.asyncio

async def test_nominal_commercial_disclosure():

    mission = _missao()

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    cd = result.payload["commercial_disclosure"]

    assert cd["platform_service_requires_payment"] is True

    assert cd["official_process_cost_separate"] is True

    assert cd["pricing_status"] == "pendente_ratificacao"

    assert cd["pricing_policy_id"] is None

    assert cd["price_amount"] is None

    assert cd["currency"] == "BRL"

    assert cd["requires_explicit_consent"] is True





@pytest.mark.asyncio

async def test_nominal_requires_payment_nao_propagado():

    mission = _missao()

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert "requires_payment" not in result.payload





@pytest.mark.asyncio

async def test_nominal_publication_allowed():

    mission = _missao()

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.payload["publication_allowed"] is False





@pytest.mark.asyncio

async def test_nominal_payload_schema_version():

    mission = _missao()

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.payload_schema == "ag_abertura.result"

    assert result.payload_version == "1.0"





@pytest.mark.asyncio

async def test_nominal_llm_metadados_ausentes():

    mission = _missao()

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.llm_used is False

    assert result.provider is None

    assert result.tokens_used is None

    assert result.cost_estimated is None

    assert result.cost_actual is None

    assert result.currency is None





@pytest.mark.asyncio

async def test_nominal_evidence_actions_vazios():

    mission = _missao()

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.evidence == []

    assert result.actions_proposed == []

    assert result.actions_executed == []





@pytest.mark.asyncio

async def test_nominal_temporalidade():

    mission = _missao()

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.started_at.utcoffset().total_seconds() == 0

    assert result.finished_at.utcoffset().total_seconds() == 0

    assert result.finished_at >= result.started_at

    assert isinstance(result.duration_ms, int)

    assert result.duration_ms >= 0





@pytest.mark.asyncio

async def test_nominal_com_agente_real_mei():

    from app.agents.ag_abertura_agent import ag_abertura_agent

    mission = _missao(source_request_id="req-real-mei")

    result = await execute_ag_abertura_mission(mission, agent=ag_abertura_agent)

    assert result.status == "sucesso"

    assert result.payload["tipo_contribuinte"] == "mei"





@pytest.mark.asyncio

async def test_nominal_com_agente_real_epp():

    from app.agents.ag_abertura_agent import ag_abertura_agent

    mission = _missao(context={"tipo_contribuinte": "epp"}, source_request_id="req-real-epp")

    result = await execute_ag_abertura_mission(mission, agent=ag_abertura_agent)

    assert result.status == "sucesso"

    assert result.payload["tipo_contribuinte"] == "epp"





@pytest.mark.asyncio

async def test_review_reasons_exactas():

    mission = _missao()

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert tuple(result.payload["review_reasons"]) == EXPECTED_REVIEW_REASONS





def test_payload_rejeita_review_reasons_vazio():

    with pytest.raises(ValidationError):

        AgAberturaPayload(**_payload_base(review_reasons=()))





def test_payload_rejeita_review_reason_ausente():

    with pytest.raises(ValidationError):

        AgAberturaPayload(**_payload_base(review_reasons=("NORMATIVE_SOURCES_MISSING",)))





def test_payload_rejeita_review_reason_duplicado():

    with pytest.raises(ValidationError):

        AgAberturaPayload(**_payload_base(

            review_reasons=("NORMATIVE_SOURCES_MISSING", "NORMATIVE_SOURCES_MISSING", "COMMERCIAL_POLICY_PENDING")

        ))





def test_payload_rejeita_review_reason_adicional():

    with pytest.raises(ValidationError):

        AgAberturaPayload(**_payload_base(

            review_reasons=EXPECTED_REVIEW_REASONS + ("NORMATIVE_SOURCES_MISSING",)

        ))





def test_payload_rejeita_review_reason_ordem_divergente():

    with pytest.raises(ValidationError):

        AgAberturaPayload(**_payload_base(

            review_reasons=("COMMERCIAL_POLICY_PENDING", "NORMATIVE_SOURCES_MISSING", "TEMPORAL_HARDCODE_PRESENT")

        ))





@pytest.mark.asyncio

async def test_links_uteis_exactos():

    mission = _missao()

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    links = result.payload["links_uteis"]

    assert len(links) == 3

    codes = tuple(lnk["code"] for lnk in links)

    assert codes == EXPECTED_LINK_CODES

    for lnk in links:

        assert lnk["url"] == EXPECTED_LINKS[lnk["code"]]





@pytest.mark.asyncio

async def test_links_nao_vem_do_legado():

    mission = _missao()

    legacy = copy.deepcopy(_LEGACY_MEI)

    legacy["payload_estruturado"]["links_uteis"] = {"portal_empreendedor": "https://malicioso.com"}

    agent = _fake_agent(legacy)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    for lnk in result.payload["links_uteis"]:

        assert lnk["url"] != "https://malicioso.com"

        assert lnk["url"] == EXPECTED_LINKS[lnk["code"]]





def test_link_rejeita_http():

    with pytest.raises(ValidationError):

        AgAberturaLink(code="redesim", url="http://redesim.gov.br")





def test_link_rejeita_codigo_desconhecido():

    with pytest.raises(ValidationError):

        AgAberturaLink(code="codigo_invalido", url="https://redesim.gov.br")





def test_link_rejeita_url_divergente():

    with pytest.raises(ValidationError):

        AgAberturaLink(code="redesim", url="https://redesim-falso.gov.br")





def test_payload_rejeita_links_ausentes():

    with pytest.raises(ValidationError):

        AgAberturaPayload(**_payload_base(links_uteis=()))





def test_payload_rejeita_link_adicional():

    links_extra = _links_canonicos() + (AgAberturaLink(code="redesim", url=EXPECTED_LINKS["redesim"]),)

    with pytest.raises(ValidationError):

        AgAberturaPayload(**_payload_base(links_uteis=links_extra))





def test_payload_rejeita_ordem_links_divergente():

    links_fora_ordem = (

        AgAberturaLink(code="redesim", url=EXPECTED_LINKS["redesim"]),

        AgAberturaLink(code="portal_empreendedor", url=EXPECTED_LINKS["portal_empreendedor"]),

        AgAberturaLink(code="receita_federal", url=EXPECTED_LINKS["receita_federal"]),

    )

    with pytest.raises(ValidationError):

        AgAberturaPayload(**_payload_base(links_uteis=links_fora_ordem))





def test_payload_rejeita_link_duplicado_tres_posicoes():

    links_com_duplicado = (

        AgAberturaLink(code="portal_empreendedor", url=EXPECTED_LINKS["portal_empreendedor"]),

        AgAberturaLink(code="redesim", url=EXPECTED_LINKS["redesim"]),

        AgAberturaLink(code="portal_empreendedor", url=EXPECTED_LINKS["portal_empreendedor"]),

    )

    with pytest.raises(ValidationError):

        AgAberturaPayload(**_payload_base(links_uteis=links_com_duplicado))





@pytest.mark.asyncio

async def test_bloqueio_modo_activo_run_nao_chamado():

    mission = _missao(execution_mode="activo")

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "bloqueado"

    agent.run.assert_not_awaited()





@pytest.mark.asyncio

async def test_bloqueio_modo_activo_alerta():

    mission = _missao(execution_mode="activo")

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert len(result.alerts) == 1

    assert result.alerts[0].code == "EXECUTION_MODE_NOT_AUTHORIZED"





@pytest.mark.asyncio

async def test_bloqueio_modo_activo_matriz_completa():

    mission = _missao(execution_mode="activo")

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "bloqueado"

    assert result.payload == {}

    assert result.error_code is None

    assert result.error_message is None

    _assert_matriz_comum_sem_llm(result)





@pytest.mark.asyncio

async def test_bloqueio_versao_incompativel_run_nao_chamado():

    mission = _missao(agent_version_required="9.9.9")

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "bloqueado"

    agent.run.assert_not_awaited()





@pytest.mark.asyncio

async def test_bloqueio_versao_incompativel_alerta():

    mission = _missao(agent_version_required="9.9.9")

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert len(result.alerts) == 1

    assert result.alerts[0].code == "AGENT_VERSION_INCOMPATIBLE"





@pytest.mark.asyncio

async def test_bloqueio_versao_incompativel_matriz_completa():

    mission = _missao(agent_version_required="9.9.9")

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "bloqueado"

    assert result.payload == {}

    assert result.error_code is None

    assert result.error_message is None

    _assert_matriz_comum_sem_llm(result)





@pytest.mark.asyncio

async def test_versao_compativel_executa():

    mission = _missao(agent_version_required="1.0")

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "sucesso"

    agent.run.assert_awaited_once()





@pytest.mark.asyncio

async def test_versao_none_executa():

    mission = _missao(agent_version_required=None)

    agent = _fake_agent(_LEGACY_MEI)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "sucesso"





@pytest.mark.asyncio

async def test_erro_interno_excecao_run():

    mission = _missao()

    agent = AsyncMock()

    agent.run = AsyncMock(side_effect=RuntimeError("falha interna"))

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "erro"

    assert result.error_code == "AG_ABERTURA_EXECUTION_ERROR"

    assert result.error_message == "Erro interno na execução do agente de abertura"





@pytest.mark.asyncio

async def test_erro_interno_sem_mensagem_bruta():

    mission = _missao()

    agent = AsyncMock()

    agent.run = AsyncMock(side_effect=RuntimeError("mensagem secreta"))

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert "mensagem secreta" not in result.error_message

    assert "Traceback" not in result.error_message

    assert "RuntimeError" not in result.error_message





@pytest.mark.asyncio

async def test_erro_resultado_nao_mapping():

    mission = _missao()

    agent = _fake_agent("string_invalida")

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "erro"

    assert result.error_code == "AG_ABERTURA_EXECUTION_ERROR"





@pytest.mark.asyncio

async def test_erro_payload_estruturado_nao_mapping():

    mission = _missao()

    legacy = copy.deepcopy(_LEGACY_MEI)

    legacy["payload_estruturado"] = "invalido"

    agent = _fake_agent(legacy)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "erro"

    assert result.error_code == "AG_ABERTURA_EXECUTION_ERROR"





@pytest.mark.asyncio

async def test_erro_checklist_nao_lista():

    mission = _missao()

    legacy = copy.deepcopy(_LEGACY_MEI)

    legacy["payload_estruturado"]["checklist"] = "invalido"

    agent = _fake_agent(legacy)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "erro"

    assert result.error_code == "AG_ABERTURA_EXECUTION_ERROR"





@pytest.mark.asyncio

async def test_erro_item_checklist_nao_mapping():

    mission = _missao()

    legacy = copy.deepcopy(_LEGACY_MEI)

    legacy["payload_estruturado"]["checklist"] = ["item_invalido"]

    agent = _fake_agent(legacy)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "erro"

    assert result.error_code == "AG_ABERTURA_EXECUTION_ERROR"





@pytest.mark.asyncio

async def test_erro_avisos_como_string():

    mission = _missao()

    legacy = copy.deepcopy(_LEGACY_MEI)

    legacy["payload_estruturado"]["avisos_legais"] = "aviso como string"

    agent = _fake_agent(legacy)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "erro"

    assert result.error_code == "AG_ABERTURA_EXECUTION_ERROR"





@pytest.mark.asyncio

async def test_erro_campo_legado_ausente():

    mission = _missao()

    legacy = copy.deepcopy(_LEGACY_MEI)

    del legacy["resposta"]

    agent = _fake_agent(legacy)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "erro"

    assert result.error_code == "AG_ABERTURA_EXECUTION_ERROR"





@pytest.mark.asyncio

async def test_erro_campo_escalar_tipo_invalido():

    mission = _missao()

    legacy = copy.deepcopy(_LEGACY_MEI)

    legacy["versao"] = {"objeto": "invalido"}

    agent = _fake_agent(legacy)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "erro"

    assert result.error_code == "AG_ABERTURA_EXECUTION_ERROR"





@pytest.mark.asyncio

async def test_erro_interno_matriz_completa():

    mission = _missao()

    agent = AsyncMock()

    agent.run = AsyncMock(side_effect=RuntimeError("x"))

    result = await execute_ag_abertura_mission(mission, agent=agent)

    assert result.status == "erro"

    assert result.error_code == "AG_ABERTURA_EXECUTION_ERROR"

    assert result.payload == {}

    assert result.alerts == []

    _assert_matriz_comum_sem_llm(result)





@pytest.mark.asyncio

async def test_falha_validacao_cruzada_codigo():

    mission = _missao()

    agent = _fake_agent(_LEGACY_MEI)

    with patch("app.agents.adapters.ag_abertura.validate_result_against_mission", side_effect=ValueError("divergencia")):

        with pytest.raises(AgAberturaResultValidationError) as exc_info:

            await execute_ag_abertura_mission(mission, agent=agent)

    assert exc_info.value.code == "RESULT_MISSION_VALIDATION_FAILED"

    assert exc_info.value.__cause__ is None

    assert exc_info.value.__suppress_context__ is True





@pytest.mark.asyncio

async def test_falha_sanitizacao_codigo():

    mission = _missao()

    agent = _fake_agent(_LEGACY_MEI)

    with patch("app.agents.adapters.ag_abertura.assert_result_sanitized", side_effect=ValueError("violacao")):

        with pytest.raises(AgAberturaResultSafetyError) as exc_info:

            await execute_ag_abertura_mission(mission, agent=agent)

    assert exc_info.value.code == "RESULT_SANITIZATION_FAILED"

    assert exc_info.value.__cause__ is None

    assert exc_info.value.__suppress_context__ is True





@pytest.mark.asyncio

async def test_copia_defensiva_mutacao_legado_nao_afecta_resultado():

    mission = _missao()

    legacy = copy.deepcopy(_LEGACY_MEI)

    agent = _fake_agent(legacy)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    checklist_resultado_antes = copy.deepcopy(result.payload["checklist"])

    legacy["payload_estruturado"]["checklist"][0]["titulo"] = "MUTADO_NO_LEGADO"

    assert result.payload["checklist"] == checklist_resultado_antes





@pytest.mark.asyncio

async def test_copia_defensiva_mutacao_resultado_nao_afecta_legado():

    mission = _missao()

    legacy = copy.deepcopy(_LEGACY_MEI)

    checklist_legado_antes = copy.deepcopy(legacy["payload_estruturado"]["checklist"])

    agent = _fake_agent(legacy)

    result = await execute_ag_abertura_mission(mission, agent=agent)

    result.payload["checklist"][0]["titulo"] = "MUTADO_NO_RESULTADO"

    assert legacy["payload_estruturado"]["checklist"] == checklist_legado_antes





@pytest.mark.asyncio

async def test_copia_defensiva_duas_execucoes():

    mission1 = _missao(source_request_id="req-def-001")

    mission2 = _missao(source_request_id="req-def-002")

    agent = _fake_agent(copy.deepcopy(_LEGACY_MEI))

    result1 = await execute_ag_abertura_mission(mission1, agent=agent)

    result1.payload["checklist"][0]["titulo"] = "MUTADO_EXEC1"

    result2 = await execute_ag_abertura_mission(mission2, agent=agent)

    assert result2.payload["checklist"][0]["titulo"] != "MUTADO_EXEC1"





@pytest.mark.asyncio

async def test_copia_defensiva_nao_altera_checklist_mei():

    from app.agents.ag_abertura_agent import ag_abertura_agent

    from app.constants import CHECKLIST_ABERTURA_MEI

    snapshot = copy.deepcopy(CHECKLIST_ABERTURA_MEI)

    mission = _missao(source_request_id="req-mei-snap")

    result = await execute_ag_abertura_mission(mission, agent=ag_abertura_agent)

    result.payload["checklist"][0]["titulo"] = "MUTADO"

    assert CHECKLIST_ABERTURA_MEI == snapshot





@pytest.mark.asyncio

async def test_copia_defensiva_nao_altera_checklist_epp():

    from app.agents.ag_abertura_agent import ag_abertura_agent

    from app.constants import CHECKLIST_ABERTURA_ME_EPP

    snapshot = copy.deepcopy(CHECKLIST_ABERTURA_ME_EPP)

    mission = _missao(context={"tipo_contribuinte": "epp"}, source_request_id="req-epp-snap")

    result = await execute_ag_abertura_mission(mission, agent=ag_abertura_agent)

    result.payload["checklist"][0]["titulo"] = "MUTADO"

    assert CHECKLIST_ABERTURA_ME_EPP == snapshot





def test_hash_agente_legado_inalterado():

    path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "app", "agents", "ag_abertura_agent.py"))

    with open(path, "rb") as f:

        digest = hashlib.sha256(f.read()).hexdigest().upper()

    assert digest == "872E849A05279FB7BF2674481E98FEA8DA7DFEF08FF3A4ADDDF3210E80911903"





def test_agente_legado_nao_tem_run_mission():

    from app.agents.ag_abertura_agent import AgAberturaAgent

    assert not hasattr(AgAberturaAgent, "run_mission")





def test_adapter_sem_imports_proibidos():

    import app.agents.adapters.ag_abertura as mod

    path = mod.__file__

    with open(path, encoding="utf-8") as f:

        source = f.read()

    tree = ast.parse(source)

    proibidos = {"sqlalchemy", "httpx", "requests", "aiohttp", "agent_scheduler", "agent_executor", "agent_registry", "agentscheduler", "agentexecutor", "agentregistry"}

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            for alias in node.names:

                nome = alias.name.casefold()

                assert not any(p in nome for p in proibidos), f"import proibido: {alias.name}"

        elif isinstance(node, ast.ImportFrom):

            if node.module:

                modulo = node.module.casefold()

                assert not any(p in modulo for p in proibidos), f"import proibido: {node.module}"

            for alias in node.names:

                nome = alias.name.casefold()

                assert not any(p in nome for p in proibidos), f"nome importado proibido: {alias.name}"





def _ficheiro_nao_referencia(caminho_modulo: str, simbolo: str) -> None:

    import importlib.util

    spec = importlib.util.find_spec(caminho_modulo)

    assert spec is not None, f"modulo nao encontrado: {caminho_modulo}"

    with open(spec.origin, encoding="utf-8") as f:

        source = f.read()

    tree = ast.parse(source)

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            for alias in node.names:

                assert alias.name != simbolo, f"{caminho_modulo} importa {simbolo}"

        elif isinstance(node, ast.ImportFrom):

            if node.module and simbolo in node.module:

                pytest.fail(f"{caminho_modulo} importa de {node.module}")

            for alias in node.names:

                assert alias.name != simbolo, f"{caminho_modulo} importa nome {simbolo}"

        elif isinstance(node, ast.Name) and node.id == simbolo:

            pytest.fail(f"{caminho_modulo} referencia {simbolo}")

        elif isinstance(node, ast.Attribute) and node.attr == simbolo:

            pytest.fail(f"{caminho_modulo} referencia atributo {simbolo}")





def test_registry_nao_referencia_adapter():

    _ficheiro_nao_referencia("app.agents.agent_registry", "execute_ag_abertura_mission")





def test_executor_nao_referencia_adapter():

    _ficheiro_nao_referencia("app.agents.agent_executor", "execute_ag_abertura_mission")





def test_scheduler_nao_referencia_adapter():

    _ficheiro_nao_referencia("app.agents.agent_scheduler", "execute_ag_abertura_mission")
