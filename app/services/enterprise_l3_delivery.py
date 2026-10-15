"""M006-C1 — deduplicação transacional LOCAL das entregas L3 Enterprise.

Ledger de EXECUÇÕES (não é uma nova memória de inteligência). Guarda apenas
identidade/hash/status e o resultado L3 já validado; nunca o evento bruto.
Não configura jobs, fontes de eventos, produção, LLM, API ou agentes legados.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID

from app.agents.contracts.agent_erro_operacional import (
    OperationalGlobalEventSnapshot,
    OperationalTenantEventSnapshot,
)
from app.agents.contracts.canonical import build_context_hash
from app.agents.contracts.execution_result import AgentExecutionResult
from app.services.enterprise_l3_event_dispatch import (
    EnterpriseL3DispatchReceipt,
    dispatch_operational_event,
)


_CREATE = """
CREATE TABLE IF NOT EXISTS enterprise_l3_event_delivery (
    event_id TEXT PRIMARY KEY NOT NULL,
    event_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('claimed', 'completed', 'failed')),
    receipt_json TEXT
)
"""


class EnterpriseL3Delivery:
    """Um ledger SQLite explicitamente escolhido; sem DB global ou migrations."""

    def __init__(self, ledger_path: str | Path) -> None:
        if not isinstance(ledger_path, (str, Path)):
            raise TypeError("ENTERPRISE_LEDGER_PATH_INVALID")
        path = Path(ledger_path)
        if not path.is_absolute() or str(path) == ":memory:":
            raise ValueError("ENTERPRISE_LEDGER_PATH_MUST_BE_ABSOLUTE")
        if not path.parent.is_dir():
            raise ValueError("ENTERPRISE_LEDGER_PARENT_MISSING")
        self._path = path

    def _connect(self):
        connection = sqlite3.connect(str(self._path), timeout=2.0)
        connection.execute("PRAGMA busy_timeout=2000")
        return connection

    def _claim_or_replay(self, event_id: UUID, event_hash: str):
        with closing(self._connect()) as conn:
            conn.execute(_CREATE)
            conn.commit()
            try:
                conn.execute("BEGIN IMMEDIATE")
                current = conn.execute(
                    "SELECT event_hash, state, receipt_json "
                    "FROM enterprise_l3_event_delivery WHERE event_id=?",
                    (str(event_id),),
                ).fetchone()

                if current is None:
                    conn.execute(
                        "INSERT INTO enterprise_l3_event_delivery "
                        "(event_id, event_hash, state, receipt_json) "
                        "VALUES (?, ?, 'claimed', NULL)",
                        (str(event_id), event_hash),
                    )
                    conn.commit()
                    return None

                saved_hash, state, receipt_json = current
                if saved_hash != event_hash:
                    raise ValueError("ENTERPRISE_EVENT_PAYLOAD_CONFLICT")
                if state == "claimed":
                    raise RuntimeError("ENTERPRISE_EVENT_IN_PROGRESS")
                if state == "failed":
                    raise RuntimeError("ENTERPRISE_EVENT_RECOVERY_REQUIRED")
                if state != "completed" or not receipt_json:
                    raise RuntimeError("ENTERPRISE_EVENT_RECEIPT_INVALID")
                saved = json.loads(receipt_json)
                if saved["event_id"] != str(event_id):
                    raise RuntimeError("ENTERPRISE_EVENT_RECEIPT_INVALID")
                replay = EnterpriseL3DispatchReceipt(
                    event_id=UUID(saved["event_id"]),
                    mission_id=UUID(saved["mission_id"]),
                    idempotency_key=saved["idempotency_key"],
                    result=AgentExecutionResult.model_validate(saved["result"]),
                )
                if replay.result.mission_id != replay.mission_id:
                    raise RuntimeError("ENTERPRISE_EVENT_RECEIPT_INVALID")
                conn.commit()
                return replay
            except BaseException:
                conn.rollback()
                raise

    def _transition(self, event_id: UUID, event_hash: str, state: str,
                    receipt: EnterpriseL3DispatchReceipt | None = None) -> None:
        saved = None
        if receipt is not None:
            if (receipt.event_id != event_id or
                    receipt.mission_id != receipt.result.mission_id or
                    receipt.result.actions_executed or receipt.result.llm_used):
                raise PermissionError("ENTERPRISE_L3_RECEIPT_NOT_AUTHORIZED")
            saved = json.dumps({
                "event_id": str(receipt.event_id),
                "mission_id": str(receipt.mission_id),
                "idempotency_key": receipt.idempotency_key,
                "result": receipt.result.model_dump(mode="json"),
            }, ensure_ascii=True, separators=(",", ":"))
        with closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute(
                    "UPDATE enterprise_l3_event_delivery "
                    "SET state=?, receipt_json=? "
                    "WHERE event_id=? AND event_hash=? AND state='claimed'",
                    (state, saved, str(event_id), event_hash),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("ENTERPRISE_EVENT_TRANSITION_CONFLICT")

    async def deliver(self, event):
        if type(event) not in (
            OperationalGlobalEventSnapshot,
            OperationalTenantEventSnapshot,
        ):
            raise TypeError("ENTERPRISE_EVENT_NOT_TYPED")
        snapshot = type(event).model_validate(event.model_dump(mode="python"))
        if snapshot.origem != "enterprise_runtime":
            raise PermissionError("ENTERPRISE_EVENT_ORIGIN_NOT_ALLOWED")
        if snapshot.tipo != "schema_drift":
            raise PermissionError("ENTERPRISE_EVENT_TYPE_NOT_ALLOWED")

        event_hash = build_context_hash(snapshot.model_dump(mode="python"))
        existing = self._claim_or_replay(snapshot.event_id, event_hash)
        if existing is not None:
            return existing

        try:
            result = await dispatch_operational_event(snapshot)
            self._transition(snapshot.event_id, event_hash, "completed", result)
            return result
        except BaseException:
            # Falha ou cancelamento: nunca repetir automaticamente.
            self._transition(snapshot.event_id, event_hash, "failed")
            raise
