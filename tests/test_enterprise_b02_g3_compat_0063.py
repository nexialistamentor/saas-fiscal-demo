"""Native 0063 integration complement. Frozen original functions reused unchanged.
The original 0062 suite is neither collected nor modified. No monkeypatch/stamp.
"""
import hashlib,importlib.util,io,os,re
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/'tests/test_enterprise_b02_r4g_postgresql.py'
FROZEN_SHA='ee04b0b763130a73bd98f9e50c86251073626da4ccdc1bf1a02c9ed2b7b2b6e0'
assert hashlib.sha256(FROZEN.read_bytes()).hexdigest()==FROZEN_SHA
spec=importlib.util.spec_from_file_location('b02_frozen_contract_library',FROZEN)
_legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(_legacy)
# Reuse the original data fixture as a fixture, without replacing any globals.
data=_legacy.data
REV='0063_adr020_policy_activation_atomicity'

@pytest.fixture(scope='session',autouse=True)
def integrated_physical_gate(data):
    assert os.environ.get('B02_G3_COMPAT_STAGE')=='APPROVED_INTEGRATED_0063'
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest()==FROZEN_SHA
    assert _legacy.scalar('SELECT version_num FROM public.alembic_version')==REV
    assert _legacy.scalar("SELECT rolsuper::text||'|'||rolcreatedb::text||'|'||rolcreaterole::text||'|'||rolreplication::text||'|'||rolbypassrls::text FROM pg_roles WHERE rolname=current_user")=='false|false|false|false|false'
    assert _legacy.scalar('SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)')=='0'
    seen=set()
    for name in ('cas','public'):
        binding=_legacy.stage(_legacy.case(data,name),'binding')
        for key in ('security_policy_binding','sanitization_policy_binding'):
            b=binding[key];aid=b['policy_activation_id']
            if aid in seen:continue
            seen.add(aid)
            rows=_legacy.scalar('SELECT policy_activation_execution_id FROM public.policy_activations WHERE policy_activation_id='+_legacy.literal(aid)+' AND record_hash='+_legacy.literal(b['policy_activation_record_hash'])+' AND policy_id='+_legacy.literal(b['policy_id'])+' AND policy_version='+str(b['policy_version'])+' AND policy_hash='+_legacy.literal(b['policy_hash']))
            assert rows,'Exact existing policy activation missing'
            _legacy.scalar('SELECT b02p_require_complete('+_legacy.literal(rows)+',false)')
    assert len(seen)==4
    yield
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest()==FROZEN_SHA

# Explicit bindings below reuse exactly the frozen behavioral function objects.
# Their globals, helpers, SQL, assertions and fixture validation stay unchanged.

def test_28_database_guard_and_actual_integrated_revision():
    assert _legacy.scalar("SELECT current_database()||'|'||session_user||'|'||current_user")==_legacy.DATABASE+'|'+_legacy.WRITER+'|'+_legacy.WRITER
    assert _legacy.scalar('SELECT version_num FROM public.alembic_version')==REV
    assert _legacy.scalar("SELECT has_database_privilege(current_user,current_database(),'CREATE')::text||'|'||has_schema_privilege(current_user,'public','CREATE')::text")=='false|false'

def _offline(number):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy.dialects import postgresql
    paths=list((ROOT/'migrations/versions').glob(number+'_*.py'));assert len(paths)==1
    s=importlib.util.spec_from_file_location('b02_offline_'+number,paths[0]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    output=io.StringIO()
    context=MigrationContext.configure(dialect=postgresql.dialect(paramstyle='named'),opts={'as_sql':True,'output_buffer':output})
    with Operations.context(context):m.upgrade()
    return output.getvalue()

def test_29_all_0062_function_bodies_and_triggers_preserved():
    sql=_offline('0062')
    functions=re.findall(r'CREATE(?: OR REPLACE)? FUNCTION\s+(\w+)\s*\([^;]*?\bAS\s+\$\$(.*?)\$\$',sql,re.S|re.I)
    assert len(functions)==9
    for name,body in functions:
        rows=_legacy.scalar("SELECT encode(convert_to(p.prosrc,'UTF8'),'hex')||'|'||p.prosecdef::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname="+_legacy.literal(name))
        assert rows and '\n' not in rows,'Function missing or overloaded: '+name
        raw,definer=rows.split('|');assert definer=='false'
        assert bytes.fromhex(raw).decode().strip()==body.strip(),name
    triggers=re.findall(r'CREATE\s+(CONSTRAINT\s+)?TRIGGER\s+(\w+)\s+.*?\bON\s+(\w+)\s+.*?EXECUTE FUNCTION\s+(\w+)\s*\(',sql,re.S|re.I)
    assert len(triggers)==18
    for constraint,name,table,function in triggers:
        query="SELECT count(*) FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgrelid='public."+table+"'::regclass AND t.tgname="+_legacy.literal(name)+" AND t.tgenabled='O' AND p.proname="+_legacy.literal(function)
        if constraint:query+=' AND t.tgdeferrable AND t.tginitdeferred'
        assert _legacy.scalar(query)=='1',(table,name)

def test_30_policy_proof_guard_is_additive_and_active():
    sql=_offline('0063')
    match=re.search(r'CREATE FUNCTION b02p_guard_consumed_policy\(\).*?\bAS\s+\$\$(.*?)\$\$',sql,re.S|re.I);assert match
    raw=_legacy.scalar("SELECT encode(convert_to(p.prosrc,'UTF8'),'hex') FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname='b02p_guard_consumed_policy' AND NOT p.prosecdef")
    assert bytes.fromhex(raw).decode().strip()==match.group(1).strip()
    assert _legacy.scalar("SELECT count(*) FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgrelid='public.acquisition_mode_bindings'::regclass AND t.tgname='a_b02p_consumed_policy' AND t.tgenabled='O' AND p.proname='b02p_guard_consumed_policy'")=='1'

test_01_exact_relational_predecessors_are_physical=_legacy.test_01_exact_relational_predecessors_are_physical

test_02_synthetic_cas_complete_unit_with_rollback=_legacy.test_02_synthetic_cas_complete_unit_with_rollback

test_03_synthetic_public_complete_unit_with_rollback=_legacy.test_03_synthetic_public_complete_unit_with_rollback

test_04_missing_predecessors_fail_closed=_legacy.test_04_missing_predecessors_fail_closed

test_05_fake_credential_binding_cannot_enter_public_mode=_legacy.test_05_fake_credential_binding_cannot_enter_public_mode

test_06_existing_credentialled_mode_cannot_use_noncredential_receipt=_legacy.test_06_existing_credentialled_mode_cannot_use_noncredential_receipt

test_07_cas_cannot_claim_new_external_transport=_legacy.test_07_cas_cannot_claim_new_external_transport

test_08_public_transport_cannot_present_credentials=_legacy.test_08_public_transport_cannot_present_credentials

test_09_unknown_or_missing_mode_is_not_inferred=_legacy.test_09_unknown_or_missing_mode_is_not_inferred

test_10_same_id_divergent_evidence_is_rejected=_legacy.test_10_same_id_divergent_evidence_is_rejected

test_11_concurrent_completion_has_one_exact_result=_legacy.test_11_concurrent_completion_has_one_exact_result

test_12_every_failure_point_rolls_back_the_completion_unit=_legacy.test_12_every_failure_point_rolls_back_the_completion_unit

test_13_receipt_precommitted_cannot_complete_acquisition=_legacy.test_13_receipt_precommitted_cannot_complete_acquisition

test_14_append_only_and_privilege_guards_remain_active=_legacy.test_14_append_only_and_privilege_guards_remain_active

test_15_writer_cannot_disable_triggers_or_become_admin=_legacy.test_15_writer_cannot_disable_triggers_or_become_admin

test_16_origin_and_content_identity_divergence_is_rejected=_legacy.test_16_origin_and_content_identity_divergence_is_rejected

test_17_byte_tampering_is_rejected=_legacy.test_17_byte_tampering_is_rejected

test_18_receipt_of_another_execution_or_attempt_is_rejected=_legacy.test_18_receipt_of_another_execution_or_attempt_is_rejected

test_19_extraction_trigger_resolves_acquisition_through_exact_artifact=_legacy.test_19_extraction_trigger_resolves_acquisition_through_exact_artifact

test_20_sanitization_never_substitutes_artifact_authenticity=_legacy.test_20_sanitization_never_substitutes_artifact_authenticity

test_21_policy_activation_missing_or_divergent_fails_closed=_legacy.test_21_policy_activation_missing_or_divergent_fails_closed

test_22_hash_divergence_cannot_be_relabelled_as_idempotence=_legacy.test_22_hash_divergence_cannot_be_relabelled_as_idempotence

test_23_forged_or_incomplete_verification_is_not_favourable=_legacy.test_23_forged_or_incomplete_verification_is_not_favourable

test_24_fresh_session_compares_actual_physical_artifact_bytes=_legacy.test_24_fresh_session_compares_actual_physical_artifact_bytes

test_25_identical_bytes_do_not_collapse_different_provenance=_legacy.test_25_identical_bytes_do_not_collapse_different_provenance

test_26_documentary_success_does_not_activate_or_charge=_legacy.test_26_documentary_success_does_not_activate_or_charge

test_27_terminal_without_receipt_or_artifact_cannot_commit=_legacy.test_27_terminal_without_receipt_or_artifact_cannot_commit
