"""Prepared physical RED/acceptance suite. Inert collection; execution gated.
Only a NEW approved policy writer, isolated DB and real synthetic predecessors.
"""
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import pytest

DB='solveris_b02_r4g_test';ROLE='solveris_b02_policy_writer';CONTAINER='solveris-pg17-migration-test'
REV='0063_adr020_policy_activation_atomicity'
TABLES=('policy_activation_executions','policy_activations','policy_activation_generations','policy_activation_outbox_events')
PKS=dict(zip(TABLES,('policy_activation_execution_id','policy_activation_id','policy_activation_generation_id','policy_activation_outbox_event_id')))

def ident(s):
    assert isinstance(s,str) and re.fullmatch('[a-z_][a-z0-9_]*',s)
    return '"'+s+'"'
def literal(s):return "'"+str(s).replace("'","''")+"'"
def value(v):
    if v is None:return 'NULL'
    if type(v) is bool:return 'TRUE' if v else 'FALSE'
    if type(v) is int:return str(v)
    if isinstance(v,str):return literal(v)
    if isinstance(v,list):return 'jsonb_build_array('+','.join(value(x) for x in v)+')'
    assert isinstance(v,dict)
    if set(v)=={'$ref'}:
        t,c,key=v['$ref'];assert t in TABLES and c=='record_hash' and key.startswith('b02p-test-')
        return '(SELECT '+ident(c)+' FROM public.'+ident(t)+' WHERE '+ident(PKS[t])+'='+literal(key)+')'
    assert not any(k.startswith('$') for k in v)
    return 'jsonb_build_object('+','.join(literal(k)+','+value(x) for k,x in v.items())+')'
def render(c):
    assert len(c['rows'])<=8
    result=[]
    for row in c['rows']:
        assert set(row)=={'table','values'} and row['table'] in TABLES
        result.append('INSERT INTO public.'+ident(row['table'])+' ('+','.join(ident(k) for k in row['values'])+') VALUES ('+','.join(value(v) for v in row['values'].values())+');')
    return ''.join(result)
def sql(body,check=True):
    pre=r'''\set VERBOSITY verbose
SET statement_timeout='15s'; SET lock_timeout='5s';
DO $g$ BEGIN IF current_database()<>'solveris_b02_r4g_test' OR current_user<>'solveris_b02_policy_writer' OR session_user<>current_user THEN RAISE EXCEPTION 'POLICY_WRITER_IDENTITY_INVALID'; END IF; END $g$;
'''
    p=subprocess.run(['docker','exec','-i',CONTAINER,'psql','-X','-q','-A','-t','--no-password','-v','ON_ERROR_STOP=1','-U',ROLE,'-d',DB],input=(pre+body).encode(),capture_output=True,timeout=40)
    out=p.stdout.decode('utf-8',errors='backslashreplace').strip();err=p.stderr.decode('utf-8',errors='backslashreplace')
    if check:assert p.returncode==0,err
    return p.returncode,out,err
def scalar(query):return sql('BEGIN READ ONLY;'+query+';ROLLBACK;')[1]
def counts():return {t:int(scalar('SELECT count(*) FROM public.'+ident(t))) for t in TABLES}
def row(c,index):return c['rows'][index]['values']
def reject(c,states=('23503','23514','P0001'),suffix='COMMIT;',code=None):
    before=counts();rc,_,err=sql('BEGIN;'+render(c)+suffix,False)
    assert rc!=0 and any(re.search(r'\b'+s+r'\b',err) for s in states),err
    assert not re.search(r'\b(?:42P01|42703|42883|42601|42501)\b',err),'Missing schema/privilege is not a semantic rejection: '+err
    if code:assert code in err,err
    assert counts()==before

@pytest.fixture(scope='session',autouse=True)
def physical_gate():
    assert os.environ.get('B02_POLICY_ATOMICITY_PHYSICAL_AUTH')=='AFTER_APPROVED_0063','Physical execution not authorised'
    assert scalar('SELECT version_num FROM public.alembic_version')==REV
    assert scalar("SELECT rolsuper::text||'|'||rolcreatedb::text||'|'||rolcreaterole::text||'|'||rolreplication::text||'|'||rolbypassrls::text||'|'||rolinherit::text FROM pg_roles WHERE rolname=current_user")=='false|false|false|false|false|false'
    assert scalar('SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)')=='0'
@pytest.fixture(scope='session')
def fixtures():
    path=os.environ.get('B02_POLICY_FIXTURE');h=os.environ.get('B02_POLICY_FIXTURE_SHA256','')
    assert path and re.fullmatch('[0-9a-f]{64}',h)
    raw=Path(path).read_bytes();assert hashlib.sha256(raw).hexdigest()==h
    d=json.loads(raw);assert d['schema']=='B02_POLICY_ATOMICITY_PHYSICAL_V1' and d['synthetic_only'] is True and d['database']==DB
    assert d['context_origin']=='ISOLATED_DB_EXACT_EXPORT'
    for c in d['cases'].values():
        assert len(c['rows'])==4 and tuple(r['table'] for r in c['rows'])==TABLES
        for r in c['rows']:assert r['values']['provenance']['synthetic_only'] is True
        render(c)
    return d
def case(fixtures,name='main'):return copy.deepcopy(fixtures['cases'][name])

def test_01_valid_complete_unit_rolls_back(fixtures):
    c=case(fixtures);before=counts();rc,_,err=sql('BEGIN;'+render(c)+'SET CONSTRAINTS ALL IMMEDIATE;ROLLBACK;',False)
    assert rc==0,err
    assert counts()==before
@pytest.mark.parametrize('missing',range(4))
def test_02_missing_member_rejected_at_commit(fixtures,missing):
    c=case(fixtures);del c['rows'][missing];reject(c)
@pytest.mark.parametrize('member',range(4))
def test_03_wrong_record_hash_rejected(fixtures,member):
    c=case(fixtures);row(c,member)['record_hash']='0'*64;reject(c,code='B02P_RECORD_HASH_DIVERGENCE')
@pytest.mark.parametrize('member,field',[(1,'policy_activation_execution_record_hash'),(2,'policy_activation_record_hash'),(3,'policy_activation_generation_hash')])
def test_04_divergent_predecessor_rejected(fixtures,member,field):
    c=case(fixtures);row(c,member)[field]='0'*64;reject(c)
@pytest.mark.parametrize('member',range(4))
def test_05_duplicate_member_rejected(fixtures,member):
    c=case(fixtures);c['rows'].insert(member+1,copy.deepcopy(c['rows'][member]));reject(c,states=('23505',))
def test_06_partial_execution_cannot_activate(fixtures):
    c=case(fixtures);row(c,0)['state']='pendente';reject(c)
def test_07_generation_must_be_complete(fixtures):
    c=case(fixtures);row(c,2)['is_complete']=False;reject(c)
def test_08_outbox_payload_and_hash_not_self_declared(fixtures):
    c=case(fixtures);row(c,3)['payload']={'forged':True};reject(c,code='B02P_OUTBOX_PAYLOAD_DIVERGENCE')
    c=case(fixtures);row(c,3)['payload_hash']='0'*64;reject(c,code='B02P_OUTBOX_PAYLOAD_HASH_DIVERGENCE')
@pytest.mark.parametrize('member',range(4))
def test_09_client_cannot_choose_transaction_id(fixtures,member):
    c=case(fixtures);row(c,member)['b02_policy_txid' if member<2 else 'assigned_txid']='1';reject(c,code='B02P_SERVER_TXID_ONLY')
@pytest.mark.parametrize('stop_after',range(1,5))
def test_10_failure_at_every_point_rolls_back(fixtures,stop_after):
    c=case(fixtures);c['rows']=c['rows'][:stop_after];before=counts()
    rc,_,err=sql('BEGIN;'+render(c)+"DO $f$ BEGIN RAISE EXCEPTION 'B02P_INJECTED_FAILURE'; END $f$;COMMIT;",False)
    assert rc!=0 and 'B02P_INJECTED_FAILURE' in err,err
    assert counts()==before

def test_11_relational_generation_link_is_deferred_and_exact():
    assert int(scalar("SELECT count(*) FROM pg_constraint WHERE conname='fk_b02p_activation_generation' AND conrelid='public.policy_activations'::regclass AND confrelid='public.policy_activation_generations'::regclass AND condeferrable AND condeferred AND cardinality(conkey)=3"))==1
    for table in TABLES[2:]:
        assert int(scalar("SELECT count(*) FROM pg_constraint WHERE conrelid='public."+table+"'::regclass AND contype='f' AND cardinality(conkey)>=2"))>=2

def test_12_writer_has_no_authority_mutation_or_normative_write():
    for table in TABLES:
        assert scalar("SELECT has_table_privilege(current_user,'public."+table+"','UPDATE,DELETE,TRUNCATE,TRIGGER')::text")=='false'
    for table in ('policy_versions','policy_decisions','bootstrap_authority_records','activation_generations','outbox_event_records','normative_activations'):
        assert scalar("SELECT has_table_privilege(current_user,'public."+table+"','INSERT,UPDATE,DELETE,TRUNCATE')::text")=='false'
    for statement in ('ALTER TABLE public.policy_activation_generations DISABLE TRIGGER ALL',"SET session_replication_role='replica'",'SET ROLE solveris_test'):
        rc,_,err=sql('BEGIN;'+statement+';ROLLBACK;',False);assert rc!=0 and '42501' in err

def test_13_concurrent_same_unit_has_one_committed_result(fixtures):
    assert os.environ.get('B02_POLICY_ALLOW_SYNTHETIC_COMMIT')=='YES','Separate synthetic commit gate required'
    c=case(fixtures,'concurrent');eid=row(c,0)['policy_activation_execution_id']
    assert scalar('SELECT count(*) FROM policy_activation_executions WHERE policy_activation_execution_id='+literal(eid))=='0','One-use fixture consumed: do not delete or rerun'
    script='BEGIN;'+render(c)+'COMMIT;'
    with ThreadPoolExecutor(max_workers=2) as pool:r=list(pool.map(lambda _:sql(script,False),range(2)))
    assert sum(rc==0 for rc,_,_ in r)==1,r
    assert '23505' in next(err for rc,_,err in r if rc!=0),r
    assert scalar('SELECT count(*) FROM policy_activation_outbox_events WHERE policy_activation_execution_id='+literal(eid))=='1'
    sql('BEGIN READ ONLY;SELECT b02p_require_complete('+literal(eid)+',false);ROLLBACK;')

@pytest.fixture
def api_connection():
    assert os.environ.get('ALEMBIC_RUNNING')=='1' and os.environ.get('DATABASE_URL')=='sqlite:///:memory:','Host metadata import must not inherit a remote URL'
    password=os.environ.get('B02_POLICY_WRITER_PASSWORD');assert password,'Restricted-role TCP credential required for writer API proof; never log it'
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool
    engine=create_engine('postgresql+psycopg2://'+ROLE+'@127.0.0.1:55432/'+DB,connect_args={'password':password,'connect_timeout':5},poolclass=NullPool,hide_parameters=True)
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            assert tuple(conn.execute(text('SELECT current_database(),session_user,current_user')).one())==(DB,ROLE,ROLE)
            conn.rollback()
            yield conn
    finally:engine.dispose()

def test_14_writer_api_owns_no_commit_and_rolls_back(fixtures,api_connection):
    from app.services.enterprise_b02_policy_activation_atomicity import stage_policy_activation
    before=counts();tx=api_connection.begin()
    try:
        result=stage_policy_activation(api_connection,**case(fixtures)['request'])
        assert result['reused'] is False and tx.is_active
    finally:tx.rollback()
    assert counts()==before

def test_15_exact_api_redelivery_reuses_committed_unit(fixtures,api_connection):
    from app.services.enterprise_b02_policy_activation_atomicity import stage_policy_activation,PolicyAtomicityError
    before=counts();request=case(fixtures,'concurrent')['request'];tx=api_connection.begin()
    try:
        result=stage_policy_activation(api_connection,**request);assert result['reused'] is True
        request['provenance']['tampered']=True
        with pytest.raises(PolicyAtomicityError) as err:stage_policy_activation(api_connection,**request)
        assert err.value.code=='IDEMPOTENT_EVIDENCE_CONFLICT'
    finally:tx.rollback()
    assert counts()==before

def test_16_new_append_only_triggers_are_active():
    for table in TABLES[2:]:
        assert int(scalar("SELECT count(*) FROM pg_trigger WHERE tgrelid='public."+table+"'::regclass AND NOT tgisinternal AND tgenabled='O' AND ((tgtype & 8)<>0 OR (tgtype & 16)<>0 OR (tgtype & 32)<>0)"))>=2
