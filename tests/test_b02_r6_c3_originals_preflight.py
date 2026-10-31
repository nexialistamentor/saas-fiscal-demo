"""Synthetic C3 source checks; never reads protected source PDFs or database."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'tools'/'b02_r6_c3_originals_preflight.py'
spec=importlib.util.spec_from_file_location('b02_r6_c3',SOURCE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def fixture(root):
    base=root/'sources'
    base.mkdir()
    docs=[]
    expected={}
    for ident, marker in [('101201900571',b'A'),('101202501245',b'B')]:
        raw=b'%PDF-'+marker*1024
        folder=base/ident
        folder.mkdir()
        (folder/'DOCUMENT.pdf').write_bytes(raw)
        digest=hashlib.sha256(raw).hexdigest()
        expected[ident]=(digest,len(raw))
        docs.append(dict(document_id=ident,sha256=digest,byte_size=len(raw),
                         g4=dict(valid_until='2026-10-30T13:00:00+00:00')))
    policy=root/'candidate.json'
    policy.write_text(json.dumps({'policy_candidate_body':{
        'policy_id':mod.POLICY_ID,'policy_version':2,
        'declared_material_applicability':{'until':'2026-10-30T13:00:00+00:00'},
        'rules':{'b02_noncredential':{'security':{'g5_release':{
            'until':'2026-10-30T13:00:00+00:00','documents':docs}}}}}}))
    return base,policy,expected

class C3ProvenanceTests(unittest.TestCase):
    def test_exact_two_originals_no_protected_write(self):
        with tempfile.TemporaryDirectory() as root:
            base,policy,pins=fixture(Path(root))
            r=mod.verify(base,policy_path=policy,expected=pins)
            self.assertEqual(r['status'],'B02_R6_C3_TWO_ORIGINALS_BYTES_READ_ONLY_PASS')
            self.assertEqual(r['files'],2)
            self.assertEqual(r['protected_database_writes'],0)
            self.assertFalse(r['authority_for_release'])
    def test_mismatched_policy_digest_stops(self):
        with tempfile.TemporaryDirectory() as root:
            base,policy,pins=fixture(Path(root))
            data=json.loads(policy.read_text())
            data['policy_candidate_body']['rules']['b02_noncredential']['security']['g5_release']['documents'][0]['sha256']='0'*64
            policy.write_text(json.dumps(data))
            with self.assertRaisesRegex(RuntimeError,'POLICY_DOCUMENT_CONTENT_MISMATCH'):
                mod.verify(base,policy_path=policy,expected=pins)
    def test_relative_path_stops(self):
        with self.assertRaisesRegex(RuntimeError,'ABSOLUTE_UNTRAVERSABLE_PATH_REQUIRED'):
            mod.check_components(Path('relative'))

if __name__=='__main__':
    unittest.main()
