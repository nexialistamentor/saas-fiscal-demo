"""B02: Ed25519 signer successor V2. CANDIDATE pending segregated review/adoption.

Never modifies historical crypto_local.py, G4, DB, ROOT or 7 evidence objects.
No private keys ever leave the local Windows custody. No automatic approval.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import getpass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import serialization as S
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

LEGACY_SHA256 = '45f32cae528eff288347f5e8f3065854f9f9bc1936bd3563bd847074c069b25c'
CONTINUITY_SHA256 = 'd0cd1765ea2ef4870a530f8e5367cdde8550b5a60a3a70cb294f9d80678f7fa8'
V1_ADOPTION = 'd1fcd244129e669fc5a37c79dc1fc77f677b1cb0e0ceaf06d4cbe9bf9740d911'
FP = '6f0ede1267a208505b2443d765cf97f2206759049f938a1d95d92a86c4c5d63c'
POLICY = '05ede0f8c8788b93d41e451288efd88d91614a560bdd2191a115f0d736c4fe2a'
SUBJECT = {'policy_type':'activation_authority','policy_id':'SOLVERIS-B02-SEFA-PR-DOCUMENTARY-AUTHORITY',
           'policy_version':1,'policy_hash':POLICY}
PROFILE='FOUNDER_SIGNED_REVIEW_BUNDLE_B02_V2'
DOMAIN='SOLVERIS-B02-GOVERNANCE-DECISION'
SIGNER_ID='SOLVERIS-B02-G4-DOCUMENTARY-LOCAL-SIGNER-V2'
# Existing PR #28 owner-issued approval is the independent authority source.
# The signer never accepts a hash or trust-source location from the CLI.
# The final signer blob can be adopted AFTER this source is committed, without
# changing these bytes or inventing another repository governance circuit.
GITHUB_ISSUE_API = 'https://api.github.com/repos/nexialistamentor/saas-fiscal-demo/issues/28'
GITHUB_OWNER_LOGIN = 'nexialistamentor'
GITHUB_OWNER_ID = 192223328
ORIGINAL_AUTHORIZATION_COMMENT_ID = 6605195432
ORIGINAL_SIGNER_GIT_BLOB = '5fd8ed57feb818e6500b74604524e090dce1b011'
APPROVED_DECISION_SHA256 = 'd3602168c53debd10421aa83d1e980c632870b660be18a451d5b5a3d998c6520'
APPROVED_MANIFEST_SHA256 = '99d1a424015fc03a5ece71e84341eee748fd0b2fc1bebd238f9df2ede253a6c1'
ORIGINAL_WINDOW_START = '2026-11-03T18:00:00Z'
ORIGINAL_WINDOW_END = '2026-11-04T18:00:00Z'
SCOPE='SEFA_PR_B02_DOCUMENTAL_AUTHENTICATION_ONLY'
FILES=('execution.json','history.json','institutional.json','mandates.json',
       'object.json','proofs.json','review.json')
DECISION_KEYS={ 'domain','schema_version','profile','algorithm','key_fingerprint','adoption_sha256',
               'continuity_adoption_sha256','signer_policy_id','manifest_sha256','policy_subject',
               'object_sha256','review_sha256','scope','valid_from','valid_until',
               'synthetic_only','residual_risk_accepted'}
AUTHORITY_KEYS={'schema','id','issuer','status','approved','signing_authorized','revoked',
                'issued_at','valid_from','valid_until','policy_subject','scope',
                'continuity_adoption_sha256','decision_sha256','manifest_sha256',
                'signer_source_git_blob','review','revocation_confirmation',
                'no_g4_reactivation','no_operational_authority'}


def stop(code):
    raise ValueError('STOP_B02_SIGNER_V2_' + code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git_blob(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()



def _github_json(url):
    """Read only the fixed GitHub PR #28 authority source over HTTPS.

    Network failure is a STOP, never an offline/self-pin fallback. No GitHub
    credentials, private key material, or bundle bytes are transmitted.
    """
    expect(url.startswith(GITHUB_ISSUE_API + '/comments') or
           url == (GITHUB_ISSUE_API.rsplit('/issues/', 1)[0] +
                   '/issues/comments/' + str(ORIGINAL_AUTHORIZATION_COMMENT_ID)),
           'AUTHORITY_SOURCE_NOT_FIXED')
    try:
        request = Request(url, headers={'Accept': 'application/vnd.github+json',
                                        'User-Agent': 'SOLVERIS-B02-signer-V2-readonly'})
        with urlopen(request, timeout=12) as response:
            expect(response.geturl() == url and response.status == 200,
                   'AUTHORITY_SOURCE_REDIRECT_OR_STATUS')
            raw = response.read(1048577)
        expect(len(raw) <= 1048576, 'AUTHORITY_SOURCE_OVERSIZE')
        return json.loads(raw)
    except (OSError, ValueError) as exc:
        stop('AUTHORITY_SOURCE_UNAVAILABLE_' + type(exc).__name__)


def _is_owner_comment(item):
    return (type(item) is dict and type(item.get('user')) is dict and
            item['user'].get('id') == GITHUB_OWNER_ID and
            item['user'].get('login') == GITHUB_OWNER_LOGIN and
            item.get('author_association') == 'OWNER' and
            item.get('issue_url') == GITHUB_ISSUE_API and
            item.get('created_at') == item.get('updated_at') and
            type(item.get('body')) is str)


def _original_authorization(decision_raw):
    """Consume Miguel's preserved 1,118-byte authorization in PR #28.

    This original act authorizes the ORIGINAL source blob only. A separately
    issued, owner-authenticated signer adoption must bind the *new* blob.
    """
    url = (GITHUB_ISSUE_API.rsplit('/issues/', 1)[0] + '/issues/comments/' +
           str(ORIGINAL_AUTHORIZATION_COMMENT_ID))
    item = _github_json(url)
    expect(_is_owner_comment(item) and
           item.get('id') == ORIGINAL_AUTHORIZATION_COMMENT_ID,
           'ORIGINAL_AUTHORIZATION_SOURCE_INVALID')
    body = item['body']
    expect(sha(decision_raw) == APPROVED_DECISION_SHA256 and
           all(token in body for token in (
               'Miguel', '1.118 bytes', APPROVED_DECISION_SHA256,
               APPROVED_MANIFEST_SHA256, ORIGINAL_SIGNER_GIT_BLOB, FP,
               ORIGINAL_WINDOW_START, ORIGINAL_WINDOW_END)),
           'ORIGINAL_AUTHORIZATION_WRONG_BYTES_OR_SCOPE')
    decision = json.loads(decision_raw)
    expect(sha(decision_raw) == APPROVED_DECISION_SHA256 and
           decision.get('manifest_sha256') == APPROVED_MANIFEST_SHA256 and
           utc(decision['valid_from']) == utc(ORIGINAL_WINDOW_START) and
           utc(decision['valid_until']) == utc(ORIGINAL_WINDOW_END),
           'ORIGINAL_AUTHORIZATION_DECISION_WINDOW_DIVERGENT')
    return body.encode('utf-8')


def _source_pinned_signer_authority(authority_raw, authority):
    """Bind only the owner-issued adoption applicable to THIS exact signer.

    Historical adoptions with the same schema/id but a different signer blob
    remain valid historical evidence and cannot create false duplicate matches.
    No CLI value or local authority body selects the applicable signer.
    """
    current_blob = git_blob(Path(__file__).read_bytes())
    applicable = []
    for page in range(1, 11):
        url = GITHUB_ISSUE_API + f'/comments?per_page=100&page={page}'
        items = _github_json(url)
        expect(type(items) is list and len(items) <= 100,
               'SIGNER_AUTHORITY_SOURCE_INVALID')
        for item in items:
            if not _is_owner_comment(item):
                continue
            body = item['body']
            try:
                obj = json.loads(body)
            except (UnicodeError, ValueError):
                continue
            if not (type(obj) is dict and
                    obj.get('schema') == 'SOLVERIS-B02-SIGNER-V2-AUTHORITY-ADOPTION-V1' and
                    obj.get('id') == SIGNER_ID and
                    obj.get('signer_source_git_blob') == current_blob):
                # Preserve unrelated and predecessor adoptions without
                # accepting them as authority for the currently running code.
                continue
            expect(canonical_for_hash(obj) == body.encode('utf-8'),
                   'SIGNER_AUTHORITY_SOURCE_NOT_CANONICAL')
            applicable.append((item, body.encode('utf-8'), obj))
        if len(items) < 100:
            break
    else:
        stop('SIGNER_AUTHORITY_SOURCE_PAGINATION_LIMIT')
    # Count *all* owner-authenticated acts for this signer before examining
    # validity; never choose newest or silently ignore a conflicting/revoked act.
    expect(len(applicable) == 1, 'COMPETENT_SIGNER_ADOPTION_NOT_UNIQUELY_ISSUED')
    item, source_raw, source = applicable[0]
    expect(source_raw == authority_raw and source == authority and
           source.get('signer_source_git_blob') == current_blob,
           'SIGNER_AUTHORITY_NOT_INDEPENDENTLY_PINNED')
    expect(source.get('issuer') == 'Miguel' and
           source.get('policy_subject') == SUBJECT and
           source.get('scope') == SCOPE and
           source.get('decision_sha256') == APPROVED_DECISION_SHA256 and
           source.get('manifest_sha256') == APPROVED_MANIFEST_SHA256 and
           source.get('approved') is True and
           source.get('signing_authorized') is True and
           source.get('status') == 'adopted' and
           source.get('revoked') is False and
           source.get('no_operational_authority') is True and
           source.get('no_g4_reactivation') is True,
           'SIGNER_AUTHORITY_APPLICABLE_ACT_INVALID')
    issued = utc(source['issued_at'])
    effective = utc(source['valid_from'])
    end = utc(source['valid_until'])
    expect(utc(ORIGINAL_WINDOW_START) <= effective < end <= utc(ORIGINAL_WINDOW_END) and
           issued <= utc(item['created_at']) <= effective,
           'SIGNER_AUTHORITY_CHRONOLOGY_INVALID')
    return sha(source_raw)


def validate_signature_authorization(args, decision_raw, signer_blob):
    """Consume the original owner authorization + the new owner-issued adoption.

    CLI files/hashes may corroborate but never choose the two trust anchors.
    """
    source_raw = _original_authorization(decision_raw)
    trusted = sha(source_raw)
    if getattr(args, 'authorization', None):
        path = Path(args.authorization)
        expect(path.is_file() and not path.is_symlink() and
               path.read_bytes() == source_raw, 'EXACT_SIGNATURE_AUTHORIZATION_REQUIRED')
    if getattr(args, 'authorization_sha256', None):
        expect(args.authorization_sha256 == trusted,
               'EXACT_SIGNATURE_AUTHORIZATION_REQUIRED')
    # The issuer's NEW, independently sourced signer adoption is what extends
    # the original decision-byte approval to the new reviewed signer blob.
    auth_raw = Path(args.signer_authority).read_bytes()
    expect(sha(auth_raw) == _source_pinned_signer_authority(
        auth_raw, json.loads(auth_raw)), 'SIGNER_AUTHORITY_NOT_INDEPENDENTLY_PINNED')
    expect(json.loads(auth_raw).get('signer_source_git_blob') == signer_blob and
           json.loads(auth_raw).get('decision_sha256') == APPROVED_DECISION_SHA256 and
           json.loads(auth_raw).get('signing_authorized') is True,
           'SIGNATURE_AUTHORIZATION_UPDATED_BLOB_NOT_ISSUED')
    return trusted

def utc(value):
    if type(value) is not str: stop('DATE_FORMAT')
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:
        stop('DATE_FORMAT')
    if d.tzinfo is None or d.utcoffset() != timedelta(0): stop('DATE_UTC_REQUIRED')
    return d.astimezone(timezone.utc)


def expect(cond, code):
    if not cond: stop(code)


def load_legacy(path):
    path=Path(path)
    expect(path.is_file() and not path.is_symlink(), 'HISTORICAL_SIGNER_MISSING')
    expect(sha(path.read_bytes())==LEGACY_SHA256,'HISTORICAL_SIGNER_PIN_MISMATCH')
    spec=importlib.util.spec_from_file_location('crypto_local_historical_pinned',path)
    c=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c)
    return c


def read(c,path):
    p=Path(path)
    expect(p.is_file() and not p.is_symlink(),'FILE_MISSING_OR_SYMLINK')
    raw=p.read_bytes()
    return raw,c.parse(raw)


def check_window(start,end,now, adoption, evidence):
    """Narrow decision interval must be contained in ALL four mandates and two reports."""
    expect(start<end and end-start<=timedelta(hours=24),'WINDOW_OVER_24H_OR_EMPTY')
    adot=adoption['decision']
    expect(utc(adot['valid_from'])<=start and end<=utc(adot['valid_until']), 'OUTSIDE_DOCUMENTARY_ADOPTION')
    expect(start<=now<end,'OUTSIDE_SIGNING_WINDOW')
    for m in evidence['mandates.json']['mandates']:
        expect(m.get('accepted') is True and m.get('revoked') is False and
               utc(m['valid_from'])<=start and end<=utc(m['valid_until']), 'ROLE_MANDATE_DECISION_WINDOW')
    proofs=evidence['proofs.json']
    for pin in adoption['origin_reports']:
        report=proofs.get(pin['sha256'])
        expect(isinstance(report,dict) and report.get('outcome')=='favoravel' and
               report.get('revoked') is False and report.get('synthetic_only') is False and
               sha(canonical_for_hash(report))==pin['sha256'], 'ORIGIN_REPORT_INVALID')
        mandate=proofs.get(report['mandate_binding']['sha256'])
        expect(isinstance(mandate,dict) and mandate.get('revoked') is False and
               sha(canonical_for_hash(mandate))==report['mandate_binding']['sha256'], 'ORIGIN_MANDATE_INVALID')
        expect(utc(mandate['valid_from'])<=start and end<=utc(mandate['valid_until']),
               'ORIGIN_MANDATE_DECISION_WINDOW')
        expect(utc(report['valid_from'])<=start and end<=utc(report['valid_until']),
               'ORIGIN_REPORT_DECISION_WINDOW')


def canonical_for_hash(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def validate(args, *, now=None, v2_checker=None):
    """Read-only fail-closed preflight; returns exact bytes and pinned public key."""
    c=load_legacy(args.legacy)
    root_input=Path(args.bundle)
    expect(root_input.is_dir() and not root_input.is_symlink(),'BUNDLE_MISSING_OR_SYMLINK')
    root=root_input.resolve()
    decision_raw,d=read(c,root/'decision.json')
    expect(sha(decision_raw)==APPROVED_DECISION_SHA256==args.approved_decision_sha256,
           'DECISION_BYTES_NOT_APPROVED')
    expect(set(d)==DECISION_KEYS,'DECISION_SCHEMA')
    expect(d['domain']==DOMAIN and d['profile']==PROFILE and d['schema_version']==2 and
           d['algorithm']=='Ed25519' and d['policy_subject']==SUBJECT and
           d['scope']==SCOPE and d['signer_policy_id']==SIGNER_ID and
           d['continuity_adoption_sha256']==CONTINUITY_SHA256 and
           d['adoption_sha256']==V1_ADOPTION,'DECISION_AUTHORITY_INCOMPATIBLE')
    expect(d['synthetic_only'] is False and d['residual_risk_accepted'] is True,'DECISION_NOT_AUTHORIZED')
    k,der=c.public(args.public)
    expect(sha(der)==FP==d['key_fingerprint']==args.fingerprint,'KEY_NOT_RECOGNIZED')
    manifest_raw,m=read(c,root/'manifest.json')
    expect(sha(manifest_raw)==d['manifest_sha256'],'MANIFEST_CHANGED')
    expect(set(m)=={'entries'} and len(m['entries'])==7 and
           [e['path'] for e in m['entries']]==list(FILES),'MANIFEST_ENTRIES')
    expected=set(FILES)|{'manifest.json','decision.json'}
    if args.mode=='verify': expected.add('signature.bin')
    expect({p.name for p in root.iterdir()}==expected,'BUNDLE_EXTRA_OR_MISSING')
    evidence={}
    for e in m['entries']:
        expect(set(e)=={'path','size','sha256'},'MANIFEST_SCHEMA')
        b,obj=read(c,root/e['path'])
        expect(len(b)==e['size'] and sha(b)==e['sha256'],'SEVEN_BYTES_DIVERGENT')
        evidence[e['path']]=obj
    expect(evidence['object.json']['policy_subject']==SUBJECT and
           sha((root/'object.json').read_bytes())==d['object_sha256'] and
           sha((root/'review.json').read_bytes())==d['review_sha256'], 'OBJECT_OR_REVIEW_PIN')
    ar,adoption=read(c,args.continuity_adoption)
    expect(sha(ar)==CONTINUITY_SHA256 and adoption['schema']=='SOLVERIS-B02-DOCUMENTARY-CONTINUITY-ADOPTION-V2'
           and adoption['id']=='B02-G4-CONTINUIDADE-DOCUMENTAL-V2-ADOCAO-20261103', 'V2_ADOPTION_PIN')
    now=now or datetime.now(timezone.utc)
    # Reuse the existing V2 continuity gate, against its ORIGINAL adopted interval,
    # not the shorter signing decision interval. No synthetic fallback.
    if v2_checker is None:
        app_root=Path(args.repo)
        source=app_root/'app/services/enterprise_b02_documentary_continuity_v2.py'
        expect(source.is_file() and not source.is_symlink() and
               git_blob(source.read_bytes())=='31be879d8d0fab9c572916b67f66ee32037b3495', 'V2_CONTRACT_CODE_PIN')
        sys.path.insert(0,str(app_root))
        from app.services.enterprise_b02_documentary_continuity_v2 import verify_supplemental_continuity
        v2_checker=verify_supplemental_continuity
    result=v2_checker(adoption=adoption,
                      trusted_pin={'id':adoption['id'],'sha256':CONTINUITY_SHA256},
                      evidence=evidence,expected=evidence['institutional.json']['expected'],
                      decisions=evidence['institutional.json']['decisions'],now=now,
                      valid_from=adoption['decision']['valid_from'],
                      valid_until=adoption['decision']['valid_until'], synthetic=False)
    expect(result['status']=='continuity_v2_conditions_met','V2_CONTRACT_NOT_MET')
    start,end=utc(d['valid_from']),utc(d['valid_until'])
    check_window(start,end,now,adoption,evidence)
    authority_raw,authority=read(c,args.signer_authority)
    trusted_authority_sha256 = _source_pinned_signer_authority(authority_raw, authority)
    expect(sha(authority_raw)==trusted_authority_sha256 and
           (not args.approved_signer_authority_sha256 or
            args.approved_signer_authority_sha256==trusted_authority_sha256),
           'SIGNER_AUTHORITY_NOT_INDEPENDENTLY_PINNED')
    expect(set(authority)==AUTHORITY_KEYS and authority['schema']=='SOLVERIS-B02-SIGNER-V2-AUTHORITY-ADOPTION-V1'
           and authority['id']==SIGNER_ID and authority['issuer']=='Miguel' and
           authority['approved'] is True and authority['signing_authorized'] is True and
           authority['status']=='adopted' and authority['revoked'] is False and
           authority['no_g4_reactivation'] is True and authority['no_operational_authority'] is True,
           'SIGNER_ADOPTION_REQUIRED')
    expect(authority['decision_sha256']==sha(decision_raw) and
           authority['manifest_sha256']==sha(manifest_raw) and
           authority['policy_subject']==SUBJECT and authority['scope']==SCOPE and
           authority['continuity_adoption_sha256']==CONTINUITY_SHA256 and
           authority['signer_source_git_blob']==args.reviewed_signer_git_blob,
           'SIGNER_ADOPTION_WRONG_BINDINGS')
    # Require independent review and actual source blob, not a self-claimed filename.
    signer_blob=git_blob(Path(__file__).read_bytes())
    expect(signer_blob==authority['signer_source_git_blob'],'SIGNER_SOURCE_NOT_REVIEWED')
    rev=authority['review']
    review_raw,review_act=read(c,args.signer_review)
    expect(sha(review_raw)==rev['review_sha256'] and
           review_act.get('reviewer_execution')==rev['reviewer_execution'] and
           review_act.get('outcome')=='favoravel' and
           review_act.get('signer_source_git_blob')==signer_blob and
           review_act.get('conflicts')==[] and review_act.get('limitations') and
           review_act.get('no_operational_authority') is True and
           utc(review_act['completed_at'])<=utc(authority['issued_at']),
           'REVIEW_DOCUMENT_NOT_VERIFIED')
    expect(set(rev)=={'reviewer_execution','outcome','review_sha256','signer_source_git_blob'} and
           rev['outcome']=='favoravel' and rev['signer_source_git_blob']==signer_blob and
           rev['reviewer_execution'] not in (adoption['actors']['author'], adoption['actors']['integrator'],
                                                adoption['actors']['origin_examiner']) and
           isinstance(rev['review_sha256'],str) and len(rev['review_sha256'])==64,
           'REVIEW_NOT_SEGREGATED_OR_PINNED')
    revoc=authority['revocation_confirmation']
    expect(set(revoc)=={'holder','status','confirmed_at'} and
           revoc['holder']=='Miguel' and revoc['status']=='no_known_revocation' and
           timedelta(0)<=now-utc(revoc['confirmed_at'])<=timedelta(hours=24),
           'KEY_REVOCATION_CONFIRMATION_REQUIRED')
    expect(utc(authority['issued_at'])<=utc(authority['valid_from'])<=now and
           start<=now<end<=utc(authority['valid_until']),
           'SIGNER_ADOPTION_WINDOW')
    return {'root':root,'decision_raw':decision_raw,'public':k,'der':der,'legacy':c,
            'signer_source_git_blob':signer_blob}


def sign(args):
    result=validate(args)
    c=result['legacy'];root=result['root']
    initial_authorization=validate_signature_authorization(
        args, result['decision_raw'], result['signer_source_git_blob'])
    priv=Path(args.private)
    expect(priv.is_file() and not priv.is_symlink() and root not in priv.resolve().parents,
           'PRIVATE_KEY_NOT_IN_CUSTODY')
    raw=priv.read_bytes()
    expect(b'ENCRYPTED PRIVATE KEY' in raw,'PRIVATE_KEY_NOT_ENCRYPTED')
    secret=getpass.getpass('Palavra-passe privada local: ')
    try:
        p=S.load_pem_private_key(raw,secret.encode())
    finally:
        del secret
    expect(isinstance(p,Ed25519PrivateKey) and
           p.public_key().public_bytes(S.Encoding.DER,S.PublicFormat.SubjectPublicKeyInfo)==result['der'],
           'PRIVATE_KEY_MISMATCH')
    start,end=utc(c.parse(result['decision_raw'])['valid_from']),utc(c.parse(result['decision_raw'])['valid_until'])
    # Every remote request happens BEFORE taking the time of the actual action.
    # Reconsult the issuer's ORIGINAL authorization, as well as signer adoption,
    # after the password delay. The originally observed bytes must be identical.
    live=validate(args)
    expect(live['decision_raw']==result['decision_raw'] and
           live['signer_source_git_blob']==result['signer_source_git_blob'],
           'PRE_SIGN_PIN_OR_AUTHORITY_CHANGED')
    current_authorization=validate_signature_authorization(
        args, result['decision_raw'], result['signer_source_git_blob'])
    expect(current_authorization==initial_authorization,
           'ORIGINAL_AUTHORIZATION_CHANGED_AFTER_PASSWORD')
    before=datetime.now(timezone.utc)
    expect(start<=before<end,'SIGNING_WINDOW_CLOSED')
    sig=p.sign(result['decision_raw'])
    result['public'].verify(sig,result['decision_raw'])
    # Before persistence, repeat BOTH remote trust checks, compare the original
    # authorization against its initial reference, then read the clock again.
    live_after=validate(args)
    expect(live_after['decision_raw']==result['decision_raw'] and
           live_after['signer_source_git_blob']==result['signer_source_git_blob'],
           'PRE_PERSIST_PIN_OR_AUTHORITY_CHANGED')
    last_authorization=validate_signature_authorization(
        args, result['decision_raw'], result['signer_source_git_blob'])
    expect(last_authorization==initial_authorization,
           'ORIGINAL_AUTHORIZATION_CHANGED_BEFORE_PERSIST')
    after=datetime.now(timezone.utc)
    expect(start<=after<end,'SIGNING_WINDOW_CLOSED_BEFORE_PERSIST')
    c.write_new(root/'signature.bin',sig)
    print('B02_V2_SIGNATURE_CREATED_LOCAL_ONLY')
    print('SIGNATURE_SHA256='+sha(sig))
    print('TRUST_PROVISIONED=NO; G5_SQL_AUTHORIZED=NO')


def verify(args):
    result=validate(args)
    raw=(result['root']/'signature.bin').read_bytes()
    expect(len(raw)==64,'SIGNATURE_LENGTH')
    result['public'].verify(raw,result['decision_raw'])
    print('B02_V2_ED25519_MATHEMATICAL_VERIFY_PASS')
    print('SIGNATURE_SHA256='+sha(raw))
    print('TRUST_PROVISIONED=NO; G5_SQL_AUTHORIZED=NO')


def main():
    p=argparse.ArgumentParser(description='B02 V2 successor signer: separate, pinned, reviewed, never root authority')
    p.add_argument('mode',choices=['preflight','sign','verify'])
    for name in ('repo','legacy','bundle','public','fingerprint','approved-decision-sha256',
                 'continuity-adoption','signer-authority','signer-review','approved-signer-authority-sha256',
                 'reviewed-signer-git-blob','authorization','authorization-sha256','private'):
        p.add_argument('--'+name,required=name not in ('authorization','authorization-sha256',
                                                    'approved-signer-authority-sha256','private'))
    a=p.parse_args()
    if a.mode=='sign':
        for x in ('private',):
            if not getattr(a,x): p.error('--'+x.replace('_','-')+' required for sign')
    try:
        if a.mode=='sign':sign(a)
        elif a.mode=='verify':verify(a)
        else:
            validate(a)
            print('B02_V2_SIGNER_PREFLIGHT_PASS_NOT_SIGNED')
    except Exception as exc:
        raise SystemExit('STOP: '+type(exc).__name__+': '+str(exc)) from None

if __name__=='__main__':main()
