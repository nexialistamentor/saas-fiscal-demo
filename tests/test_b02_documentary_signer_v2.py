"""Signer-only synthetic tests. No G4/V2/R4/A2 suites or real keys executed."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import shutil
import hashlib
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization as S

spec=importlib.util.spec_from_file_location('b02signerv2',Path(__file__).with_name('b02_documentary_signer_v2.py'))
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
NOW=datetime(2026,11,4,16,tzinfo=timezone.utc)
START='2026-11-04T15:00:00+00:00'
END='2026-11-05T15:00:00+00:00'


def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def write(folder,name,obj):
    data=canonical(obj);(folder/name).write_bytes(data);return s.sha(data)


def fixture(tmp_path,monkeypatch):
    # Synthetic only: the historical helper itself is not modified or shipped.
    import json as _json
    from cryptography.hazmat.primitives import serialization as _S
    def parse(raw):
        obj=_json.loads(raw); assert canonical(obj)==raw
        return obj
    def public(path):
        raw=Path(path).read_bytes()
        return _S.load_der_public_key(raw),raw
    monkeypatch.setattr(s,'load_legacy', lambda _path: SimpleNamespace(parse=parse,public=public))
    monkeypatch.setattr(s,'FP','')
    key=Ed25519PrivateKey.generate() # synthetic test only: not a real signer or user key
    der=key.public_key().public_bytes(S.Encoding.DER,S.PublicFormat.SubjectPublicKeyInfo)
    pub=tmp_path/'synthetic-public.der';pub.write_bytes(der)
    monkeypatch.setattr(s,'FP',s.sha(der))
    folder=tmp_path/'bundle';folder.mkdir()
    limits=('2026-11-03T11:00:00+00:00','2026-11-15T00:00:00+00:00')
    object_file={'policy_subject':s.SUBJECT,'documents':{'a':'a'*64,'b':'b'*64}}
    review={'id':'synthetic-review','object_sha256':s.sha(canonical(object_file))}
    origin_pin=[]; proof={}
    for i in (1,2):
        mandate={'id':'origin','valid_from':limits[0],'valid_until':limits[1], 'revoked':False}
        mhash=s.sha(canonical(mandate));proof[mhash]=mandate
        report={'outcome':'favoravel','revoked':False,'synthetic_only':False,
                'valid_from':limits[0],'valid_until':limits[1],
                'mandate_binding':{'sha256':mhash}}
        rhash=s.sha(canonical(report));proof[rhash]=report
        origin_pin.append({'id':f'r{i}','sha256':rhash})
    entries=[]
    for name in s.FILES:
        if name=='object.json':val=object_file
        elif name=='review.json':val=review
        elif name=='mandates.json': val={'mandates':[{'role':role,'accepted':True,'revoked':False,
            'valid_from':limits[0],'valid_until':limits[1]} for role in ('reviewer','author','integrator')]}
        elif name=='proofs.json':val=proof
        elif name=='institutional.json':val={'expected':{},'decisions':[]}
        else:val={'id':name}
        b=canonical(val);(folder/name).write_bytes(b)
        entries.append({'path':name,'size':len(b),'sha256':s.sha(b)})
    manifest_hash=write(folder,'manifest.json',{'entries':entries})
    adoption={'schema':'SOLVERIS-B02-DOCUMENTARY-CONTINUITY-ADOPTION-V2',
              'id':'B02-G4-CONTINUIDADE-DOCUMENTAL-V2-ADOCAO-20261103',
              'decision':{'valid_from':limits[0],'valid_until':limits[1]},
              'actors':{'author':'separate-author','integrator':'separate-integrator',
                        'origin_examiner':'separate-origin-examiner'},
              'origin_reports':origin_pin}
    adopted=tmp_path/'adoption.json';adopted.write_bytes(canonical(adoption))
    monkeypatch.setattr(s,'CONTINUITY_SHA256',s.sha(adopted.read_bytes()))
    fields={'domain':s.DOMAIN,'schema_version':2,'profile':s.PROFILE,'algorithm':'Ed25519',
            'key_fingerprint':s.FP,'adoption_sha256':s.V1_ADOPTION,
            'continuity_adoption_sha256':s.CONTINUITY_SHA256,'signer_policy_id':s.SIGNER_ID,
            'manifest_sha256':manifest_hash,'policy_subject':s.SUBJECT,
            'object_sha256':s.sha(canonical(object_file)), 'review_sha256':s.sha(canonical(review)),
            'scope':s.SCOPE,'valid_from':START,'valid_until':END,'synthetic_only':False,
            'residual_risk_accepted':True}
    dh=write(folder,'decision.json',fields)
    code_blob=s.git_blob(Path(s.__file__).read_bytes())
    report={'reviewer_execution':'independent-reviewer','outcome':'favoravel',
            'signer_source_git_blob':code_blob,'conflicts':[],
            'limitations':['signer code review only'], 'no_operational_authority':True,
            'completed_at':'2026-11-03T11:30:00+00:00'}
    review_file=tmp_path/'signer_review.json';review_file.write_bytes(canonical(report))
    authority={'schema':'SOLVERIS-B02-SIGNER-V2-AUTHORITY-ADOPTION-V1','id':s.SIGNER_ID,
               'issuer':'Miguel','approved':True,'signing_authorized':True,'status':'adopted',
               'revoked':False,'issued_at':'2026-11-03T12:00:00+00:00',
               'valid_from':'2026-11-03T13:00:00+00:00','valid_until':limits[1],
               'policy_subject':s.SUBJECT,'scope':s.SCOPE,
               'continuity_adoption_sha256':s.CONTINUITY_SHA256,
               'decision_sha256':dh,'manifest_sha256':manifest_hash,
               'signer_source_git_blob':code_blob,
               'review':{'reviewer_execution':'independent-reviewer','review_sha256':s.sha(review_file.read_bytes()),
                         'signer_source_git_blob':code_blob,'outcome':'favoravel'},
               'revocation_confirmation':{'holder':'Miguel','status':'no_known_revocation',
                                           'confirmed_at':'2026-11-04T15:30:00+00:00'},
               'no_g4_reactivation':True,'no_operational_authority':True}
    au=tmp_path/'authority.json';au.write_bytes(canonical(authority))
    args=SimpleNamespace(legacy='historical-pinned-read-only',bundle=str(folder),public=str(pub),fingerprint=s.FP,
         approved_decision_sha256=dh,continuity_adoption=str(adopted),
         signer_authority=str(au),signer_review=str(review_file),approved_signer_authority_sha256=s.sha(au.read_bytes()),
         reviewed_signer_git_blob=code_blob,repo=str(tmp_path),mode='preflight')
    checker=lambda **kw:{'status':'continuity_v2_conditions_met'}
    return args,fields,authority,checker


def test_november_exact_24h_authorized_synthetic_preflight(tmp_path,monkeypatch):
    args,fields,authority,check=fixture(tmp_path,monkeypatch)
    r=s.validate(args,now=NOW,v2_checker=check)
    assert r['decision_raw']==(Path(args.bundle)/'decision.json').read_bytes()
    assert s.git_blob(Path(s.__file__).read_bytes())==r['signer_source_git_blob']


def test_over_24h_rejected_even_with_fully_updated_authority(tmp_path,monkeypatch):
    args,fields,authority,check=fixture(tmp_path,monkeypatch)
    fields['valid_until']='2026-11-05T15:00:01+00:00'
    args.approved_decision_sha256=write(Path(args.bundle),'decision.json',fields)
    authority['decision_sha256']=args.approved_decision_sha256
    args.approved_signer_authority_sha256=write(tmp_path,'authority.json',authority)
    with pytest.raises(ValueError,match='WINDOW_OVER_24H_OR_EMPTY'):
        s.validate(args,now=NOW,v2_checker=check)


def test_incompatible_authority_rejected_even_with_rehashed_decision(tmp_path,monkeypatch):
    args,fields,authority,check=fixture(tmp_path,monkeypatch)
    fields['policy_subject']={'policy_id':'WRONG'}
    args.approved_decision_sha256=write(Path(args.bundle),'decision.json',fields)
    authority['decision_sha256']=args.approved_decision_sha256
    args.approved_signer_authority_sha256=write(tmp_path,'authority.json',authority)
    with pytest.raises(ValueError,match='DECISION_AUTHORITY_INCOMPATIBLE'):
        s.validate(args,now=NOW,v2_checker=check)


def test_modified_bytes_fail_even_when_canonical(tmp_path,monkeypatch):
    args,fields,authority,check=fixture(tmp_path,monkeypatch)
    fields['valid_from']='2026-11-04T15:00:01+00:00'
    write(Path(args.bundle),'decision.json',fields)
    with pytest.raises(ValueError,match='DECISION_BYTES_NOT_APPROVED'):
        s.validate(args,now=NOW,v2_checker=check)


def test_origin_mandate_window_cannot_extend(tmp_path,monkeypatch):
    args,fields,authority,check=fixture(tmp_path,monkeypatch)
    ar=Path(args.continuity_adoption)
    adoption=json.loads(ar.read_text());pin=adoption['origin_reports'][0]
    proofs=json.loads((Path(args.bundle)/'proofs.json').read_text())
    report=proofs[pin['sha256']];mandate=proofs[report['mandate_binding']['sha256']]
    mandate['valid_until']='2026-11-05T14:00:00+00:00'
    new_mhash=s.sha(canonical(mandate));proofs[new_mhash]=mandate
    report['mandate_binding']['sha256']=new_mhash
    new_rhash=s.sha(canonical(report));proofs[new_rhash]=report
    pin['sha256']=new_rhash
    # Directly exercise the *focal* temporal invariant, not historical V2 suite.
    with pytest.raises(ValueError,match='ORIGIN_MANDATE_DECISION_WINDOW'):
        s.check_window(s.utc(START),s.utc(END),NOW,adoption,{'mandates.json':{'mandates':[
            {'accepted':True,'revoked':False,'valid_from':'2026-11-03T11:00:00+00:00',
             'valid_until':'2026-11-15T00:00:00+00:00'}]},'proofs.json':proofs})


# Focal correction only: GitHub PR #28 is an independent issuer-controlled
# source; these fixtures mock its responses. No real key or live approval.
def source_bound_fixture(tmp_path, monkeypatch, *, late_adoption=False):
    args, fields, authority, checker = fixture(tmp_path, monkeypatch)
    if late_adoption:
        # Founder adoption may take effect during (not retroactive to the start of) the original 24h window.
        authority['issued_at'] = '2026-11-04T15:10:00+00:00'
        authority['valid_from'] = '2026-11-04T15:30:00+00:00'
        args.approved_signer_authority_sha256 = write(tmp_path, 'authority.json', authority)
    monkeypatch.setattr(s, 'APPROVED_DECISION_SHA256', args.approved_decision_sha256)
    monkeypatch.setattr(s, 'APPROVED_MANIFEST_SHA256', fields['manifest_sha256'])
    monkeypatch.setattr(s, 'ORIGINAL_WINDOW_START', START.replace('+00:00', 'Z'))
    monkeypatch.setattr(s, 'ORIGINAL_WINDOW_END', END.replace('+00:00', 'Z'))
    body = ('Miguel: 1.118 bytes, ' + s.APPROVED_DECISION_SHA256 + ', ' +
            s.APPROVED_MANIFEST_SHA256 + ', ' + s.ORIGINAL_SIGNER_GIT_BLOB +
            ', ' + s.FP + ', ' + s.ORIGINAL_WINDOW_START + ', ' + s.ORIGINAL_WINDOW_END)
    local_auth = tmp_path / 'original_owner_authorization.txt'
    local_auth.write_bytes(body.encode('utf-8'))
    args.authorization = str(local_auth)
    args.authorization_sha256 = s.sha(local_auth.read_bytes())
    def owner_comment(comment_id, text, created_at='2026-11-03T12:15:00Z'):
        return {'id': comment_id, 'user': {'id':s.GITHUB_OWNER_ID,
                   'login':s.GITHUB_OWNER_LOGIN}, 'author_association':'OWNER',
                'issue_url':s.GITHUB_ISSUE_API, 'created_at':created_at,
                'updated_at':created_at, 'body':text}
    original = owner_comment(s.ORIGINAL_AUTHORIZATION_COMMENT_ID,body)
    issuer_adoption = owner_comment(777777,canonical(authority).decode(),
         created_at='2026-11-04T15:20:00Z' if late_adoption else '2026-11-03T12:15:00Z')
    def source(url):
        if url.endswith(str(s.ORIGINAL_AUTHORIZATION_COMMENT_ID)):
            return original
        if '/comments?per_page=100&page=' in url:
            return [issuer_adoption]
        raise ValueError('Unexpected GitHub source URL')
    monkeypatch.setattr(s,'_github_json',source)
    return args,fields,authority,checker,local_auth


def test_focal_external_issuer_acts_consumed_without_changing_signer_blob(tmp_path,monkeypatch):
    immutable_before = s.git_blob(Path(s.__file__).read_bytes())
    args,fields,authority,checker,auth_file=source_bound_fixture(
        tmp_path,monkeypatch,late_adoption=True)
    validated = s.validate(args,now=NOW,v2_checker=checker)
    actual_authorization = s.validate_signature_authorization(
        args,validated['decision_raw'],validated['signer_source_git_blob'])
    assert actual_authorization == s.sha(auth_file.read_bytes())
    assert validated['signer_source_git_blob'] == authority['signer_source_git_blob']
    assert immutable_before == s.git_blob(Path(s.__file__).read_bytes())


def test_focal_rehashed_replaced_adoption_rejected_against_external_issuer(tmp_path,monkeypatch):
    args,fields,authority,checker,auth_file=source_bound_fixture(tmp_path,monkeypatch)
    changed = dict(authority)
    changed['revocation_confirmation'] = dict(changed['revocation_confirmation'], holder='SUBSTITUTED')
    args.approved_signer_authority_sha256 = write(tmp_path,'authority.json',changed)
    with pytest.raises(ValueError, match='SIGNER_AUTHORITY_NOT_INDEPENDENTLY_PINNED'):
        s.validate(args,now=NOW,v2_checker=checker)


def test_focal_rehashed_replaced_authorization_rejected_against_original_owner_act(tmp_path,monkeypatch):
    args,fields,authority,checker,auth_file=source_bound_fixture(tmp_path,monkeypatch)
    validated=s.validate(args,now=NOW,v2_checker=checker)
    auth_file.write_bytes(auth_file.read_bytes()+b' SUBSTITUTED')
    args.authorization_sha256 = s.sha(auth_file.read_bytes())
    with pytest.raises(ValueError, match='EXACT_SIGNATURE_AUTHORIZATION_REQUIRED'):
        s.validate_signature_authorization(
            args,validated['decision_raw'],validated['signer_source_git_blob')
