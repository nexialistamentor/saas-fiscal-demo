"""B02 G4 new temporal v4 candidate, sourced from immutable approved G4 logic.

No approval is implied. Run via existing isolated G5 loopback bridge only
after the exact combined temporal decision is separately ratified in Git.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PLAN="B02_G5_V5_SUCESSOR_TEMPORAL_PLANO_CONDICIONAL_20261030.json"
KEY="decisao_unica_temporal_antecipada_g4_g5_20261031"
SOURCE="executar_ativacao_g4_real.py"
SOURCE_BLOB="1729e6d62c77510ef4dd7db0af56a6cbe985c168"
REFERENCE="B02-G4-G5-TEMP-SUCCESSOR-20261031-01"
START=datetime.fromisoformat("2026-11-01T00:00:00+00:00")
END=datetime.fromisoformat("2026-11-15T00:00:00+00:00")
IDS={"execution_id":"B02-05ede-execution-v4",
     "activation_id":"B02-05ede-activation-v4",
     "generation_id":"B02-05ede-generation-v4",
     "outbox_id":"B02-05ede-outbox-v4",
     "idempotency_key":"B02-05ede-execution-v4-20261101T000000Z"}


def stop(reason):
    raise RuntimeError("STOP_G4_V4_TEMPORAL_"+reason)


def git(*args):
    p=subprocess.run(["git",*args],cwd=ROOT,capture_output=True,timeout=25)
    if p.returncode:stop("GIT_PIN_UNAVAILABLE")
    return p.stdout.strip()


def verify_plan(operational):
    if git("branch","--show-current")!=b"candidate/g5-v5-publicacao-local":
        stop("BRANCH_MISMATCH")
    for path in (PLAN,SOURCE):
        if git("hash-object",path)!=git("rev-parse","HEAD:"+path):
            stop("TRACKED_SOURCE_DIRTY")
    if git("rev-parse","HEAD:"+SOURCE).decode()!=SOURCE_BLOB:
        stop("HISTORICAL_G4_BLOB_CHANGED")
    q=json.loads((ROOT/PLAN).read_text(encoding="utf-8-sig"))[KEY]
    expected={k.replace("_id",""):v for k,v in IDS.items()
              if k!="idempotency_key"}
    if (q["reference"]!=REFERENCE or q["window_utc"]["from"]!=START.isoformat()
        or q["window_utc"]["until"]!=END.isoformat()
        or q["g4"]["fresh_four_record_ids"]!=expected
        or q["g4"]["one_shot_idempotency_key"]!=IDS["idempotency_key"]):
        stop("PROPOSAL_PIN_DIVERGENCE")
    if operational:
        if (q["status"]!="RATIFICADA_PROSPECTIVAMENTE"
            or q["approved"] is not True or q["approved_by"]!="Miguel"
            or not q.get("approved_at_utc") or not q.get("ratification_source")):
            stop("MISSING_OWN_TEMPORAL_RATIFICATION")
        approved=datetime.fromisoformat(q["approved_at_utc"])
        if approved.tzinfo is None or approved>=END or approved>datetime.now(timezone.utc):
            stop("NON_PROSPECTIVE_OR_FUTURE_APPROVAL")
    return q


def pinned_code():
    source=git("show","HEAD:"+SOURCE).decode("utf-8")
    exact=(
      ('e["attempt_number"]==2\n           and e["fencing_token"]==2',
       'e["attempt_number"]==4\n           and e["fencing_token"]==4'),
      ('"attempt_number":2,"lease_id":LEASE_ID,"fencing_token":2,',
       '"attempt_number":4,"lease_id":LEASE_ID,"fencing_token":4,'),
    )
    for old,new in exact:
        if source.count(old)!=1:stop("PINNED_G4_ATTEMPT_ANCHOR_DRIFT")
        source=source.replace(old,new)
    ns={"__name__":"b02_g4_v4_successor_candidate","__file__":str(ROOT/SOURCE)}
    exec(compile(source,SOURCE,"exec"),ns)
    ns["NEW_WINDOW_FROM"]=START
    ns["NEW_WINDOW_UNTIL"]=END
    ns["NEW_IDS"]=IDS
    ns["LEASE_ID"]="B02-05ede-manual-lease-v4"
    ns["PROVENANCE"]={"source":"SOLVERIS_B02_G4_WINDOW_PREPARATION",
                      "purpose":"manual_policy_activation_unit_v4",
                      "synthetic_only":False}
    return ns


def reconcile_older_path(engine):
    from sqlalchemy import text
    with engine.connect() as c:
        c.exec_driver_sql("SET TRANSACTION READ ONLY")
        older=c.execute(text("""
SELECT (SELECT count(*) FROM public.policy_activation_executions
         WHERE policy_activation_execution_id='B02-05ede-execution-v2'),
       (SELECT count(*) FROM public.policy_activations
         WHERE policy_activation_id='B02-05ede-activation-v2'),
       (SELECT count(*) FROM public.policy_activation_generations
         WHERE policy_activation_generation_id='B02-05ede-generation-v2'),
       (SELECT count(*) FROM public.policy_activation_outbox_events
         WHERE policy_activation_outbox_event_id='B02-05ede-outbox-v2')
""")).one()
        overlapping=c.execute(text("""
SELECT policy_activation_id FROM public.policy_activations
WHERE policy_id='SOLVERIS-B02-SEFA-PR-DOCUMENTARY-AUTHORITY'
  AND state='activa'
  AND (operational_interval->>'from')::timestamptz < :end
  AND (operational_interval->>'until')::timestamptz > :start
ORDER BY policy_activation_id
"""),{"start":START,"end":END}).scalars().all()
        c.rollback()
    if any(older) or any(x!=IDS["activation_id"] for x in overlapping):
        stop("PREEXISTING_NOVEMBER_G4_OR_OVERLAP")
    return overlapping


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute",action="store_true")
    p.add_argument("--approval-reference")
    a=p.parse_args()
    verify_plan(a.execute)
    ns=pinned_code()
    print(json.dumps({"status":"PROPOSAL_PREPARED_NOT_AUTHORIZED",
        "reference":REFERENCE,"window":[START.isoformat(),END.isoformat()],
        "ids":IDS,"source_blob":SOURCE_BLOB},sort_keys=True))
    if not a.execute:return
    if a.approval_reference!=REFERENCE:stop("EXACT_APPROVAL_REFERENCE_REQUIRED")
    if not START<=datetime.now(timezone.utc)<END:stop("OUTSIDE_PROSPECTIVE_WINDOW")
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool
    dsn=os.environ.get("SOLVERIS_B02_POLICY_WRITER_DSN")
    if not dsn:stop("EXISTING_ISOLATED_BRIDGE_REQUIRED")
    e=create_engine(dsn,poolclass=NullPool)
    try:reconcile_older_path(e)
    finally:e.dispose()
    # Original code still performs independent first read, one-shot staging,
    # COMMIT and independent read-back; no retry on ambiguous ACK.
    ns["run"](a)


if __name__=="__main__":
    try:main()
    except Exception as exc:
        print(str(exc) if isinstance(exc,RuntimeError)
              else "STOP_G4_V4_INTERNAL",file=sys.stderr)
        sys.exit(2)
