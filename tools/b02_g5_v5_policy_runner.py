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
    if not path or not reference:stop('EXPLICIT_AUTHORIZATION_REQUIRED')
    a=json.loads(path.read_text(encoding='utf-8'))
    expected={'status':'AUTHORIZED','scope':'POLICY_VERSION_ONLY','database':'solveris_b02_r4g_test',
              'writer':'solveris_b02_policy_writer','policy_id':POLICY_ID,'policy_version':2,
              'policy_hash':POLICY_HASH,'file_sha256':FILE_HASH,'reference':reference}
    for k,v in expected.items():
        if a.get(k)!=v:stop('AUTHORIZATION_'+k.upper())
    for k in ('authority_actor','authority_evidence','validity_evidence','key_custody_evidence','schema_hash_evidence'):
        if not a.get(k):stop('AUTHORIZATION_MISSING_'+k.upper())
    if a.get('server_record_hash_contract_verified') is not True:stop('SERVER_HASH_CONTRACT_ATTESTATION')
    record_id=a.get('policy_version_record_id')
    if not isinstance(record_id,str) or not record_id or len(record_id)>64:stop('RECORD_ID')
    return a

def reconcile(engine,record_id):
    from sqlalchemy import text
    with engine.connect() as c:
        c.exec_driver_sql('SET TRANSACTION READ ONLY')
        row=c.execute(text('SELECT * FROM public.policy_versions WHERE policy_id=:p AND policy_version=2'),{'p':POLICY_ID}).mappings().one_or_none()
        c.rollback()
    if row is None:return 'ABSENT',None
    data=dict(row)
    if (data['policy_version_record_id']!=record_id or data['policy_hash']!=POLICY_HASH
        or data['policy_type']!='activation_authority' or not HEX.fullmatch(data['record_hash'] or '')):return 'CONFLICT',data
    # The policy must match every field, not merely its identifying hash.
    return 'PRESENT_EXACT',data

def execute(repo,body,a):
    from sqlalchemy import create_engine,text,MetaData,Table,select
    from sqlalchemy.pool import NullPool
    dsn=os.environ.get('SOLVERIS_B02_POLICY_WRITER_DSN')
    if not dsn:stop('DSN_REQUIRED')
    engine=create_engine(dsn,poolclass=NullPool)
    record_id=a['policy_version_record_id']
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
            # COMMIT was acknowledged; independent connection reconciliation follows.
        status,stored=reconcile(engine,record_id)
        if status!='PRESENT_EXACT':stop('POSTCOMMIT_RECONCILIATION_'+status)
        for field in FIELDS:
            if stored[field]!=body[field]:stop('POSTCOMMIT_FIELD_MISMATCH_'+field.upper())
        print(json.dumps({'status':'COMMITTED_RECONCILED','txid':txid,'row':stored},sort_keys=True))
    except Exception:
        # An uncertain network ACK must not be retried automatically.
        try:
            status,stored=reconcile(engine,record_id)
            print(json.dumps({'reconciliation':status,'row':stored},sort_keys=True),file=sys.stderr)
        except Exception:
            print('RECONCILIATION_UNKNOWN_STOP_NO_RETRY',file=sys.stderr)
        raise
    finally:engine.dispose()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repo',type=Path,default=Path.cwd())
    p.add_argument('--manifest',type=Path)
    p.add_argument('--approval-reference')
    p.add_argument('--execute-policy-only',action='store_true')
    a=p.parse_args()
    body=candidate(a.repo)
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
