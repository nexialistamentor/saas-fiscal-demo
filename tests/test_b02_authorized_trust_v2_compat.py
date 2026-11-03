"""B02 V2 compatibility focal, synthetic-only. Never use real founder key."""
from __future__ import annotations
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

SOURCE = Path(__file__).resolve().parents[1]/'app/services/enterprise_b02_authorized_trust_v2.py'
spec = importlib.util.spec_from_file_location('test_b02_v2_appended', SOURCE)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

def can(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def put(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(can(obj));return sha(p.read_bytes())

def fixture(tmp_path,monkeypatch):
    """Construct an entirely synthetic graph; fake signer is not Miguel's key."""
    root=tmp_path/'SUCCESSOR_V3';bundle=root/'BUNDLE_ASSINADO';store=root/'STORE'
    bundle.mkdir(parents=True);store.mkdir(parents=True)
    current='2026-11-03T19:00:00+00:00'
    issued='2026-11-03T18:10:00+00:00'
    end='2026-11-04T18:00:00+00:00'
    before='2026-11-03T17:00:00+00:00'
    win={'valid_from':'2026-11-03T18:00:00+00:00','valid_until':end}
    post={'valid_from':issued,'valid_until':end}
    key=Ed25519PrivateKey.generate()
    der=key.public_key().public_bytes(Encoding.DER,PublicFormat.SubjectPublicKeyInfo)
    monkeypatch.setattr(v,'_V2_PUBLIC_DER_SHA256',sha(der))
    evidence={name: {'id':name, 'test_only':True} for name in v._V2_FILES}
    evidence['institutional.json']={'expected':{'policy_subject':v._V2_SUBJECT},'decisions':[{'decision_id':'d1','record_hash':'1'*64}]}
    evidence['object.json']={'id':'object', 'policy_subject':v._V2_SUBJECT}
    evidence['review.json']={'id':'review', 'accepted':True}
    for name,obj in evidence.items():put(bundle/name,obj)
    entries=[{'path':name,'size':(bundle/name).stat().st_size,'sha256':sha((bundle/name).read_bytes())} for name in v._V2_FILES]
    manifest={'entries':entries}; msha=put(bundle/'manifest.json',manifest)
    monkeypatch.setattr(v,'_V2_MANIFEST_SHA256',msha)
    adoption={'id':'B02-G4-CONTINUIDADE-DOCUMENTAL-V2-ADOCAO-20261103','schema':'SOLVERIS-B02-DOCUMENTARY-CONTINUITY-ADOPTION-V2',
              'decision':{'approved':True,'revoked':False,'signing_authorized':False,'valid_from':before,'valid_until':end},
              'origin_reports':[{'id':'origin-1','sha256':'a'*64},{'id':'origin-2','sha256':'b'*64}],
              'actors':{'author':'author','integrator':'integrator','origin_examiner':'origin'}}
    adsha=put(root/'CONTINUITY_ADOPTION.json',adoption)
    monkeypatch.setattr(v,'_V2_CONTINUITY_ADOPTION_SHA256',adsha)
    d={'domain':'SOLVERIS-B02-GOVERNANCE-DECISION','schema_version':2,'profile':'FOUNDER_SIGNED_REVIEW_BUNDLE_B02_V2',
       'algorithm':'Ed25519','key_fingerprint':sha(der),'adoption_sha256':v._V2_PROFILE_ADOPTION_SHA256,
       'continuity_adoption_sha256':adsha,'signer_policy_id':'SOLVERIS-B02-G4-DOCUMENTARY-LOCAL-SIGNER-V2',
       'manifest_sha256':msha,'policy_subject':v._V2_SUBJECT,'object_sha256':entries[4]['sha256'],
       'review_sha256':entries[-1]['sha256'],'scope':v._V2_SCOPE,'valid_from':win['valid_from'],
       'valid_until':win['valid_until'],'synthetic_only':False,'residual_risk_accepted':True}
    dr=can(d);(bundle/'decision.json').write_bytes(dr)
    monkeypatch.setattr(v,'_V2_DECISION_SHA256',sha(dr))
    sig=key.sign(dr);(bundle/'signature.bin').write_bytes(sig)
    reviewer={'id':'signer-review-1','reviewer_execution':'external-reviewer','outcome':'favoravel','conflicts':[],
              'limitations':['only documentary'], 'no_operational_authority':True,'completed_at':before,
              'signer_source_git_blob':v._V2_SIGNER_GIT_BLOB}
    rh=put(root/'SIGNER_REVIEW.json',reviewer)
    signer={'schema':'SOLVERIS-B02-SIGNER-V2-AUTHORITY-ADOPTION-V1',
            'id':'SOLVERIS-B02-G4-DOCUMENTARY-LOCAL-SIGNER-V2','issuer':'Miguel',
            'status':'adopted','approved':True,'signing_authorized':True,'revoked':False,
            'no_g4_reactivation':True,'no_operational_authority':True,
            'signer_source_git_blob':v._V2_SIGNER_GIT_BLOB,'decision_sha256':sha(dr),
            'manifest_sha256':msha,'continuity_adoption_sha256':adsha,
            'scope':v._V2_SCOPE,'policy_subject':v._V2_SUBJECT,
            'issued_at':before,'valid_from':win['valid_from'],'valid_until':end,
            'review':{'review_sha256':rh,'outcome':'favoravel','reviewer_execution':reviewer['reviewer_execution'],
                      'signer_source_git_blob':v._V2_SIGNER_GIT_BLOB},
            'revocation_confirmation':{'holder':'Miguel','status':'no_known_revocation','confirmed_at':current}}
    ah=put(root/'SIGNER_AUTHORITY.json',signer)
    def store_obj(obj):
        raw=can(obj);h=sha(raw);p=store/'sha256'/h[:2]/(h+'.json');p.parent.mkdir(exist_ok=True,parents=True);p.write_bytes(raw)
        return {'id':obj['id'],'sha256':h}
    head=store_obj({'id':'head1','value':1})
    genesis=store_obj({'id':'genesis1','value':2})
    mandate=store_obj({'id':'origin-m','value':3})
    writer=store_obj({'id':'writer1','value':4})
    report1=store_obj({'id':'origin-1','value':5})
    report2=store_obj({'id':'origin-2','value':6})
    adoption['origin_reports']=[report1,report2];adsha=put(root/'CONTINUITY_ADOPTION.json',adoption)
    # Repin adoption in signed decision and signer authority; resign synthetic.
    monkeypatch.setattr(v,'_V2_CONTINUITY_ADOPTION_SHA256',adsha)
    d['continuity_adoption_sha256']=adsha
    dr=can(d);(bundle/'decision.json').write_bytes(dr);monkeypatch.setattr(v,'_V2_DECISION_SHA256',sha(dr))
    sig=key.sign(dr);(bundle/'signature.bin').write_bytes(sig)
    signer['decision_sha256']=sha(dr);signer['continuity_adoption_sha256']=adsha
    ah=put(root/'SIGNER_AUTHORITY.json',signer)
    snap={'id':'snapshot1','schema':'SOLVERIS-B02-AUTHORIZED-READ-SNAPSHOT-V1',
          'context':{},
          'policy_subject':v._V2_SUBJECT,'revoked':False,'synthetic_only':False,
          'origin_report_bindings':[report1,report2],'origin_mandate_binding':mandate,
          'head_binding':head,'genesis_binding':genesis,'execution_writer_binding':writer,
          'canonical_decisions_sha256':sha(can(evidence['institutional.json']['decisions'])),
          **post}
    sp=store_obj(snap)
    rr={'schema':'SOLVERIS-B02-RECOGNIZED-SUCCESSOR-ROOT-V2','profile':d['profile'],
        'policy_subject':v._V2_SUBJECT,'key_fingerprint':sha(der),
        'decision_sha256':sha(dr),'manifest_sha256':msha,'signature_sha256':sha(sig),
        'synthetic_only':False,'revoked':False,'issued_at':issued,**post,
        'origin_document_scope':['101201900571','101202501245'],
        'no_operational_authority':True,
        'continuity_adoption_binding':{'id':adoption['id'],'sha256':adsha},
        'signer_adoption_binding':{'id':signer['id'],'sha256':ah},
        'signer_review_binding':{'id':reviewer['id'],'sha256':rh},
        'snapshot_binding':sp,'public_key_der_hex':der.hex()}
    rootsha=put(root/'ROOT.json',rr)
    approval={'schema':'SOLVERIS-B02-ROOT-V2-PROVISIONING-ADOPTION-V1', 'issuer':'Miguel',
              'approved':True,'provisioning_authorized':True,'revoked':False,
              'no_operational_authority':True, 'root_sha256':rootsha,'snapshot_sha256':sp['sha256'],
              'decision_sha256':sha(dr),'signer_adoption_sha256':ah,
              'compatibility_review_git_blob':'f'*40,'issued_at':issued,**post}
    ph=put(root/'ROOT_ADOPTION.json',approval)
    pins={'root_sha256':rootsha,'root_adoption_sha256':ph,'snapshot_sha256':sp['sha256'],
          'signer_authority_sha256':ah,'signer_review_sha256':rh,'signature_sha256':sha(sig),
          'compatibility_review_git_blob':'f'*40}
    parser=SimpleNamespace(parse=lambda raw:json.loads(raw),canonical=can)
    def checker(**kwargs):
        assert kwargs['synthetic'] is False
        return {'status':'continuity_v2_conditions_met'}
    def verify():return v._v2_validate_exact(root,pins,now=datetime.fromisoformat(current),
                                              profile=parser,continuity_checker=checker)
    return SimpleNamespace(base=root,bundle=bundle,pins=pins,decision=d,reviewer=reviewer,root=rr,
                           authority=signer,adoption=adoption,snapshot=snap,approval=approval,
                           store=store,verify=verify,now=current,can=can)


def repin_signer_act(f):
    # Rehash dependent unsigned evidence to test semantic refusal, not a stale pin.
    f.pins['signer_authority_sha256']=put(f.base/'SIGNER_AUTHORITY.json',f.authority)
    f.root['signer_adoption_binding']['sha256']=f.pins['signer_authority_sha256']
    f.pins['root_sha256']=put(f.base/'ROOT.json',f.root)
    f.approval['root_sha256']=f.pins['root_sha256']
    f.approval['signer_adoption_sha256']=f.pins['signer_authority_sha256']
    f.pins['root_adoption_sha256']=put(f.base/'ROOT_ADOPTION.json',f.approval)

def test_v2_synthetic_graph_only_no_runtime_provision(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    ans=f.verify()
    assert ans['status']=='V2_SIGNED_CUSTODY_VALIDATED_NOT_RUNTIME_PROVISIONED'
    assert ans['runtime_provisioned'] is False and ans['fiscal_authority'] is False
    assert ans['decision_sha256']==v._V2_DECISION_SHA256

def test_v2_rejects_math_signature_tamper(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    s=f.bundle/'signature.bin';raw=bytearray(s.read_bytes());raw[0]^=1;s.write_bytes(raw)
    f.pins['signature_sha256']=sha(s.read_bytes())
    f.root['signature_sha256']=f.pins['signature_sha256']
    f.pins['root_sha256']=put(f.base/'ROOT.json',f.root)
    f.approval['root_sha256']=f.pins['root_sha256']
    f.pins['root_adoption_sha256']=put(f.base/'ROOT_ADOPTION.json',f.approval)
    with pytest.raises(ValueError,match='ED25519_SIGNATURE_INVALID'): f.verify()

def test_v2_rejects_decision_tamper(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch);p=f.bundle/'decision.json'
    p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises(ValueError,match='DECISION_OR_MANIFEST_PIN'):f.verify()

def test_v2_rejects_incompatible_version_even_if_rehashed(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch);f.decision['schema_version']=1
    raw=can(f.decision);(f.bundle/'decision.json').write_bytes(raw)
    monkeypatch.setattr(v,'_V2_DECISION_SHA256',sha(raw))
    with pytest.raises(ValueError,match='V2_SCHEMA_SCOPE_OR_VERSION'):f.verify()

def test_v2_rejects_revoked_signer_authority_even_if_pinned(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch); f.authority['revoked']=True
    repin_signer_act(f)
    with pytest.raises(ValueError,match='SIGNER_ADOPTION_INVALID'): f.verify()

def test_v2_rejects_unadopted_signer(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch);f.authority['signing_authorized']=False
    repin_signer_act(f)
    with pytest.raises(ValueError,match='SIGNER_ADOPTION_INVALID'):f.verify()

def test_v2_rejects_snapshot_tamper(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    h=f.pins['snapshot_sha256'];p=f.store/'sha256'/h[:2]/(h+'.json')
    p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises(ValueError,match='STORE_PIN_DIVERGENCE'):f.verify()

def test_v2_rejects_root_pin_missing(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch);f.pins['root_sha256']=None
    with pytest.raises(ValueError,match='COMPETENT_DEPLOYMENT_PINS_REQUIRED'):f.verify()

def test_v2_rejects_root_adoption_withdrawn(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch);f.approval['approved']=False
    f.pins['root_adoption_sha256']=put(f.base/'ROOT_ADOPTION.json',f.approval)
    with pytest.raises(ValueError,match='COMPETENT_ROOT_ADOPTION_REQUIRED'):f.verify()

def test_v2_rejects_expired_decision(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    old=datetime.fromisoformat('2026-11-04T18:01:00+00:00')
    with pytest.raises(ValueError,match='V2_DECISION_WINDOW'):
        v._v2_validate_exact(f.base,f.pins,now=old,profile=SimpleNamespace(parse=lambda raw:json.loads(raw),canonical=can),
                            continuity_checker=lambda **k: {'status':'continuity_v2_conditions_met'})

def test_v2_rejects_proof_byte_tamper(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch);p=f.bundle/'proofs.json'
    p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises(ValueError,match='MANIFEST_EVIDENCE_BYTES_CHANGED'):f.verify()

def test_v2_root_after_signature_allowed_without_backdate(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    assert f.verify()['runtime_provisioned'] is False
    f.approval['valid_from']='2026-11-03T18:00:00+00:00'
    # The approval was issued at 18:10. A 18:00 effective start is retroactive.
    f.pins['root_adoption_sha256']=put(f.base/'ROOT_ADOPTION.json',f.approval)
    with pytest.raises(ValueError,match='ROOT_ADOPTION_NOT_PROSPECTIVE'):f.verify()

def test_v1_entrypoints_not_part_of_v2_append():
    code=SOURCE.read_text()
    assert 'def check_payload(' not in code and 'def activate_for_process(' not in code
    assert 'def activate_successor_for_process(' not in code

def test_v2_rejects_revoked_root_even_if_all_hashes_are_repinned(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    f.root['revoked']=True
    f.pins['root_sha256']=put(f.base/'ROOT.json',f.root)
    f.approval['root_sha256']=f.pins['root_sha256']
    f.pins['root_adoption_sha256']=put(f.base/'ROOT_ADOPTION.json',f.approval)
    with pytest.raises(ValueError,match='AUTHORITY_WINDOW_OR_REVOCATION'):f.verify()

def test_v2_rejects_wrong_scope_even_if_rehashed(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    f.decision['scope']=v._V2_SCOPE[:-1]+'Z'
    raw=can(f.decision)
    (f.bundle/'decision.json').write_bytes(raw)
    monkeypatch.setattr(v,'_V2_DECISION_SHA256',sha(raw))
    with pytest.raises(ValueError,match='V2_SCHEMA_SCOPE_OR_VERSION'):f.verify()

def test_v2_snapshot_v1_exact_contract_without_issued_at(tmp_path,monkeypatch):
    # Matches enterprise_b02_founder_runtime._resolve_history exact V1 fields.
    f=fixture(tmp_path,monkeypatch)
    assert set(f.snapshot)==v._V2_SNAPSHOT_V1_FIELDS
    assert 'issued_at' not in f.snapshot
    assert f.verify()['runtime_provisioned'] is False


def test_v2_rejects_v1_snapshot_extra_issued_at_even_rehashed(tmp_path,monkeypatch):
    # Repinning never converts an incompatible V1 snapshot into an admissible one.
    f=fixture(tmp_path,monkeypatch)
    obj=dict(f.snapshot,issued_at=f.root['issued_at'])
    raw=can(obj);h=sha(raw)
    dest=f.store/'sha256'/h[:2]/(h+'.json')
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(raw)
    f.root['snapshot_binding']={'id':obj['id'],'sha256':h}
    f.pins['snapshot_sha256']=h
    f.pins['root_sha256']=put(f.base/'ROOT.json',f.root)
    f.approval['root_sha256']=f.pins['root_sha256']
    f.approval['snapshot_sha256']=h
    f.pins['root_adoption_sha256']=put(f.base/'ROOT_ADOPTION.json',f.approval)
    with pytest.raises(ValueError,match='SNAPSHOT_SCHEMA_COMPATIBILITY'):
        f.verify()


# Focal successor signer alignment only; the 15 earlier compatibility cases
# remain untouched. Synthetic graph != issuer adoption or live deployment.
def test_focal_same_adoption_midwindow_accepted_by_v2_consumer(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    assert v._V2_SIGNER_GIT_BLOB=='0a86ec5512e843fd47c09fcfa5a0a36014819db7'
    # The exact same canonical SIGNER_AUTHORITY.json can be verified by the
    # signer via the owner-issued GitHub PR #28 record; the consumer checks
    # its SHA against the separately adopted deployment ROOT.
    f.authority['issued_at']='2026-11-03T18:05:00+00:00'
    f.authority['valid_from']='2026-11-03T18:08:00+00:00'
    repin_signer_act(f)
    actual=(f.base/'SIGNER_AUTHORITY.json').read_bytes()
    assert sha(actual)==f.pins['signer_authority_sha256']
    assert f.authority['signer_source_git_blob']==v._V2_SIGNER_GIT_BLOB
    assert f.verify()['status']=='V2_SIGNED_CUSTODY_VALIDATED_NOT_RUNTIME_PROVISIONED'


def test_focal_future_signer_adoption_rejected_even_if_repinned(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    f.authority['issued_at']='2026-11-03T18:40:00+00:00'
    f.authority['valid_from']='2026-11-03T19:10:00+00:00'
    repin_signer_act(f)
    with pytest.raises(ValueError,match='AUTHORITY_WINDOW_OR_REVOCATION'):
        f.verify()


def test_focal_expired_signer_adoption_rejected_even_if_repinned(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    f.authority['valid_until']='2026-11-03T18:59:00+00:00'
    repin_signer_act(f)
    with pytest.raises(ValueError,match='AUTHORITY_WINDOW_OR_REVOCATION'):
        f.verify()


def test_focal_other_signer_blob_rejected_even_if_repinned(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    f.authority['signer_source_git_blob']='5fd8ed57feb818e6500b74604524e090dce1b011'
    repin_signer_act(f)
    with pytest.raises(ValueError,match='SIGNER_ADOPTION_INVALID'):
        f.verify()


def test_focal_backdated_signer_adoption_rejected_even_if_repinned(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    f.authority['issued_at']='2026-11-03T18:05:00+00:00'
    f.authority['valid_from']='2026-11-03T18:00:00+00:00'
    repin_signer_act(f)
    with pytest.raises(ValueError,match='SIGNER_ADOPTION_NOT_PROSPECTIVE'):
        f.verify()
