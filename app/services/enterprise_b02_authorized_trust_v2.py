"""B02 successor documentary V2: read-only compatibility; no implicit runtime trust.

Never changes the historic V1 entrypoints or grants fiscal authority. The only
operational method returns a negative provisioned flag pending separate approval.
"""
from pathlib import Path
from datetime import datetime,timezone
from types import MappingProxyType
import hashlib,json


# --- B02 successor documentary V2: separate, fail-closed compatibility path. ---
# V1 check_payload / activate_for_process / activate_successor_for_process and
# their historical immutable pins remain unchanged. Import has no effects.
_V2_DECISION_SHA256 = 'd3602168c53debd10421aa83d1e980c632870b660be18a451d5b5a3d998c6520'
_V2_MANIFEST_SHA256 = '99d1a424015fc03a5ece71e84341eee748fd0b2fc1bebd238f9df2ede253a6c1'
_V2_CONTINUITY_ADOPTION_SHA256 = 'd0cd1765ea2ef4870a530f8e5367cdde8550b5a60a3a70cb294f9d80678f7fa8'
_V2_PROFILE_ADOPTION_SHA256 = 'd1fcd244129e669fc5a37c79dc1fc77f677b1cb0e0ceaf06d4cbe9bf9740d911'
_V2_PUBLIC_DER_SHA256 = '6f0ede1267a208505b2443d765cf97f2206759049f938a1d95d92a86c4c5d63c'
_V2_SIGNER_GIT_BLOB = '805ed5d2cdcfca047ff2ef583e91caaa108ddb37'
_V2_PROFILE_GIT_BLOB = '4167337f53fc4f5b7d7b78dbcde344a08fa8019f'
_V2_CONTINUITY_GIT_BLOB = '32b4ee9c8c11b5eb9564d4f258cef5a40cae3119'
_V2_SUBJECT = {'policy_type':'activation_authority','policy_id':'SOLVERIS-B02-SEFA-PR-DOCUMENTARY-AUTHORITY',
               'policy_version':1,'policy_hash':'05ede0f8c8788b93d41e451288efd88d91614a560bdd2191a115f0d736c4fe2a'}
_V2_SCOPE = 'SEFA_PR_B02_DOCUMENTAL_AUTHENTICATION_ONLY'
_V2_FILES = ('execution.json','history.json','institutional.json','mandates.json',
             'object.json','proofs.json','review.json')
# V1 runtime._resolve_history enforces this exact snapshot field set.
# A V1 snapshot carrying issued_at would fail operational readback.
_V2_SNAPSHOT_V1_FIELDS = {'id','schema','policy_subject','canonical_decisions_sha256',
    'head_binding','genesis_binding','context','execution_writer_binding',
    'origin_report_bindings','origin_mandate_binding','valid_from','valid_until',
    'revoked','synthetic_only'}
_V2_DECISION_FIELDS = {'domain','schema_version','profile','algorithm','key_fingerprint',
 'adoption_sha256','continuity_adoption_sha256','signer_policy_id','manifest_sha256',
 'policy_subject','object_sha256','review_sha256','scope','valid_from','valid_until',
 'synthetic_only','residual_risk_accepted'}
# These deployment pins MUST be filled by a separately reviewed source commit,
# after the actual signature and competent root adoption. Never accept pins from
# bundle, caller, environment, or a JSON-supplied self-attestation.
V2_DEPLOYMENT_PINS = MappingProxyType({
    'root_sha256': None,
    'root_adoption_sha256': None,
    'snapshot_sha256': None,
    'signer_authority_sha256': None,
    'signer_review_sha256': None,
    'signature_sha256': None,
    'compatibility_review_git_blob': None,
})

def _v2_fail(code):
    raise ValueError('B02_TRUST_V2_' + code)

def _v2_need(ok, code):
    if not ok: _v2_fail(code)

def _v2_sha(raw):
    return hashlib.sha256(raw).hexdigest()

def _v2_git_blob(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode('ascii')+b'\x00'+raw).hexdigest()

def _v2_time(value):
    from datetime import datetime, timezone
    _v2_need(type(value) is str, 'TIME_INVALID')
    try: dt = datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError: _v2_fail('TIME_INVALID')
    _v2_need(dt.tzinfo is not None and dt.utcoffset().total_seconds()==0, 'TIME_NOT_UTC')
    return dt.astimezone(timezone.utc)

def _v2_pin(pin):
    import re
    _v2_need(type(pin) is dict and set(pin)=={'id','sha256'} and
             type(pin['id']) is str and bool(pin['id']) and
             type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}',pin['sha256']) is not None,
             'BINDING_INVALID')
    return pin

def _v2_safe_path(path):
    p=Path(path)
    _v2_need(not any(q.is_symlink() or (hasattr(q,'is_junction') and q.is_junction())
                     for q in (p,*p.parents)), 'SYMLINK_OR_JUNCTION')
    return p

def _v2_read(path, *, max_size=13000000, parser=None):
    p=_v2_safe_path(path)
    _v2_need(p.is_file() and 0<p.stat().st_size<=max_size, 'FILE_UNAVAILABLE_OR_SIZE')
    raw=p.read_bytes()
    _v2_need(0<len(raw)<=max_size, 'FILE_SIZE_CHANGED')
    if parser is None:
        # Fail on duplicate keys, noncanonical JSON and NaN: same ADR-020
        # sorted UTF-8 serialization as the historical profile parser.
        def pairs(items):
            d={}
            for k,v in items:
                if k in d: _v2_fail('DUPLICATE_JSON_KEY')
                d[k]=v
            return d
        def no_constant(value):
            _v2_fail('INVALID_JSON_CONSTANT')
        try: obj=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=no_constant)
        except (UnicodeDecodeError,ValueError): _v2_fail('JSON_INVALID')
        can=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
        _v2_need(can==raw, 'JSON_NONCANONICAL')
    else:
        obj=parser(raw)
    return raw,obj

def _v2_file_from_store(store,pin,parser):
    p=_v2_pin(pin); h=p['sha256']
    raw,obj=_v2_read(store/'sha256'/h[:2]/(h+'.json'),parser=parser)
    _v2_need(_v2_sha(raw)==h and type(obj) is dict and obj.get('id')==p['id'],
             'STORE_PIN_DIVERGENCE')
    return obj

def _v2_check_window(value, start, end, now, *, revocation=True, prospectively_issued=False):
    _v2_need(type(value) is dict and
             (not revocation or value.get('revoked') is False) and
             _v2_time(value['valid_from'])<=(now if prospectively_issued else start) and end<=_v2_time(value['valid_until']) and
             _v2_time(value['valid_from'])<=now<_v2_time(value['valid_until']),
             'AUTHORITY_WINDOW_OR_REVOCATION')

def _v2_validate_exact(base,pins,*,now,profile,continuity_checker):
    """Internal read-only checker. A synthetic positive is never deployment authority.

    Operational entrypoint has no base/pins arguments and no runtime write.
    All seven signed JSON, DER and root/snapshot/adoption anchors are verified.
    """
    from datetime import timedelta
    import re
    from cryptography.hazmat.primitives.serialization import load_der_public_key,Encoding,PublicFormat
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    _v2_need(hasattr(pins, 'items') and set(pins)==set(V2_DEPLOYMENT_PINS) and all(
        type(v) is str and re.fullmatch('[0-9a-f]{40}' if k=='compatibility_review_git_blob'
                                       else '[0-9a-f]{64}',v)
        for k,v in pins.items()),
        'COMPETENT_DEPLOYMENT_PINS_REQUIRED')
    base=_v2_safe_path(base)
    _v2_need(base.is_dir(), 'CUSTODY_MISSING')
    bundle=_v2_safe_path(base/'BUNDLE_ASSINADO')
    store=_v2_safe_path(base/'STORE')
    _v2_need(bundle.is_dir() and store.is_dir(), 'LAYOUT_INVALID')
    bnames={p.name for p in bundle.iterdir()}
    _v2_need(bnames==set(_V2_FILES)|{'manifest.json','decision.json','signature.bin'},
             'BUNDLE_FILE_SET')
    decision_bytes,d=_v2_read(bundle/'decision.json',parser=profile.parse)
    manifest_bytes,m=_v2_read(bundle/'manifest.json',parser=profile.parse)
    sig_path=bundle/'signature.bin'
    _v2_need(_v2_safe_path(sig_path).is_file(), 'SIGNATURE_MISSING')
    _v2_need(sig_path.stat().st_size==64, 'SIGNATURE_LENGTH')
    sig=sig_path.read_bytes()
    _v2_need(len(sig)==64 and _v2_sha(sig)==pins['signature_sha256'],
             'SIGNATURE_PIN_DIVERGENCE')
    _v2_need(len(decision_bytes)==1118 and _v2_sha(decision_bytes)==_V2_DECISION_SHA256 and
             _v2_sha(manifest_bytes)==_V2_MANIFEST_SHA256,'DECISION_OR_MANIFEST_PIN')
    _v2_need(set(d)==_V2_DECISION_FIELDS and d['domain']=='SOLVERIS-B02-GOVERNANCE-DECISION' and
             type(d['schema_version']) is int and d['schema_version']==2 and
             d['profile']=='FOUNDER_SIGNED_REVIEW_BUNDLE_B02_V2' and d['algorithm']=='Ed25519' and
             d['scope']==_V2_SCOPE and d['policy_subject']==_V2_SUBJECT and
             d['key_fingerprint']==_V2_PUBLIC_DER_SHA256 and
             d['signer_policy_id']=='SOLVERIS-B02-G4-DOCUMENTARY-LOCAL-SIGNER-V2' and
             d['adoption_sha256']==_V2_PROFILE_ADOPTION_SHA256 and
             d['continuity_adoption_sha256']==_V2_CONTINUITY_ADOPTION_SHA256 and
             d['manifest_sha256']==_V2_MANIFEST_SHA256 and
             d['residual_risk_accepted'] is True and d['synthetic_only'] is False,
             'V2_SCHEMA_SCOPE_OR_VERSION')
    start,end=_v2_time(d['valid_from']),_v2_time(d['valid_until'])
    _v2_need(start<end and end-start<=timedelta(hours=24) and start<=now<end,
             'V2_DECISION_WINDOW')
    _v2_need(type(m) is dict and set(m)=={'entries'} and type(m['entries']) is list and
             len(m['entries'])==7 and
             [x.get('path') for x in m['entries']]==list(_V2_FILES), 'MANIFEST_SCHEMA')
    evidence={}
    evidence_raw={}
    for item in m['entries']:
        _v2_need(type(item) is dict and set(item)=={'path','size','sha256'} and
                 type(item['size']) is int and type(item['sha256']) is str,'MANIFEST_ENTRY')
        raw,obj=_v2_read(bundle/item['path'],parser=profile.parse)
        _v2_need(len(raw)==item['size'] and _v2_sha(raw)==item['sha256'],
                 'MANIFEST_EVIDENCE_BYTES_CHANGED')
        evidence[item['path']]=obj
        evidence_raw[item['path']]=raw
    _v2_need(_v2_sha(evidence_raw['object.json'])==d['object_sha256'] and
             _v2_sha(evidence_raw['review.json'])==d['review_sha256'],
             'SIGNED_OBJECT_OR_REVIEW_CHANGED')
    rroot,root=_v2_read(base/'ROOT.json',parser=profile.parse)
    _v2_need(_v2_sha(rroot)==pins['root_sha256'] and
             root.get('schema')=='SOLVERIS-B02-RECOGNIZED-SUCCESSOR-ROOT-V2' and
             root.get('profile')==d['profile'] and root.get('policy_subject')==_V2_SUBJECT and
             root.get('key_fingerprint')==_V2_PUBLIC_DER_SHA256 and
             root.get('decision_sha256')==_V2_DECISION_SHA256 and
             root.get('manifest_sha256')==_V2_MANIFEST_SHA256 and
             root.get('signature_sha256')==pins['signature_sha256'] and
             root.get('synthetic_only') is False,'ROOT_EXTERNAL_PIN_OR_DOMAIN')
    _v2_check_window(root,start,end,now,prospectively_issued=True)
    _v2_need(_v2_time(root['issued_at'])<=_v2_time(root['valid_from'])<=now,
             'ROOT_NOT_PROSPECTIVE')
    _v2_need(root.get('origin_document_scope')==['101201900571','101202501245'] and
             root.get('no_operational_authority') is True and
             root.get('continuity_adoption_binding')=={'id':'B02-G4-CONTINUIDADE-DOCUMENTAL-V2-ADOCAO-20261103',
                 'sha256':_V2_CONTINUITY_ADOPTION_SHA256}, 'ROOT_BOUNDARY')
    try: der=bytes.fromhex(root['public_key_der_hex'])
    except (ValueError,KeyError,TypeError): _v2_fail('ROOT_PUBLIC_KEY')
    _v2_need(_v2_sha(der)==_V2_PUBLIC_DER_SHA256, 'KEY_NOT_RECOGNIZED')
    try:
        key=load_der_public_key(der)
        _v2_need(isinstance(key,Ed25519PublicKey) and
                 key.public_bytes(Encoding.DER,PublicFormat.SubjectPublicKeyInfo)==der,
                 'KEY_NOT_ED25519')
        key.verify(sig,decision_bytes)
    except ValueError: raise
    except Exception: _v2_fail('ED25519_SIGNATURE_INVALID')
    raw_adopt,adopt=_v2_read(base/'CONTINUITY_ADOPTION.json',parser=profile.parse)
    _v2_need(_v2_sha(raw_adopt)==_V2_CONTINUITY_ADOPTION_SHA256 and
             adopt.get('schema')=='SOLVERIS-B02-DOCUMENTARY-CONTINUITY-ADOPTION-V2' and
             adopt.get('decision',{}).get('approved') is True and
             adopt['decision'].get('revoked') is False and
             adopt['decision'].get('signing_authorized') is False,
             'CONTINUITY_ADOPTION_PIN')
    _v2_check_window(adopt['decision'],start,end,now)
    _v2_need(root.get('signer_adoption_binding')=={'id':'SOLVERIS-B02-G4-DOCUMENTARY-LOCAL-SIGNER-V2',
             'sha256':pins['signer_authority_sha256']}, 'SIGNER_ADOPTION_ROOT_BINDING')
    raw_auth,auth=_v2_read(base/'SIGNER_AUTHORITY.json',parser=profile.parse)
    _v2_need(_v2_sha(raw_auth)==pins['signer_authority_sha256'] and
             auth.get('schema')=='SOLVERIS-B02-SIGNER-V2-AUTHORITY-ADOPTION-V1' and
             auth.get('id')=='SOLVERIS-B02-G4-DOCUMENTARY-LOCAL-SIGNER-V2' and
             auth.get('issuer')=='Miguel' and auth.get('status')=='adopted' and
             auth.get('approved') is True and auth.get('signing_authorized') is True and
             auth.get('revoked') is False and auth.get('no_g4_reactivation') is True and
             auth.get('no_operational_authority') is True and
             auth.get('signer_source_git_blob')==_V2_SIGNER_GIT_BLOB and
             auth.get('decision_sha256')==_V2_DECISION_SHA256 and
             auth.get('manifest_sha256')==_V2_MANIFEST_SHA256 and
             auth.get('continuity_adoption_sha256')==_V2_CONTINUITY_ADOPTION_SHA256 and
             auth.get('scope')==_V2_SCOPE and auth.get('policy_subject')==_V2_SUBJECT,
             'SIGNER_ADOPTION_INVALID')
    # The signer permits a competent adoption inside the original decision
    # window, but never before the independently recorded issuance. The same
    # authority is checked at current readback, not backdated to window start.
    _v2_check_window(auth,start,end,now,prospectively_issued=True)
    _v2_need(_v2_time(auth['issued_at'])<=_v2_time(auth['valid_from'])<=now,
             'SIGNER_ADOPTION_NOT_PROSPECTIVE')
    _v2_need(_v2_time(root['issued_at'])>=_v2_time(auth['valid_from']),
             'ROOT_PREDATES_SIGNER_ADOPTION')
    conf=auth.get('revocation_confirmation',{})
    _v2_need(conf.get('holder')=='Miguel' and conf.get('status')=='no_known_revocation' and
             _v2_time(conf['confirmed_at'])<=now and
             now-_v2_time(conf['confirmed_at'])<=timedelta(hours=24),
             'KEY_REVOCATION_CONFIRMATION')
    raw_review,review=_v2_read(base/'SIGNER_REVIEW.json',parser=profile.parse)
    _v2_need(_v2_sha(raw_review)==pins['signer_review_sha256'] and
             auth.get('review',{}).get('review_sha256')==pins['signer_review_sha256'] and
             auth['review'].get('outcome')=='favoravel' and
             auth['review'].get('signer_source_git_blob')==_V2_SIGNER_GIT_BLOB and
             review.get('outcome')=='favoravel' and review.get('conflicts')==[] and
             review.get('no_operational_authority') is True and
             review.get('signer_source_git_blob')==_V2_SIGNER_GIT_BLOB and
             review.get('reviewer_execution')==auth['review'].get('reviewer_execution') and
             review.get('limitations') and
             review.get('reviewer_execution') not in
               (adopt.get('actors',{}).get('author'),adopt.get('actors',{}).get('integrator'),
                adopt.get('actors',{}).get('origin_examiner')) and
             _v2_time(review['completed_at'])<=_v2_time(auth['issued_at']),
             'SIGNER_REVIEW_INDEPENDENCE_OR_PIN')
    _v2_need(root.get('signer_review_binding')=={'id':review.get('id'),
             'sha256':pins['signer_review_sha256']}, 'ROOT_REVIEW_PIN')
    # Reuse existing V2 continuity constraints. Synthetic positive cannot be
    # promoted: the public entrypoint always passes synthetic=False.
    rc=continuity_checker(adoption=adopt,
        trusted_pin={'id':adopt['id'],'sha256':_V2_CONTINUITY_ADOPTION_SHA256},
        evidence=evidence,expected=evidence['institutional.json']['expected'],
        decisions=evidence['institutional.json']['decisions'],now=now,
        valid_from=adopt['decision']['valid_from'],valid_until=adopt['decision']['valid_until'],synthetic=False)
    _v2_need(rc.get('status')=='continuity_v2_conditions_met', 'V2_CONTINUITY_CONTRACT_REJECTED')
    # Independently pinned store snapshot, not an untrusted ROOT auto-promotion.
    snapshot_pin=_v2_pin(root.get('snapshot_binding'))
    _v2_need(snapshot_pin['sha256']==pins['snapshot_sha256'], 'SNAPSHOT_DEPLOYMENT_PIN')
    snapshot=_v2_file_from_store(store,snapshot_pin,profile.parse)
    _v2_need(set(snapshot)==_V2_SNAPSHOT_V1_FIELDS, 'SNAPSHOT_SCHEMA_COMPATIBILITY')
    _v2_need(snapshot.get('schema')=='SOLVERIS-B02-AUTHORIZED-READ-SNAPSHOT-V1' and
             snapshot.get('policy_subject')==_V2_SUBJECT and
             snapshot.get('revoked') is False and snapshot.get('synthetic_only') is False and
             snapshot.get('origin_report_bindings')==adopt['origin_reports'] and
             snapshot.get('origin_mandate_binding') and
             snapshot.get('canonical_decisions_sha256')==_v2_sha(profile.canonical(
                 sorted(evidence['institutional.json']['decisions'],key=lambda x:x['decision_id']))),
             'SNAPSHOT_HISTORY_OR_ORIGIN_BINDINGS')
    _v2_check_window(snapshot,start,end,now,prospectively_issued=True)
    # V1 has no issued_at. Prospectivity is anchored to the externally pinned,
    # separately adopted ROOT issuance; never invent a field for V1.
    _v2_need(_v2_time(root['issued_at'])<=_v2_time(snapshot['valid_from'])<=now,
             'SNAPSHOT_NOT_PROSPECTIVE')
    for name in ('head_binding','genesis_binding','origin_mandate_binding','execution_writer_binding'):
        _v2_file_from_store(store,_v2_pin(snapshot.get(name)),profile.parse)
    for pin in snapshot['origin_report_bindings']:
        _v2_file_from_store(store,_v2_pin(pin),profile.parse)
    raw_approval,approval=_v2_read(base/'ROOT_ADOPTION.json',parser=profile.parse)
    _v2_need(_v2_sha(raw_approval)==pins['root_adoption_sha256'] and
             approval.get('schema')=='SOLVERIS-B02-ROOT-V2-PROVISIONING-ADOPTION-V1' and
             approval.get('issuer')=='Miguel' and approval.get('approved') is True and
             approval.get('provisioning_authorized') is True and
             approval.get('revoked') is False and approval.get('no_operational_authority') is True and
             approval.get('root_sha256')==pins['root_sha256'] and
             approval.get('snapshot_sha256')==pins['snapshot_sha256'] and
             approval.get('decision_sha256')==_V2_DECISION_SHA256 and
             approval.get('signer_adoption_sha256')==pins['signer_authority_sha256'] and
             approval.get('compatibility_review_git_blob')==pins['compatibility_review_git_blob'],
             'COMPETENT_ROOT_ADOPTION_REQUIRED')
    _v2_check_window(approval,start,end,now,prospectively_issued=True)
    _v2_need(_v2_time(approval['issued_at'])<=_v2_time(approval['valid_from'])<=now,
             'ROOT_ADOPTION_NOT_PROSPECTIVE')
    return {'status':'V2_SIGNED_CUSTODY_VALIDATED_NOT_RUNTIME_PROVISIONED',
            'signature_sha256':_v2_sha(sig), 'decision_sha256':_v2_sha(decision_bytes),
            'root_sha256':_v2_sha(rroot),'snapshot_sha256':pins['snapshot_sha256'],
            'institutional_readback':False,'fiscal_authority':False,
            'runtime_provisioned':False,'sql_writes':0}

def verify_successor_v2_for_provisioning():
    """Deployment entrypoint. No caller-controlled roots, pins or path.

    V1 runtime only accepts V1 schema. This V2 checker DOES NOT set
    _RUNTIME_AUTHORIZATIONS or claim operational admission.
    Any runtime V2 admission remains a distinct reviewed, authorized action.
    """
    from app.services import enterprise_b02_founder_review_profile as profile
    from app.services.enterprise_b02_documentary_continuity_v2 import verify_supplemental_continuity
    for mod,blob in ((profile,_V2_PROFILE_GIT_BLOB),):
        _v2_need(_v2_git_blob(Path(mod.__file__).read_bytes())==blob,
                 'V2_VERIFIER_SOURCE_CHANGED')
    from app.services import enterprise_b02_documentary_continuity_v2 as continuity
    _v2_need(_v2_git_blob(Path(continuity.__file__).read_bytes())==_V2_CONTINUITY_GIT_BLOB,
             'V2_CONTINUITY_SOURCE_CHANGED')
    base=Path.home()/'AppData/Local/SOLVERIS/B02Trust/SUCCESSOR_V3'
    return _v2_validate_exact(base,V2_DEPLOYMENT_PINS,now=datetime.now(timezone.utc),
                              profile=profile,continuity_checker=verify_supplemental_continuity)
