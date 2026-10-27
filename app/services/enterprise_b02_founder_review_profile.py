"""Candidate read-only proof profile. No deployment, trust provisioning or writer.

Evidence is authenticated as one founder-signed bundle, not as signatures of AI
actors. Legacy checks remain unchanged. Complete history and authority must be
resolved independently of bundle input. Both real registries are EMPTY.
"""
from __future__ import annotations
import hashlib
import json
import unicodedata
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from app.services.sefa_pr_policy_projection import PolicyProofError, dt, validate_institutional_chain

PROFILE = 'FOUNDER_SIGNED_REVIEW_BUNDLE_B02_V1'
DOMAIN = 'SOLVERIS-B02-GOVERNANCE-DECISION'
SCOPE = 'SEFA_PR_B02_DOCUMENTAL_AUTHENTICATION_ONLY'
ADOPTION = 'd1fcd244129e669fc5a37c79dc1fc77f677b1cb0e0ceaf06d4cbe9bf9740d911'
_DOCUMENTS = {'101202501245':'e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832',
              '101201900571':'af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d'}
# Not configurable by request, filesystem payload, environment or runtime flag.
_AUTHORIZED_CONTEXTS = MappingProxyType({})
MAX_FILE = 4 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024

def fail(code): raise PolicyProofError(code)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def exact(value, fields):
    if type(value) is not dict or set(value) != set(fields): fail('PROFILE_SCHEMA_INVALID')
    return value

def _values(value):
    if type(value) is str:
        if unicodedata.normalize('NFC',value)!=value: fail('PROFILE_NON_NFC')
    elif type(value) is dict:
        for k,v in value.items():
            if type(k) is not str: fail('PROFILE_KEY_INVALID')
            _values(k); _values(v)
    elif type(value) is list:
        for v in value: _values(v)
    elif value is not None and type(value) not in (int,bool): fail('PROFILE_VALUE_INVALID')

def canonical(value):
    _values(value)
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def _pairs(pairs):
    out={}
    for k,v in pairs:
        if k in out: fail('PROFILE_DUPLICATE_KEY')
        out[k]=v
    return out

def parse(raw):
    if type(raw) is not bytes or len(raw)>MAX_FILE: fail('PROFILE_BYTES_INVALID')
    try: value=json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs)
    except (ValueError,UnicodeError): fail('PROFILE_JSON_INVALID')
    if canonical(value)!=raw: fail('PROFILE_NON_CANONICAL')
    return value

def _path(value):
    if (type(value) is not str or not value or '\\' in value or ':' in value
        or value.startswith('/') or any(x in ('','.','..') for x in value.split('/'))
        or any(ord(c)<32 for c in value)):
        fail('PROFILE_PATH_INVALID')
    _values(value)
    if str(PurePosixPath(value))!=value: fail('PROFILE_PATH_INVALID')
    return value

def _read(root, relative):
    relative=_path(relative); p=root
    for segment in relative.split('/'):
        p=p/segment
        if p.is_symlink(): fail('PROFILE_SYMLINK_FORBIDDEN')
    if not p.is_file(): fail('PROFILE_EVIDENCE_MISSING')
    with p.open('rb') as f: raw=f.read(MAX_FILE+1)
    if len(raw)>MAX_FILE: fail('PROFILE_EVIDENCE_TOO_LARGE')
    return raw

def _current(item,now):
    if item.get('revoked') is not False: fail('PROFILE_REVOKED_OR_UNKNOWN')
    try:
        if not dt(item['valid_from'])<=now<dt(item['valid_until']): fail('PROFILE_NOT_CURRENT')
    except (KeyError,TypeError): fail('PROFILE_VALIDITY_MISSING')

class _BundleSnapshot:
    """Immutable bytes for ONE verification; avoids re-reading after signature."""
    def __init__(self,directory):
        root=Path(directory)
        if root.is_symlink() or not root.is_dir():fail('PROFILE_STORE_INVALID')
        files={};total=0
        for path in root.rglob('*'):
            if path.is_symlink():fail('PROFILE_SYMLINK_FORBIDDEN')
            if path.is_file():
                name=path.relative_to(root).as_posix();raw=_read(root,name);total+=len(raw)
                if total>MAX_TOTAL or len(files)>=64:fail('PROFILE_BUNDLE_TOO_LARGE')
                files[name]=raw
        self.files=MappingProxyType(files)
    def read(self,name):
        if name not in self.files:fail('PROFILE_EVIDENCE_MISSING')
        return self.files[name]

def _verify_bundle(directory, *, expected, decisions, context, now, synthetic, execution_binding=None, bundle_snapshot=None):
    """Internal pure validation; synthetic positives never yield 'verified'.

    context represents a trusted current authorization/history snapshot, never
    evidence supplied by a caller. Public production entry cannot accept it.
    """
    now=dt(now)
    if context.get('synthetic_only') is not synthetic: fail('PROFILE_TRUST_DOMAIN_MISMATCH')
    if (context.get('profile')!=PROFILE or context.get('adoption_sha256')!=ADOPTION
        or context.get('scope')!=SCOPE or context.get('policy_subject')!=expected['policy_subject']
        or context.get('enabled') is not True or context.get('channel_authorized') is not True
        or not context.get('bootstrap_binding') or not context.get('authorization_binding')):
        fail('PROFILE_AUTHORITY_NOT_ENABLED')
    _current(context,now)
    root=Path(directory)
    if root.is_symlink() or not root.is_dir(): fail('PROFILE_STORE_INVALID')
    root=root.resolve()
    if bundle_snapshot is not None and type(bundle_snapshot) is not _BundleSnapshot:fail('PROFILE_SNAPSHOT_TYPE_INVALID')
    read=bundle_snapshot.read if bundle_snapshot is not None else lambda name:_read(root,name)
    decision_raw=read('decision.json'); d=parse(decision_raw)
    exact(d,('domain','schema_version','profile','algorithm','key_fingerprint','adoption_sha256',
             'manifest_sha256','policy_subject','object_sha256','review_sha256','scope',
             'valid_from','valid_until','synthetic_only','residual_risk_accepted'))
    if (d['domain']!=DOMAIN or type(d['schema_version']) is not int or d['schema_version']!=1
        or d['profile']!=PROFILE or d['algorithm']!='Ed25519' or d['adoption_sha256']!=ADOPTION
        or d['scope']!=SCOPE or d['synthetic_only'] is not synthetic or d['residual_risk_accepted'] is not True
        or d['policy_subject']!=expected['policy_subject']): fail('PROFILE_DECISION_DIVERGENCE')
    _current(dict(d,revoked=False),now)
    if dt(d['valid_from'])<dt(context['valid_from']) or dt(d['valid_until'])>dt(context['valid_until']):
        fail('PROFILE_DECISION_OUTSIDE_AUTHORITY')
    try:
        from cryptography.hazmat.primitives.serialization import load_der_public_key,Encoding,PublicFormat
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        key_der=bytes.fromhex(context['public_key_der_hex'])
        if sha(key_der)!=context['key_fingerprint'] or d['key_fingerprint']!=context['key_fingerprint']:
            fail('PROFILE_KEY_NOT_AUTHORIZED')
        key=load_der_public_key(key_der)
        if not isinstance(key,Ed25519PublicKey) or key.public_bytes(Encoding.DER,PublicFormat.SubjectPublicKeyInfo)!=key_der:
            fail('PROFILE_KEY_INVALID')
        key.verify(read('signature.bin'),decision_raw)
    except PolicyProofError: raise
    except Exception: fail('PROFILE_SIGNATURE_INVALID')
    manifest_raw=read('manifest.json')
    if sha(manifest_raw)!=d['manifest_sha256']: fail('PROFILE_MANIFEST_ALTERED')
    manifest=exact(parse(manifest_raw),('entries',))
    if type(manifest['entries']) is not list or not 1<=len(manifest['entries'])<=64: fail('PROFILE_MANIFEST_INVALID')
    evidence={};seen=set();total=0;names=[]
    for e in manifest['entries']:
        exact(e,('path','size','sha256'));name=_path(e['path']); folded=name.casefold()
        if folded in seen or folded in {'manifest.json','decision.json','signature.bin'}: fail('PROFILE_MANIFEST_CYCLE_OR_COLLISION')
        seen.add(folded);names.append(name)
        raw=read(name);total+=len(raw)
        if total>MAX_TOTAL: fail('PROFILE_BUNDLE_TOO_LARGE')
        if type(e['size']) is not int or len(raw)!=e['size'] or sha(raw)!=e['sha256']: fail('PROFILE_EVIDENCE_ALTERED')
        evidence[name]=parse(raw)
    if names!=sorted(names): fail('PROFILE_MANIFEST_ORDER_INVALID')
    required={'object.json','review.json','mandates.json','execution.json','institutional.json','history.json','proofs.json'}
    if set(evidence)!=required: fail('PROFILE_EVIDENCE_SET_INVALID')
    # No hidden files can affect acceptance; delivery inventories live outside bundle.
    actual=set(bundle_snapshot.files) if bundle_snapshot is not None else set()
    if bundle_snapshot is None:
        for p in root.rglob('*'):
            if p.is_symlink(): fail('PROFILE_SYMLINK_FORBIDDEN')
            if p.is_file(): actual.add(p.relative_to(root).as_posix())
    if actual!=required|{'manifest.json','decision.json','signature.bin'}: fail('PROFILE_UNDECLARED_FILE')
    content=evidence['object.json'];review=evidence['review.json'];history=evidence['history.json']
    proofs=evidence['proofs.json']
    if type(proofs) is not dict: fail('PROFILE_PROOFS_INVALID')
    resolved={sha(canonical(v)):v for k,v in evidence.items() if k!='proofs.json'}
    for h,value in proofs.items():
        if sha(canonical(value))!=h: fail('PROFILE_PROOF_BYTES_ALTERED')
        if h in resolved and resolved[h]!=value: fail('PROFILE_PROOF_COLLISION')
        resolved[h]=value
    def resolve(h):
        if type(h) is not str or h not in resolved: fail('PROFILE_PROOF_UNAVAILABLE')
        return resolved[h]
    def resolve_pin(pin):
        exact(pin,('id','sha256'));value=resolve(pin['sha256'])
        if type(value) is not dict or value.get('id')!=pin['id']: fail('PROFILE_PROOF_ID_DIVERGENCE')
        return value
    exact(content,('policy_subject','documents','use'))
    if content!={'policy_subject':expected['policy_subject'],'documents':_DOCUMENTS,'use':'autenticar_documento_sefa_pr'}:
        fail('PROFILE_OBJECT_DIVERGENCE')
    if d['object_sha256']!=sha(canonical(content)) or d['review_sha256']!=sha(canonical(review)):
        fail('PROFILE_OBJECT_REVIEW_DIVERGENCE')
    # Authoritative complete history must be independently pinned, not vouched
    # for by a founder signature or a payload-supplied true/complete flag.
    exact(history,('object_sha256','revision','previous_revision','reviews','prior_reviews','delta_sha256'))
    if context.get('history_sha256')!=sha(canonical(history)) or context.get('history_complete') is not True:
        fail('PROFILE_COMPLETE_HISTORY_UNAVAILABLE')
    if history['object_sha256']!=d['object_sha256'] or type(history['revision']) is not int or history['revision']<1:
        fail('PROFILE_HISTORY_DIVERGENCE')
    if type(history['reviews']) is not list or len(set(history['reviews']))!=len(history['reviews']) or d['review_sha256'] not in history['reviews']:
        fail('PROFILE_REVIEW_OMITTED_OR_AMBIGUOUS')
    if context.get('unresolved_adverse_reviews')!=[] or context.get('history_branched') is not False:
        fail('PROFILE_PRIOR_REVIEW_UNRESOLVED')
    if context.get('current_object_sha256')!=d['object_sha256'] or context.get('current_review_sha256')!=d['review_sha256']:
        fail('PROFILE_CURRENT_OBJECT_DIVERGENCE')
    review_fields=('id','object_sha256','outcome','reviewer_execution','author_execution','integrator_execution',
                   'inputs_sha256','findings','limitations','conflicts','participation','mandate_id','accepted','addressed_reviews','completed_at')
    node=history; visited=set(); lineage=[]
    while True:
        node_hash=sha(canonical(node))
        if node_hash in visited or len(visited)>=64:fail('PROFILE_HISTORY_CYCLE_OR_LIMIT')
        visited.add(node_hash);lineage.append(node)
        exact(node,('object_sha256','revision','previous_revision','reviews','prior_reviews','delta_sha256'))
        if type(node['revision']) is not int or node['revision']<1:fail('PROFILE_HISTORY_REVISION_INVALID')
        if type(node['reviews']) is not list or not node['reviews'] or len(set(node['reviews']))!=len(node['reviews']):
            fail('PROFILE_HISTORY_REVIEWS_INVALID')
        if type(node['prior_reviews']) is not list or len(set(node['prior_reviews']))!=len(node['prior_reviews']):
            fail('PROFILE_HISTORY_PRIOR_INVALID')
        previous_object=resolve(node['object_sha256'])
        exact(previous_object,('policy_subject','documents','use'))
        if (previous_object['use']!='autenticar_documento_sefa_pr' or previous_object['documents']!=_DOCUMENTS
            or previous_object['policy_subject'].get('policy_id')!=expected['policy_subject']['policy_id']
            or previous_object['policy_subject'].get('policy_type')!='activation_authority'):fail('PROFILE_HISTORY_SCOPE_DIVERGENCE')
        for report_hash in node['reviews']:
            historic=exact(resolve(report_hash),review_fields)
            if (historic['object_sha256']!=node['object_sha256'] or historic['outcome'] not in ('favoravel','desfavoravel','inconclusivo')
                or historic['participation']!='review_only' or historic['accepted'] is not True
                or type(historic['findings']) is not list or not historic['findings']
                or type(historic['limitations']) is not list or not historic['limitations']):fail('PROFILE_PRIOR_REPORT_INVALID')
            if historic['reviewer_execution'] in (historic['author_execution'],historic['integrator_execution']):fail('PROFILE_PRIOR_REPORT_CONFLICT')
            if historic['outcome']!='favoravel' and node is history:fail('PROFILE_SAME_OBJECT_ADVERSE_REVIEW')
        if node['revision']==1:
            if node['previous_revision'] is not None or node['prior_reviews']!=[] or node['delta_sha256'] is not None:
                fail('PROFILE_HISTORY_ROOT_INVALID')
            break
        previous=resolve(node['previous_revision'])
        if previous.get('revision')!=node['revision']-1 or previous.get('object_sha256')==node['object_sha256']:
            fail('PROFILE_HISTORY_SUCCESSION_INVALID')
        if node['prior_reviews']!=previous.get('reviews',[])+previous.get('prior_reviews',[]):fail('PROFILE_PRIOR_REVIEW_OMITTED')
        delta=exact(resolve(node['delta_sha256']),('from','to','changes','responses'))
        if (delta['from']!=previous['object_sha256'] or delta['to']!=node['object_sha256']
            or type(delta['changes']) is not list or not delta['changes'] or type(delta['responses']) is not dict):
            fail('PROFILE_MATERIAL_DELTA_MISSING')
        for prior in node['prior_reviews']:
            historic=resolve(prior)
            if historic.get('outcome') in ('desfavoravel','inconclusivo'):
                response=delta['responses'].get(prior)
                if type(response) is not str or not response.strip():fail('PROFILE_PRIOR_OBJECTION_UNANSWERED')
                for report_hash in node['reviews']:
                    if prior not in resolve(report_hash)['addressed_reviews']:fail('PROFILE_PRIOR_REVIEW_UNRESOLVED')
        node=previous
    exact(review,('id','object_sha256','outcome','reviewer_execution','author_execution','integrator_execution',
                  'inputs_sha256','findings','limitations','conflicts','participation','mandate_id','accepted','addressed_reviews','completed_at'))
    if (review['object_sha256']!=d['object_sha256'] or review['outcome']!='favoravel' or review['accepted'] is not True
        or review['participation']!='review_only' or review['conflicts']!=[]
        or type(review['findings']) is not list or not review['findings']
        or type(review['limitations']) is not list or not review['limitations']): fail('PROFILE_REVIEW_INSUFFICIENT')
    actors=[review[k] for k in ('reviewer_execution','author_execution','integrator_execution')]
    if any(type(a) is not str or not a.strip() for a in actors) or actors[0] in actors[1:]:
        fail('PROFILE_FUNCTIONAL_CONFLICT')
    records=evidence['execution.json'];exact(records,('executions',))
    mandates=evidence['mandates.json'];exact(mandates,('mandates',))
    if type(records['executions']) is not list or type(mandates['mandates']) is not list: fail('PROFILE_EXECUTION_INVALID')
    if len(records['executions'])!=3 or len(mandates['mandates'])!=3: fail('PROFILE_EXECUTION_AMBIGUOUS')
    known={(x.get('id'),x.get('role')):x for x in records['executions']};mandates_by_id={x.get('id'):x for x in mandates['mandates']}
    if len(known)!=3 or len(mandates_by_id)!=3: fail('PROFILE_EXECUTION_AMBIGUOUS')
    for who,role in zip(actors,('reviewer','author','integrator'),strict=True):
        record=exact(known.get((who,role)),('id','role','mandate_id','context_sha256','inputs_sha256','outputs_sha256','participation','provider','model_observation','occurred_at'))
        mandate=exact(mandates_by_id.get(record['mandate_id']),('id','issuer','execution_id','role','object_sha256','valid_from','valid_until','revoked','accepted','operations','acceptance_sha256'))
        if (record['role']!=role or mandate['issuer']!='Miguel' or mandate['execution_id']!=who or mandate['role']!=role
            or mandate['object_sha256']!=d['object_sha256'] or mandate['accepted'] is not True): fail('PROFILE_MANDATE_DIVERGENCE')
        operations={'reviewer':['review','reprove'],'author':['prepare','submit'],'integrator':['integrate_candidate','test']}
        if mandate['operations']!=operations[role]: fail('PROFILE_MANDATE_OPERATIONS_INVALID')
        body={k:v for k,v in mandate.items() if k not in ('acceptance_sha256','accepted')}
        acceptance=resolve(mandate['acceptance_sha256'])
        if type(acceptance) is not dict or set(acceptance)!= {'execution_id','mandate_sha256','accepted','accepted_at'}:fail('PROFILE_MANDATE_ACCEPTANCE_DIVERGENCE')
        if {k:v for k,v in acceptance.items() if k!='accepted_at'}!={'execution_id':who,'mandate_sha256':sha(canonical(body)),'accepted':True}:
            fail('PROFILE_MANDATE_ACCEPTANCE_DIVERGENCE')
        _current(mandate,now)
        if (dt(d['valid_until'])>dt(mandate['valid_until']) or dt(d['valid_from'])<dt(mandate['valid_from'])
            or not dt(mandate['valid_from'])<=dt(acceptance['accepted_at'])<=dt(record['occurred_at'])<=dt(d['valid_from'])):
            fail('PROFILE_MANDATE_CHRONOLOGY_INVALID')
        if (not record['context_sha256'] or type(record['inputs_sha256']) is not list
            or type(record['outputs_sha256']) is not list or not record['provider'] or not record['model_observation']):fail('PROFILE_EXECUTION_UNDEMONSTRATED')
        context_proof=resolve(record['context_sha256'])
        exact(context_proof,('execution_id','role','instructions','provided_context','participation','limitations'))
        if (context_proof['execution_id']!=who or context_proof['role']!=role
            or not context_proof['instructions'] or not context_proof['provided_context']
            or context_proof['participation']!=record['participation']):fail('PROFILE_CONTEXT_DIVERGENCE')
        for h in record['inputs_sha256']+record['outputs_sha256']:resolve(h)
    auditor=known[(actors[0],'reviewer')]
    if dt(review['completed_at'])!=dt(auditor['occurred_at']):fail('PROFILE_REVIEW_TIME_DIVERGENCE')
    if d['review_sha256'] not in auditor['outputs_sha256']:fail('PROFILE_REVIEW_OUTPUT_MISSING')
    if (auditor['participation']!='review_only' or review['mandate_id']!=auditor['mandate_id']
        or review['inputs_sha256']!=auditor['inputs_sha256'] or d['object_sha256'] not in auditor['inputs_sha256']):
        fail('PROFILE_REVIEW_CONTEXT_DIVERGENCE')
    if context.get('execution_records_sha256')!=sha(canonical(records)) or context.get('mandates_sha256')!=sha(canonical(mandates)):
        fail('PROFILE_EXECUTION_NOT_INDEPENDENTLY_BOUND')
    if expected['audit_report_binding']['sha256']!=d['review_sha256'] or review.get('id')!=expected['audit_report_binding']['id']:
        fail('PROFILE_EXACT_REPORT_BINDING_DIVERGENCE')
    for item in expected['actor_identity_bindings']+[expected['technical_author']]:
        identity=resolve_pin(item['binding'])
        if identity.get('actor_id')!=item['actor_id'] or not identity.get('description'):
            fail('PROFILE_IDENTITY_RECORD_DIVERGENCE')
    for row,pin in zip(decisions,expected['record_evidence_bindings'],strict=True):
        proof=resolve_pin(pin)
        fields=('decision_id','policy_type','policy_id','policy_version','policy_hash','decision_event','institutional_role','actor','previous_decision_id','timestamp')
        if (proof.get('decision')!={k:row[k] for k in fields}
            or proof.get('previous_decision_record_hash')!=row['evidence']['previous_decision_record_hash']):
            fail('PROFILE_EXACT_RECORD_BINDING_DIVERGENCE')
    institutional=exact(evidence['institutional.json'],('expected','decisions'))
    if institutional!={'expected':expected,'decisions':decisions}: fail('PROFILE_CANONICAL_CHAIN_DIVERGENCE')
    # R2 chain validation continues to operate on actual canonical rows. No fake
    # aliases or new event kinds; founder proof does not claim actor signatures.
    binding=dict(expected['policy_subject'],decision_id=expected['decision_bindings'][-1]['id'],decision_hash=expected['decision_bindings'][-1]['sha256'])
    structural=validate_institutional_chain(decisions,binding,now=now,technical_actor=expected['technical_actor'],activated_at=now)
    if {k:v for k,v in structural.items() if k!='institutional_evidence_verified'}!=expected:
        fail('PROFILE_CANONICAL_CHAIN_DIVERGENCE')
    if (dt(decisions[0]['timestamp'])<dt(known[(actors[1],'author')]['occurred_at'])
        or dt(review['completed_at'])<dt(decisions[1]['timestamp'])
        or dt(decisions[2]['timestamp'])<dt(review['completed_at'])
        or dt(d['valid_from'])<dt(decisions[3]['timestamp'])):fail('PROFILE_INSTITUTIONAL_CHRONOLOGY_INVALID')
    # Runtime extension: execution identity is not a database privilege. The
    # binding is both in signed evidence and independently pinned by resolver.
    bound_integrator = actors[2]
    if execution_binding is not None:
        exact(execution_binding,('schema','policy_subject','execution_id','writer_role','activation_binding',
             'execution_record_binding','decision_binding','mandate_sha256','valid_from','valid_until','revoked'))
        bh=sha(canonical(execution_binding))
        if (context.get('execution_writer_binding_sha256')!=bh or resolve(bh)!=execution_binding
            or execution_binding['schema']!='SOLVERIS-B02-EXECUTION-WRITER-BINDING-V1'
            or execution_binding['policy_subject']!=expected['policy_subject']
            or execution_binding['execution_id']!=actors[2]
            or execution_binding['writer_role']!=expected['technical_actor']
            or execution_binding['writer_role']!='solveris_b02_policy_writer'
            or execution_binding['activation_binding']!=context.get('activation_binding')
            or execution_binding['execution_record_binding']!=context.get('execution_record_binding')
            or execution_binding['decision_binding']!=expected['decision_bindings'][-1]
            or execution_binding['mandate_sha256']!=sha(canonical(mandates_by_id[known[(actors[2],'integrator')]['mandate_id']]))):
            fail('PROFILE_EXECUTION_WRITER_BINDING_DIVERGENCE')
        _current(execution_binding,now)
        if dt(d['valid_from'])<dt(execution_binding['valid_from']) or dt(d['valid_until'])>dt(execution_binding['valid_until']):
            fail('PROFILE_EXECUTION_WRITER_INTERVAL_INVALID')
        bound_integrator=execution_binding['writer_role']
    if (expected['actor_identity_bindings'][0]['actor_id']!=actors[1]
        or expected['actor_identity_bindings'][1]['actor_id']!=actors[0]
        or expected['technical_author']['actor_id']!=actors[1]
        or expected['technical_actor']!=bound_integrator
        or expected['actor_identity_bindings'][3]['actor_id']!='Miguel'):
        fail('PROFILE_ACTOR_BINDING_DIVERGENCE')
    return {'status':'verified_synthetic' if synthetic else 'verified','verified_bindings':expected}

class _FounderAdapter:
    def __init__(self,directory,now): self._directory=directory;self._now=now
    def verify_exact_chain(self,*,connection,expected):
        # Explicit separate entrypoint; no fallback on a legacy rejection.
        if connection is None or not connection.in_transaction(): fail('READ_TRANSACTION_REQUIRED')
        from sqlalchemy import text
        actual=tuple(connection.execute(text("SELECT current_database(),session_user,current_user,current_setting('transaction_read_only'),current_setting('transaction_isolation')")).one())
        if actual[:4]!=('solveris_b02_r4g_test','solveris_b02_writer','solveris_b02_writer','on') or actual[4] not in ('repeatable read','serializable'):
            fail('RESTRICTED_CONSISTENT_READ_REQUIRED')
        subject=expected['policy_subject']
        contexts=[c for c in _AUTHORIZED_CONTEXTS.values() if c.get('policy_subject')==subject]
        if len(contexts)!=1: fail('FOUNDER_PROFILE_NOT_OPERATIONALLY_AUTHORIZED')
        context=contexts[0]
        rows=list(connection.execute(text('SELECT d.* FROM public.policy_decisions d WHERE d.policy_type=:policy_type AND d.policy_id=:policy_id AND d.policy_version=:policy_version AND d.policy_hash=:policy_hash'),subject).mappings().all())
        # Normalize DB timestamps for the new canonical documentary envelope.
        normalized=[]
        for row in rows:
            row=dict(row);row['timestamp']=dt(row['timestamp']).isoformat();normalized.append(row)
        order={p['id']:i for i,p in enumerate(expected['decision_bindings'])}
        if any(r['decision_id'] not in order for r in normalized): fail('PROFILE_CANONICAL_BRANCH')
        normalized.sort(key=lambda r:order[r['decision_id']])
        return _verify_bundle(self._directory,expected=expected,decisions=normalized,context=context,now=self._now,synthetic=False)

def admit_with_founder_review_bundle(evidence,*,connection,evidence_directory,now):
    """New explicit entry; authorization registry stays empty in this candidate."""
    from app.services.sefa_pr_documentary_admission import admit_documentary_verification
    return admit_documentary_verification(evidence,connection=connection,now=now,
        institutional_proof_verifier=_FounderAdapter(evidence_directory,now))
