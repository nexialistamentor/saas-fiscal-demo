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

if __name__=='__main__':
    unittest.main()
