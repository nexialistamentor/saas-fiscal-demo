"""Deterministic read-only SEFA/PR authenticity. No ORM writer or fiscal grant.

Returns an ArtifactVerificationRecord-compatible *proposal*, never a persisted
record. Integrity and institutional authentication have separate outcomes.
No PDF parsing, transport, acquisition, environment switch or client callback.
"""
from datetime import datetime, timezone
import hashlib
from app.services.sefa_pr_documentary_admission import DOCUMENTS, CRITERIA
from app.services.enterprise_b02_institutional_verifier import (
    PreservedEvidenceStore, admit_with_preserved_institutional_proofs,
    _root_for, _verify_signed, deny,
)
from app.services.sefa_pr_policy_projection import PolicyProofError, dt

VERIFIER_ID = 'SOLVERIS_B02_SEFA_PR_PRESERVED_ORIGIN'
VERIFIER_VERSION = '2'
MECHANISM = 'preserved_official_channel_corroboration'

def _verify_origin(store, context, *, root, now, synthetic, document):
    """Private deterministic core. A synthetic result cannot be a real admission."""
    if root.get('synthetic_only') is not synthetic: deny('SYNTHETIC_EVIDENCE_FORBIDDEN')
    if root.get('origin_mechanism') != MECHANISM: deny('ORIGIN_MECHANISM_NOT_AUTHORIZED')
    if root.get('policy_subject') != {k:context['policy_binding'][k] for k in ('policy_type','policy_id','policy_version','policy_hash')}:
        deny('ORIGIN_POLICY_DIVERGENCE')
    expected_verifier = {'id':context.get('verifier_id'),'version':context.get('verifier_version'),'hash':context.get('verifier_hash')}
    if root.get('origin_verifier') != expected_verifier: deny('VERIFIER_NOT_ENABLED')
    # A single approved independent report binds the actual acquisition receipt,
    # TLS transcript and method assessment; untrusted boolean claims are ignored.
    issuer = bytes.fromhex(root['identity_issuer_public_key_hex'])
    identity = _verify_signed(store.resolve(context['origin_verifier_identity']), issuer,
        kind='institutional_identity', now=now, synthetic=synthetic)
    if identity.get('policy_subject') != root['policy_subject']: deny('IDENTITY_POLICY_DIVERGENCE')
    if identity.get('actor_id') != root.get('origin_verifier_actor') or 'documentary_origin_verifier' not in identity.get('roles',[]):
        deny('ORIGIN_VERIFIER_NOT_AUTHORIZED')
    key = bytes.fromhex(identity['public_key_hex'])
    report = _verify_signed(store.resolve(context['independent_origin_report']), key,
        kind='independent_document_origin', now=now, synthetic=synthetic)
    exact_document = {'id':context['document_id'],'url':document[0],'sha256':document[1],'byte_size':document[2]}
    if report.get('document') != exact_document or report.get('policy_binding') != context['policy_binding']:
        deny('ORIGIN_DOCUMENT_DIVERGENCE')
    if report.get('verifier') != expected_verifier or report.get('actor_id') != identity['actor_id']:
        deny('ORIGIN_VERIFIER_DIVERGENCE')
    if report.get('mechanism') != MECHANISM or report.get('outcome') != 'favoravel' or report.get('criteria_id') != CRITERIA:
        deny('ORIGIN_MECHANISM_INSUFFICIENT')
    if report.get('receipt_binding') != {'id':context['receipt_id'],'sha256':context['receipt_hash']}:
        deny('ORIGIN_RECEIPT_DIVERGENCE')
    receipt = store.resolve_json(report['receipt_binding'], signed_identity=False)
    # Historical acquisition receipts need not be newly signed: their exact bytes
    # are pinned by the authorized independent signed report. No relabelling.
    projection = report.get('receipt_projection')
    if not isinstance(projection, dict): deny('PRESERVED_RECEIPT_PROJECTION_MISSING')
    payload = {}
    for name, path in projection.items():
        if not isinstance(path, list) or not path: deny('PRESERVED_RECEIPT_PROJECTION_INVALID')
        value = receipt
        try:
            for part in path: value = value[part]
        except (KeyError, IndexError, TypeError): deny('PRESERVED_RECEIPT_FIELD_MISSING')
        payload[name] = value
    session = {'requested_url':document[0],'resolved_url':document[0], 'http_status':200,
        'session_id':context['session_id'], 'received_at':context['received_at'],
        'artifact_hash':document[1], 'byte_size':document[2]}
    if any(payload.get(k) != v for k,v in session.items()): deny('PRESERVED_RECEIPT_DIVERGENCE')
    if dt(payload['received_at']) > now: deny('PRESERVED_RECEIPT_FUTURE')
    # TLS details must be separately preserved and covered by the report hash.
    tls = store.resolve(report['tls_evidence_binding'])['payload']
    if (tls.get('session_id') != context['session_id'] or tls.get('hostname') != 'www.sefanet.pr.gov.br'
        or tls.get('chain_validation') != 'verified' or tls.get('hostname_validation') != 'verified'
        or tls.get('url') != document[0] or not tls.get('certificate_chain_sha256')
        or not tls.get('validation_transcript') or dt(tls.get('validated_at')) > dt(context['received_at'])):
        deny('TLS_PROOF_INSUFFICIENT')
    # Preserve the existing equal-instant profile. A new unequal-instant
    # profile must prove its actual start in BOTH signed receipt projection
    # and TLS evidence; never synthesize a start or overwrite timestamps.
    started = payload.get('session_started_at')
    tls_started = tls.get('session_started_at')
    validated = dt(tls.get('validated_at'))
    received = dt(context['received_at'])
    temporal_profile = 'legacy_equal_instant'
    if validated != received or 'session_started_at' in payload or 'session_started_at' in tls:
        temporal_profile = 'ordered_session_events'
        if started is None or tls_started is None:
            deny('TLS_CHRONOLOGY_UNPROVEN')
        if dt(started) != dt(tls_started) or not dt(started) <= validated <= received <= now:
            deny('TLS_CHRONOLOGY_DIVERGENCE')
    # TLS and byte identity alone never constitute this report or a grant.
    if report.get('official_identifier') != context['document_id'] or not report.get('doe_references') or not report.get('mechanism_assessment'):
        deny('OFFICIAL_MECHANISM_ASSESSMENT_MISSING')
    return {'status':'verified_synthetic' if synthetic else 'verified', 'origin_report':context['independent_origin_report'],
        'receipt':report['receipt_binding'], 'tls':report['tls_evidence_binding'], 'temporal_profile':temporal_profile}

def verify_document_authenticity(*, normative_artifact_id, document_id, artifact_bytes,
                                context, connection, evidence_directory, now=None):
    """Trusted public entrypoint: no supplied verifier/root, no policy creation."""
    now = now or datetime.now(timezone.utc)
    result = {'normative_artifact_id':normative_artifact_id, 'verified_artifact_hash':None,
        'verification_type':'authenticity', 'outcome':'inconclusivo', 'integrity':'not_checked',
        'origin_authenticated':False, 'fiscal_authority':False, 'synthetic_only':False,
        'write_authorized':False, 'persisted':False, 'verifier':VERIFIER_ID, 'verifier_version':VERIFIER_VERSION}
    try:
        document = DOCUMENTS.get(document_id)
        if document is None or not isinstance(context, dict) or context.get('document_id') != document_id or not normative_artifact_id:
            deny('DOCUMENT_DIVERGENCE')
        if type(artifact_bytes) is not bytes: deny('ARTIFACT_BYTES_REQUIRED')
        actual = hashlib.sha256(artifact_bytes).hexdigest(); result['verified_artifact_hash'] = actual
        if (len(artifact_bytes),actual) != (document[2],document[1]):
            result['integrity']='divergent'; deny('DOCUMENT_BYTES_DIVERGENCE')
        result['integrity']='matches_c3'
        from pathlib import Path
        code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        if (context.get('verifier_id'),context.get('verifier_version'),context.get('verifier_hash')) != (VERIFIER_ID, VERIFIER_VERSION, code_hash):
            deny('VERIFIER_NOT_ENABLED')
        admission = admit_with_preserved_institutional_proofs(context, connection=connection,
            evidence_directory=evidence_directory, now=now)
        if not admission.permitido: deny(admission.motivo)
        root = _root_for({k:context['policy_binding'][k] for k in ('policy_type','policy_id','policy_version','policy_hash')}, now)
        verified = _verify_origin(PreservedEvidenceStore(evidence_directory), context,
            root=root, now=now, synthetic=False, document=document)
        result.update(outcome='conclusivo_favoravel',origin_authenticated=True,reason='EXACT_PRESERVED_ORIGIN_AUTHENTICATED',evidence=verified)
    except PolicyProofError as exc:
        result['reason']=str(exc)
    except Exception:
        result['reason']='INSTITUTIONAL_EVIDENCE_INSUFFICIENT'
    return result
