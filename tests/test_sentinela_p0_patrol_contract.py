from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.contracts.mission import AgentMission


# RED-01 ORIGINAL INVALIDADO
# Motivo: usava AgAbertura como sujeito da patrulha automatica.
# O contrato soberano existente de AgAbertura e request/utilizador:
# scope=utilizador, source_request_id, requested_by user/system.
# Nao deve ser reutilizado como missao scheduler/tenant.
#
# O invariante sobrevive: nenhuma execucao automatica pode contornar
# a fronteira soberana. A patrulha passa a ter contrato proprio.


@pytest.mark.asyncio
async def test_automatic_patrol_does_not_use_legacy_agent_executor_run_all():
    db = MagicMock()

    with (
        patch(
            "app.agents.agent_executor.AgentExecutor.run_all",
            new_callable=AsyncMock,
        ) as legacy_run_all,
        patch(
            "app.agents.agent_scheduler.SessionLocal",
            return_value=db,
        ),
        patch(
            "app.agents.agent_scheduler.InsightEngine",
        ) as insight_cls,
    ):
        insight_cls.return_value.gerar_insights_empresa.return_value = {
            "oportunidades": []
        }

        from app.agents.agent_scheduler import AgentScheduler

        scheduler = AgentScheduler()
        await scheduler._executar_agents_uma_empresa(37)

    assert legacy_run_all.await_count == 0, (
        "Patrulha automatica ainda atravessa AgentExecutor.run_all legado: "
        f"execucoes={legacy_run_all.await_count}"
    )


@pytest.mark.asyncio
async def test_global_patrol_does_not_exercise_executive_authority():
    db_global = MagicMock()
    db_watchdog = MagicMock()
    db_watchdog.query.return_value.all.return_value = []

    with (
        patch(
            "app.agents.agent_scheduler.SessionLocal",
            side_effect=[db_global, db_watchdog],
        ),
        patch(
            "app.agents.agent_scheduler.salvar_snapshot_metricas",
        ),
        patch(
            "app.agents.agent_scheduler.verificar_alertas_metricas",
        ),
        patch(
            "app.agents.agent_scheduler.verificar_regressao_performance",
        ),
        patch(
            "app.agents.state_recovery_agent.verificar_recuperacao_engines",
        ) as recover_engines,
        patch(
            "app.agents.normative_validation_agent.normative_validation_agent.run",
            new_callable=AsyncMock,
            return_value={
                "promovidas_mva": 0,
                "promovidas_pmpf": 0,
                "rejeitadas": 0,
            },
        ) as normative_validation,
        patch(
            "app.agents.normative_watchdog_agent.normative_watchdog_agent.run",
            new_callable=AsyncMock,
            return_value={"total_alertas": 0},
        ),
    ):
        from app.agents.agent_scheduler import AgentScheduler

        scheduler = AgentScheduler()
        await scheduler._finalizar_ciclo_metricas_e_cache()

    violacoes = []

    if recover_engines.call_count:
        violacoes.append("engine_recovery")

    if normative_validation.await_count:
        violacoes.append("normative_validation")

    assert violacoes == [], (
        "A patrulha global exerceu autoridade executiva automatica: "
        + ", ".join(violacoes)
    )

@pytest.mark.asyncio
async def test_normative_watchdog_runs_once_per_global_multi_tenant_cycle():
    db = MagicMock()
    db.query.return_value.all.return_value = []

    with (
        patch(
            "app.agents.agent_scheduler._listar_empresa_ids",
            return_value=[101, 102, 103],
        ),
        patch(
            "app.agents.agent_scheduler.SessionLocal",
            return_value=db,
        ),
        patch(
            "app.agents.agent_scheduler.InsightEngine",
        ) as insight_cls,
        patch(
            "app.agents.agent_scheduler.execute_patrol_mission",
            new_callable=AsyncMock,
            return_value=None,
        ) as patrol_run,
        patch(
            "app.agents.agent_scheduler.salvar_snapshot_metricas",
        ),
        patch(
            "app.agents.agent_scheduler.verificar_alertas_metricas",
        ),
        patch(
            "app.agents.agent_scheduler.verificar_regressao_performance",
        ),
        patch(
            "app.agents.agent_scheduler.analysis_cache",
            new={},
        ),
    ):
        insight_cls.return_value.gerar_insights_empresa.return_value = {
            "oportunidades": []
        }

        from app.agents.agent_scheduler import AgentScheduler

        scheduler = AgentScheduler()
        await scheduler.executar_ciclo_multi_tenant()

    assert patrol_run.await_count == 1, (
        "Patrulha normativa soberana deve executar exactamente uma vez "
        "por ciclo global multi-tenant; execucoes observadas="
        f"{patrol_run.await_count}"
    )



@pytest.mark.asyncio
async def test_multi_tenant_patrol_isolates_tenant_failures():
    empresa_ids = [101, 102, 103]
    executadas = []
    db = MagicMock()

    async def executar_empresa(_self, empresa_id):
        executadas.append(empresa_id)
        if empresa_id == 101:
            raise RuntimeError("falha sintetica tenant 101")

    with (
        patch(
            "app.agents.agent_scheduler._listar_empresa_ids",
            return_value=empresa_ids,
        ),
        patch(
            "app.agents.agent_scheduler.SessionLocal",
            return_value=db,
        ),
        patch(
            "app.agents.agent_scheduler.AgentScheduler._executar_agents_uma_empresa",
            new=executar_empresa,
        ),
        patch(
            "app.agents.agent_scheduler.AgentScheduler._finalizar_ciclo_metricas_e_cache",
            new_callable=AsyncMock,
        ) as finalizar,
    ):
        from app.agents.agent_scheduler import AgentScheduler

        scheduler = AgentScheduler()

        erro_propagado = None
        try:
            await scheduler.executar_ciclo_multi_tenant()
        except Exception as exc:
            erro_propagado = exc

    violacoes = []

    if erro_propagado is not None:
        violacoes.append(
            "falha_tenant_propagou="
            + type(erro_propagado).__name__
        )

    if executadas != empresa_ids:
        violacoes.append(
            f"tenants_executados={executadas}"
        )

    if finalizar.await_count != 1:
        violacoes.append(
            f"finalizacao_global={finalizar.await_count}"
        )

    assert violacoes == [], (
        "Falha de um tenant interrompeu o ciclo multi-tenant: "
        + "; ".join(violacoes)
    )

@pytest.mark.asyncio
async def test_agent_executor_does_not_open_persistence_session_for_alerts():
    agent = MagicMock()
    agent.name = "agent_sintetico"
    agent.run = AsyncMock(
        return_value={
            "agent": "agent_sintetico",
            "alertas": [
                {
                    "tipo": "TESTE",
                    "descricao": "alerta sintetico",
                    "nivel": "baixo",
                }
            ],
        }
    )

    context = {"empresa_id": 37}

    import app.agents.agent_executor as executor_module

    session_factory = MagicMock()

    with patch.object(
        executor_module,
        "SessionLocal",
        session_factory,
        create=True,
    ):
        executor = executor_module.AgentExecutor()
        executor.registry._agents = {
            agent.name: agent,
        }

        await executor.run_all(context)

    agent.run.assert_awaited_once_with(context)
    session_factory.assert_not_called()

@pytest.mark.asyncio
async def test_normative_watchdog_detector_does_not_persist_alerts():
    from app.agents.normative_watchdog_agent import NormativeWatchdogAgent

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.count.return_value = 0

    tabela = [
        {
            "estado": "PA",
            "ncm": "12345678",
            "vigencia_fim": "2020-01-01",
            "fonte_legal": "fonte-teste",
            "nivel_confianca_fonte": "oficial",
            "importado_por": "teste",
        }
    ]

    with (
        patch(
            "app.agents.normative_watchdog_agent.SessionLocal",
            return_value=db,
        ),
        patch(
            "app.agents.normative_watchdog_agent._consultar_dou",
            return_value=[],
        ),
    ):
        agent = NormativeWatchdogAgent()
        resultado = await agent.run({"tabela_normativa": tabela})

    assert resultado["alertas"], "A prova precisa produzir pelo menos um alerta."

    assert db.add.call_count == 0, (
        "NormativeWatchdog.run() persistiu durante a deteccao: "
        f"db.add={db.add.call_count}"
    )
    assert db.commit.call_count == 0, (
        "NormativeWatchdog.run() confirmou escrita durante a deteccao: "
        f"db.commit={db.commit.call_count}"
    )

@pytest.mark.asyncio
async def test_global_patrol_reaches_sovereign_patrol_mission_boundary():
    import importlib

    scheduler_module = importlib.import_module(
        "app.agents.agent_scheduler"
    )

    patrol_runner = AsyncMock(return_value=None)
    db = MagicMock()
    db.query.return_value.all.return_value = []

    with (
        patch.object(
            scheduler_module,
            "execute_patrol_mission",
            patrol_runner,
        ),
        patch.object(
            scheduler_module,
            "SessionLocal",
            return_value=db,
        ),
        patch.object(
            scheduler_module,
            "salvar_snapshot_metricas",
        ),
        patch.object(
            scheduler_module,
            "verificar_alertas_metricas",
        ),
        patch.object(
            scheduler_module,
            "verificar_regressao_performance",
        ),
    ):
        scheduler = scheduler_module.AgentScheduler()
        await scheduler._finalizar_ciclo_metricas_e_cache()

    patrol_runner.assert_awaited_once()

    mission = patrol_runner.await_args.args[0]

    assert isinstance(mission, AgentMission)
    assert mission.mission_type == "patrulhar_base_normativa"
    assert mission.target_agent == "normative_watchdog"
    assert mission.context_schema == "normative_watchdog.context"
    assert mission.output_schema == "normative_watchdog.result"
    assert mission.scope == "global"
    assert mission.tenant_id is None
    assert mission.requested_by == "scheduler"
    assert mission.authority_level == "leitura"
    assert mission.execution_mode == "activo"
    assert mission.schedule_slot



@pytest.mark.parametrize(
    ("scope", "tenant_id", "expected_empresa_id"),
    [
        ("global", None, None),
        ("tenant", 37, 37),
    ],
)
def test_patrol_alert_effect_gate_preserves_mission_scope(
    scope,
    tenant_id,
    expected_empresa_id,
):
    import importlib
    from unittest.mock import MagicMock, patch

    from app.agents.contracts.shared import AgentAlert
    from app.agents.mission_factory import create_agent_mission

    try:
        effect_gate = importlib.import_module(
            "app.agents.patrol_effect_gate"
        )
    except ModuleNotFoundError:
        pytest.fail(
            "Catraca soberana de efeitos da patrulha ausente: "
            "app.agents.patrol_effect_gate"
        )

    mission = create_agent_mission(
        mission_type="patrulhar_base_normativa",
        target_agent="normative_watchdog",
        context={},
        context_schema="normative_watchdog.context",
        output_schema="normative_watchdog.result",
        scope=scope,
        tenant_id=tenant_id,
        requested_by="scheduler",
        authority_level="leitura",
        execution_mode="activo",
        schedule_slot="2026-08-08T21:00:00Z",
    )

    alerta = AgentAlert(
        code="TESTE_PATRULHA",
        severity="baixo",
        message="alerta sintetico de patrulhamento",
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with (
        patch.object(
            effect_gate,
            "SessionLocal",
            return_value=db,
        ),
    ):
        from datetime import datetime, timezone
        from uuid import uuid4

        from app.agents.contracts.execution_result import AgentExecutionResult

        result = AgentExecutionResult(
            execution_id=uuid4(),
            attempt=1,
            agent_id="normative_watchdog",
            agent_version="1.0",
            mission_type=mission.mission_type,
            mission_id=mission.mission_id,
            correlation_id=mission.correlation_id,
            status="sucesso",
            scope=mission.scope,
            tenant_id=mission.tenant_id,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            duration_ms=0,
            mode=mission.execution_mode,
            alerts=[alerta],
            evidence=[],
            actions_proposed=[],
            actions_executed=[],
            requires_human_review=False,
            payload_schema=mission.output_schema,
            payload_version=mission.output_version,
            payload={"total_alertas": 1},
            llm_used=False,
        )

        effect_gate.persist_patrol_alerts(
            mission=mission,
            result=result,
        )

    alerta_persistido = db.add.call_args.args[0]

    assert alerta_persistido.empresa_id == expected_empresa_id, (
        "Catraca alterou a identidade de escopo da missao: "
        f"scope={scope}; tenant_id={tenant_id}; "
        f"empresa_id_persistida={alerta_persistido.empresa_id}"
    )

    assert db.add.call_count == 1
    assert db.commit.call_count == 1


def test_patrol_alert_effect_gate_persists_canonical_effect_idempotency_key():
    import importlib
    from datetime import datetime, timezone
    from unittest.mock import MagicMock, patch
    from uuid import uuid4

    from app.agents.contracts.canonical import build_effect_idempotency_key
    from app.agents.contracts.execution_result import AgentExecutionResult
    from app.agents.contracts.shared import AgentAlert
    from app.agents.mission_factory import create_agent_mission

    effect_gate = importlib.import_module(
        "app.agents.patrol_effect_gate"
    )

    mission = create_agent_mission(
        mission_type="patrulhar_base_normativa",
        target_agent="normative_watchdog",
        context={},
        context_schema="normative_watchdog.context",
        output_schema="normative_watchdog.result",
        scope="tenant",
        tenant_id=37,
        requested_by="scheduler",
        authority_level="leitura",
        execution_mode="activo",
        schedule_slot="2026-08-08T21:00:00Z",
    )

    alerta = AgentAlert(
        code="TESTE_IDEMPOTENCIA",
        severity="alto",
        message="alerta canonico",
    )

    result = AgentExecutionResult(
        execution_id=uuid4(),
        attempt=1,
        agent_id="normative_watchdog",
        agent_version="1.0",
        mission_type=mission.mission_type,
        mission_id=mission.mission_id,
        correlation_id=mission.correlation_id,
        status="sucesso",
        scope=mission.scope,
        tenant_id=mission.tenant_id,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        duration_ms=0,
        mode=mission.execution_mode,
        alerts=[alerta],
        evidence=[],
        actions_proposed=[],
        actions_executed=[],
        requires_human_review=False,
        payload_schema=mission.output_schema,
        payload_version=mission.output_version,
        payload={"total_alertas": 1},
        llm_used=False,
    )

    expected_key = build_effect_idempotency_key(
        mission_idempotency_key=mission.idempotency_key,
        effect_type="alert",
        agent_id=result.agent_id,
        effect_payload=alerta.model_dump(mode="json"),
        contract_version="1.0",
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with patch.object(
        effect_gate,
        "SessionLocal",
        return_value=db,
    ):
        effect_gate.persist_patrol_alerts(
            mission=mission,
            result=result,
        )

    persisted = db.add.call_args.args[0]

    assert getattr(
        persisted,
        "effect_idempotency_key",
        None,
    ) == expected_key



def test_patrol_effect_gate_does_not_merge_distinct_scheduled_missions():
    import importlib
    from datetime import datetime, timezone
    from unittest.mock import MagicMock, patch
    from uuid import uuid4

    from app.agents.contracts.execution_result import AgentExecutionResult
    from app.agents.contracts.shared import AgentAlert
    from app.agents.mission_factory import create_agent_mission

    effect_gate = importlib.import_module(
        "app.agents.patrol_effect_gate"
    )

    alerta = AgentAlert(
        code="TESTE_MISSOES_DISTINTAS",
        severity="medio",
        message="mesmo alerta em duas patrulhas legitimas",
    )

    missions = [
        create_agent_mission(
            mission_type="patrulhar_base_normativa",
            target_agent="normative_watchdog",
            context={},
            context_schema="normative_watchdog.context",
            output_schema="normative_watchdog.result",
            scope="tenant",
            tenant_id=37,
            requested_by="scheduler",
            authority_level="leitura",
            execution_mode="activo",
            schedule_slot=slot,
        )
        for slot in (
            "2026-08-08T21:00:00Z",
            "2026-08-08T22:00:00Z",
        )
    ]

    results = []
    for mission in missions:
        now = datetime.now(timezone.utc)
        results.append(
            AgentExecutionResult(
                execution_id=uuid4(),
                attempt=1,
                agent_id="normative_watchdog",
                agent_version="1.0",
                mission_type=mission.mission_type,
                mission_id=mission.mission_id,
                correlation_id=mission.correlation_id,
                status="sucesso",
                scope=mission.scope,
                tenant_id=mission.tenant_id,
                started_at=now,
                finished_at=now,
                duration_ms=0,
                mode=mission.execution_mode,
                alerts=[alerta],
                evidence=[],
                actions_proposed=[],
                actions_executed=[],
                requires_human_review=False,
                payload_schema=mission.output_schema,
                payload_version=mission.output_version,
                payload={"total_alertas": 1},
                llm_used=False,
            )
        )

    assert missions[0].idempotency_key != missions[1].idempotency_key

    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [
        None,
        object(),
    ]

    with patch.object(
        effect_gate,
        "SessionLocal",
        return_value=db,
    ):
        for mission, result in zip(missions, results):
            effect_gate.persist_patrol_alerts(
                mission=mission,
                result=result,
            )

    assert db.add.call_count == 2, (
        "Duas missoes logicamente distintas foram fundidas "
        "pela deduplicacao temporal"
    )



@pytest.mark.asyncio
async def test_patrol_adapter_builds_result_before_effect_gate():
    import importlib
    from unittest.mock import AsyncMock, patch

    from app.agents.mission_factory import create_agent_mission

    patrol_module = importlib.import_module(
        "app.agents.adapters.patrol"
    )

    mission = create_agent_mission(
        mission_type="patrulhar_base_normativa",
        target_agent="normative_watchdog",
        context={},
        context_schema="normative_watchdog.context",
        output_schema="normative_watchdog.result",
        scope="global",
        tenant_id=None,
        requested_by="scheduler",
        authority_level="leitura",
        execution_mode="activo",
        schedule_slot="2026-08-08T21:00:00Z",
    )

    raw_result = {
        "alertas": [
            {
                "tipo": "TESTE_PATRULHA",
                "nivel": "baixo",
                "descricao": "alerta sintetico de patrulhamento",
            }
        ],
        "ufs_sem_cobertura": [],
        "ncms_expirados": [],
    }

    with (
        patch.object(
            patrol_module.normative_watchdog_agent,
            "run",
            new_callable=AsyncMock,
            return_value=raw_result,
        ),
        patch.object(
            patrol_module,
            "persist_patrol_alerts",
        ) as effect_gate,
    ):
        result = await patrol_module.execute_patrol_mission(mission)

    effect_gate.assert_called_once_with(
        mission=mission,
        result=result,
    )

    assert result.mission_id == mission.mission_id
    assert result.agent_id == "normative_watchdog"
    assert len(result.alerts) == 1



def _resultado_para_effect_gate(mission, *, agent_id=None):
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.agents.contracts.execution_result import AgentExecutionResult

    now = datetime.now(timezone.utc)

    return AgentExecutionResult(
        execution_id=uuid4(),
        attempt=1,
        agent_id=agent_id or mission.target_agent,
        agent_version="1.0",
        mission_type=mission.mission_type,
        mission_id=mission.mission_id,
        correlation_id=mission.correlation_id,
        status="sucesso",
        scope=mission.scope,
        tenant_id=mission.tenant_id,
        started_at=now,
        finished_at=now,
        duration_ms=0,
        mode=mission.execution_mode,
        alerts=[],
        evidence=[],
        actions_proposed=[],
        actions_executed=[],
        requires_human_review=False,
        payload_schema=mission.output_schema,
        payload_version=mission.output_version,
        payload={"total_alertas": 0},
        llm_used=False,
    )


def test_patrol_effect_gate_rejects_non_patrol_mission_before_db():
    import importlib
    from unittest.mock import patch

    import pytest

    from app.agents.mission_factory import create_agent_mission

    effect_gate = importlib.import_module(
        "app.agents.patrol_effect_gate"
    )

    mission = create_agent_mission(
        mission_type="outra_missao",
        target_agent="normative_watchdog",
        context={},
        context_schema="normative_watchdog.context",
        output_schema="normative_watchdog.result",
        scope="global",
        requested_by="scheduler",
        authority_level="leitura",
        execution_mode="activo",
        schedule_slot="2026-08-11T14:00:00Z",
    )
    result = _resultado_para_effect_gate(mission)

    with patch.object(effect_gate, "SessionLocal") as session_factory:
        with pytest.raises(ValueError):
            effect_gate.persist_patrol_alerts(
                mission=mission,
                result=result,
            )

    session_factory.assert_not_called()


def test_patrol_effect_gate_rejects_non_watchdog_target_before_db():
    import importlib
    from unittest.mock import patch

    import pytest

    from app.agents.mission_factory import create_agent_mission

    effect_gate = importlib.import_module(
        "app.agents.patrol_effect_gate"
    )

    mission = create_agent_mission(
        mission_type="patrulhar_base_normativa",
        target_agent="auditor_fiscal",
        context={},
        context_schema="normative_watchdog.context",
        output_schema="normative_watchdog.result",
        scope="global",
        requested_by="scheduler",
        authority_level="leitura",
        execution_mode="activo",
        schedule_slot="2026-08-11T14:01:00Z",
    )
    result = _resultado_para_effect_gate(mission)

    with patch.object(effect_gate, "SessionLocal") as session_factory:
        with pytest.raises(ValueError):
            effect_gate.persist_patrol_alerts(
                mission=mission,
                result=result,
            )

    session_factory.assert_not_called()


def test_patrol_effect_gate_revalidates_result_against_mission_before_db():
    import importlib
    from unittest.mock import patch

    import pytest

    from app.agents.mission_factory import create_agent_mission

    effect_gate = importlib.import_module(
        "app.agents.patrol_effect_gate"
    )

    mission = create_agent_mission(
        mission_type="patrulhar_base_normativa",
        target_agent="normative_watchdog",
        context={},
        context_schema="normative_watchdog.context",
        output_schema="normative_watchdog.result",
        scope="global",
        requested_by="scheduler",
        authority_level="leitura",
        execution_mode="activo",
        schedule_slot="2026-08-11T14:02:00Z",
    )
    result = _resultado_para_effect_gate(
        mission,
        agent_id="auditor_fiscal",
    )

    with patch.object(effect_gate, "SessionLocal") as session_factory:
        with pytest.raises(ValueError):
            effect_gate.persist_patrol_alerts(
                mission=mission,
                result=result,
            )

    session_factory.assert_not_called()
