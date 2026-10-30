#!/usr/bin/env python3
"""Commit only GPT-6's own G5 V5 institutional 'submetida' event.

Source records are user-issued designation and executor-issued acceptance and
submission, pinned to published Git blobs. No policy INSERT, grant, reviewer act,
ratification, native operation or migration. Owner can insert only the decision;
independent verification uses restricted writer. One attempt, never auto-retry.
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
import b02_g5_v5_policy_runner as policy

ROOT=Path(__file__).resolve().parents[1]
PATH="tools/b02_g5_v5_submission_runner.py"
DESIGNATION="B02_G5_V5_ADITAMENTO_DESIGNACAO_GPT6_EMITIDO_20261029.json"
ACCEPTANCE="B02_G5_V5_ACEITACAO_PROPONENTE_GPT6_20261029.json"
SUBMISSION="B02_G5_V5_SUBMISSAO_PROPONENTE_GPT6_20261029.json"
BLOBS={
    DESIGNATION:"05f1286ac7720386ca34e8bd27d81c776bf08da2",
    ACCEPTANCE:"faa8f74eae68cee33b330c755288c841f4a3708a",
    SUBMISSION:"454c94fc6ce3ce60107324a037f233763c65468d",
}
ACTOR="GPT-6/executor-tecnico-chat-b02-g5-v5-20261029"
DECISION_ID="B02-G5-V5-GPT6-submetida-v1"
POLICY_RECORD_HASH="fa3e4684b32b1bba38f975493f19f182aa77fe2f80a13563198ace7357b992e9"
START=datetime.fromisoformat("2026-10-29T13:00:00+00:00")
END=datetime.fromisoformat("2026-10-30T13:00:00+00:00")
MANDATE_END=datetime.fromisoformat("2026-11-08T00:00:00+00:00")


def stop(reason):
    raise RuntimeError("STOP_G5_SUBMISSION_"+reason)


def sources():
    """Verify committed Git blobs; validate_checkout enforces a clean, synced tree."""
    output={}
    for name,blob in BLOBS.items():
        result=subprocess.run(["git","rev-parse","HEAD:"+name],cwd=ROOT,
                              capture_output=True,text=True,timeout=15,check=True)
        if result.stdout.strip()!=blob:
            stop("GIT_BLOB_"+name)
        output[name]=json.loads((ROOT/name).read_text(encoding="utf-8"))
    d,a,s=output[DESIGNATION],output[ACCEPTANCE],output[SUBMISSION]
    if (d.get("status")!="EMITIDO_POR_MANIFESTACAO_EXPRESSA_DO_UTILIZADOR_SEM_ASSINATURA_CRIPTOGRAFICA"
        or d.get("emission_source",{}).get("literal_approval_excerpt")!=
           "APROVO E EMITO o aditamento de designação apresentado"):
        stop("DESIGNATION_NOT_EMITTED")
    if (d.get("designacao",{}).get("technical_functional_actor")!=ACTOR
        or d["designacao"].get("policy_hash")!=policy.POLICY_HASH
        or d["designacao"].get("policy_version")!=2
        or d["designacao"].get("policy_record_hash")!=POLICY_RECORD_HASH):
        stop("MANDATE_SUBJECT")
    if (a.get("status")!="ACEITACAO_FUNCIONAL_PROPRIA_EMITIDA"
        or a.get("functional_actor")!=ACTOR
        or a.get("object",{}).get("policy_hash")!=policy.POLICY_HASH
        or a.get("mandate",{}).get("addendum_publication_commit")!=
           "d65558f9c12db974903ce87fcc53b24fbcb87813"):
        stop("ACCEPTANCE_MISMATCH")
    if (s.get("status")!="SUBMETIDA_DOCUMENTALMENTE_PELO_PROPRIO_PROPONENTE_PERSISTENCIA_DB_A_RECONCILIAR"
        or s.get("decision_id")!=DECISION_ID or s.get("actor")!=ACTOR
        or s.get("decision_event")!="submetida"
        or s.get("institutional_role")!="proponente_institucional"
        or s.get("previous_decision_id") is not None
        or s.get("policy",{}).get("policy_hash")!=policy.POLICY_HASH
        or s["policy"].get("policy_version")!=2
        or s["policy"].get("policy_record_hash")!=POLICY_RECORD_HASH
        or s.get("authority_and_acceptance",{}).get("proponent_self_acceptance_commit")!=
           "a18d7297de929a4c0023dabeef96273ddf0f6981"):
        stop("SUBMISSION_MISMATCH")
    if policy.candidate(ROOT)["policy_version"]!=2:
        stop("POLICY_BYTES")
    return s


def payload(s):
    evidence={
        "schema":"SOLVERIS_B02_G5_V5_INSTITUTIONAL_SUBMISSION_PROVENANCE_V1",
        "documentary_submission":SUBMISSION,
        "documentary_submission_git_blob":BLOBS[SUBMISSION],
        "self_acceptance":ACCEPTANCE,
        "self_acceptance_git_blob":BLOBS[ACCEPTANCE],
        "mandate_addendum":DESIGNATION,
        "mandate_addendum_git_blob":BLOBS[DESIGNATION],
        "issued_original_mandate":"MANDATO_G5_SUCESSOR_EMITIDO.json",
        "actor_functional_identity":ACTOR,
        "source_policy_record_id":"B02-G5-V5-policy-v2",
        "source_policy_record_hash":POLICY_RECORD_HASH,
        "previous_decision_record_hash":None,
        "proponent_is_not_reviewer_or_ratifier":True,
        "source_limits":"Documentary acceptance; no cryptographic signature, no fiscal authority, no audit or activation",
    }
    return {
        "decision_id":DECISION_ID,
        "decision_event":"submetida",
        "policy_type":"activation_authority",
        "policy_id":policy.POLICY_ID,
        "policy_version":2,
        "policy_hash":policy.POLICY_HASH,
        "actor":ACTOR,
        "institutional_role":"proponente_institucional",
        "evidence":evidence,
        "rationale":s["rationale"],
        "previous_decision_id":None,
        "idempotency_key":s["idempotency_key"],
    }


def independent_readback(expected):
    """Read committed evidence without institutional INSERT privilege."""
    sql="""BEGIN READ ONLY;
SELECT current_database()||'|'||session_user||'|'||current_user;
SELECT version_num FROM public.alembic_version;
SELECT coalesce((SELECT jsonb_build_object(
 'row',to_jsonb(d),
 'hash_ok',d.record_hash=public.b02_json_hash(to_jsonb(d)-'record_hash')
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
    got=owner.psql(sql,bridge.ROLE)
    if len(got)!=8 or got[:3]!=["BEGIN",bridge.DATABASE+"|"+bridge.ROLE+"|"+bridge.ROLE,
          "0063_adr020_policy_activation_atomicity"] or got[5:]!=["1","2","ROLLBACK"]:
        stop("READBACK_ROLE_POLICY_OR_G4")
    observation=json.loads(got[3])
    count=int(got[4])
    if observation is None:
        if count==0: return "ABSENT",None
        return "CONFLICT",None
    row=observation["row"]
    if (count!=1 or observation["hash_ok"] is not True
        or not re.fullmatch("[a-f0-9]{64}",row.get("record_hash") or "")
        or any(row.get(k)!=v for k,v in expected.items())):
        return "CONFLICT",row
    return "PRESENT_EXACT",row


def commit_sql(expected):
    body=json.dumps(expected,ensure_ascii=False,allow_nan=False,separators=(",",":"))
    for token in ("$g5_submission_payload$","$g5_submission_do$"):
        if token in body:stop("SQL_LITERAL_COLLISION")
    return """BEGIN;
SET LOCAL statement_timeout='15s';
SET LOCAL lock_timeout='3s';
DO $g5_submission_do$
DECLARE
 material jsonb := $g5_submission_payload$"""+body+"""$g5_submission_payload$::jsonb;
 result_hash text;
BEGIN
 IF current_database()<>'solveris_b02_r4g_test'
 OR current_user<>'solveris_test' OR session_user<>'solveris_test'
 OR (SELECT version_num FROM public.alembic_version)<>'0063_adr020_policy_activation_atomicity'
 OR (SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid='public.policy_decisions'::regclass)<>'solveris_test'
 THEN RAISE EXCEPTION 'STOP_G5_SUBMISSION_OWNER_IDENTITY'; END IF;
 IF clock_timestamp()<TIMESTAMPTZ '2026-10-29T13:00:00+00:00'
 OR clock_timestamp()>=TIMESTAMPTZ '2026-10-30T13:00:00+00:00'
 THEN RAISE EXCEPTION 'STOP_G5_SUBMISSION_POLICY_WINDOW'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE:2',0));
 IF NOT EXISTS(
   SELECT 1 FROM public.policy_versions p
   WHERE p.policy_version_record_id='B02-G5-V5-policy-v2'
   AND p.policy_hash='007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf'
   AND p.record_hash='fa3e4684b32b1bba38f975493f19f182aa77fe2f80a13563198ace7357b992e9'
   AND p.record_hash=public.b02_json_hash(to_jsonb(p)-'record_hash')
 ) THEN RAISE EXCEPTION 'STOP_G5_SUBMISSION_POLICY_PREDECESSOR'; END IF;
 IF EXISTS(
  SELECT 1 FROM public.policy_decisions
   WHERE policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
   AND policy_version=2
 ) THEN RAISE EXCEPTION 'STOP_G5_SUBMISSION_DECISION_ALREADY_PRESENT'; END IF;
 material := material || jsonb_build_object('timestamp',transaction_timestamp());
 material := material || jsonb_build_object('record_hash',public.b02_json_hash(material));
 INSERT INTO public.policy_decisions
 SELECT i.* FROM jsonb_populate_record(NULL::public.policy_decisions,material) i
 RETURNING record_hash INTO result_hash;
 IF result_hash IS DISTINCT FROM
   (SELECT public.b02_json_hash(to_jsonb(d)-'record_hash')
    FROM public.policy_decisions d WHERE decision_id='B02-G5-V5-GPT6-submetida-v1')
 THEN RAISE EXCEPTION 'STOP_G5_SUBMISSION_PRECOMMIT_HASH'; END IF;
END
$g5_submission_do$;
COMMIT;
SELECT 'B02_G5_V5_SUBMISSION_COMMIT_ACK';"""


def execute(s):
    now=datetime.now(timezone.utc)
    if not (START<=now<END and now<MANDATE_END):
        stop("MANDATE_OR_POLICY_WINDOW_OUTSIDE")
    expected=payload(s)
    with bridge.managed_container():
        state,row=independent_readback(expected)
        if state=="CONFLICT":stop("EXISTING_DECISION_CONFLICT")
        if state=="PRESENT_EXACT":
            print(json.dumps({"status":"G5_V5_SUBMETIDA_ALREADY_RECONCILED",
                  "record_hash":row["record_hash"],"decision_id":DECISION_ID,
                  "writes_now":0},sort_keys=True))
            return
        sql=commit_sql(expected)
        ack=None
        error=None
        try:
            ack=owner.psql(sql,owner.OWNER)
        except Exception as exc:
            error=exc
        try:
            final,post=independent_readback(expected)
        except Exception:
            stop("POSTCOMMIT_RECONCILIATION_UNKNOWN_NO_RETRY")
        if final=="CONFLICT":stop("POSTCOMMIT_CONFLICT_NO_RETRY")
        if error is not None or ack is None or ack[-2:]!=[
                "COMMIT","B02_G5_V5_SUBMISSION_COMMIT_ACK"]:
            print(json.dumps({"status":"ACK_UNCERTAIN_NO_RETRY",
                    "readback":final,"record_hash":post["record_hash"] if post else None},
                    sort_keys=True),file=sys.stderr)
            stop("ACK_UNCERTAIN_MANUAL_RECONCILIATION")
        if final!="PRESENT_EXACT":stop("COMMIT_NOT_PERSISTED")
        print(json.dumps({"status":"B02_G5_V5_SUBMETIDA_COMMITTED_RECONCILED",
              "decision_id":DECISION_ID,"decision_record_hash":post["record_hash"],
              "policy_hash":policy.POLICY_HASH,"policy_record_hash":POLICY_RECORD_HASH,
              "actor":ACTOR,"event":"submetida",
              "owner_insert_only":"solveris_test",
              "independent_readback":"solveris_b02_policy_writer",
              "policy_insert_count":0,"audits_created":0,
              "ratifications_created":0,"activations_created":0,
              "grants":0},sort_keys=True))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--commit-submission",action="store_true")
    args=parser.parse_args()
    bridge.validate_checkout(PATH)
    s=sources()
    if not args.commit_submission:
        print(json.dumps({"status":"SUBMISSION_SOURCE_IDENTITIES_VERIFIED_NO_DB_WRITE",
              "actor":ACTOR,"policy_hash":policy.POLICY_HASH},sort_keys=True))
        return
    execute(s)


if __name__=="__main__":
    try:main()
    except Exception as e:
        print(str(e),file=sys.stderr)
        raise SystemExit(2)
