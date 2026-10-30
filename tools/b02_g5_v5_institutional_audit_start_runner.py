#!/usr/bin/env python3
"""G5 V5: persist only the REVIEWER'S OWN audit-start event (not an audit result).

Sources: the reviewer's separately issued, committed 2026-10-30 declaration
and adendum. Never fabricate a reviewer identity, acceptance or result.
Requires a clean/synchronised approved branch, exact Git blobs, PG 0063,
owner-only INSERT, and independent restricted-role readback. Never auto-retry.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

import b02_g5_v5_local_bridge as bridge
import b02_g5_v5_institutional_owner_rollback_probe as owner
import b02_g5_v5_submission_runner as submission
import b02_g5_v5_policy_runner as policy

ROOT = Path(__file__).resolve().parents[1]
PATH = "tools/b02_g5_v5_institutional_audit_start_runner.py"
START_FILE = "B02_G5_V5_AUDITORIA_INICIADA_DECLARACAO_PROPRIA_20261030.json"
ADDENDUM_FILE = "B02_G5_V5_ADITAMENTO_PROPRIO_G5_REAPRECIACAO_20261030.json"
SOURCE_BLOBS = {
    START_FILE: "d17ac2ba04be468b92285e76774737c29a3a36df",
    ADDENDUM_FILE: "93cead223b473998d816ba8e6a09e58b56a5c94f",
}
SOURCE_COMMITS = {
    START_FILE: "8b1dff286ea09529ade4dc30c09456639a4e0929",
    ADDENDUM_FILE: "061daa7c3af1c496bbcd06bc7519b6035af1b640",
}
POLICY_RECORD_HASH = "fa3e4684b32b1bba38f975493f19f182aa77fe2f80a13563198ace7357b992e9"
PREVIOUS_ID = "B02-G5-V5-GPT6-submetida-v1"
PREVIOUS_HASH = "dfa49ca6a05fae13e649a04ba795f6bf9f0576151a0b3751a582b903d4599f2a"
REVIEWER = "GPT-6/revisor-documental-chat-b02-g5-v5-20261030"
PROPONENT = "GPT-6/executor-tecnico-chat-b02-g5-v5-20261029"
DECISION_ID = "B02-G5-V5-GPT6-auditoria-iniciada-v1"
IDEMPOTENCY = "B02-G5-V5-AUDIT-START-8b1dff286ea09529ade4dc30c09456639a4e0929"
MANDATE_FROM = datetime.fromisoformat("2026-10-29T12:00:00+00:00")
MANDATE_UNTIL = datetime.fromisoformat("2026-11-08T00:00:00+00:00")
MATERIAL_UNTIL = datetime.fromisoformat("2026-10-30T13:00:00+00:00")


def stop(msg):
    raise RuntimeError("STOP_G5_AUDIT_START_" + msg)


def read_exact_source(name, blob):
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD:" + name], cwd=ROOT,
        capture_output=True, text=True, check=True, timeout=15
    ).stdout.strip()
    if sha != blob:
        stop("SOURCE_BLOB_" + name)
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sources():
    b = {name: read_exact_source(name, blob)
         for name, blob in SOURCE_BLOBS.items()}
    a = b[ADDENDUM_FILE]
    d = b[START_FILE]
    p = policy.candidate(ROOT)
    if (p["policy_id"], p["policy_version"]) != (policy.POLICY_ID, 2):
        stop("POLICY_SUBJECT")
    if (a["actor"] != REVIEWER or d["actor"] != REVIEWER
        or REVIEWER == PROPONENT or a.get("scope", {}).get("policy_hash") != policy.POLICY_HASH
        or a["scope"]["policy_version"] != 2
        or d.get("policy", {}).get("policy_hash") != policy.POLICY_HASH
        or d["policy"]["policy_version"] != 2):
        stop("REVIEWER_IDENTITY_OR_POLICY")
    if (a.get("precedent", {}).get("predecessor_decision_id") != PREVIOUS_ID
        or a["precedent"].get("predecessor_decision_record_hash") != PREVIOUS_HASH
        or d.get("previous_decision_id") != PREVIOUS_ID
        or d.get("evidence", {}).get("previous_decision_record_hash") != PREVIOUS_HASH):
        stop("PREDECESSOR_PIN")
    if (d.get("event") != "auditoria_iniciada"
        or d.get("institutional_role") != "auditor_independente"
        or d.get("persistence_status") != "DECLARED_NOT_COMMITTED"
        or d.get("decision_id") != "PENDING_EXECUTOR_ID_ALLOCATION"
        or d.get("record_hash") is not None or d.get("not_audit_result") is not True
        or a.get("merit") != "FAVORAVEL_LIMITADO_INTEGRIDADE_E_ADMISSIBILIDADE_DA_SUBMISSAO_G5"
        or a.get("audit_result") != "NOT_ISSUED_NOT_PREJUDGED"):
        stop("NOT_OWN_DOCUMENTARY_START")
    conflicts = a.get("own_declaration", {}).get("conflicts_and_limits", [])
    if (a["own_declaration"].get("not_proponent") != PROPONENT
        or not isinstance(conflicts, list) or len(conflicts) < 3
        or "own read-only G5 authority inventory script" not in " ".join(conflicts)):
        # The script contribution is disclosed using different exact prose:
        # check the actual disclosure, rather than asserting independence.
        if (a["own_declaration"].get("not_proponent") != PROPONENT
            or not any("read-only G5 authority inventory script" in x for x in conflicts)):
            stop("CONFLICTS_NOT_DISCLOSED")
    t = datetime.fromisoformat(d["issued_at_utc"].replace("Z", "+00:00"))
    if not MANDATE_FROM <= t < MATERIAL_UNTIL:
        stop("SOURCE_DECLARATION_OUTSIDE_WINDOW")
    if d.get("evidence", {}).get("conflict_disclosure") != ADDENDUM_FILE:
        stop("DISCLOSURE_REFERENCE")
    return a, d


def expected_payload():
    return {
        "decision_id": DECISION_ID,
        "decision_event": "auditoria_iniciada",
        "policy_type": "activation_authority",
        "policy_id": policy.POLICY_ID,
        "policy_version": 2,
        "policy_hash": policy.POLICY_HASH,
        "actor": REVIEWER,
        "institutional_role": "auditor_independente",
        "evidence": {
            "schema": "SOLVERIS_B02_G5_V5_AUDIT_START_PROVENANCE_V1",
            "original_event": "auditoria_iniciada",
            "own_declaration_file": START_FILE,
            "own_declaration_git_blob": SOURCE_BLOBS[START_FILE],
            "own_declaration_commit": SOURCE_COMMITS[START_FILE],
            "own_reassessment_file": ADDENDUM_FILE,
            "own_reassessment_git_blob": SOURCE_BLOBS[ADDENDUM_FILE],
            "own_reassessment_commit": SOURCE_COMMITS[ADDENDUM_FILE],
            "own_manifestation_library_file":
                "B02_G5_V5_MANIFESTACAO_PROPRIA_INICIO_REVISAO_20261030.json",
            "issued_mandate_library_file": "MANDATO_G5_SUCESSOR_EMITIDO.json",
            "own_actor_identification": REVIEWER,
            "proponent_actor_identification": PROPONENT,
            "functional_segregation": "different declared functional actor; material independence not certified",
            "conflicts_and_contribution": "see own reassessment (including ancillary read-only G5 tool)",
            "policy_record_id": "B02-G5-V5-policy-v2",
            "policy_record_hash": POLICY_RECORD_HASH,
            "previous_decision_record_hash": PREVIOUS_HASH,
            "audit_result": "NOT_ISSUED_NOT_PREJUDGED",
            "r2_not_a_direct_g5_sql_0022_condition": True,
            "no_operational_approval_or_signature": True
        },
        "rationale": "Inicio institucional de auditoria por revisor funcional distinto; conflitos e limitacoes declarados; nenhuma conclusao favoravel ou desfavoravel, nem autorizacao de instalar/ativar G5.",
        "previous_decision_id": PREVIOUS_ID,
        "idempotency_key": IDEMPOTENCY,
    }


def independent_readback(expected):
    """Read-only restricted role, fail-closed on ambiguity, verify both links."""
    sql = """BEGIN READ ONLY;
SELECT current_database()||'|'||session_user||'|'||current_user;
SELECT version_num FROM public.alembic_version;
SELECT coalesce((SELECT jsonb_build_object(
  'row',to_jsonb(d),'hash_ok',d.record_hash=public.b02_json_hash(to_jsonb(d)-'record_hash')
)::text FROM public.policy_decisions d WHERE decision_id='B02-G5-V5-GPT6-auditoria-iniciada-v1'),'null');
SELECT coalesce((SELECT jsonb_build_object(
  'row',to_jsonb(d),'hash_ok',d.record_hash=public.b02_json_hash(to_jsonb(d)-'record_hash')
)::text FROM public.policy_decisions d WHERE decision_id='B02-G5-V5-GPT6-submetida-v1'),'null');
SELECT count(*) FROM public.policy_decisions
 WHERE policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE' AND policy_version=2;
SELECT count(*) FROM public.policy_versions p WHERE policy_version_record_id='B02-G5-V5-policy-v2'
 AND policy_hash='007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf'
 AND record_hash='fa3e4684b32b1bba38f975493f19f182aa77fe2f80a13563198ace7357b992e9'
 AND record_hash=public.b02_json_hash(to_jsonb(p)-'record_hash');
SELECT count(*) FROM public.policy_versions p
 WHERE policy_version_record_id IN ('B02-57982-policy-v1','B02-05ede-policy-v1')
 AND record_hash=public.b02_json_hash(to_jsonb(p)-'record_hash');
ROLLBACK;"""
    got = owner.psql(sql, bridge.ROLE)
    if (len(got) != 9 or got[:3] !=
        ["BEGIN", bridge.DATABASE + "|" + bridge.ROLE + "|" + bridge.ROLE,
         "0063_adr020_policy_activation_atomicity"]
        or got[6:] != ["1", "2", "ROLLBACK"]):
        stop("INDEPENDENT_READBACK_ROLE_SCHEMA_OR_POLICY")
    actual = json.loads(got[3])
    predecessor = json.loads(got[4])
    if (predecessor is None or predecessor["hash_ok"] is not True
        or predecessor["row"]["decision_event"] != "submetida"
        or predecessor["row"]["institutional_role"] != "proponente_institucional"
        or predecessor["row"]["actor"] != PROPONENT
        or predecessor["row"]["record_hash"] != PREVIOUS_HASH
        or predecessor["row"]["policy_hash"] != policy.POLICY_HASH
        or predecessor["row"]["policy_version"] != 2):
        stop("PREDECESSOR_NOT_EXACT_OR_NOT_COMMITTED")
    if actual is None:
        if got[5] == "1":
            return "ABSENT", None
        return "CONFLICT", None
    row = actual["row"]
    if (actual["hash_ok"] is not True or got[5] != "2"
        or not re.fullmatch(r"[0-9a-f]{64}", row.get("record_hash") or "")
        or any(row.get(k) != value for k, value in expected.items())):
        return "CONFLICT", row
    return "PRESENT_EXACT", row


def commit_sql(expected):
    body = json.dumps(expected, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    for token in ("$g5_audit_payload$", "$g5_audit_do$"):
        if token in body:
            stop("SQL_DELIMITER_COLLISION")
    return """BEGIN;
SET LOCAL statement_timeout='15s';
SET LOCAL lock_timeout='3s';
DO $g5_audit_do$
DECLARE
 material jsonb := $g5_audit_payload$""" + body + """$g5_audit_payload$::jsonb;
 result_hash text;
BEGIN
 IF current_database()<>'solveris_b02_r4g_test'
 OR current_user<>'solveris_test' OR session_user<>'solveris_test'
 OR (SELECT version_num FROM public.alembic_version)<>'0063_adr020_policy_activation_atomicity'
 OR (SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid='public.policy_decisions'::regclass)<>'solveris_test'
 THEN RAISE EXCEPTION 'STOP_G5_AUDIT_START_OWNER_IDENTITY'; END IF;
 IF clock_timestamp()<TIMESTAMPTZ '2026-10-29T12:00:00+00:00'
 OR clock_timestamp()>=TIMESTAMPTZ '2026-11-08T00:00:00+00:00'
 THEN RAISE EXCEPTION 'STOP_G5_AUDIT_START_MANDATE_WINDOW'; END IF;
 PERFORM pg_advisory_xact_lock(
  hashtextextended('SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE:2',0));
 IF NOT EXISTS(
  SELECT 1 FROM public.policy_versions p WHERE
  p.policy_version_record_id='B02-G5-V5-policy-v2'
  AND p.policy_hash='007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf'
  AND p.record_hash='fa3e4684b32b1bba38f975493f19f182aa77fe2f80a13563198ace7357b992e9'
  AND p.record_hash=public.b02_json_hash(to_jsonb(p)-'record_hash')
 ) THEN RAISE EXCEPTION 'STOP_G5_AUDIT_START_POLICY_NOT_RECONCILED'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.policy_decisions d WHERE
  d.decision_id='B02-G5-V5-GPT6-submetida-v1'
  AND d.decision_event='submetida'
  AND d.institutional_role='proponente_institucional'
  AND d.actor='GPT-6/executor-tecnico-chat-b02-g5-v5-20261029'
  AND d.record_hash='dfa49ca6a05fae13e649a04ba795f6bf9f0576151a0b3751a582b903d4599f2a'
  AND d.record_hash=public.b02_json_hash(to_jsonb(d)-'record_hash')
  AND d.policy_version=2
  AND d.policy_hash='007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf')
 THEN RAISE EXCEPTION 'STOP_G5_AUDIT_START_PREDECESSOR_MISMATCH'; END IF;
 IF EXISTS(SELECT 1 FROM public.policy_decisions
  WHERE policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
  AND policy_version=2 AND decision_id<>'B02-G5-V5-GPT6-submetida-v1')
 THEN RAISE EXCEPTION 'STOP_G5_AUDIT_START_DECISION_ALREADY_EXISTS'; END IF;
 material := material || jsonb_build_object('timestamp',transaction_timestamp());
 material := material || jsonb_build_object('record_hash',public.b02_json_hash(material));
 INSERT INTO public.policy_decisions
 SELECT i.* FROM jsonb_populate_record(NULL::public.policy_decisions,material) i
 RETURNING record_hash INTO result_hash;
 IF result_hash IS DISTINCT FROM
  (SELECT public.b02_json_hash(to_jsonb(d)-'record_hash') FROM public.policy_decisions d
   WHERE decision_id='B02-G5-V5-GPT6-auditoria-iniciada-v1')
 THEN RAISE EXCEPTION 'STOP_G5_AUDIT_START_PRECOMMIT_HASH'; END IF;
END
$g5_audit_do$;
COMMIT;
SELECT 'B02_G5_V5_AUDIT_START_COMMIT_ACK';"""


def execute(expected):
    now = datetime.now(timezone.utc)
    if not (MANDATE_FROM <= now < MANDATE_UNTIL):
        stop("MANDATE_WINDOW_OUTSIDE")
    with bridge.managed_container():
        state, row = independent_readback(expected)
        if state == "CONFLICT":
            stop("EXISTING_DECISION_CONFLICT")
        if state == "PRESENT_EXACT":
            print(json.dumps({"status": "B02_G5_V5_AUDIT_START_ALREADY_RECONCILED",
                              "decision_id": DECISION_ID, "record_hash": row["record_hash"],
                              "committed_writes_now": 0}, sort_keys=True))
            return
        ack = None
        error = None
        try:
            ack = owner.psql(commit_sql(expected), owner.OWNER)
        except Exception as exc:
            error = exc
        try:
            final, row = independent_readback(expected)
        except Exception:
            stop("ACK_UNCERTAIN_INDEPENDENT_READBACK_UNAVAILABLE_NO_RETRY")
        if final == "CONFLICT":
            stop("POSTCOMMIT_CONFLICT_NO_RETRY")
        if error is not None or ack is None or ack[-2:] != [
            "COMMIT", "B02_G5_V5_AUDIT_START_COMMIT_ACK"
        ]:
            print(json.dumps({"status": "ACK_UNCERTAIN_NO_RETRY",
                              "readback": final,
                              "record_hash": row["record_hash"] if row else None},
                             sort_keys=True), file=sys.stderr)
            stop("ACK_UNCERTAIN_MANUAL_RECONCILIATION")
        if final != "PRESENT_EXACT":
            stop("NO_COMMITTED_ROW")
        print(json.dumps({
            "status": "B02_G5_V5_AUDIT_START_COMMITTED_RECONCILED",
            "decision_id": DECISION_ID, "record_hash": row["record_hash"],
            "event": "auditoria_iniciada", "reviewer": REVIEWER,
            "predecessor_record_hash": PREVIOUS_HASH,
            "review_result_issued": False, "ratification": False,
            "activation": False, "migrations": 0, "native_binary": False,
            "owner_insert_only": owner.OWNER,
            "independent_readback": bridge.ROLE,
        }, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect-db", action="store_true")
    parser.add_argument("--commit-audit-start", action="store_true")
    args = parser.parse_args()
    if args.inspect_db and args.commit_audit_start:
        stop("MUTUALLY_EXCLUSIVE_ARGS")
    bridge.validate_checkout(PATH)
    sources()
    expected = expected_payload()
    if args.commit_audit_start:
        execute(expected)
    elif args.inspect_db:
        with bridge.managed_container():
            state, row = independent_readback(expected)
        print(json.dumps({"status": "G5_V5_AUDIT_START_" + state,
                          "record_hash": row["record_hash"] if row else None,
                          "db_writes": 0}, sort_keys=True))
    else:
        print(json.dumps({"status": "G5_V5_AUDIT_START_SOURCES_PASS",
                          "event": "auditoria_iniciada",
                          "actor": REVIEWER, "policy_hash": policy.POLICY_HASH,
                          "db_writes": 0}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
