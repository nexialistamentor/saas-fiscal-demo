"""Synthetic preflight selection tests; not institutional proof or real-origin validation."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('b02_successor_preparer',ROOT/'B02_PREPARAR_BUNDLE_SUCESSOR.py')
PREP=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREP)

FROM='2026-11-04T00:00:00+00:00'
UNTIL='2026-11-10T00:00:00+00:00'
ACTOR='GPT-6/test-origin-examiner-synthetic'
AUTHOR='GPT-6/test-author-synthetic'
REVIEWER='GPT-6/test-reviewer-synthetic'

def add(proofs,value):
    h=PREP.sha(PREP.canonical(value))
    proofs[h]=value
    return h

def fixture():
    proofs={}
    review={'inputs_sha256':['0'*64],
            'reviewer_execution':REVIEWER,
            'author_execution':AUTHOR,
            'integrator_execution':AUTHOR}
    ids=[]
    for index,(docid,sha256) in enumerate(PREP.DOCS.items()):
        document={'id':docid,'url':PREP.DOC_META[docid][0],
                  'sha256':sha256,'byte_size':PREP.DOC_META[docid][1]}
        mandate={'id':f'B02-G4-SYNTH-ORIGIN-{index}',
                 'issuer':'Miguel','policy_subject':PREP.SUBJECT,'execution_id':ACTOR,
                 'operations':['examine_document_origin','report','abstain'],
                 'valid_from':'2026-11-02T00:00:00+00:00',
                 'valid_until':'2026-11-15T00:00:00+00:00',
                 'revoked':False,'synthetic_only':False}
        mandate_sha=add(proofs,mandate)
        binding={'id':mandate['id'],'sha256':mandate_sha}
        acceptance={'execution_id':ACTOR,'mandate_sha256':mandate_sha,
                    'accepted':True,'accepted_at':'2026-11-03T09:00:00+00:00'}
        acceptance_sha=add(proofs,acceptance)
        examination={'actor_execution':ACTOR,'document':document,'mandate_binding':binding,
                     'examined_at':'2026-11-03T10:00:00+00:00',
                     'own_findings':['synthetic fixture only'], 'limitations':['not real evidence']}
        examination_sha=add(proofs,examination)
        report={'id':f'B02-G4-SYNTH-REPORT-{index}',
                'kind':PREP.ORIGIN_KIND,'policy_subject':PREP.SUBJECT,'document':document,
                'actor_execution':ACTOR,'technical_author_execution':AUTHOR,
                'technical_integrator_execution':AUTHOR,'mandate_binding':binding,
                'mandate_acceptance_sha256':acceptance_sha,
                'outcome':'favoravel','synthetic_only':False,
                'official_identifier':docid,'receipt_binding':{'id':'synthetic-receipt','sha256':'2'*64},
                'tls_evidence_binding':{'id':'synthetic-tls','sha256':'3'*64},
                'receipt_projection':{'synthetic':'fixture'},'verifier':{'id':'synthetic'},
                'doe_references':['synthetic'],'mechanism_assessment':['synthetic'],
                'examination_record_sha256':examination_sha,
                'valid_from':'2026-11-02T00:00:00+00:00',
                'valid_until':'2026-11-15T00:00:00+00:00',
                'examined_at':'2026-11-03T10:00:00+00:00'}
        pin=add(proofs,report)
        ids.append(pin)
    review['inputs_sha256'].extend(ids)
    return proofs,review,ids

class ExactSuccessorOriginSelection(unittest.TestCase):
    def selected(self,proofs,review):
        return PREP._selected_successor_origin_reports(
            proofs,review,valid_from=FROM,valid_until=UNTIL)

    def test_two_explicit_pins_with_unselected_historic_reports(self):
        proofs,review,ids=fixture()
        historic={'kind':PREP.ORIGIN_KIND,'document':{'id':'101202501245'},
                  'valid_until':'2026-10-29T00:00:00+00:00'}
        old=add(proofs,historic)
        result=self.selected(proofs,review)
        self.assertEqual({r['id'] for r in result},{proofs[h]['id'] for h in ids})
        self.assertIn(old,proofs)
        self.assertEqual(len([v for v in proofs.values()
            if isinstance(v,dict) and v.get('kind')==PREP.ORIGIN_KIND]),3)

    def test_missing_pin_fails_closed(self):
        proofs,review,ids=fixture()
        review['inputs_sha256'].remove(ids[-1])
        with self.assertRaisesRegex(RuntimeError,'ORIGIN_EXPLICIT_SUCCESSOR_BINDINGS_NOT_TWO'):
            self.selected(proofs,review)

    def test_historical_report_wrongly_pinned_fails_closed(self):
        proofs,review,ids=fixture()
        old=add(proofs,{'kind':PREP.ORIGIN_KIND,'document':{'id':'101202501245'},
                        'valid_until':'2026-10-29T00:00:00+00:00'})
        review['inputs_sha256'].append(old)
        with self.assertRaisesRegex(RuntimeError,'ORIGIN_EXPLICIT_SUCCESSOR_BINDINGS_NOT_TWO'):
            self.selected(proofs,review)

    def test_duplicate_pin_fails_closed(self):
        proofs,review,ids=fixture()
        review['inputs_sha256'].append(ids[0])
        with self.assertRaisesRegex(RuntimeError,'ORIGIN_EXPLICIT_REVIEW_INPUTS_INVALID'):
            self.selected(proofs,review)

    def test_wrong_report_hash_fails_closed(self):
        proofs,review,ids=fixture()
        proofs[ids[0]]['outcome']='desfavoravel'
        with self.assertRaisesRegex(RuntimeError,'ORIGIN_REPORT_PIN_DIVERGENT'):
            self.selected(proofs,review)

    def test_document_scope_swapped_fails_closed(self):
        proofs,review,ids=fixture()
        original=proofs.pop(ids[0])
        original['document']['sha256']='f'*64
        wrong=add(proofs,original)
        review['inputs_sha256'][1]=wrong
        with self.assertRaisesRegex(RuntimeError,'ORIGIN_SUCCESSOR_REPORT_SCOPE_INVALID'):
            self.selected(proofs,review)

    def test_wrong_mandate_binding_fails_closed(self):
        proofs,review,ids=fixture()
        original=proofs.pop(ids[0])
        original['mandate_binding']['sha256']='e'*64
        wrong=add(proofs,original)
        review['inputs_sha256'][1]=wrong
        with self.assertRaisesRegex(RuntimeError,'ORIGIN_SUCCESSOR_MANDATE_INVALID'):
            self.selected(proofs,review)

    def test_wrong_acceptance_fails_closed(self):
        proofs,review,ids=fixture()
        original=proofs.pop(ids[0])
        original['mandate_acceptance_sha256']='e'*64
        wrong=add(proofs,original)
        review['inputs_sha256'][1]=wrong
        with self.assertRaisesRegex(RuntimeError,'ORIGIN_SUCCESSOR_ACCEPTANCE_INVALID'):
            self.selected(proofs,review)

    def test_expired_report_fails_closed(self):
        proofs,review,ids=fixture()
        original=proofs.pop(ids[0])
        original['valid_until']='2026-11-03T11:00:00+00:00'
        wrong=add(proofs,original)
        review['inputs_sha256'][1]=wrong
        with self.assertRaisesRegex(RuntimeError,'ORIGIN_SUCCESSOR_CHRONOLOGY_INVALID'):
            self.selected(proofs,review)

if __name__=='__main__':
    unittest.main()
