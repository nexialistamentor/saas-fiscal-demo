"""Only new B02 R7 V2 overlay; synthetic read-only focused tests."""
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

MOD = Path(__file__).with_name('b02_r7_v2_readonly.py')
spec = importlib.util.spec_from_file_location('b02_r7_v2_overlay', MOD)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_json_duplicate_key_rejected():
    with pytest.raises(ValueError, match='DUPLICATE_JSON_KEY'):
        m.unique([('id', 1), ('id', 2)])


def test_read_exact_hash_rejects_changed_bytes(tmp_path):
    (tmp_path/'evidence.json').write_bytes(b'{"accepted":true}')
    with pytest.raises(ValueError, match='PIN_DIVERGENCE'):
        m.read(tmp_path, 'evidence.json', expected_sha='0'*64)


def test_mathematical_signature_absent_fails_closed(tmp_path):
    with pytest.raises(ValueError, match='SIGNED_BUNDLE_NOT_FOUND'):
        m.mathematical_signature(tmp_path/'not_there', tmp_path/'public.der')


def signed_fixture(tmp_path, monkeypatch, *, corrupt=False):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    import json
    key = Ed25519PrivateKey.generate()  # synthetic fixture only; never persisted
    pub = key.public_key().public_bytes(serialization.Encoding.DER,
                                       serialization.PublicFormat.SubjectPublicKeyInfo)
    decision = b'{' + b' ' * 1116 + b'}'
    manifest = b'{"entries": []}'
    sig = key.sign(decision)
    if corrupt: sig = sig[:-1] + bytes([sig[-1]^1])
    monkeypatch.setattr(m, 'DECISION_SHA', m.sha(decision))
    monkeypatch.setattr(m, 'MANIFEST_SHA', m.sha(manifest))
    monkeypatch.setattr(m, 'PUBLIC_DER_SHA', m.sha(pub))
    bundle = tmp_path/'bundle'; bundle.mkdir()
    (bundle/'decision.json').write_bytes(decision)
    (bundle/'manifest.json').write_bytes(manifest)
    (bundle/'signature.bin').write_bytes(sig)
    p = tmp_path/'public.der'; p.write_bytes(pub)
    return bundle, p


def test_valid_math_does_not_claim_trust(tmp_path, monkeypatch):
    bundle, pub = signed_fixture(tmp_path, monkeypatch)
    result = m.mathematical_signature(bundle, pub)
    assert result['mathematical_verification'] == 'B02_V2_ED25519_MATHEMATICAL_VERIFY_PASS'
    assert result['operational_trust'] == 'NOT_GRANTED_BY_MATH_VERIFICATION'
    assert result['signature_sha256'] == m.sha((bundle/'signature.bin').read_bytes())


def test_changed_signature_rejected(tmp_path, monkeypatch):
    bundle, pub = signed_fixture(tmp_path, monkeypatch, corrupt=True)
    with pytest.raises(ValueError, match='ED25519_MATHEMATICAL_FAILURE'):
        m.mathematical_signature(bundle, pub)


def test_projection_keeps_b02_open_when_previous_two_closed(tmp_path, monkeypatch):
    prior_remaining = {'G5_V3_OWN_INDEPENDENT_AUDIT','G5_NEW_TEMPORAL_POLICY',
        'R1_NATIVE_ROOT_SUCCESSOR','R5_FULL_0064_0065_PHYSICAL',
        'R6_NORMATIVE_TO_FISCAL','R7_COMPETENT_B02_FINAL'}
    class Old:
        FENCE_PATH='FENCE.json'; MANIFEST_PATH='MANIFEST.json'
        POST_G4_PATH='G4.json'; V3_PATH='V3.json'; A2_FOCAL_PATH='A2.md'
        def evaluate(self, fence, manifest, **kwargs): return {'claim_of_b02_release':False}
        def evaluate_post_g4(self, result, *args, **kwargs):
            return {**result, 'post_g4_completed_predecessors':['CURRENT_G4_V3_SUCCESSOR'],
                    'remaining_predecessors':sorted(prior_remaining|{'RCV31_A2_V4_OWN_REVIEW'})}
        def consume_a2_v4_focal_review(self, result, **kwargs):
            return {**result, 'post_g4_completed_predecessors':['CURRENT_G4_V3_SUCCESSOR','RCV31_A2_V4_OWN_REVIEW'],
                    'remaining_predecessors':sorted(prior_remaining)}
    monkeypatch.setattr(m,'load_old',lambda repo: Old())
    monkeypatch.setattr(m,'clean_pinned',lambda repo,paths: None)
    monkeypatch.setattr(m,'git',lambda repo,*args: 'deadbeef')
    monkeypatch.setattr(m,'ADOPTION_SHA', 'a'*64)
    (tmp_path/'A2.md').write_text('synthetic current A2 already closed')
    adoption = {'schema':'SOLVERIS-B02-DOCUMENTARY-CONTINUITY-ADOPTION-V2',
        'decision':{'signing_authorized':False},'successor_review':{'sha256':m.REVIEW_SHA},
        'object_sha256':m.OBJECT_SHA,'policy_subject':{'policy_id':'documentary'}}
    evidence = {k:{'policy_subject':adoption['policy_subject']} if k=='object.json'
                  else ({str(i):i for i in range(149)} if k=='proofs.json' else {}) for k in m.SEVEN}
    def fake_read(repo,path,**kwargs):
        if path==m.ADOPTION: return b'not true digest fixture', adoption
        if path.startswith('evidence/b02/successor_v3/'):
            return b'',evidence[Path(path).name]
        return b'',{}
    monkeypatch.setattr(m,'read',fake_read)
    actual = m.baseline(tmp_path)
    assert actual['status']=='B02_OPEN_B03_BLOCKED'
    assert actual['r7_closed'] is False
    assert len(actual['current_unproved_r7_predecessors'])==6
    assert set(actual['closed_gates_only_in_scope'])=={
        'CURRENT_G4_V3_SUCCESSOR','RCV31_A2_V4_OWN_REVIEW'}
