"""Policy-only four-record writer candidate. No authority creation or commit.
Only the caller may commit/roll back the outer transaction. No network, bootstrap,
policy/decision creation, migrations, delivery worker or normative activation.
"""
from __future__ import annotations
from datetime import datetime, timezone
from types import SimpleNamespace
from app.services.enterprise_b02_noncredential_acquisition import canonical_bytes, record_hash

DATABASE='solveris_b02_r4g_test'
WRITER='solveris_b02_policy_writer'
SCHEMA='ADR020_POLICY_ACTIVATION_UNIT_V1'

class PolicyAtomicityError(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)

def fail(code):raise PolicyAtomicityError(code)

def reject_server_fields(value):
    if not isinstance(value,dict):fail('REQUEST_OBJECT_REQUIRED')
    if {'record_hash','assigned_txid','b02_policy_txid','payload_hash'} & set(value):fail('SERVER_FIELDS_FORBIDDEN')

def _plain(value):
    if isinstance(value,datetime):
        if value.tzinfo is None:fail('TIMEZONE_REQUIRED')
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value,dict):return {k:_plain(v) for k,v in value.items()}
    if isinstance(value,list):return [_plain(v) for v in value]
    return value

def assert_same_request(expected,actual):
    if canonical_bytes(_plain(expected))!=canonical_bytes(_plain(actual)):fail('IDEMPOTENT_EVIDENCE_CONFLICT')

def _timestamp(value):
    if isinstance(value,str):
        try:value=datetime.fromisoformat(value.replace('Z','+00:00'))
        except ValueError:fail('TIMESTAMP_INVALID')
    if not isinstance(value,datetime) or value.tzinfo is None:fail('TIMEZONE_REQUIRED')
    return value.astimezone(timezone.utc)

def _bind(data,key,value):
    if key in data and data[key]!=value:fail('EXACT_PREDECESSOR_DIVERGENCE')
    data[key]=value

def _complete(table,data):
    unknown=set(data)-set(table.c.keys())
    if unknown:fail('UNKNOWN_REQUEST_FIELD')
    data=dict(data)
    for c in table.c:
        if c.name in ('record_hash','b02_policy_txid'):continue
        if c.name not in data:
            if c.nullable:data[c.name]=None
            else:fail('REQUIRED_REQUEST_FIELD_MISSING')
        if c.name in data and data[c.name] is None and not c.nullable:fail('REQUIRED_REQUEST_FIELD_MISSING')
        if c.name.endswith('_at') and data[c.name] is not None:data[c.name]=_timestamp(data[c.name])
    return data

def _project(row,keys):return {k:row[k] for k in keys}

def stage_policy_activation(connection,*,execution,activation,generation_id,outbox_id,provenance):
    """Stage an authorised manual unit and return server hashes; never commit.

    Ratified decision, existing policy version and exact bootstrap/superior
    authority must already be provided. This function creates none of them.
    ID/hash re-delivery validates every supplied field and the complete stored
    unit before reuse. Changed input is a conflict, never ON CONFLICT DO NOTHING.
    """
    if not connection.in_transaction():fail('OUTER_TRANSACTION_REQUIRED')
    from sqlalchemy import select,text
    identity=connection.execute(text('SELECT current_database(),session_user,current_user')).one()
    if tuple(identity)!=(DATABASE,WRITER,WRITER):fail('DISTINCT_ISOLATED_POLICY_WRITER_REQUIRED')
    flags=connection.execute(text('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolinherit FROM pg_roles WHERE rolname=current_user')).one()
    if any(flags):fail('ADMINISTRATIVE_WRITER_FORBIDDEN')
    memberships=connection.execute(text('SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)')).scalar_one()
    if memberships:fail('WRITER_ROLE_MEMBERSHIP_FORBIDDEN')
    from app import models
    from app.models_policy_activation_atomicity import PolicyActivationGeneration,PolicyActivationOutboxEvent
    E=models.PolicyActivationExecution.__table__;A=models.PolicyActivation.__table__
    G=PolicyActivationGeneration.__table__;O=PolicyActivationOutboxEvent.__table__;P=models.PolicyVersion.__table__
    for obj in (execution,activation,provenance):reject_server_fields(obj)
    e=dict(execution);a=dict(activation)
    if 'policy_activation_execution_record_hash' in a:fail('SERVER_FIELDS_FORBIDDEN')
    if e.get('state')!='concluida' or e.get('execution_mode')!='manual':fail('MANUAL_COMPLETED_WRITER_ONLY')
    if 'structured_result' in e:fail('SERVER_COMPLETION_MANIFEST_ONLY')
    if not e.get('policy_decision_record_hash'):fail('EXACT_DECISION_HASH_REQUIRED')
    for value in (generation_id,outbox_id,a.get('policy_activation_id')):
        if not isinstance(value,str) or not value.strip() or len(value)>64:fail('EXACT_UNIT_IDS_REQUIRED')
    _bind(e,'actor_or_worker',WRITER)
    for key in ('policy_activation_execution_id','policy_decision_id','policy_decision_record_hash','policy_type','policy_id','policy_version','policy_hash'):_bind(a,key,e.get(key))
    _bind(a,'activation_generation_id',generation_id);_bind(a,'technical_actor',WRITER)
    if a.get('state')!='activa':fail('ACTIVE_CREATION_WRITER_ONLY')
    policy=connection.execute(select(P).where(P.c.policy_id==e['policy_id'],P.c.policy_version==e['policy_version'],P.c.policy_hash==e['policy_hash'],P.c.policy_type==e['policy_type'])).mappings().one_or_none()
    if policy is None:fail('EXACT_POLICY_MISSING')
    if a.get('domain')!=policy['domain']:fail('EXACT_POLICY_DOMAIN_REQUIRED')
    import hashlib
    e['structured_result']={'schema':SCHEMA,'policy_activation_id':a['policy_activation_id'],'policy_activation_generation_id':generation_id,
        'policy_activation_outbox_event_id':outbox_id,'domain':a['domain'],'modality':a['modality'],'scope_hash':hashlib.sha256(canonical_bytes(policy['scope'])).hexdigest()}
    # Hash is derived from server INSERT, not accepted from the caller.
    a.pop('policy_activation_execution_record_hash',None)
    e=_complete(E,e);a=_complete(A,a)
    # This one derived predecessor is filled from the actual returned execution.
    a.pop('policy_activation_execution_record_hash',None)
    connection.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'),{'key':e['idempotency_key']})
    previous=connection.execute(select(E).where(E.c.idempotency_key==e['idempotency_key'])).mappings().one_or_none()
    if previous is not None:
        assert_same_request(e,_project(previous,e))
        stored_a=connection.execute(select(A).where(A.c.policy_activation_id==a['policy_activation_id'])).mappings().one_or_none()
        if stored_a is None:fail('IDEMPOTENT_UNIT_INCOMPLETE')
        assert_same_request(a,_project(stored_a,a))
        for T,key,value in ((G,'policy_activation_generation_id',generation_id),(O,'policy_activation_outbox_event_id',outbox_id)):
            row=connection.execute(select(T).where(T.c[key]==value)).mappings().one_or_none()
            if row is None:fail('IDEMPOTENT_UNIT_INCOMPLETE')
            assert_same_request(provenance,row['provenance'])
            assert_same_request({'created_at':a['activated_at']},{'created_at':row['created_at']})
        connection.execute(text('SELECT b02p_require_complete(:id,false)'),{'id':e['policy_activation_execution_id']})
        return {'reused':True,'execution_id':previous['policy_activation_execution_id'],'execution_hash':previous['record_hash'],'activation_id':stored_a['policy_activation_id'],'activation_hash':stored_a['record_hash'],'generation_id':generation_id,'outbox_id':outbox_id}
    er=connection.execute(E.insert().values(**e,record_hash=None).returning(E)).mappings().one()
    models._adr020_validate_policy_activation_execution_insert(None,connection,SimpleNamespace(**er))
    a['policy_activation_execution_record_hash']=er['record_hash']
    ar=connection.execute(A.insert().values(**a,record_hash=None).returning(A)).mappings().one()
    models._adr020_validate_policy_activation_insert(None,connection,SimpleNamespace(**ar))
    exact={key:ar[key] for key in ('policy_activation_execution_id','policy_activation_execution_record_hash','policy_decision_id','policy_decision_record_hash','policy_id','policy_version','policy_hash')}
    exact.update(policy_activation_id=ar['policy_activation_id'],policy_activation_record_hash=ar['record_hash'])
    g=dict(exact,policy_activation_generation_id=generation_id,schema_version=1,domain=ar['domain'],modality=ar['modality'],scope_descriptor=policy['scope'],
        scope_hash=e['structured_result']['scope_hash'],operational_interval=ar['operational_interval'],completion_manifest=er['structured_result'],is_complete=True,
        created_at=ar['activated_at'],provenance=provenance)
    gr=connection.execute(G.insert().values(**g).returning(G)).mappings().one()
    o=dict(exact,policy_activation_outbox_event_id=outbox_id,policy_activation_generation_id=generation_id,policy_activation_generation_hash=gr['record_hash'],
        schema_version=1,event_type='policy_activation_completed',created_at=ar['activated_at'],provenance=provenance)
    connection.execute(O.insert().values(**o).returning(O)).mappings().one()
    # Explicit unit validation does not change the caller's constraint modes.
    connection.execute(text('SELECT b02p_require_complete(:id,true)'),{'id':er['policy_activation_execution_id']})
    return {'reused':False,'execution_id':er['policy_activation_execution_id'],'execution_hash':er['record_hash'],'activation_id':ar['policy_activation_id'],
            'activation_hash':ar['record_hash'],'generation_id':generation_id,'generation_hash':gr['record_hash'],'outbox_id':outbox_id}
