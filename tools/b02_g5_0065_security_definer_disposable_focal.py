#!/usr/bin/env python3
"""B02 0065: ONLY the new SECURITY DEFINER privilege delta in disposable PG17.10.

No protected database, no G5 real native signature, no policy authorization,
no full 0064/0065 installation, no repetition of V30. Test profile is STUBBED
deliberately to isolate SQL privileges; this is not a positive G5 release.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
MIG = "migrations/candidates/0065_b02_g5_one_shot_real_CANDIDATE.py"
PINNED_BLOB = "7f3fbf53217aecfe045280f343982ece5a72d60c"
IMAGE = "postgres:17.10-trixie"
DB = "solveris_b02_r4g_test"
PREFIX = "solveris-b02-0065-focal-"


def run(args, *, stdin=None, ok=True):
    p = subprocess.run(args, cwd=ROOT, text=True, input=stdin,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=90, check=False)
    if ok and p.returncode:
        raise RuntimeError("COMMAND_FAILED " + args[0] + " " + p.stderr[-340:])
    return p


def get_fragment():
    checked = run(["git", "rev-parse", "HEAD:" + MIG]).stdout.strip()
    working = run(["git", "hash-object", MIG]).stdout.strip()
    if checked != PINNED_BLOB or working != PINNED_BLOB:
        raise RuntimeError("STOP_0065_SOURCE_NOT_PINNED")
    tree = ast.parse((ROOT / MIG).read_text(encoding="utf-8"))
    values = [ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "_SQL"
                      for t in node.targets)]
    if len(values) != 1:
        raise RuntimeError("STOP_0065_SQL_LITERAL_MISSING")
    sql = values[0]
    prefix = sql.split("CREATE FUNCTION public.b02_g5_assert_one_shot()", 1)[0]
    anchors = (
        "CREATE TABLE public.b02_g5_operational_approval_uses",
        "REVOKE ALL ON public.b02_g5_operational_approval_uses FROM solveris_b02_writer;",
        "RETURNS text LANGUAGE plpgsql SECURITY DEFINER",
        "SET search_path=pg_catalog,pg_temp",
        "session_user<>'solveris_b02_writer'",
        "current_user<>'solveris_test'",
        "INSERT INTO public.b02_g5_operational_approval_uses",
        "GRANT EXECUTE ON FUNCTION public.b02_g5_reserve_operational_decision",
    )
    if len(sql.split("CREATE FUNCTION public.b02_g5_assert_one_shot()")) != 2 \
            or not all(a in prefix for a in anchors) \
            or "CREATE OR REPLACE FUNCTION public.b02g5_capability_manifest()" in prefix:
        raise RuntimeError("STOP_0065_SECURITY_FRAGMENT_NOT_EXACT")
    return prefix


def psql(name, database, sql, *, expect_failure=False):
    cmd = ["docker", "exec", "-i", name, "psql", "-X", "-v", "ON_ERROR_STOP=1",
           "-A", "-t", "-F", "|", "-U", "postgres", "-d", database]
    res = run(cmd, stdin=sql, ok=False)
    if expect_failure:
        if res.returncode == 0:
            raise RuntimeError("STOP_0065_EXPECTED_DENIAL_DID_NOT_OCCUR")
    elif res.returncode:
        raise RuntimeError("STOP_0065_DISPOSABLE_PSQL " + res.stderr[-500:])
    return res


def verify():
    if not shutil.which("docker"):
        raise RuntimeError("STOP_0065_DOCKER_MISSING")
    fragment = get_fragment()
    run(["docker", "image", "inspect", IMAGE])
    name = PREFIX + uuid.uuid4().hex[:12]
    created = False
    try:
        run(["docker", "run", "--detach", "--rm", "--pull=never",
             "--network", "none", "--name", name,
             "--tmpfs", "/var/lib/postgresql/data:rw,size=256m",
             "-e", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE])
        created = True
        for _ in range(40):
            ready = run(["docker", "exec", name, "pg_isready", "-q",
                         "-U", "postgres"], ok=False)
            if ready.returncode == 0:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("STOP_0065_DISPOSABLE_POSTGRES_NOT_READY")
        psql(name, "postgres", "CREATE ROLE solveris_test LOGIN;")
        psql(name, "postgres", "CREATE ROLE solveris_b02_writer LOGIN;")
        psql(name, "postgres", "CREATE DATABASE " + DB + " OWNER solveris_test;")
        # STUB (not a genuine native G5 signature): privilege-only differential.
        setup = """SET SESSION AUTHORIZATION solveris_test;
CREATE FUNCTION public.b02g5_native_profile() RETURNS text
LANGUAGE sql STABLE AS $$SELECT 'REAL_PROFILE_COMPILED_APPROVED_ROOTS'::text$$;
GRANT USAGE ON SCHEMA public TO solveris_b02_writer;
"""
        psql(name, DB, setup + fragment)
        facts = psql(name, DB, """SELECT
  pg_get_userbyid(p.proowner), p.prosecdef,
  has_table_privilege('solveris_b02_writer',
    'public.b02_g5_operational_approval_uses','INSERT'),
  has_table_privilege('solveris_b02_writer',
    'public.b02_g5_operational_approval_uses','SELECT'),
  has_function_privilege('solveris_b02_writer',p.oid,'EXECUTE')
FROM pg_proc p
WHERE p.proname='b02_g5_reserve_operational_decision'
  AND p.pronamespace='public'::regnamespace;
""").stdout.strip().splitlines()
        if facts != ["solveris_test|t|f|t|t"]:
            raise RuntimeError("STOP_0065_PHYSICAL_OWNER_OR_PRIVILEGES " + repr(facts))
        direct = psql(name, DB, """SET SESSION AUTHORIZATION solveris_b02_writer;
INSERT INTO public.b02_g5_operational_approval_uses
(approval_id,release_id,assigned_txid,operator_sha256,
 decision_document_sha256,writer_name,database_name)
VALUES ('direct','direct','1',repeat('a',64),repeat('b',64),
 session_user,current_database());
""", expect_failure=True)
        if "permission denied for table b02_g5_operational_approval_uses" not in direct.stderr:
            raise RuntimeError("STOP_0065_DIRECT_INSERT_DENIAL_NOT_ACL " + direct.stderr[-260:])
        positive = psql(name, DB, """SET SESSION AUTHORIZATION solveris_b02_writer;
BEGIN;
SELECT public.b02_g5_reserve_operational_decision(
'focal-0065','focal-release',repeat('a',64)::char(64),
repeat('b',64)::char(64));
SELECT count(*) FROM public.b02_g5_operational_approval_uses
WHERE approval_id='focal-0065';
ROLLBACK;
""").stdout.strip().splitlines()
        if len(positive) != 5 or positive[0:2] != ["SET","BEGIN"] \
                or not positive[2].isdigit() or positive[3:] != ["1", "ROLLBACK"]:
            raise RuntimeError("STOP_0065_RESERVATION_RESULT " + repr(positive))
        spoof = psql(name, DB, """SET ROLE solveris_b02_writer;
SELECT public.b02_g5_reserve_operational_decision(
'spoof','spoof',repeat('a',64)::char(64),
repeat('b',64)::char(64));
""", expect_failure=True)
        if "G5_ONESHOT_PROTECTED_WRITER_ONLY" not in spoof.stderr:
            raise RuntimeError("STOP_0065_SESSION_USER_GUARD " + spoof.stderr[-260:])
        remaining = psql(name, DB, """SELECT count(*)
FROM public.b02_g5_operational_approval_uses;""").stdout.strip()
        if remaining != "0":
            raise RuntimeError("STOP_0065_ROLLBACK_LEFT_ROWS")
        return {
            "status": "B02_0065_SECURITY_DEFINER_PHYSICAL_DISPOSABLE_PASS",
            "pg_image": IMAGE, "migration_source_blob": PINNED_BLOB,
            "direct_insert_denied": True, "owner": "solveris_test",
            "restricted_writer_exec_function": True,
            "session_user_spoof_denied": True, "rows_after_rollback": 0,
            "native_profile": "STUB_ONLY_NOT_REAL_G5_PROOF",
            "full_migration": "NOT_INSTALLED", "protected_writes": 0,
            "host_ports": [], "network": "none"
        }
    finally:
        if created:
            run(["docker", "rm", "-f", name], ok=True)


def main():
    try:
        result = verify()
        print(json.dumps(result, sort_keys=True))
    except Exception as exc:
        print("STOP_B02_0065_SECURITY " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
