"""Explicit candidate founder-profile runtime. Read-only; defaults closed.

Preserves the V2/legacy entrypoints. No client callback/root, environment switch,
ledger writer, identity issuer, trust provisioning or automatic fallback.
Origin evidence is a founder-sealed independent assessment, never an AI signature
or official SEFA signature. All favourable test outcomes remain synthetic.
"""
from __future__ import annotations
from datetime import datetime,timezone
from types import MappingProxyType
from pathlib import Path
import copy,hashlib
from app.services import enterprise_b02_founder_review_profile as profile
from app.services.enterprise_b02_institutional_verifier import PreservedEvidenceStore
from app.services.sefa_pr_policy_projection import (
    PolicyProofError,dt,validate_institutional_chain,project_current_authorization,
)
from app.services.sefa_pr_documentary_admission import DOCUMENTS,CRITERIA

RUNTIME_PROFILE='FOUNDER_SIGNED_REVIEW_BUNDLE_B02_RUNTIME_V1'
VERIFIER_ID='SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN'
VERIFIER_VERSION='1'
MECHANISM='preserved_official_channel_corroboration'
# Future entries require a separate authorized deployment, outside this candidate.
# Pins come from the recognized authority source, NEVER from request/evidence/env.
_RUNTIME_AUTHORIZATIONS=MappingProxyType({})

def fail(code):raise PolicyProofError(code)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def digest(v):return sha(profile.canonical(_plain(v)))
def _plain(v):
    if isinstance(v,datetime):return dt(v).isoformat()
    if isinstance(v,dict):return {k:_plain(x) for k,x in v.items()}
    if isinstance(v,list):return [_plain(x) for x in v]
    return v

def _texts(value):
    return type(value) is list and bool(value) and all(type(v) is str and bool(v.strip()) for v in value)

def _contains_synthetic(value):
    if type(value) is dict:
        return ('synthetic_only' in value and value['synthetic_only'] is not False) or any(_contains_synthetic(v) for v in value.values())
    return type(value) is list and any(_contains_synthetic(v) for v in value)

def _resolve(store,pin):
    if type(store) is not PreservedEvidenceStore:fail('RUNTIME_TRUSTED_STORE_REQUIRED')
    value=store.resolve_json(pin,signed_identity=False)
    if value.get('id')!=pin['id']:fail('RUNTIME_EVIDENCE_ID_DIVERGENCE')
    return value

def _root(subject,now):
    matches=[r for r in _RUNTIME_AUTHORIZATIONS.values() if r.get('policy_subject')==subject]
    if len(matches)!=1:fail('RUNTIME_AUTHORIZATION_MISSING_OR_AMBIGUOUS')
    root=copy.deepcopy(matches[0]);_current(root,now,False)
    return root

def _current(value,now,synthetic):
    if value.get('synthetic_only') is not synthetic:fail('RUNTIME_SYNTHETIC_DOMAIN_DIVERGENCE')
    profile._current(value,dt(now))

def _read_identity(connection):
    if connection is None or not connection.in_transaction():fail('RUNTIME_READ_TRANSACTION_REQUIRED')
    from sqlalchemy import text
    identity=tuple(connection.execute(text("SELECT current_database(),session_user,current_user,current_setting('transaction_read_only'),current_setting('transaction_isolation')")).one())
    if identity[:4]!=('solveris_b02_r4g_test','solveris_b02_writer','solveris_b02_writer','on') or identity[4] not in ('repeatable read','serializable'):
        fail('RUNTIME_RESTRICTED_READ_REQUIRED')
    flags=connection.execute(text('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolinherit FROM pg_roles WHERE rolname=current_user')).one()
    memberships=connection.execute(text('SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)')).scalar_one()
    if any(flags) or memberships:fail('RUNTIME_PRIVILEGED_READER_FORBIDDEN')

def _read_snapshot(connection,subject,binding):
    from sqlalchemy import text
    # ALL versions/events of policy ID: later, adverse or competing rows cannot
    # be hidden by selecting only a favourable terminal decision.
    decisions=[_plain(dict(r)) for r in connection.execute(text('''/* FOUNDER_RUNTIME_DECISIONS */
 SELECT d.* FROM public.policy_decisions d WHERE d.policy_type=:policy_type AND d.policy_id=:policy_id'''),subject).mappings().all()]
    activation=connection.execute(text('''/* FOUNDER_RUNTIME_EXACT_ACTIVATION */
 SELECT a.* FROM public.policy_activations a WHERE a.policy_activation_id=:policy_activation_id
 AND a.record_hash=:policy_activation_record_hash AND a.policy_id=:policy_id
 AND a.policy_version=:policy_version AND a.policy_hash=:policy_hash AND a.policy_type=:policy_type'''),binding).mappings().one_or_none()
    if activation is None:fail('RUNTIME_EXACT_ACTIVATION_MISSING')
    activation=_plain(dict(activation))
    execution=connection.execute(text('''/* FOUNDER_RUNTIME_EXACT_EXECUTION */
 SELECT e.* FROM public.policy_activation_executions e WHERE e.policy_activation_execution_id=:id'''),{'id':activation['policy_activation_execution_id']}).mappings().one_or_none()
    if execution is None:fail('RUNTIME_EXACT_EXECUTION_MISSING')
    return decisions,activation,_plain(dict(execution))

def _resolve_history(store,root,decisions,*,now,synthetic):
    """Read adapter over pinned preserved history; no new history/event writer.

    Recognized head pin and canonical DB snapshot commitment are external to the
    bundle. History omission, stale DB projection and a claimed boolean fail.
    """
    _current(root,now,synthetic)
    if (root.get('runtime_profile')!=RUNTIME_PROFILE or root.get('adoption_sha256')!=profile.ADOPTION
        or not root.get('recognition_binding') or not root.get('bootstrap_binding')):
        fail('RUNTIME_ROOT_PREDECESSORS_MISSING')
    snapshot=_resolve(store,root['snapshot_binding'])
    profile.exact(snapshot,('id','schema','policy_subject','canonical_decisions_sha256','head_binding',
        'genesis_binding','context','execution_writer_binding','origin_report_bindings','origin_mandate_binding',
        'valid_from','valid_until','revoked','synthetic_only'))
    _current(snapshot,now,synthetic)
    if snapshot['schema']!='SOLVERIS-B02-AUTHORIZED-READ-SNAPSHOT-V1' or snapshot['policy_subject']!=root['policy_subject']:
        fail('RUNTIME_SNAPSHOT_SUBJECT_DIVERGENCE')
    rows=sorted(decisions,key=lambda r:r['decision_id'])
    if snapshot['canonical_decisions_sha256']!=digest(rows):fail('RUNTIME_STALE_OR_OMITTED_CANONICAL_DECISIONS')
    current=snapshot['head_binding'];seen=set();nodes=[]
    while current is not None:
        key=(current['id'],current['sha256'])
        if key in seen or len(seen)>=64:fail('RUNTIME_HISTORY_CYCLE_OR_LIMIT')
        seen.add(key);node=_resolve(store,current)
        profile.exact(node,('id','schema','policy_subject','sequence','previous','history_sha256',
            'review_hashes','object_sha256','current_review_sha256','supersedes','valid_from','valid_until','revoked','synthetic_only'))
        _current(node,now,synthetic)
        if (node['schema']!='SOLVERIS-B02-PRESERVED-REVIEW-PROJECTION-V1'
            or node['policy_subject']!=root['policy_subject'] or type(node['sequence']) is not int
            or node['sequence']<1 or type(node['review_hashes']) is not list
            or len(set(node['review_hashes']))!=len(node['review_hashes']) or not node['review_hashes']):
            fail('RUNTIME_HISTORY_NODE_INVALID')
        if nodes:
            child=nodes[-1]
            if (child['sequence']!=node['sequence']+1 or child['supersedes']!=current
                or child['object_sha256']==node['object_sha256']):fail('RUNTIME_HISTORY_SUCCESSION_INVALID')
        nodes.append(node)
        if node['previous'] is None:
            if node['sequence']!=1 or current!=snapshot['genesis_binding'] or node['supersedes'] is not None:
                fail('RUNTIME_HISTORY_GENESIS_DIVERGENCE')
        current=node['previous']
    if not nodes:fail('RUNTIME_HISTORY_EMPTY')
    context=copy.deepcopy(snapshot['context']);head=nodes[0]
    if (context.get('history_sha256')!=head['history_sha256']
        or context.get('current_object_sha256')!=head['object_sha256']
        or context.get('current_review_sha256')!=head['current_review_sha256']):
        fail('RUNTIME_HISTORY_CONTEXT_DIVERGENCE')
    # These values follow the resolved authoritative chain, not incoming flags.
    context.update(policy_subject=root['policy_subject'],synthetic_only=synthetic,
        profile=profile.PROFILE,adoption_sha256=profile.ADOPTION,scope=profile.SCOPE,
        public_key_der_hex=root['public_key_der_hex'],key_fingerprint=root['key_fingerprint'],
        bootstrap_binding=root['bootstrap_binding'],authorization_binding=root['recognition_binding'],
        valid_from=max(dt(root['valid_from']),dt(snapshot['valid_from'])).isoformat(),valid_until=min(dt(root['valid_until']),dt(snapshot['valid_until'])).isoformat(),
        revoked=False,enabled=True,channel_authorized=True,history_complete=True,history_branched=False,unresolved_adverse_reviews=[])
    return snapshot,context,nodes

def _binding(context,proof_binding,activation,execution,expected,*,now):
    # Compare data privileges to the actual canonical execution and preserve the
    # separately mandated integrator execution identity; never rename one as other.
    if (proof_binding.get('writer_role')!='solveris_b02_policy_writer'
        or execution.get('actor_or_worker')!=proof_binding['writer_role']
        or activation.get('technical_actor')!=proof_binding['writer_role']
        or expected['technical_actor']!=proof_binding['writer_role']
        or execution.get('state')!='concluida' or activation.get('state')!='activa'
        or activation.get('policy_activation_execution_id')!=execution.get('policy_activation_execution_id')
        or activation.get('policy_decision_id')!=expected['decision_bindings'][-1]['id']
        or execution.get('policy_decision_id')!=expected['decision_bindings'][-1]['id']
        or execution.get('policy_decision_record_hash')!=expected['decision_bindings'][-1]['sha256']):
        fail('RUNTIME_EXECUTION_WRITER_DIVERGENCE')
    for row in (activation,execution):
        if {k:row.get(k) for k in ('policy_type','policy_id','policy_version','policy_hash')}!=expected['policy_subject']:
            fail('RUNTIME_EXECUTION_POLICY_DIVERGENCE')
    actual_a={'id':activation['policy_activation_id'],'sha256':activation['record_hash']}
    actual_e={'id':execution['policy_activation_execution_id'],'sha256':execution['record_hash']}
    if proof_binding['activation_binding']!=actual_a or proof_binding['execution_record_binding']!=actual_e:
        fail('RUNTIME_ACTIVATION_BINDING_DIVERGENCE')
    context.update(activation_binding=actual_a,execution_record_binding=actual_e,
                   execution_writer_binding_sha256=digest(proof_binding))
    profile._current(proof_binding,dt(now))

def _institutional_core(store,bundle_directory,*,root,decisions,activation,execution,expected,now,synthetic):
    snapshot,context,nodes=_resolve_history(store,root,decisions,now=now,synthetic=synthetic)
    binding=snapshot['execution_writer_binding']
    _binding(context,binding,activation,execution,expected,now=now)
    frozen=profile._BundleSnapshot(bundle_directory)
    chain={r['decision_id']:r for r in decisions if {k:r[k] for k in ('policy_type','policy_id','policy_version','policy_hash')}==expected['policy_subject']}
    if len({r['decision_id'] for r in decisions})!=len(decisions) or set(chain)!={p['id'] for p in expected['decision_bindings']}:fail('RUNTIME_CANONICAL_CHAIN_AMBIGUOUS')
    ordered=[chain[p['id']] for p in expected['decision_bindings']]
    result=profile._verify_bundle(bundle_directory,expected=expected,decisions=ordered,
        context=context,now=now,synthetic=synthetic,execution_binding=binding,bundle_snapshot=frozen)
    history=profile.parse(frozen.read('history.json'))
    all_reviews=history['reviews']+history['prior_reviews']
    projected=[r for n in reversed(nodes) for r in n['review_hashes']]
    if len(set(projected))!=len(projected) or set(projected)!=set(all_reviews):fail('RUNTIME_HISTORY_REVIEW_OMISSION_OR_BRANCH')
    if nodes[0]['current_review_sha256']!=context['current_review_sha256']:fail('RUNTIME_CURRENT_REVIEW_DIVERGENCE')
    proofs=profile.parse(frozen.read('proofs.json'))
    current_history=history
    for index,node in enumerate(nodes):
        if (digest(current_history)!=node['history_sha256'] or current_history['object_sha256']!=node['object_sha256']
            or current_history['reviews']!=node['review_hashes'] or node['current_review_sha256'] not in current_history['reviews']
            or current_history['revision']!=node['sequence']):fail('RUNTIME_HISTORY_NODE_SNAPSHOT_DIVERGENCE')
        previous=current_history['previous_revision']
        if index==len(nodes)-1:
            if previous is not None:fail('RUNTIME_HISTORY_PREDECESSOR_OMITTED')
        else:
            current_history=proofs.get(previous)
            if type(current_history) is not dict:fail('RUNTIME_HISTORY_SNAPSHOT_MISSING')
    context['verified_author_execution']=profile.parse(frozen.read('review.json'))['author_execution']
    context['verified_integrator_execution']=profile.parse(frozen.read('review.json'))['integrator_execution']
    return result,snapshot,context,proofs

class _RuntimeAdapter:
    def __init__(self,bundle_directory,evidence_directory,now,binding):
        self.bundle=bundle_directory;self.store=PreservedEvidenceStore(evidence_directory)
        self.now=now;self.binding=copy.deepcopy(binding);self.resolved=None
    def verify_exact_chain(self,*,connection,expected):
        _read_identity(connection);root=_root(expected['policy_subject'],self.now)
        decisions,activation,execution=_read_snapshot(connection,expected['policy_subject'],self.binding)
        result,snapshot,context,proofs=_institutional_core(self.store,self.bundle,root=root,decisions=decisions,
            activation=activation,execution=execution,expected=expected,now=self.now,synthetic=False)
        self.resolved=(root,snapshot,context,proofs,decisions,activation,execution,expected)
        return result


def admit_with_founder_runtime(evidence,*,connection,bundle_directory,evidence_directory,now):
    """Explicit new entrypoint; no callback/root/profile argument from clients."""
    from app.services.sefa_pr_documentary_admission import admit_documentary_verification
    binding=evidence.get('policy_binding',{}) if type(evidence) is dict else {}
    adapter=_RuntimeAdapter(bundle_directory,evidence_directory,now,binding)
    return admit_documentary_verification(evidence,connection=connection,now=now,institutional_proof_verifier=adapter)


def _origin_core(store,bundle_directory,context,*,root,snapshot,now,synthetic,verified_proofs,verified_context):
    """Validate signed independent report and actual preserved V2 transport data.

    Founder signature has already authenticated the EXACT proofs.json containing
    report/mandate, not official SEFA authorship. A separately authorized examiner
    must actually have performed/accepted the origin examination.
    """
    _current(root,now,synthetic);document=DOCUMENTS.get(context.get('document_id'))
    if document is None:fail('RUNTIME_ORIGIN_DOCUMENT_UNKNOWN')
    pins=snapshot['origin_report_bindings']
    if type(pins) is not dict or set(pins)!=set(DOCUMENTS):fail('RUNTIME_ORIGIN_REPORT_SET_INVALID')
    pin=pins[context['document_id']];proofs=verified_proofs
    report=proofs.get(pin['sha256']);mandate=proofs.get(snapshot['origin_mandate_binding']['sha256'])
    if report is None or digest(report)!=pin['sha256'] or report.get('id')!=pin['id']:
        fail('RUNTIME_SIGNED_ORIGIN_REPORT_MISSING')
    if mandate is None or digest(mandate)!=snapshot['origin_mandate_binding']['sha256'] or mandate.get('id')!=snapshot['origin_mandate_binding']['id']:
        fail('RUNTIME_ORIGIN_MANDATE_MISSING')
    profile.exact(report,('id','kind','policy_subject','document','actor_execution','technical_author_execution','technical_integrator_execution',
        'mandate_binding','mandate_acceptance_sha256','mechanism','criteria_id','outcome','verifier','receipt_binding','receipt_projection',
        'tls_evidence_binding','official_identifier','doe_references','mechanism_assessment','examination_record_sha256',
        'examined_at','valid_from','valid_until','revoked','synthetic_only'))
    profile.exact(mandate,('id','issuer','policy_subject','execution_id','operations','valid_from','valid_until','revoked','synthetic_only'))
    for item in (report,mandate):_current(item,now,synthetic)
    if (report['kind']!='independent_document_origin_founder_sealed' or report['policy_subject']!=root['policy_subject']
        or mandate['policy_subject']!=root['policy_subject'] or mandate['issuer']!='Miguel'
        or report['mandate_binding']!=snapshot['origin_mandate_binding']
        or mandate['execution_id']!=report['actor_execution']
        or mandate['operations']!=['examine_document_origin','report','abstain']
        or report['technical_author_execution']!=verified_context.get('verified_author_execution')
        or report['technical_integrator_execution']!=verified_context.get('verified_integrator_execution')
        or not report['actor_execution'] or report['actor_execution'] in (report['technical_author_execution'],report['technical_integrator_execution'])
        or report['outcome']!='favoravel' or report['mechanism']!=MECHANISM or report['criteria_id']!=CRITERIA):
        fail('RUNTIME_ORIGIN_AUTHORITY_OR_SEGREGATION_INVALID')
    acceptance=proofs.get(report['mandate_acceptance_sha256']);examination=proofs.get(report['examination_record_sha256'])
    if type(acceptance) is not dict or set(acceptance)!={'execution_id','mandate_sha256','accepted','accepted_at'}:
        fail('RUNTIME_ORIGIN_ACCEPTANCE_INVALID')
    if {k:acceptance[k] for k in ('execution_id','mandate_sha256','accepted')}!={'execution_id':report['actor_execution'],'mandate_sha256':digest(mandate),'accepted':True}:fail('RUNTIME_ORIGIN_ACCEPTANCE_INVALID')
    if type(examination) is not dict or examination.get('actor_execution')!=report['actor_execution'] or examination.get('document')!=report['document'] or examination.get('mandate_binding')!=report['mandate_binding'] or examination.get('examined_at')!=report['examined_at'] or not _texts(examination.get('own_findings')) or not _texts(examination.get('limitations')):
        fail('RUNTIME_ORIGIN_OWN_EXAMINATION_MISSING')
    when=dt(report['examined_at'])
    if not dt(mandate['valid_from'])<=dt(acceptance['accepted_at'])<=when<dt(mandate['valid_until']) or when>dt(now):fail('RUNTIME_ORIGIN_MANDATE_CHRONOLOGY')
    exact_document={'id':context['document_id'],'url':document[0],'sha256':document[1],'byte_size':document[2]}
    verifier={'id':VERIFIER_ID,'version':VERIFIER_VERSION,'hash':sha(Path(__file__).read_bytes())}
    if (report['document']!=exact_document or report['official_identifier']!=context['document_id']
        or report['verifier']!=verifier or {k:context.get('verifier_'+k) for k in ('id','version','hash')}!=verifier
        or not _texts(report['doe_references']) or not _texts(report['mechanism_assessment'])):fail('RUNTIME_ORIGIN_SCOPE_DIVERGENCE')
    if report['receipt_binding']!={'id':context['receipt_id'],'sha256':context['receipt_hash']}:fail('RUNTIME_ORIGIN_RECEIPT_BINDING')
    receipt=store.resolve_json(report['receipt_binding'],signed_identity=False)
    if not synthetic and _contains_synthetic(receipt):fail('RUNTIME_SYNTHETIC_TRANSPORT_FORBIDDEN')
    projection=report['receipt_projection'];payload={}
    names={'requested_url','resolved_url','http_status','session_id','received_at','artifact_hash','byte_size','session_started_at'}
    if type(projection) is not dict or set(projection)!=names:fail('RUNTIME_RECEIPT_PROJECTION_INVALID')
    for name,path in projection.items():
        if type(path) is not list or not path:fail('RUNTIME_RECEIPT_PROJECTION_INVALID')
        current=receipt
        try:
            for segment in path:current=current[segment]
        except (TypeError,KeyError,IndexError):fail('RUNTIME_RECEIPT_FIELD_MISSING')
        payload[name]=current
    wanted={'requested_url':document[0],'resolved_url':document[0],'http_status':200,'session_id':context['session_id'],
        'received_at':context['received_at'],'artifact_hash':document[1],'byte_size':document[2]}
    if any(payload.get(k)!=v for k,v in wanted.items()) or type(payload['http_status']) is not int or type(payload['byte_size']) is not int:
        fail('RUNTIME_RECEIPT_DIVERGENCE')
    tls=store.resolve(report['tls_evidence_binding'])['payload']
    if not synthetic and _contains_synthetic(tls):fail('RUNTIME_SYNTHETIC_TRANSPORT_FORBIDDEN')
    if (tls.get('session_id')!=context['session_id'] or tls.get('hostname')!='www.sefanet.pr.gov.br'
        or tls.get('url')!=document[0] or tls.get('chain_validation')!='verified' or tls.get('hostname_validation')!='verified'
        or not tls.get('certificate_chain_sha256') or not tls.get('validation_transcript')):fail('RUNTIME_TLS_PROOF_INSUFFICIENT')
    if (dt(payload['session_started_at'])!=dt(tls.get('session_started_at'))
        or not dt(payload['session_started_at'])<=dt(tls.get('validated_at'))<=dt(payload['received_at'])<=when<=dt(now)):
        fail('RUNTIME_TLS_SESSION_CHRONOLOGY')
    return {'status':'verified_synthetic' if synthetic else 'verified','origin_report_binding':pin,
            'receipt_binding':report['receipt_binding'],'tls_binding':report['tls_evidence_binding'],'temporal_profile':'ordered_session_events'}


def verify_document_authenticity_with_founder_runtime(*,normative_artifact_id,document_id,artifact_bytes,
        context,connection,bundle_directory,evidence_directory,now=None):
    """V3 separate entrypoint. No implicit selection or fallback from V2."""
    now=now or datetime.now(timezone.utc)
    result={'normative_artifact_id':normative_artifact_id,'verified_artifact_hash':None,'verification_type':'authenticity',
        'outcome':'inconclusivo','integrity':'not_checked','origin_authenticated':False,'fiscal_authority':False,
        'synthetic_only':False,'write_authorized':False,'persisted':False,'verifier':VERIFIER_ID,'verifier_version':VERIFIER_VERSION}
    try:
        document=DOCUMENTS.get(document_id)
        if document is None or type(context) is not dict or context.get('document_id')!=document_id or not normative_artifact_id:
            fail('RUNTIME_DOCUMENT_DIVERGENCE')
        if type(artifact_bytes) is not bytes:fail('RUNTIME_ARTIFACT_BYTES_REQUIRED')
        actual=sha(artifact_bytes);result['verified_artifact_hash']=actual
        if (len(artifact_bytes),actual)!=(document[2],document[1]):
            result['integrity']='divergent';fail('RUNTIME_DOCUMENT_BYTES_DIVERGENCE')
        result['integrity']='matches_c3'
        expected_verifier=(VERIFIER_ID,VERIFIER_VERSION,sha(Path(__file__).read_bytes()))
        if tuple(context.get('verifier_'+k) for k in ('id','version','hash'))!=expected_verifier:fail('RUNTIME_VERIFIER_NOT_ENABLED')
        _read_identity(connection)
        subject={k:context['policy_binding'][k] for k in ('policy_type','policy_id','policy_version','policy_hash')}
        _root(subject,now)  # Fail before any policy admission when no recognized root.
        from app.services.sefa_pr_documentary_admission import admit_documentary_verification
        adapter=_RuntimeAdapter(bundle_directory,evidence_directory,now,context['policy_binding'])
        admitted=admit_documentary_verification(context,connection=connection,now=now,institutional_proof_verifier=adapter)
        if not admitted.permitido:fail(admitted.motivo)
        if adapter.resolved is None:fail('RUNTIME_INSTITUTIONAL_PROOF_NOT_RESOLVED')
        root,snapshot,proof_context,proofs,*_=adapter.resolved
        verified=_origin_core(adapter.store,bundle_directory,context,root=root,snapshot=snapshot,now=now,synthetic=False,verified_proofs=proofs,verified_context=proof_context)
        result.update(outcome='conclusivo_favoravel',origin_authenticated=True,reason='EXACT_FOUNDER_PROFILE_ORIGIN_AUTHENTICATED',evidence=verified)
    except PolicyProofError as exc:result['reason']=str(exc)
    except Exception:result['reason']='RUNTIME_EVIDENCE_INSUFFICIENT'
    return result
