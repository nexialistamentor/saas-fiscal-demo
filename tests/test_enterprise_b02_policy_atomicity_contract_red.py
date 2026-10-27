"""Frozen policy atomicity RED. Metadata/pure functions only; never connects."""
import ast
import hashlib
import importlib.util
import inspect
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'app/models_policy_activation_atomicity.py'
WRITER=ROOT/'app/services/enterprise_b02_policy_activation_atomicity.py'
MIGRATION=ROOT/'migrations/versions/0063_adr020_policy_activation_atomicity.py'

def load(path,name):
    assert path.is_file(),'POLICY_ATOMICITY_CANDIDATE_ABSENT:'+path.name
    if name in sys.modules:return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def writer():return load(WRITER,'b02_policy_writer_contract_target')

@pytest.mark.parametrize('name,parents',[
 ('PolicyActivationGeneration',{'policy_activation_executions','policy_activations'}),
 ('PolicyActivationOutboxEvent',{'policy_activation_generations','policy_activation_executions','policy_activations'})])
def test_exact_composite_predecessors(name,parents):
    m=load(MODEL,'app.models_policy_activation_atomicity')
    table=getattr(m,name).__table__
    assert not table.c.record_hash.nullable and not table.c.assigned_txid.nullable
    for parent in parents:
        assert any(fk.referred_table.name==parent and len(fk.elements)>=2 and any('hash' in x.parent.name for x in fk.elements) for fk in table.foreign_key_constraints)

def test_outer_transaction_is_required():
    m=writer()
    class C:
        def in_transaction(self):return False
    with pytest.raises(m.PolicyAtomicityError) as e:m.stage_policy_activation(C(),execution={},activation={},generation_id='g',outbox_id='o',provenance={})
    assert e.value.code=='OUTER_TRANSACTION_REQUIRED'

def test_hash_excludes_only_own_record_hash():
    m=writer();a={'schema':'policy-test','v':2}
    assert m.record_hash(a)==m.record_hash(dict(a,record_hash='0'*64))
    assert m.record_hash(a)!=m.record_hash(dict(a,v=3))

@pytest.mark.parametrize('field',['record_hash','assigned_txid','b02_policy_txid'])
def test_server_fields_cannot_be_supplied(field):
    m=writer()
    with pytest.raises(m.PolicyAtomicityError) as e:m.reject_server_fields({field:'0'})
    assert e.value.code=='SERVER_FIELDS_FORBIDDEN'

def test_replay_detects_changed_provenance():
    m=writer()
    with pytest.raises(m.PolicyAtomicityError) as e:m.assert_same_request({'id':'x','provenance':{'v':1}},{'id':'x','provenance':{'v':2}})
    assert e.value.code=='IDEMPOTENT_EVIDENCE_CONFLICT'

def test_no_internal_commit_rollback_or_schema_creation():
    m=writer();tree=ast.parse(inspect.getsource(m))
    forbidden={'commit','rollback','create_all','drop_all'}
    assert not [n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in forbidden]

def test_successor_is_exact_and_irreversible():
    m=load(MIGRATION,'b02_policy_atomicity_migration_contract_target')
    assert m.revision=='0063_adr020_policy_activation_atomicity'
    assert m.down_revision=='0062_adr020_noncredential_acquisition'
    with pytest.raises(RuntimeError):m.downgrade()

def test_deferred_atomic_guards_and_no_normative_parent_reuse():
    assert MIGRATION.is_file(),'POLICY_ATOMICITY_CANDIDATE_ABSENT:'+MIGRATION.name
    src=MIGRATION.read_text()
    assert 'DEFERRABLE INITIALLY DEFERRED' in src
    assert 'pg_current_xact_id()' in src and 'SECURITY DEFINER' not in src
    assert 'REFERENCES activation_generations' not in src and 'REFERENCES outbox_event_records' not in src

def test_0062_is_unchanged_control():
    p=ROOT/'migrations/versions/0062_adr020_noncredential_acquisition.py'
    assert hashlib.sha256(p.read_bytes()).hexdigest()=='bf8c953c6ed8448b33b90205540882f3dddcf46895cb1d6ef932148952fa1d0e'
