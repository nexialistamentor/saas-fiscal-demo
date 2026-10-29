"""SOLVERIS B02 G4: unit preparation, execution and independent reconciliation.

DEFAULT: dry-run; no write. --execute requires a separate, explicit
institutional G4 authorization. This file does not grant such authorization.
Only app.services.enterprise_b02_policy_activation_atomicity.stage_policy_activation
may stage the four records; the caller owns COMMIT and ROLLBACK.
"""
import argparse, sys, os, json, hashlib, re
from datetime import datetime, timezone

# ---------------------------------------------------------------------
# Confirmado por leitura real (nao fabricado):
# ---------------------------------------------------------------------
DATABASE = "solveris_b02_r4g_test"
WRITER = "solveris_b02_policy_writer"  # confirmado: existe, sem flags admin, 0 memberships, INSERT nas 4 tabelas

POLICY_TYPE = "activation_authority"
POLICY_ID = "SOLVERIS-B02-SEFA-PR-DOCUMENTARY-AUTHORITY"
POLICY_VERSION = 1
POLICY_HASH = "05ede0f8c8788b93d41e451288efd88d91614a560bdd2191a115f0d736c4fe2a"
DOMAIN = "SEFA_PR_B02_DOCUMENTAL"
MODALITY = "LOCAL_CAS_INCORPORATION"  # unico em policy.modalities, confirmado

DECISION_ID = "B02-05ede-ratificada-v1"
DECISION_RECORD_HASH = "4c5c3d2ffe03118559d3dc617fa90ee90672c13ecec5b616deb3772321d88018"

BOOTSTRAP_ID = "B02-05ede-bootstrap-v1"
BOOTSTRAP_RECORD_HASH = "8bbc9af2383860d79ec00221efbe9df1eda0dd9d10b10ca13c775a1ba8ffac17"

AUTHORIZATION_BASIS_TYPE = "bootstrap_authority_record"  # confirmado: caminho usado pela execucao historica real; NAO depende de nenhuma ativacao previa nem do seu intervalo -- B02P_SUPERIOR_INTERVAL_INVALID nunca entra em jogo por esta via
AUTHORIZATION_CLASS = "constitucional_reservada"  # confirmado: unico em permitted_authorization_classes
EXECUTION_MODE = "manual"  # confirmado: unico em permitted_execution_modes

NEW_WINDOW_FROM = datetime(2026, 10, 29, 13, 0, 0, tzinfo=timezone.utc)
NEW_WINDOW_UNTIL = datetime(2026, 10, 30, 13, 0, 0, tzinfo=timezone.utc)

NEW_IDS = {
    "execution_id": "B02-05ede-execution-v3",
    "activation_id": "B02-05ede-activation-v3",
    "generation_id": "B02-05ede-generation-v3",
    "outbox_id": "B02-05ede-outbox-v3",
    "idempotency_key": "B02-05ede-execution-v3-20261029T130000Z",
}


# Proposed client-side identifiers; these are NOT server record hashes or grants.
LEASE_ID = "B02-05ede-manual-lease-v3"
PROVENANCE = {"source":"SOLVERIS_B02_G4_WINDOW_PREPARATION",
              "purpose":"manual_policy_activation_unit_v3", "synthetic_only":False}
DSN_VARIABLE = "SOLVERIS_B02_POLICY_WRITER_DSN"
SHA = re.compile(r"^[0-9a-f]{64}$")

class G4Stop(RuntimeError):
    pass

def ensure(value, reason):
    if not value:
        raise G4Stop(reason)

def get_row(conn, table, key, value):
    from sqlalchemy import text
    # Table and column identifiers are fixed in this file; never user input.
    return conn.execute(text(f"SELECT * FROM public.{table} WHERE {key}=:v"),
                        {"v":value}).mappings().one_or_none()

def get_unit(conn):
    return {
        "e": get_row(conn,"policy_activation_executions",
                     "policy_activation_execution_id",NEW_IDS["execution_id"]),
        "a": get_row(conn,"policy_activations",
                     "policy_activation_id",NEW_IDS["activation_id"]),
        "g": get_row(conn,"policy_activation_generations",
                     "policy_activation_generation_id",NEW_IDS["generation_id"]),
        "o": get_row(conn,"policy_activation_outbox_events",
                     "policy_activation_outbox_event_id",NEW_IDS["outbox_id"]),
    }

def preflight(conn):
    """Read-only-compatible checks, repeated just before staging."""
    from sqlalchemy import text
    identity = conn.execute(text(
        "SELECT current_database(),session_user,current_user")).one()
    ensure(tuple(identity)==(DATABASE,WRITER,WRITER),"WRITER_DATABASE_IDENTITY_MISMATCH")
    flags=conn.execute(text(
        "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolinherit "
        "FROM pg_roles WHERE rolname=current_user")).one()
    ensure(not any(flags),"ADMINISTRATIVE_ROLE_FORBIDDEN")
    n=conn.execute(text(
        "SELECT count(*) FROM pg_auth_members "
        "WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)")).scalar_one()
    ensure(n==0,"ROLE_MEMBERSHIP_FORBIDDEN")
    for table in ("policy_activation_executions","policy_activations",
                  "policy_activation_generations","policy_activation_outbox_events"):
        for privilege in ("SELECT","INSERT"):
            ensure(conn.execute(text(
                "SELECT has_table_privilege(current_user,:t,:p)"),
                {"t":"public."+table,"p":privilege}).scalar_one(),
                "REQUIRED_TABLE_PERMISSION_MISSING")
    for table in ("policy_versions","policy_decisions","bootstrap_authority_records"):
        ensure(conn.execute(text(
            "SELECT has_table_privilege(current_user,:t,'SELECT')"),
            {"t":"public."+table}).scalar_one(),"PREDECESSOR_READ_PERMISSION_MISSING")
    for fn in ("b02p_check_authority","b02p_require_complete"):
        ensure(conn.execute(text(
            "SELECT count(*) FROM pg_proc WHERE proname=:fn"),
            {"fn":fn}).scalar_one()>0,"REQUIRED_SQL_FUNCTION_MISSING")
    policy=conn.execute(text(
        "SELECT policy_id,policy_version,policy_hash,policy_type,domain,scope,"
        "modalities,permitted_authorization_classes,permitted_execution_modes "
        "FROM public.policy_versions WHERE policy_id=:id "
        "AND policy_version=:v AND policy_hash=:h AND policy_type=:t"),
        {"id":POLICY_ID,"v":POLICY_VERSION,"h":POLICY_HASH,
         "t":POLICY_TYPE}).mappings().one_or_none()
    ensure(policy is not None,"EXACT_POLICY_MISSING")
    ensure(policy["domain"]==DOMAIN and MODALITY in policy["modalities"],
           "POLICY_DOMAIN_OR_MODALITY_CONFLICT")
    ensure(AUTHORIZATION_CLASS in policy["permitted_authorization_classes"]
           and EXECUTION_MODE in policy["permitted_execution_modes"],
           "AUTHORIZATION_CLASS_OR_EXECUTION_MODE_CONFLICT")
    decision=conn.execute(text(
        "SELECT decision_id,record_hash,decision_event,timestamp,policy_type,"
        "policy_id,policy_version,policy_hash FROM public.policy_decisions "
        "WHERE decision_id=:id AND record_hash=:h"),
        {"id":DECISION_ID,"h":DECISION_RECORD_HASH}).mappings().one_or_none()
    ensure(decision is not None and decision["decision_event"]=="ratificada",
           "EXACT_RATIFIED_DECISION_MISSING")
    bootstrap=conn.execute(text(
        "SELECT bootstrap_authority_record_id,record_hash,validity,"
        "independent_audit_result,policy_type,policy_id,policy_version,"
        "policy_hash,domain FROM public.bootstrap_authority_records "
        "WHERE bootstrap_authority_record_id=:id AND record_hash=:h"),
        {"id":BOOTSTRAP_ID,"h":BOOTSTRAP_RECORD_HASH}).mappings().one_or_none()
    ensure(bootstrap is not None and bootstrap["validity"]=="valida"
           and bootstrap["independent_audit_result"]=="favoravel",
           "EXACT_VALID_BOOTSTRAP_MISSING")
    for r in (decision,bootstrap):
        ensure(all(r[k]==v for k,v in
            (("policy_type",POLICY_TYPE),("policy_id",POLICY_ID),
             ("policy_version",POLICY_VERSION),("policy_hash",POLICY_HASH))),
             "PREDECESSOR_POLICY_MISMATCH")
    ensure(bootstrap["domain"]==DOMAIN,"BOOTSTRAP_DOMAIN_MISMATCH")
    # This is the SAME derivation as the existing service, not a caller input.
    from app.services.enterprise_b02_noncredential_acquisition import canonical_bytes
    scope_hash=hashlib.sha256(canonical_bytes(policy["scope"])).hexdigest()
    ensure(bool(SHA.fullmatch(scope_hash)),"DERIVED_SCOPE_HASH_INVALID")
    previous=conn.execute(text(
        "SELECT policy_activation_execution_id FROM public.policy_activation_executions "
        "WHERE idempotency_key=:key"),
        {"key":NEW_IDS["idempotency_key"]}).scalar_one_or_none()
    ensure(previous in (None,NEW_IDS["execution_id"]),"IDEMPOTENCY_KEY_COLLISION")
    return policy,decision,scope_hash

def reconcile(conn,scope_hash,policy):
    """Verify all four durable records on an independent read-only connection."""
    from sqlalchemy import text
    u=get_unit(conn)
    if all(x is None for x in u.values()):
        return None                 # Absence is NOT proof of a rollback.
    ensure(all(x is not None for x in u.values()),"FOUR_RECORD_UNIT_INCOMPLETE")
    e,a,g,o=(u[k] for k in ("e","a","g","o"))
    for r in (e,a,g,o):
        ensure(isinstance(r["record_hash"],str)
               and bool(SHA.fullmatch(r["record_hash"])),"RECORD_HASH_INVALID")
        ensure(all(r[k]==v for k,v in (
            ("policy_id",POLICY_ID),("policy_version",POLICY_VERSION),
            ("policy_hash",POLICY_HASH))),"EXACT_POLICY_BINDING_CONFLICT")
        ensure(r["policy_decision_id"]==DECISION_ID
               and r["policy_decision_record_hash"]==DECISION_RECORD_HASH,
               "EXACT_DECISION_BINDING_CONFLICT")
        ensure(r["provenance"]==PROVENANCE,"PROVENANCE_CONFLICT")
    ensure(e["policy_activation_execution_id"]==NEW_IDS["execution_id"]
           and e["idempotency_key"]==NEW_IDS["idempotency_key"],
           "EXECUTION_IDEMPOTENCY_CONFLICT")
    ensure(e["state"]=="concluida" and e["execution_mode"]==EXECUTION_MODE
           and e["authorization_basis_type"]==AUTHORIZATION_BASIS_TYPE
           and e["authorization_class"]==AUTHORIZATION_CLASS,
           "EXECUTION_AUTHORITY_STATE_CONFLICT")
    ensure(e["bootstrap_authority_record_id"]==BOOTSTRAP_ID
           and e["bootstrap_authority_record_hash"]==BOOTSTRAP_RECORD_HASH,
           "EXACT_BOOTSTRAP_BINDING_CONFLICT")
    ensure(e["actor_or_worker"]==WRITER and e["attempt_number"]==3
           and e["fencing_token"]==3 and e["lease_id"]==LEASE_ID,
           "EXECUTION_ACTOR_ATTEMPT_FENCE_CONFLICT")
    ensure(e["started_at"] is not None and e["finished_at"] is not None
           and e["started_at"]<=e["finished_at"],"EXECUTION_TIME_CONFLICT")
    manifest={"schema":"ADR020_POLICY_ACTIVATION_UNIT_V1",
        "policy_activation_id":NEW_IDS["activation_id"],
        "policy_activation_generation_id":NEW_IDS["generation_id"],
        "policy_activation_outbox_event_id":NEW_IDS["outbox_id"],
        "domain":DOMAIN,"modality":MODALITY,"scope_hash":scope_hash}
    ensure(e["structured_result"]==manifest,"SERVER_COMPLETION_MANIFEST_CONFLICT")
    expected_interval={"from":NEW_WINDOW_FROM.isoformat(),
                       "until":NEW_WINDOW_UNTIL.isoformat()}
    ensure(a["state"]=="activa" and a["domain"]==DOMAIN
           and a["modality"]==MODALITY
           and a["operational_interval"]==expected_interval
           and a["technical_actor"]==WRITER
           and a["activation_generation_id"]==NEW_IDS["generation_id"],
           "ACTIVATION_CONTENT_CONFLICT")
    ensure(a["policy_activation_execution_id"]==NEW_IDS["execution_id"]
           and a["policy_activation_execution_record_hash"]==e["record_hash"],
           "ACTIVATION_EXECUTION_LINK_CONFLICT")
    ensure(g["policy_activation_execution_id"]==NEW_IDS["execution_id"]
           and g["policy_activation_execution_record_hash"]==e["record_hash"]
           and g["policy_activation_id"]==NEW_IDS["activation_id"]
           and g["policy_activation_record_hash"]==a["record_hash"],
           "GENERATION_LINK_CONFLICT")
    ensure(g["scope_descriptor"]==policy["scope"]
           and g["scope_hash"]==scope_hash
           and g["completion_manifest"]==manifest
           and g["operational_interval"]==expected_interval
           and g["schema_version"]==1 and g["is_complete"] is True
           and g["domain"]==DOMAIN and g["modality"]==MODALITY,
           "GENERATION_CONTENT_CONFLICT")
    ensure(o["policy_activation_execution_id"]==NEW_IDS["execution_id"]
           and o["policy_activation_execution_record_hash"]==e["record_hash"]
           and o["policy_activation_id"]==NEW_IDS["activation_id"]
           and o["policy_activation_record_hash"]==a["record_hash"]
           and o["policy_activation_generation_id"]==NEW_IDS["generation_id"]
           and o["policy_activation_generation_hash"]==g["record_hash"],
           "OUTBOX_LINK_CONFLICT")
    ensure(o["event_type"]=="policy_activation_completed"
           and o["schema_version"]==1
           and isinstance(o["payload"],dict)
           and isinstance(o["payload_hash"],str)
           and bool(SHA.fullmatch(o["payload_hash"])),
           "OUTBOX_CONTENT_OR_HASH_INVALID")
    payload_hash=conn.execute(text(
        "SELECT b02_json_hash(payload) FROM public.policy_activation_outbox_events "
        "WHERE policy_activation_outbox_event_id=:id"),
        {"id":NEW_IDS["outbox_id"]}).scalar_one()
    ensure(payload_hash==o["payload_hash"],"OUTBOX_PAYLOAD_HASH_CONFLICT")
    ensure(g["created_at"]==a["activated_at"]==o["created_at"],
           "UNIT_CREATED_AT_CONFLICT")
    txids=(e["b02_policy_txid"],a["b02_policy_txid"],
           g["assigned_txid"],o["assigned_txid"])
    ensure(all(t is not None for t in txids)
           and len(set(txids))==1,"FOUR_RECORD_TXID_CONFLICT")
    complete=conn.execute(text("SELECT b02p_require_complete(:id,false)"),
                          {"id":NEW_IDS["execution_id"]}).scalar_one()
    ensure(complete is not False,"SERVER_COMPLETENESS_REJECTED")
    return {"status":"FOUR_RECORDS_RECONCILED",
        "execution_id":NEW_IDS["execution_id"],"execution_hash":e["record_hash"],
        "activation_id":NEW_IDS["activation_id"],"activation_hash":a["record_hash"],
        "generation_id":NEW_IDS["generation_id"],"generation_hash":g["record_hash"],
        "outbox_id":NEW_IDS["outbox_id"],"outbox_hash":o["record_hash"],
        "outbox_payload_hash":o["payload_hash"],"scope_hash":scope_hash,
        "policy_hash":POLICY_HASH}

def independent_read(engine):
    """Fresh connection; explicitly READ ONLY before any SELECT."""
    with engine.connect() as conn:
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        policy,_,scope_hash=preflight(conn)
        result=reconcile(conn,scope_hash,policy)
        conn.rollback()
        return result

def run(args):
    plan={"mode":"EXECUTION_REQUESTED" if args.execute else "DRY_RUN",
        "database":DATABASE,"writer":WRITER,"policy_id":POLICY_ID,
        "policy_hash":POLICY_HASH,"decision_id":DECISION_ID,
        "bootstrap_id":BOOTSTRAP_ID,"ids":NEW_IDS,"lease_id":LEASE_ID,
        "window":{"from":NEW_WINDOW_FROM.isoformat(),
                  "until":NEW_WINDOW_UNTIL.isoformat()},
        "scope_hash":"DERIVED_BY_SERVICE_FROM_STORED_POLICY_NOT_CALLER_INPUT"}
    print(json.dumps(plan,sort_keys=True))
    ensure(NEW_WINDOW_FROM<=datetime.now(timezone.utc)<NEW_WINDOW_UNTIL,"ACTIVATION_WINDOW_NOT_CURRENT")
    dsn=os.environ.get(DSN_VARIABLE)
    if not args.execute and not dsn:
        print("DRY_RUN_STATIC_ONLY: no DB read and no DB write")
        return
    ensure(bool(dsn),"POLICY_WRITER_DSN_NOT_CONFIGURED")
    if args.execute:
        ensure(bool(args.approval_reference and args.approval_reference.strip()),
               "SPECIFIC_INSTITUTIONAL_G4_APPROVAL_REFERENCE_REQUIRED")
    from sqlalchemy import create_engine,text
    engine=create_engine(dsn,pool_pre_ping=True)
    commit_attempted=False
    try:
        existing=independent_read(engine)
        if existing:
            print(json.dumps(existing,sort_keys=True))
            print("EXISTING_UNIT_RECONCILED: no INSERT")
            return
        if not args.execute:
            print("DRY_RUN_DB_READ_ONLY_PASS: exact predecessors, IDs available")
            return
        from app.services.enterprise_b02_policy_activation_atomicity import stage_policy_activation
        with engine.connect() as conn:
            tx=conn.begin()
            try:
                _,decision,_=preflight(conn)
                ensure(all(r is None for r in get_unit(conn).values()),
                       "UNIT_ID_COLLISION_BEFORE_INSERT")
                # Server clock obtained inside the outer transaction.
                stamp=conn.execute(text("SELECT clock_timestamp()")).scalar_one()
                ensure(stamp>=decision["timestamp"],"DECISION_TIME_NOT_REACHED")
                execution={
                    "policy_activation_execution_id":NEW_IDS["execution_id"],
                    "policy_decision_id":DECISION_ID,
                    "policy_decision_record_hash":DECISION_RECORD_HASH,
                    "policy_type":POLICY_TYPE,"policy_id":POLICY_ID,
                    "policy_version":POLICY_VERSION,"policy_hash":POLICY_HASH,
                    "authorization_basis_type":AUTHORIZATION_BASIS_TYPE,
                    "authorization_class":AUTHORIZATION_CLASS,
                    "execution_mode":EXECUTION_MODE,
                    "bootstrap_authority_record_id":BOOTSTRAP_ID,
                    "bootstrap_authority_record_hash":BOOTSTRAP_RECORD_HASH,
                    "attempt_number":3,"lease_id":LEASE_ID,"fencing_token":3,
                    "idempotency_key":NEW_IDS["idempotency_key"],
                    "state":"concluida","started_at":stamp,"finished_at":stamp,
                    "structured_error":None,"provenance":PROVENANCE}
                activation={
                    "policy_activation_id":NEW_IDS["activation_id"],
                    "state":"activa","domain":DOMAIN,"modality":MODALITY,
                    "operational_interval":{"from":NEW_WINDOW_FROM.isoformat(),
                                            "until":NEW_WINDOW_UNTIL.isoformat()},
                    "activated_at":stamp,"provenance":PROVENANCE}
                staged=stage_policy_activation(
                    conn,execution=execution,activation=activation,
                    generation_id=NEW_IDS["generation_id"],
                    outbox_id=NEW_IDS["outbox_id"],provenance=PROVENANCE)
                ensure(staged.get("reused") is False,"UNEXPECTED_REDELIVERY")
                commit_attempted=True
                tx.commit()
            except BaseException:
                if tx.is_active:
                    tx.rollback()
                raise
        result=independent_read(engine)
        ensure(result is not None,"ACK_UNRECONCILED")
        print(json.dumps(result,sort_keys=True))
    except BaseException:
        if not commit_attempted:
            raise
        # Unknown COMMIT ACK: do not retry any INSERT. Only independent reads.
        for _ in range(3):
            try:
                result=independent_read(engine)
                if result:
                    print(json.dumps(result,sort_keys=True))
                    print("ACK_RECOVERED_FROM_INDEPENDENT_FOUR_RECORD_RECONCILIATION")
                    return
            except Exception:
                pass
        raise G4Stop("COMMIT_OUTCOME_UNKNOWN_MANUAL_RECONCILIATION_REQUIRED")
    finally:
        engine.dispose()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute",action="store_true",
                        help="Never use until separately authorized for this G4 write")
    parser.add_argument("--approval-reference",
                        help="Exact previously issued institutional reference; flag is not authorization")
    args=parser.parse_args()
    try:
        run(args)
    except Exception as exc:
        # No SQLAlchemy DSN, database messages, or credentials in output.
        reason=str(exc) if isinstance(exc,G4Stop) else type(exc).__name__
        print("STOP: "+reason,file=sys.stderr)
        sys.exit(2)

if __name__=="__main__":
    main()
