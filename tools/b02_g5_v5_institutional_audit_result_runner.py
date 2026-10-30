#!/usr/bin/env python3
"""B02 G5 V5: consume ONLY a separately issued own reviewer audit result.

The reviewer must first publish their actual outcome and immutable Git blob.
This runner never creates a review, a reviewer identity, a ratification, or
operational authority. Default = read-only validation. One INSERT at most on
--commit-audit-result, with independent readback; never retry uncertain COMMIT.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

import b02_g5_v5_institutional_audit_start_runner as start
import b02_g5_v5_institutional_owner_rollback_probe as owner
import b02_g5_v5_local_bridge as bridge
import b02_g5_v5_policy_runner as policy

ROOT = Path(__file__).resolve().parents[1]
PATH = "tools/b02_g5_v5_institutional_audit_result_runner.py"
START_ID = "B02-G5-V5-GPT6-auditoria-iniciada-v1"
START_HASH = "da26dccf706582ef71868a6523d286e1bfe3aeae7b0272e3b8bd6a89ff8608d3"
RESULT_ID = "B02-G5-V5-GPT6-auditada-v1"
RESULT_EVENTS = {"auditada_favoravelmente", "auditada_desfavoravelmente"}
MANDATE_FROM = datetime.fromisoformat("2026-10-29T12:00:00+00:00")
MANDATE_UNTIL = datetime.fromisoformat("2026-11-08T00:00:00+00:00")


def stop(code):
    raise RuntimeError("STOP_G5_V5_AUDIT_RESULT_" + code)


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True, timeout=15)
    if p.returncode:
        stop("GIT_SOURCE_NOT_VERIFIED")
    return p.stdout.strip()


def load_issued_act(filename, commit, blob):
    if not re.fullmatch(r"B02_G5_V5_[A-Za-z0-9_]+\.json", filename):
        stop("UNEXPECTED_REVIEWER_ACT_PATH")
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not re.fullmatch(r"[0-9a-f]{40}", blob):
        stop("BAD_SOURCE_GIT_PIN")
    if git("rev-parse", "HEAD:" + filename) != blob:
        stop("REVIEWER_ACT_NOT_AT_HEAD_EXACT_BLOB")
    if git("rev-parse", commit + ":" + filename) != blob:
        stop("REVIEWER_ACT_NOT_AT_DECLARED_COMMIT")
    git("merge-base", "--is-ancestor", commit, "HEAD")
    raw = (ROOT / filename).read_text(encoding="utf-8")
    doc = json.loads(raw)
    if not isinstance(doc, dict):
        stop("ACT_NOT_OBJECT")
    actor = doc.get("actor") or doc.get("functional_actor")
    event = doc.get("decision_event") or doc.get("event")
    pol = doc.get("policy") or doc.get("scope")
    predecessor_id = doc.get("previous_decision_id") or doc.get("predecessor_id")
    predecessor_hash = (doc.get("previous_decision_record_hash")
                        or doc.get("predecessor_record_hash"))
    evidence = doc.get("evidence")
    if not isinstance(evidence, dict):
        stop("ACT_EVIDENCE_MISSING")
    predecessor_hash = predecessor_hash or evidence.get("previous_decision_record_hash")
    if (actor != start.REVIEWER or event not in RESULT_EVENTS
        or doc.get("institutional_role") != "auditor_independente"
        or not isinstance(pol, dict)
        or any(pol.get(k) != v for k, v in (
            ("policy_type", "activation_authority"), ("policy_id", policy.POLICY_ID),
            ("policy_version", 2), ("policy_hash", policy.POLICY_HASH)))
        or predecessor_id != START_ID or predecessor_hash != START_HASH):
        stop("ACT_SUBJECT_ACTOR_OR_PREDECESSOR_DIVERGENCE")
    if doc.get("persistence_status") in ("COMMITTED", "PERSISTED"):
        stop("ACT_ALREADY_CLAIMS_DB_PERSISTENCE")
    findings = doc.get("findings") or doc.get("fundamentacao")
    if not findings or not isinstance(findings, (list, dict, str)):
        stop("OWN_SUBSTANTIATED_FINDINGS_MISSING")
    if not isinstance(doc.get("rationale"), str) or not doc["rationale"].strip():
        stop("OWN_RESULT_RATIONALE_MISSING")
    issued = doc.get("issued_at_utc")
    if not isinstance(issued, str):
        stop("ISSUED_TIME_MISSING")
    try:
        stamp = datetime.fromisoformat(issued.replace("Z", "+00:00"))
    except ValueError:
        stop("ISSUED_TIME_INVALID")
    if stamp.tzinfo is None or not (MANDATE_FROM <= stamp < MANDATE_UNTIL):
        stop("ISSUED_TIME_OUTSIDE_MANDATE")
    if stamp > datetime.now(timezone.utc):
        stop("ACT_IN_FUTURE")
    return doc, event


def expected_payload(doc, event, filename, commit, blob):
    return {
        "decision_id": RESULT_ID, "decision_event": event,
        "policy_type": "activation_authority", "policy_id": policy.POLICY_ID,
        "policy_version": 2, "policy_hash": policy.POLICY_HASH,
        "actor": start.REVIEWER, "institutional_role": "auditor_independente",
        "evidence": {
            "schema": "B02_G5_V5_OWN_AUDIT_RESULT_PROVENANCE_V1",
            "previous_decision_record_hash": START_HASH,
            "issued_own_act_file": filename, "issued_own_act_commit": commit,
            "issued_own_act_git_blob": blob,
            "issued_own_act_timestamp_utc": doc["issued_at_utc"],
            "findings": doc.get("findings") or doc.get("fundamentacao"),
            "audit_report": {
                "auditor_id": start.REVIEWER,
                "outcome": "favoravel" if event == "auditada_favoravelmente" else "desfavoravel",
                "source_file": filename, "git_blob": blob,
            },
            "operational_gates_not_inferred": True,
            "material_interval_not_extended": True,
            "no_r2_transfer_to_g5": True,
        },
        "rationale": doc["rationale"],
        "previous_decision_id": START_ID,
        "idempotency_key": "B02-G5-V5-AUDIT-" + blob,
    }


def independent_readback(expected):
    sql = """BEGIN READ ONLY;
SELECT current_database()||'|'||session_user||'|'||current_user;
SELECT version_num FROM public.alembic_version;
SELECT coalesce((SELECT jsonb_build_object('row',to_jsonb(d),
 'hash_ok',d.record_hash=public.b02_json_hash(to_jsonb(d)-'record_hash'))::text
 FROM public.policy_decisions d WHERE decision_id='B02-G5-V5-GPT6-auditoria-iniciada-v1'),'null');
SELECT coalesce((SELECT jsonb_build_object('row',to_jsonb(d),
 'hash_ok',d.record_hash=public.b02_json_hash(to_jsonb(d)-'record_hash'))::text
 FROM public.policy_decisions d WHERE decision_id='B02-G5-V5-GPT6-auditada-v1'),'null');
SELECT count(*) FROM public.policy_decisions WHERE
 policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE' AND policy_version=2;
ROLLBACK;"""
    got = owner.psql(sql, bridge.ROLE)
    if len(got) != 7 or got[:3] != [
        "BEGIN", bridge.DATABASE + "|" + bridge.ROLE + "|" + bridge.ROLE,
        "0063_adr020_policy_activation_atomicity"] or got[-1] != "ROLLBACK":
        stop("READBACK_IDENTITY_OR_SCHEMA")
    prior, actual = json.loads(got[3]), json.loads(got[4])
    if prior is None or prior["hash_ok"] is not True:
        stop("START_NOT_COMMITTED")
    p = prior["row"]
    if (p.get("decision_id") != START_ID or p.get("record_hash") != START_HASH
        or p.get("actor") != start.REVIEWER
        or p.get("decision_event") != "auditoria_iniciada"
        or p.get("policy_hash") != policy.POLICY_HASH):
        stop("START_PREDECESSOR_INVALID")
    if actual is None:
        return ("ABSENT", None) if got[5] == "2" else ("CONFLICT", None)
    row = actual["row"]
    if (actual["hash_ok"] is not True or got[5] != "3"
        or any(row.get(k) != value for k, value in expected.items())
        or not re.fullmatch(r"[0-9a-f]{64}", row.get("record_hash") or "")):
        return "CONFLICT", row
    return "PRESENT_EXACT", row


def commit_sql(expected):
    encoded = json.dumps(expected, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":"))
    if "$g5_result_payload$" in encoded or "$g5_result_do$" in encoded:
        stop("SQL_PAYLOAD_DELIMITER_COLLISION")
    return """BEGIN;
SET LOCAL statement_timeout='15s';
SET LOCAL lock_timeout='3s';
DO $g5_result_do$
DECLARE
 material jsonb := $g5_result_payload$""" + encoded + """$g5_result_payload$::jsonb;
 inserted_hash text;
BEGIN
 IF current_database()<>'solveris_b02_r4g_test'
 OR session_user<>'solveris_test' OR current_user<>'solveris_test'
 OR (SELECT version_num FROM public.alembic_version)<>'0063_adr020_policy_activation_atomicity'
 OR (SELECT pg_get_userbyid(relowner) FROM pg_class
     WHERE oid='public.policy_decisions'::regclass)<>'solveris_test'
 THEN RAISE EXCEPTION 'STOP_G5_RESULT_OWNER_OR_SCHEMA'; END IF;
 IF clock_timestamp()<TIMESTAMPTZ '2026-10-29T12:00:00Z'
 OR clock_timestamp()>=TIMESTAMPTZ '2026-11-08T00:00:00Z'
 THEN RAISE EXCEPTION 'STOP_G5_RESULT_MANDATE_EXPIRED'; END IF;
 PERFORM pg_advisory_xact_lock(
 hashtextextended('SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE:2',0));
 IF (SELECT count(*) FROM public.policy_decisions WHERE
    policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE' AND policy_version=2)<>2
 THEN RAISE EXCEPTION 'STOP_G5_RESULT_CHAIN_COUNT'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.policy_decisions d WHERE
    d.decision_id='B02-G5-V5-GPT6-auditoria-iniciada-v1'
    AND d.record_hash='da26dccf706582ef71868a6523d286e1bfe3aeae7b0272e3b8bd6a89ff8608d3'
    AND d.record_hash=public.b02_json_hash(to_jsonb(d)-'record_hash')
    AND d.actor='GPT-6/revisor-documental-chat-b02-g5-v5-20261030'
    AND d.decision_event='auditoria_iniciada'
    AND d.policy_version=2
    AND d.policy_hash='007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf')
 THEN RAISE EXCEPTION 'STOP_G5_RESULT_PREDECESSOR'; END IF;
 material := material || jsonb_build_object('timestamp',transaction_timestamp());
 material := material || jsonb_build_object('record_hash',public.b02_json_hash(material));
 INSERT INTO public.policy_decisions
 SELECT i.* FROM jsonb_populate_record(NULL::public.policy_decisions,material) i
 RETURNING record_hash INTO inserted_hash;
 IF inserted_hash IS DISTINCT FROM
   (SELECT public.b02_json_hash(to_jsonb(d)-'record_hash') FROM public.policy_decisions d
    WHERE decision_id='B02-G5-V5-GPT6-auditada-v1')
 THEN RAISE EXCEPTION 'STOP_G5_RESULT_INSERTED_HASH'; END IF;
END $g5_result_do$;
COMMIT;
SELECT 'B02_G5_V5_AUDIT_RESULT_COMMIT_ACK';"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--act-file", required=True)
    parser.add_argument("--act-commit", required=True)
    parser.add_argument("--act-blob", required=True)
    parser.add_argument("--inspect-db", action="store_true")
    parser.add_argument("--commit-audit-result", action="store_true")
    args = parser.parse_args()
    if args.inspect_db and args.commit_audit_result:
        stop("MUTUALLY_EXCLUSIVE")
    bridge.validate_checkout(PATH)
    doc, event = load_issued_act(args.act_file, args.act_commit, args.act_blob)
    expected = expected_payload(doc, event, args.act_file, args.act_commit, args.act_blob)
    if not (args.inspect_db or args.commit_audit_result):
        print(json.dumps({"status": "OWN_AUDIT_RESULT_SOURCE_VALIDATED_NO_WRITE",
                          "event": event, "source_blob": args.act_blob}))
        return
    if args.commit_audit_result and not (
        MANDATE_FROM <= datetime.now(timezone.utc) < MANDATE_UNTIL):
        stop("MANDATE_NOT_CURRENT")
    with bridge.managed_container():
        state, row = independent_readback(expected)
        if state == "CONFLICT":
            stop("EXISTING_CHAIN_CONFLICT")
        if state == "PRESENT_EXACT":
            print(json.dumps({"status": "AUDIT_RESULT_ALREADY_RECONCILED",
                              "record_hash": row["record_hash"], "writes_now": 0}))
            return
        if not args.commit_audit_result:
            print(json.dumps({"status": "AUDIT_RESULT_READY_NOT_INSERTED",
                              "event": event, "writes_now": 0}))
            return
        ack = None
        failed = False
        try:
            ack = owner.psql(commit_sql(expected), owner.OWNER)
        except Exception:
            failed = True
        try:
            final, row = independent_readback(expected)
        except Exception:
            stop("UNKNOWN_ACK_READBACK_UNAVAILABLE_NO_RETRY")
        if final == "CONFLICT":
            stop("POSTCOMMIT_CHAIN_CONFLICT_NO_RETRY")
        if failed or ack is None or ack[-2:] != [
            "COMMIT", "B02_G5_V5_AUDIT_RESULT_COMMIT_ACK"]:
            stop("UNCERTAIN_ACK_NO_RETRY_READBACK_" + final)
        if final != "PRESENT_EXACT":
            stop("NOT_COMMITTED")
        print(json.dumps({
            "status": "B02_G5_V5_AUDIT_RESULT_COMMITTED_RECONCILED",
            "event": event, "decision_id": RESULT_ID,
            "record_hash": row["record_hash"], "actor": start.REVIEWER,
            "ratification": False, "activation": False,
            "independent_readback_role": bridge.ROLE,
        }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
