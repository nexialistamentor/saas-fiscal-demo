from __future__ import annotations

import sqlite3

from sqlalchemy.exc import IntegrityError

from app.agents.contracts.canonical import build_effect_idempotency_key
from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.mission import AgentMission
from app.agents.contracts.validation import validate_result_against_mission
from app.database import SessionLocal
from app.models import AlertaFiscal


PATROL_ALERT_EFFECT_CONTRACT_VERSION = "1.0"
_PATROL_MISSION_TYPE = "patrulhar_base_normativa"
_PATROL_TARGET_AGENT = "normative_watchdog"

_EFFECT_IDEMPOTENCY_CONSTRAINT = (
    "uq_alertas_fiscais_effect_idempotency_key"
)
_SQLITE_EFFECT_IDEMPOTENCY_UNIQUE_SIGNATURE = (
    "UNIQUE constraint failed: "
    "alertas_fiscais.effect_idempotency_key"
)


def _is_effect_idempotency_unique_violation(
    exc: IntegrityError,
) -> bool:
    orig = exc.orig
    diag = getattr(orig, "diag", None)

    if diag is not None:
        return (
            getattr(diag, "constraint_name", None)
            == _EFFECT_IDEMPOTENCY_CONSTRAINT
        )

    if isinstance(orig, sqlite3.IntegrityError):
        return str(orig) == _SQLITE_EFFECT_IDEMPOTENCY_UNIQUE_SIGNATURE

    return False


def _empresa_id_da_missao(mission: AgentMission) -> int | None:
    if mission.scope == "global":
        if mission.tenant_id is not None:
            raise ValueError("PATROL_GLOBAL_TENANT_FORBIDDEN")
        return None

    if mission.scope == "tenant":
        if mission.tenant_id is None:
            raise ValueError("PATROL_TENANT_REQUIRED")
        return mission.tenant_id

    raise ValueError("PATROL_SCOPE_UNSUPPORTED")


def _validar_autoridade(mission: AgentMission) -> None:
    if mission.mission_type != _PATROL_MISSION_TYPE:
        raise ValueError("PATROL_MISSION_TYPE_UNSUPPORTED")

    if mission.target_agent != _PATROL_TARGET_AGENT:
        raise ValueError("PATROL_TARGET_MISMATCH")

    if mission.requested_by != "scheduler":
        raise ValueError("PATROL_REQUESTER_UNSUPPORTED")

    if mission.authority_level != "leitura":
        raise ValueError("PATROL_AUTHORITY_UNSUPPORTED")

    if mission.execution_mode != "activo":
        raise ValueError("PATROL_MODE_UNSUPPORTED")

    if not mission.schedule_slot:
        raise ValueError("PATROL_SCHEDULE_SLOT_REQUIRED")


def persist_patrol_alerts(
    *,
    mission: AgentMission,
    result: AgentExecutionResult,
) -> None:
    _validar_autoridade(mission)
    validate_result_against_mission(mission, result)

    agent_id = result.agent_id
    alerts = result.alerts

    if not agent_id.strip():
        raise ValueError("PATROL_AGENT_ID_REQUIRED")

    empresa_id = _empresa_id_da_missao(mission)

    db = SessionLocal()
    try:
        for alert in alerts:
            effect_idempotency_key = build_effect_idempotency_key(
                mission_idempotency_key=mission.idempotency_key,
                effect_type="alert",
                agent_id=agent_id,
                effect_payload=alert.model_dump(mode="json"),
                contract_version=PATROL_ALERT_EFFECT_CONTRACT_VERSION,
            )

            try:
                with db.begin_nested():
                    db.add(
                        AlertaFiscal(
                            effect_idempotency_key=effect_idempotency_key,
                            agente=agent_id,
                            tipo=alert.code,
                            descricao=alert.message,
                            nivel=alert.severity,
                            empresa_id=empresa_id,
                        )
                    )
                    db.flush()
            except IntegrityError as exc:
                if _is_effect_idempotency_unique_violation(exc):
                    continue
                raise

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
