#!/usr/bin/env python3
"""B02 G5 V5 policy-only staged transaction; dry-run by default.
Never creates institutional decisions, signatures, activations or G5 native artifacts.
"""
import argparse, hashlib, json, os, re, sys
from pathlib import Path

POLICY_ID = 'SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
POLICY_HASH = '007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf'
FILE_HASH = 'bf7cdb951ac8e4fb8e5b8e2a1aa6fa3095fad194cbd5845a0dc0e20afd7a3ae9'
FILENAME = 'POLICY_G5_CANDIDATO_SUCESSOR_OUTUBRO_V5_VERSION_2_PARA_REVISAO.json'
FIELDS = ('policy_type','policy_id','policy_version','domain','scope','declared_material_applicability',
          'modalities','permitted_authorization_classes','permitted_execution_modes','gates','roles',
          'segregation_of_duties','limits','rules','exact_references','origin_evidence')
HEX = re.compile(r'^[0-9a-f]{64}$')

def stop(reason):
    raise RuntimeError('STOP_' + reason)

def canonical(obj):
    def check(v):
        if v is None or type(v) in (str, bool, int): return
        if isinstance(v,list):
            for x in v: check(x)
            return
        if isinstance(v,dict) and all(type(k) is str for k in v):
            for x in v.values(): check(x)
            return
        stop('CANONICAL_TYPE')
    check(obj)
    return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')

def candidate(repo):
    raw=(repo/FILENAME).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=FILE_HASH:stop('FILE_HASH')
    body=json.loads(raw)['policy_candidate_body']
    if hashlib.sha256(canonical(body)).hexdigest()!=POLICY_HASH:stop('BODY_HASH')
    if (body.get('policy_id'),body.get('policy_version'),body.get('policy_type'))!=(POLICY_ID,2,'activation_authority'):stop('IDENTITY')
    if set(body)!=set(FIELDS):stop('BODY_COLUMNS')
    return body

def authorize(path, reference):
    """Verify the existing user instruction for an inert policy-row INSERT ONLY.

    This does not fabricate approval, evidence, an institutional decision or a
    signature. Separate decision/activation gates remain outside this command.
    """
    if not path:
        path=Path(__file__).resolve().parents[1]/'B02_G5_V5_AUTHORIZATION_MANIFEST_DRAFT.json'
    if not reference:
        reference='USER_ORDER_INSTALA_E_ATIVA_G5_V5_VERSION_2'
    a=json.loads(path.read_text(encoding='utf-8'))
    expected={'scope':'POLICY_VERSION_ONLY','database':'solveris_b02_r4g_test',
              'writer':'solveris_b02_policy_writer','policy_id':POLICY_ID,
              'policy_version':2,'policy_hash':POLICY_HASH,'file_sha256':FILE_HASH,
              'reference':reference,'authorization_text':'INSTALA E ATIVA'}
    for key,value in expected.items():
        if a.get(key)!=value:stop('AUTHORIZATION_'+key.upper())
    if reference!='USER_ORDER_INSTALA_E_ATIVA_G5_V5_VERSION_2':
        stop('AUTHORIZATION_REFERENCE_NOT_EXISTING_ORDER')
    receipt=a.get('authorization_received',{})
    if receipt.get('literal')!='INSTALA E ATIVA' or receipt.get('source')!='user instruction in conversation':
        stop('AUTHORIZATION_SOURCE_UNVERIFIED')
    if a.get('status')!='PENDING_EVIDENCE':
        stop('AUTHORIZATION_MANIFEST_UNEXPECTED_STATE')
    if a.get('restrictions',{}).get('g4_and_mei_immutable') is not True:
        stop('HISTORICAL_SCOPE_GUARD')
    if a.get('server_record_hash_contract_verified') is not True:
        stop('SERVER_HASH_CONTRACT_ATTESTATION')
    if a.get('policy_version_record_id') not in (None,'B02-G5-V5-policy-v2'):
        stop('TECHNICAL_RECORD_ID_CONFLICT')
    # Only the technical row ID is deterministic. No person, review,
    # custody, validity certificate or ratified decision is inferred.
    a['policy_version_record_id']='B02-G5-V5-policy-v2'
    return a


def reconcile(engine,record_id):
    from sqlalchemy import text
    with engine.connect() as c:
        row=c.execute(text('SELECT * FROM public.policy_versions WHERE policy_id=:p AND policy_version=2'),{'p':POLICY_ID}).mappings().one_or_none()
        c.rollback()
    if row is None:return 'ABSENT',None
    data=dict(row)
    if (data['policy_version_record_id']!=record_id or data['policy_hash']!=POLICY_HASH
        or data['policy_type']!='activation_authority' or not HEX.fullmatch(data['record_hash'] or '')):return 'CONFLICT',data
    return 'PRESENT_IDENTITY',data

class _PolicyRollbackProbe(Exception):
    """Deliberate exception inside the transaction context, forcing ROLLBACK."""
    pass


def _owner_commit_sql(body,record_id):
    """Derive the one-shot SQL from the physically proven owner INSERT template."""
    import b02_g5_v5_institutional_owner_rollback_probe as owner
    if record_id!='B02-G5-V5-policy-v2':
        stop('TECHNICAL_RECORD_ID_UNAPPROVED')
    if not (body['origin_evidence'].get('synthetic_only') is False
            and body['origin_evidence'].get('classification')==
            'candidate_for_real_documentary_persistence_not_execution_claim'):
        stop('POLICY_ORIGIN_CLASSIFICATION')
    template=owner.make_rollback_sql(body)
    old_id='B02-G5-V5-ROLLBACK-PROBE'
    suffix="ROLLBACK;\nSELECT 'B02_G5_V5_OWNER_ROLLBACK_ACK';"
    if template.count(old_id)!=2 or not template.endswith(suffix):
        stop('OWNER_ROLLBACK_TEMPLATE_UNEXPECTED')
    guard=""" IF clock_timestamp()<TIMESTAMPTZ '2026-10-29T13:00:00+00:00'
 OR clock_timestamp()>=TIMESTAMPTZ '2026-10-30T13:00:00+00:00'
 THEN RAISE EXCEPTION 'STOP_G5_V5_WINDOW_NOT_CURRENT'; END IF;
 IF NOT EXISTS (
 SELECT 1 FROM public.policy_activations
 WHERE policy_activation_id='B02-05ede-activation-v3'
 AND record_hash='504b7f03b299068786aa73257c809de7f78d6aa5a67ed66c04b38a0230b9c4f4'
 ) THEN RAISE EXCEPTION 'STOP_G4_EXACT_PREDECESSOR_MISSING'; END IF;
"""
    needle=' PERFORM pg_advisory_xact_lock(\n'
    if template.count(needle)!=1:
        stop('OWNER_SQL_GUARD_ANCHOR')
    statement=(template.replace(old_id,record_id)
               .replace(needle,guard+needle)
               .removesuffix(suffix)+
               "COMMIT;\nSELECT 'B02_G5_V5_OWNER_COMMIT_ACK';")
    if statement.count('COMMIT;')!=1 or statement.count('ROLLBACK;')!=0:
        stop('OWNER_SINGLE_COMMIT_CONTRACT')
    return statement


def _restricted_readback(body,record_id):
    """Independent full row/physical hash check using the restricted writer."""
    import b02_g5_v5_institutional_owner_rollback_probe as owner
    sql="""BEGIN READ ONLY;
SELECT current_database()||'|'||session_user||'|'||current_user;
SELECT version_num FROM public.alembic_version;
SELECT coalesce((SELECT jsonb_build_object(
 'stored',to_jsonb(p),
 'record_hash_ok',p.record_hash=public.b02_json_hash(to_jsonb(p)-'record_hash')
 )::text FROM public.policy_versions p
 WHERE policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
 AND policy_version=2),'null');
SELECT count(*) FROM public.policy_versions p
 WHERE policy_version_record_id IN ('B02-57982-policy-v1','B02-05ede-policy-v1')
 AND p.record_hash=public.b02_json_hash(to_jsonb(p)-'record_hash');
ROLLBACK;"""
    lines=owner.psql(sql,owner.bridge.ROLE)
    if len(lines)!=6 or lines[:3]!=[
        'BEGIN',
        owner.bridge.DATABASE+'|'+owner.bridge.ROLE+'|'+owner.bridge.ROLE,
        '0063_adr020_policy_activation_atomicity'
    ] or lines[4:]!=['2','ROLLBACK']:
        stop('INDEPENDENT_READBACK_IDENTITY_OR_G4')
    observation=json.loads(lines[3])
    if observation is None:return 'ABSENT',None
    row=observation['stored']
    if (observation['record_hash_ok'] is not True
        or row.get('policy_version_record_id')!=record_id
        or row.get('policy_hash')!=POLICY_HASH
        or row.get('policy_type')!='activation_authority'
        or not HEX.fullmatch(row.get('record_hash') or '')
        or any(row.get(k)!=v for k,v in body.items())):
        return 'CONFLICT',row
    return 'PRESENT_EXACT',row


def _execute_owner_policy_only(repo,body,a):
    """Only the policy INSERT runs as table owner; readback uses writer role."""
    import b02_g5_v5_institutional_owner_rollback_probe as owner
    from datetime import datetime, timezone
    now=datetime.now(timezone.utc)
    if not (datetime.fromisoformat(body['declared_material_applicability']['from'])<=now
            <datetime.fromisoformat(body['declared_material_applicability']['until'])):
        stop('V5_MATERIAL_WINDOW_EXPIRED_OR_NOT_STARTED')
    record_id=a['policy_version_record_id']
    with owner.bridge.managed_container():
        status,row=_restricted_readback(body,record_id)
        if status=='CONFLICT':stop('EXISTING_G5_POLICY_CONFLICT')
        if status=='PRESENT_EXACT':
            print(json.dumps({'status':'ALREADY_PERSISTED_EXACT_RECONCILED',
              'policy_hash':POLICY_HASH,'record_id':record_id,
              'record_hash':row['record_hash'],'writes_now':0},sort_keys=True))
            return
        owner.owner_preflight()
        sql=_owner_commit_sql(body,record_id)
        # Exactly one attempt, no retry on connection/COMMIT uncertainty.
        error=None
        ack=None
        try:
            ack=owner.psql(sql,owner.OWNER)
        except Exception as exc:
            error=exc
        try:
            final,row=_restricted_readback(body,record_id)
        except Exception:
            print('STOP_POSTCOMMIT_RECONCILIATION_UNKNOWN_NO_RETRY',file=sys.stderr)
            raise
        if final=='CONFLICT':stop('POSTCOMMIT_POLICY_CONFLICT')
        if error is not None or ack is None or ack[-2:]!=[
            'COMMIT','B02_G5_V5_OWNER_COMMIT_ACK'
        ]:
            print(json.dumps({'status':'COMMIT_ACK_UNCERTAIN_NO_RETRY',
                'independent_readback':final,'record_id':record_id,
                'record_hash':row['record_hash'] if row else None},sort_keys=True),
                file=sys.stderr)
            stop('COMMIT_ACK_UNCERTAIN_MANUAL_RECONCILIATION')
        if final!='PRESENT_EXACT':stop('COMMIT_NOT_PERSISTED')
        print(json.dumps({'status':'COMMITTED_POLICY_V2_RECONCILED',
              'policy_hash':POLICY_HASH,'record_id':record_id,
              'record_hash':row['record_hash'],'policy_role':'solveris_test',
              'readback_role':'solveris_b02_policy_writer',
              'institutional_decisions_created':0,'activations_created':0,
              'grants':0},sort_keys=True))


def execute(repo,body,a,*,rollback_probe=False):
    if not rollback_probe:
        return _execute_owner_policy_only(repo,body,a)
    from sqlalchemy import create_engine,text,MetaData,Table,select
    from sqlalchemy.pool import NullPool
    dsn=os.environ.get('SOLVERIS_B02_POLICY_WRITER_DSN')
    if not dsn:stop('DSN_REQUIRED')
    engine=create_engine(dsn,poolclass=NullPool)
    record_id=a['policy_version_record_id']
    if rollback_probe and record_id != 'B02-G5-V5-ROLLBACK-PROBE':
        stop('ROLLBACK_PROBE_IDENTITY')
    try:
        with engine.connect() as c:
            # Explicit outer transaction. Any exception rolls back.
            with c.begin():
                identity=tuple(c.execute(text('SELECT current_database(),session_user,current_user')).one())
                if identity!=('solveris_b02_r4g_test','solveris_b02_policy_writer','solveris_b02_policy_writer'):stop('DB_IDENTITY')
                rev=c.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one()
                if rev!='0063_adr020_policy_activation_atomicity':stop('REVISION')
                c.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:k,0))'),{'k':POLICY_ID+':2'})
                existing=c.execute(text('SELECT count(*) FROM public.policy_versions WHERE policy_id=:p AND policy_version=2'),{'p':POLICY_ID}).scalar_one()
                if existing:stop('ALREADY_PRESENT_RECONCILE')
                # PolicyVersion has no INSERT trigger; require the known PostgreSQL hash function.
                fn=c.execute(text("SELECT pg_get_functiondef('public.b02_json_hash(jsonb)'::regprocedure)")).scalar_one()
                if "public.b02_canonical_json(v)" not in fn or "'sha256'" not in fn:
                    stop('SERVER_HASH_CONTRACT')
                if not c.execute(text("SELECT has_table_privilege(current_user,'public.policy_versions','INSERT')")).scalar_one():stop('POLICY_INSERT_PRIVILEGE')
                cols={r['column_name']:(r['is_nullable'],r['column_default']) for r in c.execute(text("SELECT column_name,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' AND table_name='policy_versions'")).mappings()}
                for col in (*FIELDS,'policy_hash','policy_version_record_id','record_hash'):
                    if col not in cols:stop('SCHEMA_MISSING_'+col)
                table=Table('policy_versions',MetaData(),autoload_with=c,schema='public')
                # The physical record hash includes created_at. Calculate it on the
                # database using the same timestamp and JSONB values being inserted.
                created_at=c.execute(text('SELECT transaction_timestamp()')).scalar_one()
                payload=dict(body,policy_version_record_id=record_id,policy_hash=POLICY_HASH,created_at=created_at)
                # PostgreSQL formats timestamptz itself, matching to_jsonb(row)
                # and avoiding Python ISO timestamp serialization differences.
                material=dict(body,policy_version_record_id=record_id,policy_hash=POLICY_HASH)
                material_json=json.dumps(material,ensure_ascii=False,allow_nan=False)
                payload['record_hash']=c.execute(
                    text("""SELECT public.b02_json_hash(
                        CAST(:material AS jsonb) ||
                        jsonb_build_object('created_at', to_jsonb(CAST(:created_at AS timestamptz)))
                    )"""),
                    {'material':material_json,'created_at':created_at}
                ).scalar_one()
                if not HEX.fullmatch(payload['record_hash'] or ''):stop('SERVER_HASH_RESULT')
                result=c.execute(table.insert().values(**payload).returning(table.c.policy_version_record_id,table.c.policy_hash,table.c.record_hash)).mappings().one()
                if result['policy_version_record_id']!=record_id or result['policy_hash']!=POLICY_HASH or not HEX.fullmatch(result['record_hash'] or ''):stop('SERVER_RESULT')
                c.execute(text('SET CONSTRAINTS ALL IMMEDIATE'))
                # Verify the stored row inside the transaction, before COMMIT.
                stored=c.execute(text('SELECT * FROM public.policy_versions WHERE policy_version_record_id=:id'),{'id':record_id}).mappings().one()
                if stored['policy_hash']!=POLICY_HASH or not HEX.fullmatch(stored['record_hash'] or ''):stop('PRECOMMIT_ROW_MISMATCH')
                physical_hash=c.execute(text("SELECT public.b02_json_hash(to_jsonb(p)-'record_hash') FROM public.policy_versions p WHERE policy_version_record_id=:id"),{'id':record_id}).scalar_one()
                if stored['record_hash']!=physical_hash:stop('PRECOMMIT_PHYSICAL_HASH_MISMATCH')
                for field in FIELDS:
                    if stored[field]!=body[field]:stop('PRECOMMIT_FIELD_MISMATCH_'+field.upper())
                txid=c.execute(text('SELECT txid_current()')).scalar_one()
                # This is intentionally raised BEFORE the transaction context
                # exits. It forces SQLAlchemy to ROLLBACK the fully staged row.
                if rollback_probe:
                    raise _PolicyRollbackProbe()
            # COMMIT was acknowledged; independent connection reconciliation follows.
        status,stored=reconcile(engine,record_id)
        if status!='PRESENT_IDENTITY':stop('POSTCOMMIT_RECONCILIATION_'+status)
        for field in FIELDS:
            if stored[field]!=body[field]:stop('POSTCOMMIT_FIELD_MISMATCH_'+field.upper())
        with engine.connect() as check:
            actual=check.execute(text("SELECT public.b02_json_hash(to_jsonb(p)-'record_hash') FROM public.policy_versions p WHERE policy_version_record_id=:id"),{'id':record_id}).scalar_one()
            if stored['record_hash']!=actual:stop('POSTCOMMIT_PHYSICAL_HASH_MISMATCH')
        print(json.dumps({'status':'COMMITTED_RECONCILED','txid':txid,'record_id':record_id,'record_hash':stored['record_hash']},sort_keys=True))
    except _PolicyRollbackProbe:
        # Separate session after ROLLBACK; do not mistake transaction-local
        # INSERT/readback for durable persistence.
        status,stored=reconcile(engine,record_id)
        if status!='ABSENT':
            stop('ROLLBACK_POSTREAD_CONFLICT_'+status)
        print(json.dumps({'status':'PHYSICAL_POLICY_ROLLBACK_RECONCILED',
                          'policy_hash':POLICY_HASH,'record_id':record_id,
                          'writes_committed':0},sort_keys=True))
        return
    except Exception:
        # An uncertain network ACK must not be retried automatically.
        try:
            status,stored=reconcile(engine,record_id)
            print(json.dumps({'reconciliation':status,'record_id':record_id,'record_hash':stored['record_hash'] if stored else None},sort_keys=True),file=sys.stderr)
        except Exception:
            print('RECONCILIATION_UNKNOWN_STOP_NO_RETRY',file=sys.stderr)
        raise
    finally:engine.dispose()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repo',type=Path,default=Path.cwd())
    p.add_argument('--manifest',type=Path)
    p.add_argument('--approval-reference')
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--execute-policy-only',action='store_true')
    mode.add_argument('--probe-policy-rollback',action='store_true')
    a=p.parse_args()
    body=candidate(a.repo)
    if a.probe_policy_rollback:
        # No institutional event is generated; the DB row is rolled back.
        execute(a.repo,body,{'policy_version_record_id':'B02-G5-V5-ROLLBACK-PROBE'},
                rollback_probe=True)
        return
    if not a.execute_policy_only:
        print(json.dumps({'status':'DRY_RUN_PASS','policy_hash':POLICY_HASH,'version':2,'db_connected':False,'db_writes':0,'required_authorization':'POLICY_VERSION_ONLY'},sort_keys=True))
        return
    manifest=authorize(a.manifest,a.approval_reference)
    execute(a.repo,body,manifest)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(2)
