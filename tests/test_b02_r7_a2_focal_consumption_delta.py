"""Only the NEW R7 A2 V4 scoped-consumption delta; no G4, R4 or old tests."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('b02_r7_a2_delta',ROOT/'tools/b02_r7_release_readiness.py')
R7=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R7)
REPORT_PATH=ROOT/R7.A2_FOCAL_PATH

class B02R7A2FocalConsumptionDelta(unittest.TestCase):
    def setUp(self):
        self.text=REPORT_PATH.read_text(encoding='utf-8-sig')
        self.result={
            'claim_of_b02_release':False,'claim_of_b03_release':False,
            'remaining_predecessors':['RCV31_A2_V4_OWN_REVIEW','R7_COMPETENT_B02_FINAL'],
        }

    def consume(self,blob=None,text=None,result=None):
        return R7.consume_a2_v4_focal_review(
            self.result if result is None else result,
            report_blob=R7.A2_FOCAL_BLOB if blob is None else blob,
            report_text=self.text if text is None else text)

    def test_pinned_focal_result_closes_only_bounded_review(self):
        result=self.consume()
        self.assertEqual(result['a2_v4_focal_review'],
            'CLOSED_IN_ITS_TECHNICAL_SYNTHETIC_SCOPE_NO_RETEST')
        self.assertIs(result['a2_v4_focal_review_reexecution_required'],False)
        self.assertIs(result['a2_v4_original_reviewer_identity_not_attested'],True)
        self.assertEqual(result['remaining_predecessors'],['R7_COMPETENT_B02_FINAL'])
        self.assertEqual(result['missing_independently_owned_acts'],1)
        self.assertIn('RCV31_A2_V4_OWN_REVIEW',result['post_g4_completed_predecessors'])
        self.assertIs(result['r7_original_fence_preserved'],True)
        self.assertIs(result['claim_of_b02_release'],False)
        self.assertIs(result['claim_of_b03_release'],False)

    def test_wrong_exact_git_blob_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError,'A2_FOCAL_REVIEW_BLOB_DIVERGENCE'):
            self.consume(blob='0'*40)

    def test_report_downgraded_or_truncated_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError,'A2_FOCAL_REVIEW_CONTENT_DIVERGENCE'):
            self.consume(text=self.text.replace(
                'encerrada a revisão focal deste delta','revisão ainda aberta'))

    def test_fabricated_release_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'A2_SCOPED_NOT_AN_INSTITUTIONAL_RELEASE'):
            self.consume(result=dict(self.result,claim_of_b02_release=True))

    def test_original_predecessor_not_silently_removed(self):
        with self.assertRaisesRegex(RuntimeError,'A2_SCOPED_NOT_AN_INSTITUTIONAL_RELEASE'):
            self.consume(result=dict(self.result,remaining_predecessors=['R7_COMPETENT_B02_FINAL']))


class R7CurrentIssuedActsReconciliationTests(unittest.TestCase):
    """Only the post-31/10 current evidence projection; no historic gate reruns."""

    @classmethod
    def setUpClass(cls):
        import json
        cls.own=json.loads((ROOT/R7.SUCCESSOR_OWN_ACT_PATH).read_text(encoding='utf-8'))
        cls.bodies={name:json.loads((ROOT/R7.SUCCESSOR_MANDATE_DIR/name).read_text(encoding='utf-8'))
                    for name, _, _ in R7.SUCCESSOR_MANDATES.values()}
        cls.prior={format(i,'064x'):{'preserved':i} for i in range(134)}
        cls.prior[R7.SUCCESSOR_REVIEWER_ACCEPTANCE]={'preserved':'reviewer'}
        cls.base={'claim_of_b02_release':False,'claim_of_b03_release':False}

    def consume(self,proofs,blob,own=None):
        return R7.consume_issued_successor_acts(
            self.base, proofs=proofs,prior_proofs=self.prior,
            own=self.own if own is None else own,
            bodies=self.bodies,proofs_blob=blob)

    def test_135_proves_current_own_acceptances_issued_but_not_indexed(self):
        result=self.consume(dict(self.prior),R7.SUCCESSOR_PROOFS_BASE_135_BLOB)
        self.assertEqual(result['g4_author_integrator_current_own_acceptances'],
                         'TWO_CURRENT_OWN_ACCEPTANCES_ISSUED')
        self.assertFalse(result['g4_successor_five_issued_proofs_indexed'])
        self.assertEqual(result['g4_successor_proofs_count'],135)
        self.assertFalse(result['claim_of_b02_release'])

    def test_140_requires_all_five_and_preserves_prior_135(self):
        proofs=dict(self.prior)
        for role,(name,mandate_hash,acceptance_hash) in R7.SUCCESSOR_MANDATES.items():
            proofs[mandate_hash]=self.bodies[name]
            if acceptance_hash is not None:
                current=next(x for x in self.own['acceptances'] if x['role']==role)
                proofs[acceptance_hash]=current['own_canonical_acceptance']
        self.assertEqual(len(proofs),140)
        result=self.consume(proofs,'synthetic-new-committed-blob')
        self.assertTrue(result['g4_successor_five_issued_proofs_indexed'])
        self.assertEqual(result['g4_distinct_origin_examiner_own_acceptance'],
                         'NOT_PRESENT_IN_THIS_EVIDENCE')

    def test_prior_135_change_is_not_a_140_pass(self):
        proofs=dict(self.prior)
        proofs[next(iter(proofs))]={'tampered':True}
        for role,(name,mandate_hash,acceptance_hash) in R7.SUCCESSOR_MANDATES.items():
            proofs[mandate_hash]=self.bodies[name]
            if acceptance_hash is not None:
                current=next(x for x in self.own['acceptances'] if x['role']==role)
                proofs[acceptance_hash]=current['own_canonical_acceptance']
        with self.assertRaisesRegex(RuntimeError,'SUCCESSOR_140_PROOFS_MISMATCH'):
            self.consume(proofs,'synthetic-new-committed-blob')

    def test_current_author_acceptance_tamper_rejected(self):
        import copy
        own=copy.deepcopy(self.own)
        own['acceptances'][0]['own_canonical_acceptance']['accepted']=False
        with self.assertRaisesRegex(RuntimeError,'SUCCESSOR_OWN_ACCEPTANCE'):
            self.consume(dict(self.prior),R7.SUCCESSOR_PROOFS_BASE_135_BLOB,own=own)

if __name__=='__main__':
    unittest.main()
