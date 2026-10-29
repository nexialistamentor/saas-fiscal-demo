#!/usr/bin/env python3
"""Physical PostgreSQL transaction/rollback probe, isolated B02 G5 V5.

Uses an actual transaction under solveris_b02_policy_writer. Writes only to
a transaction-local temporary table and rolls it back; no public schema writes,
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
CREATE TEMP TABLE pg_temp.b02_g5_v5_rollback_probe (probe_id integer PRIMARY KEY) ON COMMIT DROP;
INSERT INTO pg_temp.b02_g5_v5_rollback_probe (probe_id) VALUES (1);
SELECT count(*) FROM pg_temp.b02_g5_v5_rollback_probe;
ROLLBACK;
SELECT to_regclass('pg_temp.b02_g5_v5_rollback_probe') IS NULL;
"""
    proc=subprocess.run(["docker","exec","-i",CONTAINER,"psql","-X",
        "-v","ON_ERROR_STOP=1","-U",ROLE,"-d",DB,"-At"],
        input=sql,text=True,capture_output=True)
    if proc.returncode:
        raise RuntimeError("STOP_PHYSICAL_TRANSACTION_PROBE_FAILED")
    lines=proc.stdout.strip().splitlines()
    expected=["BEGIN",DB+"|"+ROLE+"|"+ROLE,"CREATE TABLE","INSERT 0 1","1","ROLLBACK","t"]
    if lines!=expected:
        raise RuntimeError("STOP_PHYSICAL_ROLLBACK_NOT_PROVEN")
    return {"status":"PHYSICAL_TRANSACTION_ROLLBACK_PASS",
            "database":DB,"role":ROLE,"temp_inserted":1,
            "temp_after_rollback":0,"public_schema_writes":0,
            "policy_installations":0,"activations":0}

if __name__=="__main__":
    print(json.dumps(probe(),sort_keys=True))
