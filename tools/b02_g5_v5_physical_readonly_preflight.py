#!/usr/bin/env python3
"""Read-only physical G5 V5 preflight against isolated PostgreSQL.

Never INSERTs, UPDATEs, DELETEs, signs, or activates. Uses explicit read-only
transaction and a role with no elevated privileges. Requires DSN from environment.
"""
import json
import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

DB="solveris_b02_r4g_test"
REV="0063_adr020_policy_activation_atomicity"
POLICY="SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE"
POLICY_HASH="007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf"

def inspect(engine):
    with engine.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        db, session_user, current_user = c.execute(text("SELECT current_database(),session_user,current_user")).one()
        if db != DB: raise RuntimeError("STOP_WRONG_DB")
        if session_user != "solveris_b02_policy_writer" or current_user != session_user:
            raise RuntimeError("STOP_WRONG_ROLE")
        revision=c.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
        if revision!=REV:raise RuntimeError("STOP_WRONG_REVISION")
        flags=c.execute(text("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolinherit FROM pg_roles WHERE rolname=current_user")).one()
        if any(flags):raise RuntimeError("STOP_PRIVILEGED_ROLE")
        memberships=c.execute(text("SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)")).scalar_one()
        if memberships:raise RuntimeError("STOP_ROLE_MEMBERSHIPS")
        historical=c.execute(text("""SELECT policy_version_record_id,
          record_hash=public.b02_json_hash(to_jsonb(p)-'record_hash') AS hash_equivalent
          FROM public.policy_versions p WHERE policy_version_record_id IN
          ('B02-57982-policy-v1','B02-05ede-policy-v1') ORDER BY policy_version_record_id""")).mappings().all()
        if len(historical)!=2 or not all(x["hash_equivalent"] for x in historical):
            raise RuntimeError("STOP_G4_HISTORICAL_HASH")
        candidate=c.execute(text("""SELECT policy_version_record_id,policy_hash,policy_version
           FROM public.policy_versions WHERE policy_id=:policy AND policy_version=2"""),
           {"policy":POLICY}).mappings().all()
        if any(x["policy_hash"]!=POLICY_HASH for x in candidate) or len(candidate)>1:
            raise RuntimeError("STOP_G5_POLICY_CONFLICT")
        tables=c.execute(text("""SELECT table_name FROM information_schema.tables
           WHERE table_schema='public' AND table_name IN
           ('policy_activation_executions','policy_activations',
           'policy_activation_generations','policy_activation_outbox_events','policy_decisions')""")).scalars().all()
        if len(tables)!=5:raise RuntimeError("STOP_ATOMIC_TABLES_MISSING")
        c.rollback()
        return {"status":"PHYSICAL_READ_ONLY_PREFLIGHT_PASS","database":db,"revision":revision,
          "role":current_user,"g4_hash_equivalence":len(historical),
          "g5_v5_policy_rows":len(candidate),"atomic_tables":len(tables),"writes":0}

def main():
    dsn=os.environ.get("SOLVERIS_B02_POLICY_WRITER_DSN")
    if not dsn:raise RuntimeError("STOP_DSN_REQUIRED")
    engine=create_engine(dsn,poolclass=NullPool)
    try:print(json.dumps(inspect(engine),sort_keys=True))
    finally:engine.dispose()

if __name__=="__main__":main()
