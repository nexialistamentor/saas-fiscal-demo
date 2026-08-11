"""RED: retry idempotente nao pode provocar rollback de efeito irmao."""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import models
from app.agents.contracts.canonical import build_effect_idempotency_key
from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.shared import AgentAlert
from app.agents.mission_factory import create_agent_mission
from app.agents import patrol_effect_gate
from app.models import AlertaFiscal


def _sqlite_engine_with_real_savepoints(tmp_path):
    db_path = tmp_path / "patrol_effect_gate.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")

    @event.listens_for(engine, "connect")
    def _sqlite_connect(dbapi_connection, _connection_record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _sqlite_begin(connection):
        connection.exec_driver_sql("BEGIN")

    models.Base.metadata.create_all(bind=engine)
    return engine


def _mission_and_result(*, duplicate_first: bool):
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
        schedule_slot="2026-08-10T20:00:00Z",
    )

    duplicate = AgentAlert(
        code="TESTE_DUPLICADO",
        severity="alto",
        message="efeito ja persistido",
    )
    sibling = AgentAlert(
        code="TESTE_IRMAO",
        severity="medio",
        message="efeito legitimo da mesma execucao",
    )

    alerts = [duplicate, sibling] if duplicate_first else [sibling, duplicate]
    now = datetime.now(timezone.utc)

    result = AgentExecutionResult(
        execution_id=uuid4(),
        attempt=2,
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
        alerts=alerts,
        evidence=[],
        actions_proposed=[],
        actions_executed=[],
        requires_human_review=False,
        payload_schema=mission.output_schema,
        payload_version=mission.output_version,
        payload={"total_alertas": 2},
        llm_used=False,
    )

    duplicate_key = build_effect_idempotency_key(
        mission_idempotency_key=mission.idempotency_key,
        effect_type="alert",
        agent_id=result.agent_id,
        effect_payload=duplicate.model_dump(mode="json"),
        contract_version=patrol_effect_gate.PATROL_ALERT_EFFECT_CONTRACT_VERSION,
    )

    return mission, result, duplicate_key


@pytest.mark.parametrize(
    "duplicate_first",
    [True, False],
    ids=["duplicate_then_sibling", "sibling_then_duplicate"],
)
def test_duplicate_effect_does_not_rollback_sibling(
    tmp_path,
    duplicate_first,
):
    engine = _sqlite_engine_with_real_savepoints(tmp_path)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    mission, result, duplicate_key = _mission_and_result(
        duplicate_first=duplicate_first,
    )

    seed = Session()
    try:
        seed.add(
            AlertaFiscal(
                effect_idempotency_key=duplicate_key,
                agente="normative_watchdog",
                tipo="TESTE_DUPLICADO",
                descricao="efeito ja persistido",
                nivel="alto",
                empresa_id=37,
            )
        )
        seed.commit()
    finally:
        seed.close()

    try:
        with patch.object(
            patrol_effect_gate,
            "SessionLocal",
            side_effect=Session,
        ):
            patrol_effect_gate.persist_patrol_alerts(
                mission=mission,
                result=result,
            )

        verify = Session()
        try:
            duplicate_count = (
                verify.query(AlertaFiscal)
                .filter(
                    AlertaFiscal.effect_idempotency_key == duplicate_key,
                )
                .count()
            )
            sibling_count = (
                verify.query(AlertaFiscal)
                .filter(
                    AlertaFiscal.tipo == "TESTE_IRMAO",
                    AlertaFiscal.empresa_id == 37,
                )
                .count()
            )
        finally:
            verify.close()

        assert duplicate_count == 1
        assert sibling_count == 1
    finally:
        engine.dispose()
