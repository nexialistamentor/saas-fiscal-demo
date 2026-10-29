"""Focused tests for the G5 V5 policy-only owner/writer split. No database writes."""
import contextlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT/'tools') not in sys.path:sys.path.insert(0,str(ROOT/'tools'))
spec=importlib.util.spec_from_file_location('g5_owner_commit_runner',ROOT/'tools'/'b02_g5_v5_policy_runner.py')
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
import b02_g5_v5_institutional_owner_rollback_probe as owner


class OwnerCommitDeltaTests(unittest.TestCase):
    def test_existing_user_instruction_is_reused_without_fabricated_evidence(self):
        approval=runner.authorize(None,None)
        self.assertEqual(approval['reference'],'USER_ORDER_INSTALA_E_ATIVA_G5_V5_VERSION_2')
        self.assertEqual(approval['policy_version_record_id'],'B02-G5-V5-policy-v2')
        self.assertIsNone(approval['authority_actor'])
        self.assertIsNone(approval['key_custody_evidence'])

    def test_false_instruction_is_rejected_before_any_write(self):
        approval=json.loads((ROOT/'B02_G5_V5_AUTHORIZATION_MANIFEST_DRAFT.json').read_text(encoding='utf8'))
        approval['authorization_received']['literal']='OTHER'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'approval.json'
            path.write_text(json.dumps(approval),encoding='utf8')
            with self.assertRaisesRegex(RuntimeError,'STOP_AUTHORIZATION_SOURCE_UNVERIFIED'):
                runner.authorize(path,None)

    def test_single_commit_uses_physically_proven_sql_and_current_window(self):
        body=runner.candidate(ROOT)
        sql=runner._owner_commit_sql(body,'B02-G5-V5-policy-v2')
        self.assertEqual(sql.count('COMMIT;'),1)
        self.assertEqual(sql.count('INSERT INTO public.policy_versions'),1)
        self.assertNotIn('ROLLBACK;',sql)
        self.assertNotIn('GRANT ',sql)
        self.assertNotIn('INSERT INTO public.policy_decisions',sql)
        self.assertNotIn('INSERT INTO public.policy_activations',sql)
        self.assertIn("2026-10-30T13:00:00+00:00",sql)
        self.assertIn('STOP_G4_EXACT_PREDECESSOR_MISSING',sql)
        self.assertIn('B02-G5-V5-policy-v2',sql)
        self.assertNotIn('B02-G5-V5-ROLLBACK-PROBE',sql)

    def test_independent_readback_verifies_all_fields_and_physical_hash(self):
        body=runner.candidate(ROOT)
        row=dict(body,policy_version_record_id='B02-G5-V5-policy-v2',
                 policy_hash=runner.POLICY_HASH,record_hash='a'*64)
        lines=['BEGIN',owner.bridge.DATABASE+'|'+owner.bridge.ROLE+'|'+owner.bridge.ROLE,
               '0063_adr020_policy_activation_atomicity',
               json.dumps({'stored':row,'record_hash_ok':True}),'2','ROLLBACK']
        with patch.object(owner,'psql',return_value=lines) as called:
            result,stored=runner._restricted_readback(body,'B02-G5-V5-policy-v2')
        self.assertEqual(result,'PRESENT_EXACT')
        self.assertEqual(stored['record_hash'],'a'*64)
        self.assertEqual(called.call_args.args[1],owner.bridge.ROLE)
        lines[3]=json.dumps({'stored':dict(row,scope={}), 'record_hash_ok':True})
        with patch.object(owner,'psql',return_value=lines):
            result,_=runner._restricted_readback(body,'B02-G5-V5-policy-v2')
        self.assertEqual(result,'CONFLICT')

    def test_owner_write_once_restricted_readback_twice(self):
        body={'declared_material_applicability':{'from':'2020-01-01T00:00:00+00:00',
             'until':'2035-01-01T00:00:00+00:00'}}
        a={'policy_version_record_id':'B02-G5-V5-policy-v2'}
        with patch.object(owner.bridge,'managed_container',return_value=contextlib.nullcontext()), \
             patch.object(owner,'owner_preflight') as preflight, \
             patch.object(owner,'psql',return_value=['COMMIT','B02_G5_V5_OWNER_COMMIT_ACK']) as write, \
             patch.object(runner,'_owner_commit_sql',return_value='ONE_APPROVED_TRANSACTION'), \
             patch.object(runner,'_restricted_readback',side_effect=[
                 ('ABSENT',None),('PRESENT_EXACT',{'record_hash':'a'*64})]) as readback:
            runner._execute_owner_policy_only(ROOT,body,a)
        preflight.assert_called_once()
        write.assert_called_once_with('ONE_APPROVED_TRANSACTION',owner.OWNER)
        self.assertEqual(readback.call_count,2)

    def test_uncertain_ack_never_retries_even_if_row_present(self):
        body={'declared_material_applicability':{'from':'2020-01-01T00:00:00+00:00',
             'until':'2035-01-01T00:00:00+00:00'}}
        a={'policy_version_record_id':'B02-G5-V5-policy-v2'}
        with patch.object(owner.bridge,'managed_container',return_value=contextlib.nullcontext()), \
             patch.object(owner,'owner_preflight'), \
             patch.object(owner,'psql',side_effect=RuntimeError('NETWORK_ACK_UNKNOWN')) as write, \
             patch.object(runner,'_owner_commit_sql',return_value='ONE_APPROVED_TRANSACTION'), \
             patch.object(runner,'_restricted_readback',side_effect=[
                 ('ABSENT',None),('PRESENT_EXACT',{'record_hash':'a'*64})]) as readback:
            with self.assertRaisesRegex(RuntimeError,'STOP_COMMIT_ACK_UNCERTAIN_MANUAL_RECONCILIATION'):
                runner._execute_owner_policy_only(ROOT,body,a)
        self.assertEqual(write.call_count,1)
        self.assertEqual(readback.call_count,2)


if __name__=='__main__':
    unittest.main()
