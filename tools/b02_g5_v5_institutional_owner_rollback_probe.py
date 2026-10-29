#!/usr/bin/env python3
"""Physical, rollback-only test of PolicyVersion INSERT through table's technical owner.

This is NOT a ratification, a policy installation, an institutional actor,
a grant, or activation. The operational policy writer is never given INSERT
on policy_versions/decisions/bootstrap. A failed SQL transaction is closed
without COMMIT and an independent session checks durable absence.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

import b02_g5_v5_local_bridge as bridge
import b02_g5_v5_policy_runner as policy

ROOT = Path(__file__).resolve().parents[1]
OWNER = "solveris_test"
RECORD_ID = "B02-G5-V5-ROLLBACK-PROBE"
PATH = "tools/b02_g5_v5_institutional_owner_rollback_probe.py"


def psql(sql: str, role: str):
    if role not in (OWNER, bridge.ROLE):
        raise RuntimeError("STOP_UNEXPECTED_DATABASE_ROLE")
    args = ["docker", "exec", "-i", bridge.CONTAINER, "psql",
            "-X", "-w", "-v", "ON_ERROR_STOP=1", "-U", role,
            "-d", bridge.DATABASE, "-At"]
    proc = subprocess.run(args, input=sql.encode("utf-8"),
                          capture_output=True, timeout=45)
    output = proc.stdout.decode("utf-8", errors="replace").strip().splitlines()
    if proc.returncode:
        error = proc.stderr.decode("utf-8", errors="replace")[-700:].strip()
        raise RuntimeError("STOP_PSQL_" + role.upper() + ": " + error)
    return output


def owner_preflight():
    sql = """BEGIN READ ONLY;
SELECT current_database()||'|'||session_user||'|'||current_user;
SELECT version_num FROM public.alembic_version;
SELECT pg_get_userbyid(relowner) FROM pg_class
 WHERE oid='public.policy_versions'::regclass;
SELECT count(*) FROM public.policy_versions
 WHERE policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
 AND policy_version=2;
ROLLBACK;"""
    result = psql(sql, OWNER)
    expected = ["BEGIN", bridge.DATABASE + "|" + OWNER + "|" + OWNER,
                "0063_adr020_policy_activation_atomicity", OWNER, "0", "ROLLBACK"]
    if result != expected:
        raise RuntimeError("STOP_POLICY_OWNER_IDENTITY_SCHEMA_OR_VERSION")
    return True


def make_rollback_sql(body):
    # No interpolation of identifiers or SQL commands from the policy object.
    payload = json.dumps(body, ensure_ascii=False, allow_nan=False)
    for token in ("$b02g5_v5_body$", "$b02g5_v5_probe$"):
        if token in payload:
            raise RuntimeError("STOP_PAYLOAD_DELIMITER_COLLISION")
    sql = """BEGIN;
SET LOCAL statement_timeout='15s';
SET LOCAL lock_timeout='3s';
DO $b02g5_v5_probe$
DECLARE
 body jsonb := $b02g5_v5_body$""" + payload + """$b02g5_v5_body$::jsonb;
 material jsonb; inserted_policy_hash text; inserted_record_hash text;
BEGIN
 IF current_database()<>'solveris_b02_r4g_test'
    OR session_user<>'solveris_test' OR current_user<>'solveris_test'
    OR (SELECT version_num FROM public.alembic_version)
       <>'0063_adr020_policy_activation_atomicity'
    OR (SELECT pg_get_userbyid(relowner) FROM pg_class
        WHERE oid='public.policy_versions'::regclass)<>'solveris_test'
 THEN RAISE EXCEPTION 'STOP_OWNER_PROBE_IDENTITY'; END IF;
 PERFORM pg_advisory_xact_lock(
   hashtextextended('SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE:2',0));
 IF EXISTS(SELECT 1 FROM public.policy_versions
   WHERE policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
     AND policy_version=2)
 THEN RAISE EXCEPTION 'STOP_G5V5_ALREADY_PRESENT'; END IF;
 IF public.b02_json_hash(body)
   IS DISTINCT FROM '007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf'
 THEN RAISE EXCEPTION 'STOP_G5V5_BODY_CANONICAL_HASH'; END IF;
 material := body || jsonb_build_object(
   'policy_version_record_id','B02-G5-V5-ROLLBACK-PROBE',
   'policy_hash','007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf',
   'created_at',transaction_timestamp());
 material := material || jsonb_build_object(
   'record_hash',public.b02_json_hash(material));
 INSERT INTO public.policy_versions
 SELECT i.* FROM jsonb_populate_record(
   NULL::public.policy_versions, material) AS i
 RETURNING policy_hash,record_hash
 INTO inserted_policy_hash,inserted_record_hash;
 IF inserted_policy_hash IS DISTINCT FROM
   '007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf'
 OR inserted_record_hash IS DISTINCT FROM
   (SELECT public.b02_json_hash(to_jsonb(p)-'record_hash')
      FROM public.policy_versions p
      WHERE p.policy_version_record_id='B02-G5-V5-ROLLBACK-PROBE')
 THEN RAISE EXCEPTION 'STOP_G5V5_STAGED_RECORD_HASH'; END IF;
END
$b02g5_v5_probe$;
ROLLBACK;
SELECT 'B02_G5_V5_OWNER_ROLLBACK_ACK';"""
    return sql


def independent_absence():
    # Independent authenticated role with no INSERT on institutional records.
    sql = """BEGIN READ ONLY;
SELECT count(*) FROM public.policy_versions
 WHERE policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
 AND policy_version=2;
SELECT count(*) FROM public.policy_versions
 WHERE policy_version_record_id='B02-G5-V5-ROLLBACK-PROBE';
SELECT count(*) FROM public.policy_versions p WHERE
 policy_version_record_id IN ('B02-57982-policy-v1','B02-05ede-policy-v1')
 AND record_hash=public.b02_json_hash(to_jsonb(p)-'record_hash');
ROLLBACK;"""
    got = psql(sql, bridge.ROLE)
    if got != ["BEGIN", "0", "0", "2", "ROLLBACK"]:
        raise RuntimeError("STOP_POLICY_PROBE_POSTREAD_CONFLICT")
    return True


def main():
    bridge.validate_checkout(PATH)
    body = policy.candidate(ROOT)
    with bridge.managed_container():
        owner_preflight()
        failure = None
        try:
            result = psql(make_rollback_sql(body), OWNER)
            if not result or result[-1] != "B02_G5_V5_OWNER_ROLLBACK_ACK":
                raise RuntimeError("STOP_POLICY_ROLLBACK_NOT_ACKNOWLEDGED")
        except Exception as exc:
            failure = exc
        # Check independently even when the insert failed. NEVER retry.
        independent_absence()
        if failure:
            raise failure
    print(json.dumps({
        "status": "PHYSICAL_G5_V5_OWNER_INSERT_ROLLBACK_RECONCILED",
        "database": bridge.DATABASE, "owner_session": OWNER,
        "policy_hash": policy.POLICY_HASH, "policy_rows_after": 0,
        "probe_rows_after": 0, "g4_historical_hashes": 2,
        "committed_writes": 0, "grants": 0
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(str(exc))
