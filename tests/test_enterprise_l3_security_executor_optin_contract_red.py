"""M006-C3 — opt-in local de SecurityAudit na fronteira central L3.

A allowlist global por defeito permanece intacta; nenhuma activacao produtiva.
"""
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from app.agents.agent_executor import AgentExecutor
from app.agents.mission_factory import create_agent_mission


def _security_mission(**overrides):
    args = dict(
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
    args.update(overrides)
    return create_agent_mission(**args)


@pytest.mark.asyncio
async def test_c3_security_optin_reaches_pure_shadow_adapter(monkeypatch):
    from app.agents.security_audit_agent import security_audit_agent

    legacy = AsyncMock(side_effect=AssertionError("SECURITY_LEGACY_MUST_NOT_RUN"))
    monkeypatch.setattr(security_audit_agent, "run", legacy)
    executor = AgentExecutor(enable_security_shadow=True)
    mission = _security_mission()
    result = await executor.execute_mission(mission)

    assert result.agent_id == "security_audit_agent"
    assert result.mission_id == mission.mission_id
    assert result.mode == "sombra"
    assert result.status == "sucesso"
    assert result.payload["alert_codes"] == [
        "MULTI_ACCOUNT_PATTERN",
        "USER_REQUEST_VOLUME",
        "MISSING_USER_AGENT_VOLUME",
    ]
    assert result.requires_human_review is True
    assert result.payload["publication_allowed"] is False
    assert result.payload["security_action_allowed"] is False
    assert result.actions_proposed == []
    assert result.actions_executed == []
    assert result.llm_used is False
    legacy.assert_not_awaited()


@pytest.mark.asyncio
async def test_c3_default_executor_stays_ratified_and_closed():
    executor = AgentExecutor()
    assert "security_audit_agent" not in executor.registry._l3_adapters
    with pytest.raises(LookupError, match="L3_TARGET_NOT_ALLOWLISTED"):
        await executor.execute_mission(_security_mission())


@pytest.mark.asyncio
async def test_c3_optin_does_not_open_legacy_mission():
    with pytest.raises(LookupError, match="L3_MISSION_TYPE_NOT_ALLOWLISTED"):
        await AgentExecutor(enable_security_shadow=True).execute_mission(
            _security_mission(mission_type="legacy_only")
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides", [
    {"execution_mode": "activo"},
    {"authority_level": "proposta"},
    {"requested_by": "user"},
    {"scope": "tenant", "tenant_id": 1},
])
async def test_c3_optin_still_respects_security_boundary(overrides):
    mission = _security_mission(**overrides)
    with pytest.raises(PermissionError):
        await AgentExecutor(enable_security_shadow=True).execute_mission(mission)


@pytest.mark.parametrize("bad_value", [None, 1, "true", [], {}])
def test_c3_optin_requires_exact_boolean(bad_value):
    with pytest.raises(TypeError, match="L3_SECURITY_OPTIN_INVALID"):
        AgentExecutor(enable_security_shadow=bad_value)
