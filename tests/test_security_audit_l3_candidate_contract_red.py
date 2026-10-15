"""M006-C2: fronteira de seguranca L3 candidata, sem allowlist produtiva."""
from uuid import uuid4

import pytest

from app.agents.agent_executor import AgentExecutor
from app.agents.mission_factory import create_agent_mission


def _mission(**override):
    params = dict(
        target_agent="security_audit_agent",
        mission_type="auditar_seguranca_agregada",
        context_schema="security_audit.context",
        output_schema="security_audit.result",
        context={
            "source_kind": "enterprise_aggregated_request_logs",
            "window_minutes": 60,
            "max_distinct_accounts_per_ip": 4,
            "max_requests_per_user": 101,
            "requests_without_user_agent": 21,
        },
        scope="global",
        requested_by="system",
        authority_level="leitura",
        execution_mode="sombra",
        source_event_id=uuid4(),
        agent_version_required="1.0",
    )
    params.update(override)
    return create_agent_mission(**params)


@pytest.mark.asyncio
async def test_c2_agente_seguranca_avalia_agregados_sem_identificadores(monkeypatch):
    from app.agents.adapters.security_audit import execute_security_audit_mission
    from app.agents.security_audit_agent import security_audit_agent

    async def forbidden_legacy_run(context):
        raise AssertionError("LEGACY_SECURITY_AGENT_MUST_NOT_RUN")

    monkeypatch.setattr(security_audit_agent, "run", forbidden_legacy_run)
    mission = _mission()
    result = await execute_security_audit_mission(mission)
    assert result.status == "sucesso"
    assert result.agent_id == "security_audit_agent"
    assert result.mode == "sombra"
    assert result.requires_human_review is True
    assert result.payload["alert_codes"] == [
        "MULTI_ACCOUNT_PATTERN",
        "USER_REQUEST_VOLUME",
        "MISSING_USER_AGENT_VOLUME",
    ]
    assert result.payload["total_alerts"] == 3
    assert result.payload["publication_allowed"] is False
    assert result.payload["security_action_allowed"] is False
    assert result.actions_executed == []
    assert result.actions_proposed == []
    assert result.llm_used is False
    dumped = result.model_dump_json()
    assert "192.168." not in dumped
    assert "user_id" not in dumped
    assert "email" not in dumped.lower()


@pytest.mark.asyncio
async def test_c2_limiar_exato_nao_dispara_alerta():
    from app.agents.adapters.security_audit import execute_security_audit_mission

    context = {
        "source_kind": "enterprise_aggregated_request_logs",
        "window_minutes": 60,
        "max_distinct_accounts_per_ip": 3,
        "max_requests_per_user": 100,
        "requests_without_user_agent": 20,
    }
    result = await execute_security_audit_mission(_mission(context=context))
    assert result.status == "sucesso"
    assert result.payload["alert_codes"] == []
    assert result.payload["total_alerts"] == 0


@pytest.mark.asyncio
async def test_c2_rejeita_identificadores_brutos():
    from app.agents.adapters.security_audit import execute_security_audit_mission
    context = dict(_mission().context)
    context["unexpected_counter"] = 1
    with pytest.raises(PermissionError, match="SECURITY_L3_CONTEXT_INVALID"):
        await execute_security_audit_mission(_mission(context=context))
    sensitive = dict(_mission().context)
    sensitive["ip"] = "192.168.1.1"
    with pytest.raises(ValueError, match="ContextSanitizationGuard"):
        _mission(context=sensitive)


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides", [
    {"execution_mode": "activo"},
    {"requested_by": "user"},
    {"authority_level": "proposta"},
    {"scope": "tenant", "tenant_id": 1},
    {"agent_version_required": "2.0"},
])
async def test_c2_missao_sem_autoridade_rejeitada(overrides):
    from app.agents.adapters.security_audit import execute_security_audit_mission
    with pytest.raises(PermissionError, match="SECURITY_L3_BOUNDARY_DENIED"):
        await execute_security_audit_mission(_mission(**overrides))


def test_c2_limiares_iguais_aos_do_agente_legado():
    from app.agents.security_audit_agent import (
        _MAX_CONTAS_POR_IP, _MAX_REQUESTS_POR_USER,
    )
    from app.agents.engines.security_audit import (
        MAX_CONTAS_POR_IP, MAX_REQUESTS_POR_USER,
        MAX_REQUESTS_SEM_UA,
    )
    assert (_MAX_CONTAS_POR_IP, _MAX_REQUESTS_POR_USER) == (3, 100)
    assert (MAX_CONTAS_POR_IP, MAX_REQUESTS_POR_USER, MAX_REQUESTS_SEM_UA) == (3, 100, 20)


@pytest.mark.asyncio
async def test_c2_allowlist_ratificada_permanece_fechada():
    with pytest.raises(LookupError, match="L3_TARGET_NOT_ALLOWLISTED"):
        await AgentExecutor().execute_mission(_mission())
