"""Prova PostgreSQL real da idempotencia da patrulha."""

import importlib.util
import socket
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import psycopg
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.agents import patrol_effect_gate
from app.agents.contracts.canonical import build_effect_idempotency_key
from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.shared import AgentAlert
from app.agents.mission_factory import create_agent_mission
from app.models import AlertaFiscal


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_0042 = (
    ROOT / "migrations" / "versions"
    / "0042_patrol_effect_idempotency.py"
)


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "test_patrol_effect_idempotency_0042",
        MIGRATION_0042,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Nao foi possivel carregar migration 0042")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _is_postgresql_unavailable(error):
    sqlstate = error.sqlstate
    return (
        sqlstate is None
        or sqlstate == "57P03"
        or sqlstate.startswith("08")
    )


@pytest.fixture(scope="module")
def postgresql_patrol():
    name = f"patrol-idempotency-{uuid.uuid4().hex[:12]}"
    database = f"patrol_{uuid.uuid4().hex[:12]}"
    password = uuid.uuid4().hex
    port = _free_port()
    container_id = None
    engine = None

    try:
        result = subprocess.run(
            [
                "docker", "run", "--detach",
                "--name", name,
                "--label", "mission=SENTINELA-P0-PATROL-IDEMPOTENCY",
                "-e", "POSTGRES_USER=patrol",
                "-e", f"POSTGRES_PASSWORD={password}",
                "-e", f"POSTGRES_DB={database}",
                "-p", f"127.0.0.1:{port}:5432",
                "postgres:16-alpine",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise AssertionError(
                f"docker run falhou: {result.stderr}"
            )

        container_id = result.stdout.strip()
        plain_url = (
            f"postgresql://patrol:{password}"
            f"@127.0.0.1:{port}/{database}"
        )
        url = plain_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

        deadline = time.monotonic() + 60
        consecutive = 0
        last_error = None

        while time.monotonic() < deadline:
            try:
                with psycopg.connect(
                    plain_url,
                    connect_timeout=2,
                ) as conn:
                    assert conn.execute(
                        "SELECT 1"
                    ).fetchone() == (1,)
                consecutive += 1
                if consecutive >= 2:
                    break
            except psycopg.OperationalError as exc:
                if not _is_postgresql_unavailable(exc):
                    raise
                consecutive = 0
                last_error = exc
                time.sleep(0.25)
        else:
            raise AssertionError(
                f"PostgreSQL nao ficou pronto: {last_error!r}"
            )

        engine = create_engine(url)

        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE alertas_fiscais (
                    id SERIAL PRIMARY KEY,
                    agente VARCHAR,
                    tipo VARCHAR,
                    descricao VARCHAR,
                    nivel VARCHAR,
                    empresa_id INTEGER,
                    relatorio_analise_id INTEGER,
                    criado_em TIMESTAMP,
                    silenciado BOOLEAN DEFAULT FALSE,
                    processado BOOLEAN NOT NULL DEFAULT FALSE,
                    processado_em TIMESTAMP,
                    processado_por VARCHAR(100),
                    notas_resolucao VARCHAR(1000)
                )
            """))

            operations = Operations(
                MigrationContext.configure(conn)
            )
            migration = _load_migration()
            migration.op = operations
            migration.upgrade()

        yield engine

    finally:
        if engine is not None:
            engine.dispose()
        if container_id is not None:
            subprocess.run(
                ["docker", "rm", "--force", name],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )



CONSTRAINT_NAME = "uq_alertas_fiscais_effect_idempotency_key"


def test_postgresql_reports_exact_effect_idempotency_constraint(
    postgresql_patrol,
):
    engine = postgresql_patrol
    key = "b" * 64

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO alertas_fiscais (
                    effect_idempotency_key
                )
                VALUES (:key)
                """
            ),
            {"key": key},
        )

    with pytest.raises(IntegrityError) as captured:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO alertas_fiscais (
                        effect_idempotency_key
                    )
                    VALUES (:key)
                    """
                ),
                {"key": key},
            )

    assert (
        captured.value.orig.diag.constraint_name
        == CONSTRAINT_NAME
    )
    assert (
        patrol_effect_gate._is_effect_idempotency_unique_violation(
            captured.value
        )
        is True
    )


def test_postgresql_allows_multiple_null_effect_keys(
    postgresql_patrol,
):
    engine = postgresql_patrol

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO alertas_fiscais (
                    effect_idempotency_key
                )
                VALUES (NULL), (NULL)
                """
            )
        )

        count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM alertas_fiscais
                WHERE effect_idempotency_key IS NULL
                """
            )
        ).scalar_one()

    assert count == 2



def _mission_and_result(*, duplicate_first: bool):
    slot = (
        "2026-08-10T21:00:00Z"
        if duplicate_first
        else "2026-08-10T22:00:00Z"
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
        schedule_slot=slot,
    )

    duplicate = AgentAlert(
        code="PG_DUPLICADO",
        severity="alto",
        message=f"efeito duplicado {slot}",
    )
    sibling = AgentAlert(
        code="PG_IRMAO",
        severity="medio",
        message=f"efeito irmao {slot}",
    )

    alerts = (
        [duplicate, sibling]
        if duplicate_first
        else [sibling, duplicate]
    )

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
        contract_version=(
            patrol_effect_gate.PATROL_ALERT_EFFECT_CONTRACT_VERSION
        ),
    )

    sibling_key = build_effect_idempotency_key(
        mission_idempotency_key=mission.idempotency_key,
        effect_type="alert",
        agent_id=result.agent_id,
        effect_payload=sibling.model_dump(mode="json"),
        contract_version=(
            patrol_effect_gate.PATROL_ALERT_EFFECT_CONTRACT_VERSION
        ),
    )

    return mission, result, duplicate_key, sibling_key


@pytest.mark.parametrize(
    "duplicate_first",
    [True, False],
    ids=[
        "duplicate_then_sibling",
        "sibling_then_duplicate",
    ],
)
def test_postgresql_duplicate_effect_does_not_rollback_sibling(
    postgresql_patrol,
    duplicate_first,
):
    engine = postgresql_patrol
    Session = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    (
        mission,
        result,
        duplicate_key,
        sibling_key,
    ) = _mission_and_result(
        duplicate_first=duplicate_first,
    )

    seed = Session()
    try:
        seed.add(
            AlertaFiscal(
                effect_idempotency_key=duplicate_key,
                agente="normative_watchdog",
                tipo="PG_DUPLICADO",
                descricao="efeito ja persistido",
                nivel="alto",
                empresa_id=37,
            )
        )
        seed.commit()
    finally:
        seed.close()

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
                AlertaFiscal.effect_idempotency_key
                == duplicate_key
            )
            .count()
        )
        sibling_count = (
            verify.query(AlertaFiscal)
            .filter(
                AlertaFiscal.effect_idempotency_key
                == sibling_key
            )
            .count()
        )
    finally:
        verify.close()

    assert duplicate_count == 1
    assert sibling_count == 1

def test_postgresql_0042_downgrade_is_physically_reversible(
    postgresql_patrol,
):
    engine = postgresql_patrol

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            operations = Operations(
                MigrationContext.configure(conn)
            )
            migration = _load_migration()
            migration.op = operations
            migration.downgrade()

            column_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'alertas_fiscais'
                      AND column_name = 'effect_idempotency_key'
                    """
                )
            ).scalar_one()

            constraint_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM pg_constraint
                    WHERE conname = :constraint_name
                    """
                ),
                {"constraint_name": CONSTRAINT_NAME},
            ).scalar_one()

            assert column_count == 0
            assert constraint_count == 0
        finally:
            transaction.rollback()

    with engine.connect() as conn:
        restored_column_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'alertas_fiscais'
                  AND column_name = 'effect_idempotency_key'
                """
            )
        ).scalar_one()

        restored_constraint_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM pg_constraint
                WHERE conname = :constraint_name
                """
            ),
            {"constraint_name": CONSTRAINT_NAME},
        ).scalar_one()

    assert restored_column_count == 1
    assert restored_constraint_count == 1
