"""Only new B02 R7 V2 overlay; synthetic read-only focused tests."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

MOD = Path(__file__).resolve().parents[1] / 'tools' / 'b02_r7_v2_readonly.py'
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
    monkeypatch.setattr(m,'resolve_v3_snapshots',
                        lambda repo, old, post, raw, candidate: (b'historic',{}))
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


def _synthetic_historic_v3():
    """Minimum old V3 schema; deliberately no ROOT, signature or inspections."""
    docs = []
    for doc_id in m.G4_HISTORICAL_ORIGIN:
        docs.append({
            'document_id': doc_id,
            'g4': {
                'origin_report_binding': None,
                'verifier': None,
                'outcome': 'AWAITING_OWN_CURRENT_FOUNDER_ORIGIN',
            },
            'sanitization': {'outcome': 'AWAITING_CURRENT_REAL_INDEPENDENT_INSPECTION'},
        })
    return {
        'status': 'V3_PROSPECTIVE_DRAFT_UNISSUED_INCOMPLETE_AUTHORITY',
        '__AVISO_G4_PREENCHIDO__': 'historical-not-linked',
        '__V3_DRAFT_PROVENANCE__': {
            'not_signed_or_authorized': True,
            'policy_body_sha256_is_draft_only': 'old-hash',
        },
        'policy_candidate_body': {
            'roles': {'proponent_and_integrator': None, 'functional_reviewer': None},
            'rules': {'b02_noncredential': {'security': {'g5_release': {
                'capability_root_id': None, 'actor': None, 'documents': docs,
            }}}},
        },
    }


def test_r7_current_v3_reconstruction_preserves_historical_roots():
    old = _synthetic_historic_v3()
    candidate = m.reconstruct_current_v3_from_historic(old)
    assert all(d['g4']['origin_report_binding'] is None
               for d in old['policy_candidate_body']['rules']
                            ['b02_noncredential']['security']['g5_release']['documents'])
    docs = candidate['policy_candidate_body']['rules']['b02_noncredential']['security']['g5_release']['documents']
    assert {d['document_id'] for d in docs} == set(m.G4_HISTORICAL_ORIGIN)
    for d in docs:
        identifier, digest = m.G4_HISTORICAL_ORIGIN[d['document_id']]
        assert d['g4']['origin_report_binding'] == {'id': identifier, 'sha256': digest}
        assert d['g4']['verifier'] is None
        assert d['g4']['outcome'] == 'AWAITING_OWN_CURRENT_FOUNDER_ORIGIN'
        assert d['sanitization']['outcome'] == 'AWAITING_CURRENT_REAL_INDEPENDENT_INSPECTION'
    assert candidate['status'] == 'V3_PROSPECTIVE_DRAFT_UNISSUED_INCOMPLETE_AUTHORITY'
    assert candidate['policy_candidate_body']['roles']['proponent_and_integrator'] == m.CURRENT_V3_ACCEPTED_PROPONENT
    assert candidate['policy_candidate_body']['roles']['functional_reviewer'] is None
    assert old['policy_candidate_body']['roles']['proponent_and_integrator'] is None


def test_r7_historic_v3_reconstruction_rejects_authority_promotion():
    old = _synthetic_historic_v3()
    old['policy_candidate_body']['rules']['b02_noncredential']['security']['g5_release']['capability_root_id'] = 'pretend-root'
    with pytest.raises(ValueError, match='V3_HISTORIC_AUTHORITY_NOT_CLOSED'):
        m.reconstruct_current_v3_from_historic(old)


def _stub_v3_snapshots(monkeypatch):
    old = _synthetic_historic_v3()
    historical_raw = json.dumps(old, sort_keys=True).encode('utf-8')
    monkeypatch.setattr(m, 'HISTORIC_G5_V3_SHA256', m.sha(historical_raw))
    candidate = m.reconstruct_current_v3_from_historic(old)
    new_body = json.dumps(candidate['policy_candidate_body'],
                          sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False).encode('utf-8')
    monkeypatch.setattr(m, 'CURRENT_G5_V3_BODY_SHA256', m.sha(new_body))
    candidate = m.reconstruct_current_v3_from_historic(old)
    current_raw = json.dumps(candidate, sort_keys=True).encode('utf-8')
    monkeypatch.setattr(m, 'CURRENT_G5_V3_SHA256', m.sha(current_raw))
    monkeypatch.setattr(m, 'git', lambda repo, *args: m.CURRENT_G5_V3_BLOB)
    monkeypatch.setattr(m.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout=historical_raw))
    old_adapter = SimpleNamespace(
        V3_PATH='POLICY_G5_CANDIDATO_SUCESSOR_V3_PARA_REVISAO.json',
        G5_V3_FILE_SHA256=m.HISTORIC_G5_V3_SHA256)
    pin = {'g5_v3_consumer': {
        'path': old_adapter.V3_PATH,
        'git_blob': m.HISTORIC_G5_V3_BLOB,
        'sha256_exact': m.HISTORIC_G5_V3_SHA256,
        'policy_active': False,
    }}
    return old_adapter, pin, current_raw, candidate, historical_raw


def test_r7_two_v3_snapshots_use_historic_blob_and_current_exact_delta(monkeypatch, tmp_path):
    old_adapter, pin, raw, candidate, historic_raw = _stub_v3_snapshots(monkeypatch)
    returned_raw, returned = m.resolve_v3_snapshots(
        tmp_path, old_adapter, pin, raw, candidate)
    assert returned_raw == historic_raw
    assert returned['status'] == 'V3_PROSPECTIVE_DRAFT_UNISSUED_INCOMPLETE_AUTHORITY'


def test_r7_two_v3_snapshots_reject_an_unscoped_current_change(monkeypatch, tmp_path):
    old_adapter, pin, raw, candidate, _ = _stub_v3_snapshots(monkeypatch)
    candidate['policy_candidate_body']['rules']['b02_noncredential']['security']['g5_release']['actor'] = 'unapproved'
    changed_raw = json.dumps(candidate, sort_keys=True).encode('utf-8')
    monkeypatch.setattr(m, 'CURRENT_G5_V3_SHA256', m.sha(changed_raw))
    with pytest.raises(ValueError, match='CURRENT_V3_UNSCOPED_CHANGE'):
        m.resolve_v3_snapshots(tmp_path, old_adapter, pin, changed_raw, candidate)


def test_r7_two_v3_snapshots_reject_historic_pin_replacement(monkeypatch, tmp_path):
    old_adapter, pin, raw, candidate, _ = _stub_v3_snapshots(monkeypatch)
    pin['g5_v3_consumer']['git_blob'] = 'e'*40
    with pytest.raises(ValueError, match='HISTORIC_V3_PIN_CONFLICT'):
        m.resolve_v3_snapshots(tmp_path, old_adapter, pin, raw, candidate)


def test_r7_proponent_role_delta_requires_previously_unassigned_historic_role():
    historic = _synthetic_historic_v3()
    historic['policy_candidate_body']['roles']['proponent_and_integrator'] = 'unverified-impostor'
    with pytest.raises(ValueError, match='V3_HISTORIC_ROLE_ALREADY_ASSIGNED'):
        m.reconstruct_current_v3_from_historic(historic)


def test_r7_proponent_role_cannot_preassign_reviewer():
    historic = _synthetic_historic_v3()
    historic['policy_candidate_body']['roles']['functional_reviewer'] = 'unaccepted-reviewer'
    with pytest.raises(ValueError, match='V3_HISTORIC_ROLE_ALREADY_ASSIGNED'):
        m.reconstruct_current_v3_from_historic(historic)
