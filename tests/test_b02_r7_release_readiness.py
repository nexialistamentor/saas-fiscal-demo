"""Fail-closed synthetic contracts for the read-only R7 release gate."""
from __future__ import annotations
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('b02_r7_probe',
    Path(__file__).resolve().parents[1] / 'tools/b02_r7_release_readiness.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
BLOB = 'a'*40

def valid():
    fence = {
        'schema': 'SOLVERIS_B02_R7_CLOSEOUT_RELEASE_FENCE_V1',
        'status': 'B02_NOT_CLOSED_B03_NOT_RELEASED',
        'read_only_origin': {'branch':mod.BRANCH},
        'strict_release_rules': {k: True for k in (
            'no_backdated_authority', 'no_reuse_expired_g4_g5_or_native_roots',
            'no_synthetic_to_real_promotion',
            'no_production_ddl_dml_without_explicit_new_prospective_authority',
            'no_auto_retry_after_uncertain_commit_ack',
            'no_mei_or_historical_b02_mutation',
            'no_unnecessary_repetition_of_accepted_r4_c3_r5_tests',
            'technical_signoff_not_institutional_signoff')},
        'exact_missing_predecessors': [{'id': i, 'observed':'NOT_ISSUED'}
                                       for i in sorted(mod.REQUIRED_GAPS)],
        'technically_completed_not_to_repeat': [
            {'gate':k,'status':v} for k,v in mod.COMPLETED_SCOPES.items()],
    }
    fence['strict_release_rules']['final_b02_closed_allowed'] = False
    fence['strict_release_rules']['b03_release_allowed'] = False
    manifest = {
        'r1_r7_continuity_matrix': {
            'status':'B02_OPEN_B03_BLOCKED',
            'R7_release_fence_20261031': {
                'file':mod.FENCE_PATH,'git_blob':BLOB,
                'b02_closed':False,'b03_released':False,
                'protected_database_writes_in_this_reconciliation':0,
                'missing_predecessors':list(mod.REQUIRED_GAPS),
            },
            'R5_disposable_two_unit_candidate': {
                'status':'R5_TWO_UNIT_SOURCE_RED_GREEN_AND_PG17_DISPOSABLE_CAUSAL_PASS_WAITING_ORIGINAL_INDEPENDENT_REVIEW',
            },
        },
        'reviewer_documentary_evidence': {'sql_auditada_favoravelmente':'NOT_ISSUED'},
    }
    return fence,manifest

class ReleaseFenceNegativeTests(unittest.TestCase):
    def evaluate(self, f=None, m=None):
        if f is None or m is None:
            f,m=valid()
        return mod.evaluate(f,m,fence_blob=BLOB)

    def test_truthful_open_state_is_accepted_only_as_blocked(self):
        result=self.evaluate()
        self.assertEqual(result['result'],'B02_OPEN_B03_BLOCKED_CORROBORATED')
        self.assertFalse(result['claim_of_b02_release'])
        self.assertFalse(result['claim_of_b03_release'])
        self.assertEqual(result['database_writes'],0)

    def test_missing_independent_act_rejected(self):
        f,m=valid();f['exact_missing_predecessors'].pop()
        with self.assertRaisesRegex(RuntimeError,'INCOMPLETE_GAP_INVENTORY'):
            self.evaluate(f,m)

    def test_fake_favourable_audit_rejected(self):
        f,m=valid();m['reviewer_documentary_evidence']['sql_auditada_favoravelmente']='ISSUED'
        with self.assertRaisesRegex(RuntimeError,'INSTITUTIONAL_AUDIT_STATUS_DIVERGENCE'):
            self.evaluate(f,m)

    def test_fake_b02_or_b03_release_rejected(self):
        for key in ('final_b02_closed_allowed','b03_release_allowed'):
            f,m=valid();f['strict_release_rules'][key]=True
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError,'UNAUTHORIZED_RELEASE_FLAG'):
                self.evaluate(f,m)

    def test_fence_blob_substitution_rejected(self):
        f,m=valid();m['r1_r7_continuity_matrix']['R7_release_fence_20261031']['git_blob']='b'*40
        with self.assertRaisesRegex(RuntimeError,'MANIFEST_FENCE_LINK_DIVERGENCE'):
            self.evaluate(f,m)

    def test_scoped_r5_proof_cannot_be_promoted_to_real(self):
        f,m=valid(); f['technically_completed_not_to_repeat'][2]['status']='REAL_0064_0065_PASS'
        with self.assertRaisesRegex(RuntimeError,'TECHNICAL_SCOPE_PROMOTED_OR_CHANGED'):
            self.evaluate(f,m)

    def test_protected_write_claim_rejected(self):
        f,m=valid();m['r1_r7_continuity_matrix']['R7_release_fence_20261031']['protected_database_writes_in_this_reconciliation']=1
        with self.assertRaisesRegex(RuntimeError,'PROTECTED_WRITE_ASSERTION'):
            self.evaluate(f,m)

if __name__=='__main__':
    unittest.main()
