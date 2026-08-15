from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.agents.agent_executor import AgentExecutor
from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.shared import BudgetPolicy, SourceRef
from app.agents.mission_factory import create_agent_mission


CREATED_AT = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def _mission(**overrides: object):
    values: dict[str, object] = {
        "mission_type": "sanitizar_contexto_fiscal",
        "target_agent": "data_sanitization_agent",
        "context": {"empresa_id": 7, "faturamento": 1000},
        "context_schema": "data_sanitization.context",
        "context_version": "1.0",
        "output_schema": "data_sanitization.result",
        "output_version": "1.0",
        "scope": "tenant",
        "tenant_id": 42,
        "actor_id": 42,
        "entity_type": "empresa",
        "entity_id": 7,
        "requested_by": "user",
        "authority_level": "leitura",
        "execution_mode": "sombra",
        "source_request_id": "req-l3-executor-001",
        "created_at": CREATED_AT,
        "budget_policy": BudgetPolicy(),
        "sources": [],
    }
    values.update(overrides)
    return create_agent_mission(**values)


def _adapter_test_mission(filename: str, helper: str, **overrides: object):
    path = ROOT / "tests" / filename
    spec = importlib.util.spec_from_file_location(
        f"_l3_purity_{path.stem}", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, helper)(**overrides)


@pytest.mark.asyncio
async def test_valid_mission_resolves_and_returns_canonical_result() -> None:
    mission = _mission()

    result = await AgentExecutor().execute_mission(mission)

    assert isinstance(result, AgentExecutionResult)
    assert result.mission_id == mission.mission_id
    assert result.correlation_id == mission.correlation_id
    assert result.agent_id == mission.target_agent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target", "mission_type"),
    [
        ("unknown_agent", "unknown_mission"),
        ("security_audit_agent", "legacy_only"),
    ],
)
async def test_unknown_or_non_allowlisted_target_fails_closed(
    target: str,
    mission_type: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = AgentExecutor()
    legacy_get_agent = MagicMock()
    legacy_run_all = AsyncMock()
    legacy_runs = [AsyncMock() for _ in executor.registry.get_agents()]
    monkeypatch.setattr(executor.registry, "get_agent", legacy_get_agent)
    monkeypatch.setattr(executor, "run_all", legacy_run_all)
    for agent, legacy_run in zip(
        executor.registry.get_agents().values(), legacy_runs, strict=True
    ):
        monkeypatch.setattr(agent, "run", legacy_run)

    with pytest.raises(LookupError, match="NOT_ALLOWLISTED"):
        await executor.execute_mission(
            _mission(target_agent=target, mission_type=mission_type)
        )

    legacy_get_agent.assert_not_called()
    legacy_run_all.assert_not_awaited()
    for legacy_run in legacy_runs:
        legacy_run.assert_not_awaited()


def test_l3_classifications_are_explicit_and_executive_is_absent() -> None:
    registry = AgentExecutor().registry

    assert registry._l3_classifications == {
        "data_sanitization_agent": "ADVISORY",
        "consistency_audit_agent": "READ_ONLY",
        "memorial_validator_agent": "READ_ONLY",
        "ag_abertura": "ADVISORY",
        "agent_erro_operacional": "READ_ONLY",
    }
    assert set(registry._l3_classifications) == set(registry._l3_adapters)
    assert "EXECUTIVE" not in registry._l3_classifications.values()


def test_l3_allowlist_is_exactly_the_ratified_pure_read_only_pairs() -> None:
    registry = AgentExecutor().registry

    pairs = {
        (target, mission_type)
        for target, missions in registry._l3_adapters.items()
        for mission_type in missions
    }
    assert pairs == {
        ("data_sanitization_agent", "sanitizar_contexto_fiscal"),
        ("consistency_audit_agent", "auditar_consistencia_fiscal"),
        ("memorial_validator_agent", "validar_memorial_fiscal"),
        ("ag_abertura", "orientar_abertura_empresa"),
        ("agent_erro_operacional", "diagnosticar_evento_operacional"),
        (
            "agent_erro_operacional",
            "diagnosticar_evento_operacional_llm_fallback",
        ),
    }


@pytest.mark.asyncio
async def test_ag_encerramento_fails_closed_before_adapter_reader_or_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.agents.adapters.ag_encerramento as adapter_module
    import app.agents.readers.ag_encerramento as reader_module
    import app.database as database_module

    adapter = AsyncMock()
    reader = MagicMock()
    session_factory = MagicMock()
    monkeypatch.setattr(
        adapter_module, "execute_ag_encerramento_mission", adapter
    )
    monkeypatch.setattr(reader_module, "AgEncerramentoReader", reader)
    monkeypatch.setattr(database_module, "SessionLocal", session_factory)

    executor = AgentExecutor()
    legacy_get_agent = MagicMock()
    legacy_run_all = AsyncMock()
    legacy_run = AsyncMock()
    monkeypatch.setattr(executor.registry, "get_agent", legacy_get_agent)
    monkeypatch.setattr(executor, "run_all", legacy_run_all)
    monkeypatch.setattr(
        executor.registry.get_agents()["ag_encerramento"], "run", legacy_run
    )
    with pytest.raises(LookupError, match="NOT_ALLOWLISTED"):
        await executor.execute_mission(
            _mission(
                target_agent="ag_encerramento",
                mission_type="orientar_encerramento_empresa",
            )
        )

    adapter.assert_not_awaited()
    reader.assert_not_called()
    session_factory.assert_not_called()
    legacy_get_agent.assert_not_called()
    legacy_run_all.assert_not_awaited()
    legacy_run.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target", "mission_type", "filename", "helper", "overrides"),
    [
        (
            "data_sanitization_agent", "sanitizar_contexto_fiscal",
            "test_data_sanitization_mission_adapter.py", "_mission", {},
        ),
        (
            "consistency_audit_agent", "auditar_consistencia_fiscal",
            "test_consistency_audit_mission_adapter.py", "_mission", {},
        ),
        (
            "memorial_validator_agent", "validar_memorial_fiscal",
            "test_memorial_validator_mission_adapter.py", "_mission", {},
        ),
        (
            "ag_abertura", "orientar_abertura_empresa",
            "test_ag_abertura_mission_adapter.py", "_missao", {},
        ),
        (
            "agent_erro_operacional", "diagnosticar_evento_operacional",
            "test_agent_erro_operacional_mission_adapter.py", "_mission", {},
        ),
        (
            "agent_erro_operacional",
            "diagnosticar_evento_operacional_llm_fallback",
            "test_agent_erro_operacional_llm_fallback_mission_adapter.py",
            "_mission", {},
        ),
    ],
)
async def test_each_allowlisted_pure_read_only_path_remains_green(
    target: str,
    mission_type: str,
    filename: str,
    helper: str,
    overrides: dict[str, object],
) -> None:
    mission = _adapter_test_mission(filename, helper, **overrides)
    assert mission.target_agent == target
    assert mission.mission_type == mission_type

    executor = AgentExecutor()

    result = await executor.execute_mission(mission)

    assert isinstance(result, AgentExecutionResult)


@pytest.mark.asyncio
async def test_execute_mission_reuses_deterministic_adapter_mission_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.agents.adapters.data_sanitization as adapter_module

    engine = MagicMock()
    monkeypatch.setattr(adapter_module, "construir_payload_sanitizacao", engine)
    mission = _mission(context_schema="schema.nao_autorizado")

    with pytest.raises(Exception):
        await AgentExecutor().execute_mission(mission)

    engine.assert_not_called()


@pytest.mark.asyncio
async def test_execute_mission_reuses_legacy_adapter_context_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.agents.adapters.ag_abertura as adapter_module

    legacy_run = AsyncMock()
    monkeypatch.setattr(adapter_module.ag_abertura_agent, "run", legacy_run)
    mission = _adapter_test_mission(
        "test_ag_abertura_mission_adapter.py",
        "_missao",
        context={"tipo_contribuinte": "sociedade_anonima"},
    )

    with pytest.raises(Exception):
        await AgentExecutor().execute_mission(mission)

    legacy_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_mission_reuses_event_adapter_source_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.agents.engines.agent_erro_operacional as engine_module

    engine = MagicMock()
    monkeypatch.setattr(
        engine_module, "executar_agent_erro_operacional_engine", engine
    )
    mission = _adapter_test_mission(
        "test_agent_erro_operacional_mission_adapter.py",
        "_mission",
    ).model_copy(
        update={
            "sources": [
                SourceRef(
                    fonte_id="fonte-nao-autorizada",
                    uso_pretendido="validar_fato_operacional",
                )
            ]
        }
    )

    with pytest.raises(Exception):
        await AgentExecutor().execute_mission(mission)

    engine.assert_not_called()


@pytest.mark.asyncio
async def test_incompatible_authority_fails_before_adapter() -> None:
    executor = AgentExecutor()
    adapter = AsyncMock()
    executor.registry._l3_adapters["data_sanitization_agent"][
        "sanitizar_contexto_fiscal"
    ] = adapter

    with pytest.raises(PermissionError, match="AUTHORITY"):
        await executor.execute_mission(_mission(authority_level="proposta"))

    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_mission_never_calls_legacy_run_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = AgentExecutor()
    legacy = AsyncMock()
    monkeypatch.setattr(executor, "run_all", legacy)

    await executor.execute_mission(_mission())

    legacy.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target",
    [
        "normative_watchdog",
        "patrol",
        "repair",
        "repair_agent",
        "state_recovery",
        "state_recovery_agent",
    ],
)
async def test_excluded_targets_never_execute(target: str) -> None:
    executor = AgentExecutor()
    forbidden = AsyncMock()
    executor.registry._l3_adapters[target] = {"forbidden": forbidden}
    executor.registry._l3_classifications[target] = "ADVISORY"

    with pytest.raises(PermissionError, match="TARGET_EXCLUDED"):
        await executor.execute_mission(
            _mission(target_agent=target, mission_type="forbidden")
        )

    forbidden.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatched_field", ["mission_id", "correlation_id"])
async def test_result_mission_or_correlation_mismatch_fails_closed(
    mismatched_field: str,
) -> None:
    executor = AgentExecutor()
    mission = _mission()
    valid = await executor.execute_mission(mission)
    mismatch = AgentExecutionResult.model_validate(
        {
            **valid.model_dump(),
            mismatched_field: uuid4(),
        }
    )
    adapter = AsyncMock(return_value=mismatch)
    executor.registry._l3_adapters[mission.target_agent][
        mission.mission_type
    ] = adapter

    with pytest.raises(ValueError, match="L3_RESULT_MISSION_MISMATCH"):
        await executor.execute_mission(mission)


@pytest.mark.asyncio
async def test_invalid_input_and_classification_fail_before_adapter() -> None:
    executor = AgentExecutor()
    adapter = AsyncMock()
    executor.registry._l3_adapters["data_sanitization_agent"][
        "sanitizar_contexto_fiscal"
    ] = adapter

    with pytest.raises(TypeError, match="MISSION_INVALID"):
        await executor.execute_mission({"target_agent": "data_sanitization_agent"})  # type: ignore[arg-type]

    executor.registry._l3_classifications[
        "data_sanitization_agent"
    ] = "EXECUTIVE"
    with pytest.raises(PermissionError, match="CLASSIFICATION"):
        await executor.execute_mission(_mission())

    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_adapter_result_fails_closed() -> None:
    executor = AgentExecutor()
    adapter = AsyncMock(return_value={"status": "sucesso"})
    executor.registry._l3_adapters["data_sanitization_agent"][
        "sanitizar_contexto_fiscal"
    ] = adapter

    with pytest.raises(TypeError, match="RESULT_INVALID"):
        await executor.execute_mission(_mission())


@pytest.mark.asyncio
async def test_legacy_run_all_behavior_is_preserved() -> None:
    executor = AgentExecutor()
    legacy_agent = AsyncMock()
    legacy_agent.name = "legacy_probe"
    legacy_agent.run.return_value = {"agent": "legacy_probe", "status": "ok"}
    executor.registry._agents = {legacy_agent.name: legacy_agent}
    context = {"empresa_id": 42}

    results = await executor.run_all(context)

    legacy_agent.run.assert_awaited_once_with(context)
    assert results[0]["agent"] == "legacy_probe"
    assert results[0]["status"] == "ok"
    assert "executado_em" in results[0]
