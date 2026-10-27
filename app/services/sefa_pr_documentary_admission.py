"""Candidate SEFA/PR admission only. No verifier, network, writes or authority creation.
The read connection is internal, never accepted from an HTTP/client payload.
Positive admission authorizes requesting a verification; it is NOT authenticity.
"""
from datetime import datetime,timezone,timedelta
import re
from app.schemas.source_authority_schema import SourceAuthorityResult

USE='autenticar_documento_sefa_pr'
SOURCE='SEFA-PR-B02-DOCUMENTAL'
CRITERIA='SEFA_PR_DOCUMENTARY_ADMISSION_V1'
DOCUMENTS={
 '101202501245':('https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/101202501245.pdf','e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832',258302),
 '101201900571':('https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/101201900571.pdf','af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d',1944929),
}

def _result(code,allowed=False):
    return SourceAuthorityResult(permitido=allowed,fonte_id=SOURCE,uso_pretendido=USE,motivo=code,
      acao='Admissao documental somente; autenticidade nao executada.',pode_fundamentar_decisao=False,pode_validar_fato_operacional=False,pode_ser_usada_por_llm=False)

def _time(value):
    if not isinstance(value,str):raise ValueError('TIME_REQUIRED')
    v=datetime.fromisoformat(value.replace('Z','+00:00'))
    if v.tzinfo is None:raise ValueError('TIMEZONE_REQUIRED')
    return v.astimezone(timezone.utc)

def _hash(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None

def admit_documentary_verification(evidence,*,connection=None,now=None,institutional_proof_verifier=None):
    """Read-only policy admission. Missing data/DB/proof always abstains.

    Proposed real policy uses existing activation_authority, not coverage as a
    grant. Binding and current policy records are queried with exact identities.
    No source is added to the global manifest and no existing use is expanded.
    """
    if not isinstance(evidence,dict):return _result('DOCUMENTARY_CONTEXT_REQUIRED')
    if evidence.get('source_id')!=SOURCE:return _result('SOURCE_NOT_AUTHORIZED')
    item=DOCUMENTS.get(evidence.get('document_id'))
    if item is None or (evidence.get('url'),evidence.get('artifact_hash'),evidence.get('byte_size'))!=item or evidence.get('resolved_url')!=item[0] or type(evidence.get('byte_size')) is not int:
        return _result('DOCUMENT_DIVERGENCE')
    if evidence.get('tls_verified') is not True or type(evidence.get('http_status')) is not int or evidence['http_status']!=200 or not all(isinstance(evidence.get(k),str) and evidence[k].strip() for k in ('session_id','tls_evidence_reference','receipt_id')) or not _hash(evidence.get('receipt_hash')):
        return _result('ACQUISITION_EVIDENCE_INCOMPLETE')
    if evidence.get('criteria_id')!=CRITERIA:return _result('VERIFICATION_CRITERIA_DIVERGENCE')
    b=evidence.get('policy_binding')
    required={'policy_type','policy_id','policy_version','policy_hash','policy_activation_id','policy_activation_record_hash','decision_id','decision_hash'}
    if not isinstance(b,dict) or set(b)!=required or not all(_hash(b.get(k)) for k in ('policy_hash','policy_activation_record_hash','decision_hash')) or not all(isinstance(b.get(k),str) and b[k].strip() for k in ('policy_id','policy_activation_id','decision_id')) or type(b.get('policy_version')) is not int or b['policy_version']<1:
        return _result('EXACT_DECISION_REQUIRED')
    if b['policy_type']!='activation_authority':return _result('AUTHORITY_POLICY_TYPE_REQUIRED')
    if now is None:now=datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None:return _result('CLOCK_INVALID')
    try:observed=_time(evidence.get('received_at'))
    except (ValueError,TypeError):return _result('ACQUISITION_EVIDENCE_INCOMPLETE')
    if observed>now:return _result('ACQUISITION_EVIDENCE_EXPIRED')
    if connection is None or not connection.in_transaction():return _result('AUTHORITATIVE_READ_CONNECTION_REQUIRED')
    from sqlalchemy import text
    try:
        identity=tuple(connection.execute(text("SELECT current_database(),session_user,current_user,current_setting('transaction_read_only')")).one())
        if identity!=('solveris_b02_r4g_test','solveris_b02_writer','solveris_b02_writer','on'):return _result('RESTRICTED_READ_IDENTITY_REQUIRED')
        flags=connection.execute(text('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolinherit FROM pg_roles WHERE rolname=current_user')).one()
        if any(flags) or connection.execute(text('SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)')).scalar_one():return _result('RESTRICTED_READ_IDENTITY_REQUIRED')
        row=connection.execute(text('''SELECT p.policy_type,p.domain,p.scope,p.rules,p.origin_evidence AS policy_provenance,
 a.state,a.operational_interval,a.provenance AS activation_provenance,a.technical_actor,a.activated_at,a.modality,
 a.policy_activation_execution_id AS policy_execution_id,d.decision_event,d.institutional_role,d.actor
 FROM public.policy_versions p
 JOIN public.policy_activations a ON a.policy_id=p.policy_id AND a.policy_version=p.policy_version AND a.policy_hash=p.policy_hash AND a.policy_type=p.policy_type
 JOIN public.policy_decisions d ON d.decision_id=a.policy_decision_id AND d.policy_id=p.policy_id AND d.policy_version=p.policy_version AND d.policy_hash=p.policy_hash AND d.policy_type=p.policy_type
 WHERE p.policy_type=:policy_type AND p.policy_id=:policy_id AND p.policy_version=:policy_version AND p.policy_hash=:policy_hash
 AND a.policy_activation_id=:policy_activation_id AND a.record_hash=:policy_activation_record_hash
 AND d.decision_id=:decision_id AND d.record_hash=:decision_hash'''),b).mappings().one_or_none()
        if row is None:return _result('EXACT_AUTHORITY_BINDING_MISSING')
        if row['policy_type']!='activation_authority' or row['domain']!='SEFA_PR_B02_DOCUMENTAL':return _result('SOURCE_NOT_AUTHORIZED')
        from app.services.sefa_pr_policy_projection import PolicyProofError,require_current_authority
        try:
            require_current_authority(connection,b,row,now=now,proof_verifier=institutional_proof_verifier)
        except PolicyProofError as error:
            return _result(str(error))
        if row['decision_event']!='ratificada' or row['institutional_role']!='autoridade_constitucional_final' or not row['actor'] or row['actor']==row['technical_actor']:return _result('EXACT_DECISION_REQUIRED')
        for key in ('policy_provenance','activation_provenance'):
            # No automatic promotion of an unmarked or synthetic specimen.
            if not isinstance(row[key],dict) or row[key].get('synthetic_only') is not False:return _result('SYNTHETIC_AUTHORITY_FORBIDDEN')
        scope=row['scope']
        if not isinstance(scope,dict) or scope.get('source_id')!=SOURCE or evidence['artifact_hash'] not in scope.get('document_hashes',[]):return _result('SOURCE_NOT_AUTHORIZED')
        interval=row['operational_interval']
        try:
            start=_time(interval['from']);end=_time(interval['until'])
            if row['state']!='activa' or not start<=now<end:return _result('AUTHORIZATION_NOT_CURRENT')
        except (KeyError,TypeError,ValueError):return _result('AUTHORIZATION_NOT_CURRENT')
        rule=row['rules'].get('sefa_pr_documentary_admission',{})
        if rule.get('schema')!=CRITERIA or rule.get('source_id')!=SOURCE or rule.get('uses')!=[USE] or rule.get('criteria_id')!=CRITERIA:return _result('SOURCE_NOT_AUTHORIZED')
        preserved={'id':evidence['receipt_id'],'sha256':evidence['receipt_hash']} in rule.get('preserved_receipts',[])
        if observed<start and not preserved:return _result('HISTORICAL_RECEIPT_NOT_AUTHORIZED')
        expected={'id':evidence['document_id'],'url':item[0],'sha256':item[1],'byte_size':item[2]}
        if expected not in rule.get('documents',[]):return _result('DOCUMENT_DIVERGENCE')
        verifier={'id':evidence.get('verifier_id'),'version':evidence.get('verifier_version'),'hash':evidence.get('verifier_hash')}
        if not all(isinstance(v,str) and v.strip() for v in verifier.values()) or not _hash(verifier['hash']) or verifier not in rule.get('verifiers',[]):return _result('VERIFIER_NOT_ENABLED')
        max_age=rule.get('max_evidence_age_seconds')
        if type(max_age) is not int or not 1<=max_age<=86400:return _result('VERIFICATION_CRITERIA_DIVERGENCE')
        if now-observed>timedelta(seconds=max_age) and not preserved:return _result('ACQUISITION_EVIDENCE_EXPIRED')
        connection.execute(text('SELECT public.b02p_require_complete(:execution_id,false)'),{'execution_id':row['policy_execution_id']})
    except Exception:
        # Do not leak SQL parameters, credentials or untrusted report contents.
        return _result('AUTHORITATIVE_PROOF_UNAVAILABLE')
    return _result('DOCUMENTARY_VERIFICATION_REQUEST_ADMITTED_NOT_AUTHENTICATED',True)

def verification_procedure():
    """Audit specification only: not an attestation, ORM row or writer."""
    return {'execution_status':'NOT_EXECUTED','entity':'ArtifactVerificationRecord','verification_type':'authenticity',
      'outcome':None,'allowed_outcomes':['conclusivo_favoravel','conclusivo_desfavoravel','inconclusivo'],
      'required_subject':['normative_artifact_id','verified_artifact_hash'],
      'required_verifier':['verifier','verifier_version','authorized_verifier_hash'],
      'required_evidence':['source_authorization_exact_binding','session_response_receipt','tls_validation_evidence','official_mechanism_assessment','independent_origin_report'],
      'abstentions':['authority_missing','verifier_missing','evidence_incomplete','official_mechanism_insufficient','document_divergence'],
      'write_authorized':False,'fiscal_authority':False}
