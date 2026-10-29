#!/usr/bin/env python3
"""Physical PostgreSQL transaction/rollback probe, isolated B02 G5 V5.

Uses an actual transaction under solveris_b02_policy_writer. Uses transaction-scoped advisory locks and rolls them back; no public schema writes,
no policy installation, no activation, no institutional records.
"""
import json
import subprocess

DB="solveris_b02_r4g_test"
ROLE="solveris_b02_policy_writer"
CONTAINER="solveris-pg17-migration-test"

def probe():
    sql="""BEGIN;
SELECT current_database(),session_user,current_user;
SELECT pg_advisory_xact_lock(90452026);
SELECT pg_advisory_xact_lock_shared(90452027);
ROLLBACK;
SELECT NOT EXISTS (SELECT 1 FROM pg_locks WHERE pid=pg_backend_pid() AND locktype='advisory');
"""
    proc=subprocess.run(["docker","exec","-i",CONTAINER,"psql","-X",
        "-v","ON_ERROR_STOP=1","-U",ROLE,"-d",DB,"-At"],
        input=sql,text=True,capture_output=True)
    if proc.returncode:
        detail=(proc.stderr or "").strip()[-1200:]
        raise RuntimeError("STOP_PHYSICAL_TRANSACTION_PROBE_FAILED: "+detail)
    lines=proc.stdout.strip().splitlines()
    expected=["BEGIN",DB+"|"+ROLE+"|"+ROLE,"","","ROLLBACK","t"]
    if lines!=expected:
        raise RuntimeError("STOP_PHYSICAL_ROLLBACK_NOT_PROVEN")
    return {"status":"PHYSICAL_TRANSACTION_ROLLBACK_PASS",
            "database":DB,"role":ROLE,"transaction_scoped_advisory_locks_released":True,"public_schema_writes":0,
            "policy_installations":0,"activations":0}

if __name__=="__main__":
    print(json.dumps(probe(),sort_keys=True))
