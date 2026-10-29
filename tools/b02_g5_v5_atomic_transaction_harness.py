#!/usr/bin/env python3
"""G5 V5 isolated transaction harness. Never creates institutional authority.

Caller owns COMMIT/ROLLBACK. Only pre-existing, independently verified decisions
may be supplied to stage_policy_activation; no default decision is synthesized.
"""
from __future__ import annotations
import json
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from app.services.enterprise_b02_policy_activation_atomicity import stage_policy_activation

DB = "solveris_b02_r4g_test"
ROLE = "solveris_b02_policy_writer"

class Stop(RuntimeError):
    pass

def assert_writer(conn):
    identity = tuple(conn.execute(text("SELECT current_database(), session_user, current_user")).one())
    if identity != (DB, ROLE, ROLE):
        raise Stop("WRONG_DATABASE_OR_WRITER")
    revision = conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
    if revision != "0063_adr020_policy_activation_atomicity":
        raise Stop("WRONG_ALEMBIC_REVISION")

def stage(conn, request):
    """Stage only; deliberately never commits or creates a decision."""
    assert_writer(conn)
    required = ("execution", "activation", "generation_id", "outbox_id", "provenance")
    if set(request) != set(required):
        raise Stop("EXACT_REQUEST_FIELDS_REQUIRED")
    return stage_policy_activation(conn, **request)

def reconcile_unit(engine, execution_id, activation_id, generation_id, outbox_id):
    """Independent read-only check after known or uncertain commit outcome."""
    from app import models
    from app.models_policy_activation_atomicity import PolicyActivationGeneration, PolicyActivationOutboxEvent
    tables = (
        (models.PolicyActivationExecution.__table__, "policy_activation_execution_id", execution_id),
        (models.PolicyActivation.__table__, "policy_activation_id", activation_id),
        (PolicyActivationGeneration.__table__, "policy_activation_generation_id", generation_id),
        (PolicyActivationOutboxEvent.__table__, "policy_activation_outbox_event_id", outbox_id),
    )
    from sqlalchemy import select
    with engine.connect() as conn:
        assert_writer(conn)
        rows = []
        for table, column, value in tables:
            rows.append(conn.execute(select(table).where(table.c[column] == value)).mappings().one_or_none())
        conn.rollback()
    if all(row is None for row in rows):
        return "ABSENT"
    if any(row is None for row in rows):
        return "PARTIAL_CONFLICT"
    e,a,g,o=rows
    for row in (a,g,o):
        for key in ("policy_activation_execution_id","policy_decision_id",
                    "policy_decision_record_hash","policy_id","policy_version","policy_hash"):
            if row[key]!=e[key]:
                return "EXACT_PREDECESSOR_CONFLICT"
    if a["policy_activation_execution_record_hash"]!=e["record_hash"]:
        return "EXECUTION_HASH_LINK_CONFLICT"
    for row in (g,o):
        if row["policy_activation_id"]!=activation_id or row["policy_activation_record_hash"]!=a["record_hash"]:
            return "ACTIVATION_HASH_LINK_CONFLICT"
    if o["policy_activation_generation_id"]!=generation_id or o["policy_activation_generation_hash"]!=g["record_hash"]:
        return "GENERATION_HASH_LINK_CONFLICT"
    if g["provenance"]!=o["provenance"]:
        return "PROVENANCE_CONFLICT"
    if e["state"]!="concluida" or a["state"]!="activa" or not g["is_complete"]:
        return "INCOMPLETE_UNIT_CONFLICT"
    return "PRESENT_FOUR_RECORDS_EXACT_LINKS_VERIFIED"

def run(engine, request, *, commit=False):
    """Explicit transaction boundary; no automatic retry on uncertain ACK."""
    execution_id = request["execution"]["policy_activation_execution_id"]
    activation_id = request["activation"]["policy_activation_id"]
    generation_id, outbox_id = request["generation_id"], request["outbox_id"]
    baseline = reconcile_unit(engine, execution_id, activation_id, generation_id, outbox_id)
    if baseline not in ("ABSENT", "PRESENT_FOUR_RECORDS_EXACT_LINKS_VERIFIED"):
        raise Stop("PREEXISTING_UNIT_CONFLICT_" + baseline)
    try:
        with engine.begin() as conn:
            result = stage(conn, request)
            if not commit:
                raise _RollbackProbe(result)
    except _RollbackProbe as probe:
        status = reconcile_unit(engine, execution_id, activation_id, generation_id, outbox_id)
        if status != baseline:
            raise Stop("ROLLBACK_CHANGED_BASELINE_" + baseline + "_TO_" + status)
        return {"status": "ROLLBACK_RECONCILED", "staged": probe.result}
    except Exception:
        # Unknown COMMIT ACK must be classified, never retried automatically.
        try:
            status = reconcile_unit(engine, execution_id, activation_id, generation_id, outbox_id)
        except Exception:
            status = "UNKNOWN_STOP_NO_RETRY"
        raise Stop("TRANSACTION_FAILED_RECONCILIATION_" + status) from None
    status = reconcile_unit(engine, execution_id, activation_id, generation_id, outbox_id)
    if status != "PRESENT_FOUR_RECORDS_EXACT_LINKS_VERIFIED":
        raise Stop("POSTCOMMIT_" + status)
    return {"status": status, "staged": result}

class _RollbackProbe(Exception):
    def __init__(self, result):
        self.result = result

def main():
    import argparse, os
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, help="Verified pre-existing decision and exact IDs in JSON")
    parser.add_argument("--commit", action="store_true", help="Only after all gates verified")
    args = parser.parse_args()
    if args.commit:
        raise Stop("LIVE_COMMIT_DISABLED_PENDING_INDEPENDENT_EVIDENCE_GATES")
    dsn = os.environ.get("SOLVERIS_B02_POLICY_WRITER_DSN")
    if not dsn:
        raise Stop("DSN_REQUIRED")
    request = json.loads(open(args.request, encoding="utf-8").read())
    engine = create_engine(dsn, poolclass=NullPool)
    try:
        print(json.dumps(run(engine, request, commit=False), default=str, sort_keys=True))
    finally:
        engine.dispose()

if __name__ == "__main__":
    main()
