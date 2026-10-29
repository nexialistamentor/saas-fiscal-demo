#!/usr/bin/env python3
"""Read-only physical G5 V5 preflight against isolated PostgreSQL.

Never INSERTs, UPDATEs, DELETEs, signs, or activates. Uses explicit read-only
transaction and a role with no elevated privileges. Requires DSN from environment.
"""
import json
import os
import subprocess
import time
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.pool import NullPool

DB="solveris_b02_r4g_test"
CONTAINER="solveris-pg17-migration-test"
VOLUME_PREFIX="4fe15764d8f4c6c2b5aaaad634c0ed54ec"
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
        # The canonical decisions table uses decision_id, not policy_decision_id.
        # Count the entire version, not a limited sample, and reject any hash mismatch.
        decisions=c.execute(text("""SELECT count(*) AS total,
            count(*) FILTER (WHERE policy_hash <> :expected_hash) AS divergent
            FROM public.policy_decisions
            WHERE policy_id=:policy AND policy_version=2"""),
            {"policy":POLICY,"expected_hash":POLICY_HASH}).mappings().one()
        if decisions["divergent"]:
            raise RuntimeError("STOP_G5_DECISION_POLICY_HASH_CONFLICT")
        c.rollback()
        return {"status":"PHYSICAL_READ_ONLY_PREFLIGHT_PASS","database":db,"revision":revision,
          "role":current_user,"g4_hash_equivalence":len(historical),
          "g5_v5_policy_rows":len(candidate),"g5_v5_decision_rows":decisions["total"],"atomic_tables":len(tables),"writes":0}

def _acl_inventory(engine):
    """Read-only physical ACL/owner inventory; no grants, DDL, role switch or data writes."""
    names = (
        "policy_versions", "policy_decisions", "bootstrap_authority_records",
        "policy_activation_executions", "policy_activations",
        "policy_activation_generations", "policy_activation_outbox_events",
    )
    with engine.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        db,session_user,current_user,revision = c.execute(text(
            "SELECT current_database(),session_user,current_user,"
            "(SELECT version_num FROM public.alembic_version)"
        )).one()
        if (db,session_user,current_user,revision)!=(
            DB,"solveris_b02_policy_writer","solveris_b02_policy_writer",REV
        ):raise RuntimeError("STOP_ACL_IDENTITY_REVISION")
        query=text("""
            SELECT cls.relname AS table_name,
                   pg_get_userbyid(cls.relowner) AS owner,
                   has_table_privilege(current_user,cls.oid,'SELECT') AS can_select,
                   has_table_privilege(current_user,cls.oid,'INSERT') AS can_insert,
                   has_table_privilege(current_user,cls.oid,'UPDATE') AS can_update,
                   has_table_privilege(current_user,cls.oid,'DELETE') AS can_delete
            FROM pg_class cls JOIN pg_namespace ns ON ns.oid=cls.relnamespace
            WHERE ns.nspname='public' AND cls.relkind IN ('r','p')
              AND cls.relname IN :names
            ORDER BY cls.relname
        """).bindparams(bindparam("names",expanding=True))
        rows=c.execute(query,{"names":list(names)}).mappings().all()
        if {r["table_name"] for r in rows}!=set(names):
            raise RuntimeError("STOP_ACL_TABLES_MISSING")
        inventory=[dict(r) for r in rows]
        c.rollback()
    return {"status":"PHYSICAL_READ_ONLY_ACL_INVENTORY_PASS","database":db,
            "revision":revision,"writer":current_user,"tables":inventory,
            "writes":0,"grants":0}


def _database_preflight():
    dsn=os.environ.get("SOLVERIS_B02_POLICY_WRITER_DSN")
    if not dsn:
        sql = """BEGIN READ ONLY;
SELECT current_database(),current_user,(SELECT version_num FROM public.alembic_version);
SELECT policy_version_record_id,record_hash=public.b02_json_hash(to_jsonb(p)-'record_hash')
FROM public.policy_versions p WHERE policy_version_record_id IN
('B02-57982-policy-v1','B02-05ede-policy-v1') ORDER BY policy_version_record_id;
SELECT count(*) FROM information_schema.tables WHERE table_schema='public'
AND table_name IN ('policy_activation_executions','policy_activations',
'policy_activation_generations','policy_activation_outbox_events','policy_decisions');
SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolinherit,
(SELECT count(*) FROM pg_auth_members WHERE member=pg_roles.oid)
FROM pg_roles WHERE rolname='solveris_b02_policy_writer';
SELECT count(*), count(*) FILTER (WHERE policy_hash='007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf')
FROM public.policy_versions
WHERE policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE' AND policy_version=2;
SELECT count(*), count(*) FILTER (WHERE policy_hash<>'007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf')
FROM public.policy_decisions
WHERE policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE' AND policy_version=2;
ROLLBACK;"""
        result=subprocess.run(["docker","exec","-i","solveris-pg17-migration-test",
            "psql","-X","-v","ON_ERROR_STOP=1","-U","solveris_b02_writer",
            "-d",DB,"-At"],input=sql,text=True,capture_output=True)
        if result.returncode:
            raise RuntimeError("STOP_DOCKER_SQL_READ_ONLY: "+result.stderr.strip())
        lines=result.stdout.strip().splitlines()
        if len(lines)!=9:raise RuntimeError("STOP_DOCKER_OUTPUT_SHAPE")
        if lines[0]!="BEGIN" or lines[1]!=DB+"|solveris_b02_writer|"+REV:
            raise RuntimeError("STOP_DOCKER_IDENTITY_REVISION")
        if lines[2]!="B02-05ede-policy-v1|t" or lines[3]!="B02-57982-policy-v1|t":
            raise RuntimeError("STOP_G4_HISTORICAL_HASH")
        if lines[4]!="5":raise RuntimeError("STOP_ATOMIC_TABLES_MISSING")
        if lines[5]!="solveris_b02_policy_writer|f|f|f|f|f|f|0":
            raise RuntimeError("STOP_POLICY_WRITER_ROLE_PRIVILEGES")
        if lines[6] not in ("0|0","1|1"):raise RuntimeError("STOP_G5_POLICY_VERSION_OR_HASH_CONFLICT")
        decision_parts=lines[7].split("|")
        if len(decision_parts)!=2 or not all(part.isdigit() for part in decision_parts):
            raise RuntimeError("STOP_G5_DECISION_COUNT")
        if decision_parts[1]!="0":raise RuntimeError("STOP_G5_DECISION_POLICY_HASH_CONFLICT")
        if lines[8]!="ROLLBACK":raise RuntimeError("STOP_DOCKER_ROLLBACK")
        auth_sql="BEGIN READ ONLY; SELECT current_database(),session_user,current_user; ROLLBACK;"
        auth=subprocess.run(["docker","exec","-i","solveris-pg17-migration-test",
            "psql","-X","-v","ON_ERROR_STOP=1","-U","solveris_b02_policy_writer",
            "-d",DB,"-At"],input=auth_sql,text=True,capture_output=True)
        auth_verified=(auth.returncode==0 and
            auth.stdout.strip().splitlines()==["BEGIN",
            DB+"|solveris_b02_policy_writer|solveris_b02_policy_writer","ROLLBACK"])
        if auth.returncode==0 and not auth_verified:
            raise RuntimeError("STOP_POLICY_WRITER_AUTH_IDENTITY")
        print(json.dumps({"status":"PHYSICAL_DOCKER_READ_ONLY_PREFLIGHT_PASS",
            "database":DB,"revision":REV,"role":"solveris_b02_writer",
            "g4_hash_equivalence":2,"atomic_tables":5,
            "g5_v5_policy_rows":int(lines[6].split("|")[0]),"g5_v5_decision_rows":int(decision_parts[0]),"writes":0,
            "policy_writer_role_catalog_verified":True,
            "policy_writer_authenticated":auth_verified,
            "policy_writer_auth_requires_setup":not auth_verified},sort_keys=True))
        return
    engine=create_engine(dsn,poolclass=NullPool)
    try:print(json.dumps(inspect(engine),sort_keys=True))
    finally:engine.dispose()

def _docker(*args, timeout=15):
    result=subprocess.run(["docker",*args],text=True,capture_output=True,timeout=timeout)
    if result.returncode:
        raise RuntimeError("STOP_DOCKER_COMMAND: "+(result.stderr or "").strip()[-300:])
    return result.stdout.strip()

def main():
    import sys
    if len(sys.argv)>1:
        if sys.argv[1:]!=["--acl-inventory"]:
            raise RuntimeError("STOP_UNKNOWN_PREFLIGHT_OPTION")
        dsn=os.environ.get("SOLVERIS_B02_POLICY_WRITER_DSN")
        if not dsn:raise RuntimeError("STOP_ACL_INVENTORY_REQUIRES_BRIDGE")
        engine=create_engine(dsn,poolclass=NullPool)
        try:print(json.dumps(_acl_inventory(engine),sort_keys=True))
        finally:engine.dispose()
        return
    # Preserve initial Docker state; do not require passwords or change pg_hba.
    if os.environ.get("SOLVERIS_B02_POLICY_WRITER_DSN"):
        return _database_preflight()
    info=json.loads(_docker("inspect",CONTAINER))
    if len(info)!=1:
        raise RuntimeError("STOP_CONTAINER_IDENTITY")
    container=info[0]
    volumes=[m for m in container.get("Mounts",[])
             if m.get("Type")=="volume" and m.get("Name","").startswith(VOLUME_PREFIX)]
    if len(volumes)!=1:
        raise RuntimeError("STOP_CONTAINER_VOLUME_MISMATCH")
    started=False
    if not container["State"]["Running"]:
        _docker("start",CONTAINER,timeout=25)
        started=True
    try:
        deadline=time.monotonic()+20
        while True:
            ready=subprocess.run(
                ["docker","exec",CONTAINER,"pg_isready","-q","-h","127.0.0.1",
                 "-p","5432","-U","solveris_b02_writer","-d",DB],
                text=True,capture_output=True,timeout=5)
            if ready.returncode==0:
                break
            if time.monotonic()>=deadline:
                raise RuntimeError("STOP_POSTGRESQL_READINESS_TIMEOUT")
            time.sleep(0.4)
        return _database_preflight()
    finally:
        if started:
            # An already-running container is never stopped. An initially
            # stopped container is stopped only if no other client is active.
            try:
                clients=_docker(
                    "exec",CONTAINER,"psql","-X","-q","-At","-w",
                    "-U","solveris_b02_writer","-d",DB,"-c",
                    "SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid()")
                if clients=="0":
                    _docker("stop",CONTAINER,timeout=25)
                else:
                    print("CONTAINER_PRESERVED_RUNNING_ACTIVE_CLIENTS",flush=True)
            except Exception:
                print("CONTAINER_STATE_UNCERTAIN_MANUAL_REVIEW_NO_RETRY",flush=True)
                raise

if __name__=="__main__":main()
