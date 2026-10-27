"""Frozen PostgreSQL acceptance contracts, 02-R4G.

Collection is inert. Actual execution requires approved 0062, a hash-pinned
synthetic fixture manifest, and explicit synthetic-commit permission for T11.
No administrative identity, schema installation or production data is used.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import pytest

CONTAINER = 'solveris-pg17-migration-test'
DATABASE = 'solveris_b02_r4g_test'
WRITER = 'solveris_b02_writer'
REVISION = '0062_adr020_noncredential_acquisition'
TABLES = (
    'artifact_references', 'acquisition_executions', 'normative_artifacts',
    'artifact_verification_records', 'acquisition_mode_bindings',
    'noncredential_acquisition_receipts', 'noncredential_sanitization_verifications',
)
NEW = TABLES[-3:]
ALLOWED_STAGES = {'reference', 'planning', 'binding', 'start', 'receipt',
                  'verification', 'terminal', 'artifact'}
STAGE_TABLE = {
    'reference':'artifact_references', 'planning':'acquisition_executions',
    'binding':NEW[0], 'start':'acquisition_executions', 'receipt':NEW[1],
    'verification':NEW[2], 'terminal':'acquisition_executions',
    'artifact':'normative_artifacts',
}


def ident(value):
    assert isinstance(value,str) and re.fullmatch(r'[a-z_][a-z0-9_]*',value)
    return '"'+value+'"'


def literal(value):
    return "'"+str(value).replace("'","''")+"'"


def value_sql(value):
    if value is None:return 'NULL'
    if type(value) is bool:return 'TRUE' if value else 'FALSE'
    if type(value) is int:return str(value)
    if isinstance(value,str):return literal(value)
    if isinstance(value,list):
        return 'jsonb_build_array('+','.join(value_sql(x) for x in value)+')'
    assert isinstance(value,dict), 'non-canonical value in fixture'
    if set(value)=={'$bytea_hex'}:
        raw=value['$bytea_hex']
        assert isinstance(raw,str) and re.fullmatch(r'(?:[0-9a-f]{2})*',raw)
        return 'decode('+literal(raw)+",'hex')"
    if set(value)=={'$ref'}:
        r=value['$ref']
        assert set(r)=={'table','column','key','id'} and r['table'] in TABLES
        assert isinstance(r['id'],str) and r['id'].startswith('b02test-')
        return '(SELECT '+ident(r['column'])+' FROM public.'+ident(r['table'])+' WHERE '+ident(r['key'])+'='+literal(r['id'])+')'
    if set(value)=={'$txid'}:
        assert value['$txid'] is True
        return 'pg_current_xact_id()'
    assert not any(k.startswith('$') for k in value), 'unknown fixture expression'
    return 'jsonb_build_object('+','.join(literal(k)+','+value_sql(v) for k,v in value.items())+')'


def insert_sql(row):
    assert set(row)=={'stage','table','values'}
    assert row['stage'] in ALLOWED_STAGES and row['table']==STAGE_TABLE[row['stage']]
    assert isinstance(row['values'],dict) and row['values']
    return 'INSERT INTO public.'+ident(row['table'])+' ('+','.join(ident(k) for k in row['values'])+') VALUES ('+','.join(value_sql(v) for v in row['values'].values())+');'


def rendered(case):return '\n'.join(insert_sql(r) for r in case['rows'])


def psql(script, *, check=True):
    # All actual SQL in this file uses this single, constant writer connection.
    prefix=r"""\set VERBOSITY verbose
SET lock_timeout='4s';
SET statement_timeout='15s';
DO $identity$ BEGIN
 IF current_database()<>'solveris_b02_r4g_test'
    OR current_user<>'solveris_b02_writer'
    OR session_user<>'solveris_b02_writer'
 THEN RAISE EXCEPTION 'WRONG_TEST_IDENTITY'; END IF;
END $identity$;
"""
    p=subprocess.run(['docker','exec','-i',CONTAINER,'psql','-X','-q','-A','-t',
                      '--no-password','-v','ON_ERROR_STOP=1','-U',WRITER,'-d',DATABASE],
                     input=(prefix+script).encode('utf-8'),capture_output=True,timeout=30)
    out=p.stdout.decode('utf-8',errors='backslashreplace').strip()
    err=p.stderr.decode('utf-8',errors='backslashreplace')
    if check:assert p.returncode==0, err
    return p.returncode,out,err


def scalar(query):return psql('BEGIN READ ONLY;'+query+';ROLLBACK;')[1]


def counts():
    return {t:int(scalar('SELECT count(*) FROM public.'+ident(t))) for t in TABLES}


def case(data, name='cas'):
    return copy.deepcopy(data['cases'][name])


def stage(c,name):
    rows=[r for r in c['rows'] if r['stage']==name]
    assert len(rows)==1, 'fixture must have exactly one '+name
    return rows[0]['values']


def rejected(c, states=('23503','23514','P0001'), *, suffix='ROLLBACK;', code=None):
    before=counts()
    rc,_,error=psql('BEGIN;'+rendered(c)+suffix,check=False)
    assert rc!=0, 'invalid evidence was accepted'
    assert any(re.search(r'\b'+s+r'\b',error) for s in states), error
    assert not re.search(r'\b(?:42703|42P01|42601|42883)\b',error), 'schema/syntax failure is not an admissible rejection: '+error
    if code is not None:assert code in error, 'wrong rejection gate: '+error
    assert counts()==before, 'rejected unit left partial rows'
    return error


def valid_rollback(c):
    before=counts()
    rc,out,error=psql('BEGIN;'+rendered(c)+"SET CONSTRAINTS ALL IMMEDIATE;SELECT 'VALID_SYNTHETIC_UNIT';ROLLBACK;",check=False)
    assert rc==0,error
    assert out=='VALID_SYNTHETIC_UNIT'
    assert counts()==before


@pytest.fixture(scope='session',autouse=True)
def physical_gate():
    assert os.environ.get('SOLVERIS_B02_R4G_PHYSICAL_STAGE')=='AFTER_APPROVED_0062', 'Execution blocked until separate 0062 application approval'
    assert scalar('SELECT version_num FROM public.alembic_version')==REVISION
    assert scalar("SELECT rolsuper::text||'|'||rolcreatedb::text||'|'||rolcreaterole::text||'|'||rolreplication::text||'|'||rolbypassrls::text FROM pg_roles WHERE rolname=current_user")=='false|false|false|false|false'


@pytest.fixture(scope='session')
def data():
    name=os.environ.get('SOLVERIS_B02_R4G_SYNTHETIC_FIXTURE','')
    expected=os.environ.get('SOLVERIS_B02_R4G_SYNTHETIC_FIXTURE_SHA256','')
    assert name and re.fullmatch('[0-9a-f]{64}',expected), 'A separately reviewed, hash-pinned synthetic fixture is required'
    raw=Path(name).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==expected
    d=json.loads(raw)
    assert d['schema']=='SOLVERIS_B02_R4G_PHYSICAL_FIXTURES_V1'
    assert d['synthetic_only'] is True and d['database']==DATABASE
    assert set(d['cases'])=={'cas','public','concurrent','credentialled_without_chain'}
    assert d['policy_fixture_origin']=='PREPARED_IN_ISOLATED_DATABASE_NOT_INSTITUTIONAL_AUTHORITY'
    for name,c in d['cases'].items():
        assert isinstance(c['case_id'],str) and c['case_id'].startswith('b02test-')
        assert c['rows'] and all(r['stage'] in ALLOWED_STAGES for r in c['rows'])
        if name!='credentialled_without_chain':
            for s in ('planning','binding','start','receipt','verification','terminal','artifact'):stage(c,s)
            order=[r['stage'] for r in c['rows']]
            assert order.index('planning')<order.index('binding')<order.index('start')<order.index('receipt')<order.index('verification')<order.index('terminal')<order.index('artifact')
            artifact=stage(c,'artifact')
            assert set(artifact['immutable_bytes'])=={'$bytea_hex'}
            assert bytes.fromhex(artifact['immutable_bytes']['$bytea_hex']).startswith(b'%PDF-SYNTHETIC-B02')
            assert artifact['provenance']['synthetic_only'] is True
        for row in c['rows']:
            if row['table'] in NEW:
                assert 'record_hash' not in row['values'], 'positive new rows use server-computed hashes'
                if row['stage']=='receipt':assert 'receipt_hash' not in row['values']
            insert_sql(row)
    return d


def test_01_exact_relational_predecessors_are_physical():
    for table,parent in ((NEW[0],'acquisition_executions'),(NEW[1],NEW[0]),(NEW[1],'acquisition_executions'),(NEW[2],NEW[1])):
        n=scalar("SELECT count(*) FROM pg_constraint c WHERE c.contype='f' AND c.conrelid='public."+table+"'::regclass AND c.confrelid='public."+parent+"'::regclass AND cardinality(c.conkey)>=2")
        assert int(n)>=1,(table,parent)


def test_02_synthetic_cas_complete_unit_with_rollback(data):valid_rollback(case(data))


def test_03_synthetic_public_complete_unit_with_rollback(data):valid_rollback(case(data,'public'))


def test_04_missing_predecessors_fail_closed(data):
    for missing in ('planning','binding','start','receipt','verification'):
        c=case(data);c['rows']=[r for r in c['rows'] if r['stage']!=missing]
        rejected(c)


def test_05_fake_credential_binding_cannot_enter_public_mode(data):
    c=case(data,'public');stage(c,'receipt')['transport_manifest']['credential_binding_id']='b02test-fictitious-credential'
    rejected(c,states=('23514','P0001'),code='NONCREDENTIAL_CREDENTIAL_FIELDS_FORBIDDEN')


def test_06_existing_credentialled_mode_cannot_use_noncredential_receipt(data):
    c=case(data);stage(c,'binding')['mode']='EXTERNAL_CREDENTIALLED'
    rejected(c,code='CREDENTIALLED_REQUIRES_ORIGINAL_CHAIN')
    rejected(case(data,'credentialled_without_chain'))


def test_07_cas_cannot_claim_new_external_transport(data):
    c=case(data);stage(c,'receipt')['transport_manifest']={'dispatched':True,'response_observed':True}
    rejected(c,code='CAS_EXTERNAL_TRANSPORT_FORBIDDEN')


def test_08_public_transport_cannot_present_credentials(data):
    for category in ('authorization','cookie','query_token','proxy_authorization','client_certificate','credentialled_redirect'):
        c=case(data,'public');stage(c,'receipt')['transport_manifest'].update(credential_presentation_observed=True,credential_categories=[category])
        rejected(c,code='PUBLIC_CREDENTIAL_PRESENTATION_FORBIDDEN')


def test_09_unknown_or_missing_mode_is_not_inferred(data):
    for mode in ('UNKNOWN','',None):
        c=case(data);stage(c,'binding')['mode']=mode
        rejected(c,states=('23502','23514','P0001'))


def test_10_same_id_divergent_evidence_is_rejected(data):
    c=case(data);rows=c['rows'];index=next(i for i,r in enumerate(rows) if r['stage']=='receipt')
    duplicate=copy.deepcopy(rows[index]);duplicate['values']['receipt_hash']='0'*64
    rows.insert(index+1,duplicate)
    rejected(c,states=('23505','23514','P0001'))


def test_11_concurrent_completion_has_one_exact_result(data):
    assert os.environ.get('SOLVERIS_B02_R4G_ALLOW_SYNTHETIC_COMMIT')=='YES', 'Separate synthetic-commit gate required; not a real documentary write'
    c=case(data,'concurrent');aid=stage(c,'artifact')['normative_artifact_id']
    assert scalar('SELECT count(*) FROM public.normative_artifacts WHERE normative_artifact_id='+literal(aid))=='0', 'Concurrent fixture was already consumed; do not delete append-only history'
    script='BEGIN;'+rendered(c)+'COMMIT;'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:psql(script,check=False),range(2)))
    assert sum(rc==0 for rc,_,_ in results)==1, results
    loser=next(err for rc,_,err in results if rc!=0)
    assert re.search(r'\b23505\b',loser),loser
    assert scalar('SELECT count(*) FROM public.normative_artifacts WHERE normative_artifact_id='+literal(aid))=='1'
    assert scalar('SELECT count(*) FROM public.acquisition_executions WHERE acquisition_execution_id='+literal(stage(c,'terminal')['acquisition_execution_id'])+" AND projected_state='concluida'")=='1'


def test_12_every_failure_point_rolls_back_the_completion_unit(data):
    c=case(data)
    for stop_at in ('receipt','verification','terminal','artifact'):
        before=counts();prefix=[]
        for row in c['rows']:
            prefix.append(insert_sql(row))
            if row['stage']==stop_at:break
        rc,_,err=psql('BEGIN;'+'\n'.join(prefix)+"DO $fault$ BEGIN RAISE EXCEPTION 'B02_INJECTED_FAILURE' USING ERRCODE='P0001'; END $fault$;COMMIT;",check=False)
        assert rc!=0 and 'B02_INJECTED_FAILURE' in err,err
        assert counts()==before


def test_13_receipt_precommitted_cannot_complete_acquisition(data):
    c=case(data);c['rows']=[r for r in c['rows'] if r['stage'] not in ('terminal','artifact')]
    rejected(c,suffix='COMMIT;')


def test_14_append_only_and_privilege_guards_remain_active():
    for table in NEW:
        n=int(scalar("SELECT count(*) FROM pg_trigger WHERE tgrelid='public."+table+"'::regclass AND NOT tgisinternal AND tgenabled='O' AND ((tgtype & 8) <> 0 OR (tgtype & 16) <> 0 OR (tgtype & 32) <> 0)"))
        assert n>=2,table
        assert scalar("SELECT has_table_privilege(current_user,'public."+table+"','UPDATE,DELETE,TRUNCATE,TRIGGER')::text")=='false'


def test_15_writer_cannot_disable_triggers_or_become_admin():
    for statement in ('ALTER TABLE public.acquisition_executions DISABLE TRIGGER ALL',"SET session_replication_role='replica'",'SET ROLE solveris_test'):
        rc,_,err=psql('BEGIN;'+statement+';ROLLBACK;',check=False)
        assert rc!=0 and re.search(r'\b42501\b',err),err


def test_16_origin_and_content_identity_divergence_is_rejected(data):
    c=case(data);stage(c,'receipt')['source_identity_binding']['source_id']='urn:solveris:synthetic:wrong-origin'
    rejected(c)


def test_17_byte_tampering_is_rejected(data):
    c=case(data);a=stage(c,'artifact');a['immutable_bytes']['$bytea_hex']+='00'
    rejected(c)


def test_18_receipt_of_another_execution_or_attempt_is_rejected(data):
    for field,value in (('acquisition_execution_id','b02test-other-execution'),('attempt_number',2)):
        c=case(data);stage(c,'receipt')[field]=value
        rejected(c)


def test_19_extraction_trigger_resolves_acquisition_through_exact_artifact():
    before=int(scalar('SELECT count(*) FROM public.extraction_runs'))
    sql="""INSERT INTO public.extraction_runs (
extraction_run_record_id,extraction_run_id,normative_artifact_id,artifact_hash,
extractor_id,extractor_version,parameters_hash,attempt_number,run_event,
projected_state,event_sequence,evidence,provenance,record_hash)
VALUES ('b02test-extract-record','b02test-extract-run','b02test-missing-artifact',
repeat('a',64),'SYNTHETIC_B02_G1','1',repeat('b',64),1,'criacao','pendente',1,
'{"synthetic_only":true}'::jsonb,'{"synthetic_only":true}'::jsonb,repeat('c',64));"""
    rc,_,err=psql('BEGIN;'+sql+'ROLLBACK;',check=False)
    assert rc!=0 and re.search(r'\b(?:23503|P0001)\b',err),err
    assert not re.search(r'\b42703\b',err),'Original missing-column defect remains: '+err
    assert int(scalar('SELECT count(*) FROM public.extraction_runs'))==before


def test_20_sanitization_never_substitutes_artifact_authenticity(data):
    c=case(data);artifact=stage(c,'artifact');before=int(scalar('SELECT count(*) FROM public.extraction_runs'))
    eid='b02test-no-auth-extract';sql="""INSERT INTO public.extraction_runs (
extraction_run_record_id,extraction_run_id,normative_artifact_id,artifact_hash,
extractor_id,extractor_version,parameters_hash,attempt_number,run_event,
projected_state,event_sequence,evidence,provenance,record_hash) VALUES ("""+','.join([
        literal(eid),literal(eid),literal(artifact['normative_artifact_id']),literal(artifact['artifact_hash']),
        "'SYNTHETIC_B02'","'1'",literal('d'*64),'1',"'criacao'","'pendente'",'1',"'{}'::jsonb","'{\"synthetic_only\":true}'::jsonb",literal('e'*64)])+');'
    # Exercise append-only INSERT transition, not forbidden UPDATE privileges.
    transition="INSERT INTO public.extraction_runs (extraction_run_record_id,extraction_run_id,normative_artifact_id,artifact_hash,extractor_id,extractor_version,parameters_hash,attempt_number,run_event,projected_state,event_sequence,previous_extraction_run_record_id,started_at,evidence,provenance,record_hash) VALUES ("+','.join([
        literal(eid+'-2'),literal(eid),literal(artifact['normative_artifact_id']),literal(artifact['artifact_hash']),
        "'SYNTHETIC_B02'","'1'",literal('d'*64),'1',"'inicio'","'em_processamento'",'2',literal(eid),
        'now()',"'{}'::jsonb","'{\"synthetic_only\":true}'::jsonb",literal('f'*64)])+');'
    rc,_,err=psql('BEGIN;'+rendered(c)+sql+transition+'COMMIT;',check=False)
    assert rc!=0 and re.search(r'\b(?:23503|23514|P0001)\b',err),err
    assert int(scalar('SELECT count(*) FROM public.extraction_runs'))==before


def test_21_policy_activation_missing_or_divergent_fails_closed(data):
    for kind in ('security_policy_binding','sanitization_policy_binding'):
        c=case(data);stage(c,'receipt')[kind]['policy_activation_id']='b02test-missing-activation'
        stage(c,'receipt')[kind]['policy_activation_record_hash']='0'*64
        rejected(c)


def test_22_hash_divergence_cannot_be_relabelled_as_idempotence(data):
    c=case(data);stage(c,'verification')['record_hash']='0'*64
    rejected(c)


def test_23_forged_or_incomplete_verification_is_not_favourable(data):
    for outcome in ('inconclusive','verified_violation'):
        c=case(data);stage(c,'verification')['verification_outcome']=outcome
        rejected(c)
    c=case(data);stage(c,'verification')['inspected_component_manifest']={'complete':False}
    rejected(c)


def test_24_fresh_session_compares_actual_physical_artifact_bytes(data):
    c=case(data);a=stage(c,'artifact');raw=bytes.fromhex(a['immutable_bytes']['$bytea_hex'])
    assert hashlib.sha256(raw).hexdigest()==a['artifact_hash']
    # The concurrency fixture intentionally persists one synthetic unit, and only
    # that case may be inspected across sessions after a real synthetic commit.
    aid=stage(case(data,'concurrent'),'artifact')['normative_artifact_id']
    sql='SELECT artifact_hash||\'|\'||encode(digest(immutable_bytes,\'sha256\'),\'hex\')||\'|\'||byte_size::text||\'|\'||octet_length(immutable_bytes)::text FROM public.normative_artifacts WHERE normative_artifact_id='+literal(aid)
    row=scalar(sql)
    assert row, 'The separately gated concurrent synthetic-commit case must have run first'
    h,physical,n,physical_n=row.split('|')
    assert h==physical and n==physical_n


def test_25_identical_bytes_do_not_collapse_different_provenance(data):
    c=case(data);other=case(data,'public')
    assert stage(c,'artifact')['artifact_hash']==stage(other,'artifact')['artifact_hash']
    assert stage(c,'artifact')['normative_artifact_id']!=stage(other,'artifact')['normative_artifact_id']
    assert stage(c,'artifact')['provenance']!=stage(other,'artifact')['provenance']
    before=counts()
    rc,_,err=psql('BEGIN;'+rendered(c)+rendered(other)+'SET CONSTRAINTS ALL IMMEDIATE;ROLLBACK;',check=False)
    assert rc==0,err
    assert counts()==before


def test_26_documentary_success_does_not_activate_or_charge(data):
    protected=('normative_activations','activation_generations','rule_versions','outbox_event_records')
    # No INSERT privilege is granted on authority tables to this writer.
    for t in protected:
        assert scalar("SELECT has_table_privilege(current_user,'public."+t+"','INSERT,UPDATE,DELETE')::text")=='false'
    valid_rollback(case(data))
    assert scalar("SELECT has_table_privilege(current_user,'public.pagamentos','INSERT,UPDATE,DELETE')::text")=='false'


def test_27_terminal_without_receipt_or_artifact_cannot_commit(data):
    for missing in ('receipt','artifact'):
        c=case(data);c['rows']=[r for r in c['rows'] if r['stage']!=missing]
        rejected(c,suffix='COMMIT;')


def test_28_database_guard_and_exact_revision():
    assert scalar("SELECT current_database()||'|'||session_user||'|'||current_user")==DATABASE+'|'+WRITER+'|'+WRITER
    assert scalar('SELECT version_num FROM public.alembic_version')==REVISION
    assert scalar("SELECT has_database_privilege(current_user,current_database(),'CREATE')::text||'|'||has_schema_privilege(current_user,'public','CREATE')::text")=='false|false'
