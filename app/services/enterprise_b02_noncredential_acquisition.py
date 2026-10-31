"""ADR-020 R4F boundaries. No network, credentials, policy activation or commit."""
from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping

MODES = ('EXTERNAL_CREDENTIALLED', 'EXTERNAL_PUBLIC_NO_CREDENTIALS', 'LOCAL_CAS_INCORPORATION')
CANONICAL_CONTRACT_ID = 'ADR020_B02_INTEGER_JSON_UTF8_V1'
CANONICAL_CONTRACT_VERSION = 1
# Fixed specification; metadata hashes exclude only their own record_hash.
CANONICAL_SPEC = ('UTF-8;JSON;sorted-Unicode-keys;compact-separators;ensure_ascii=false;'
                  'integers-only;no-duplicate-keys;record-excludes-record_hash;'
                  'receipt-material-excludes:receipt_id,receipt_hash,receipt_created_at,creator,provenance,record_hash')
CANONICAL_CONTRACT_HASH = hashlib.sha256(CANONICAL_SPEC.encode('utf-8')).hexdigest()

class AcquisitionEvidenceError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def _fail(code):
    raise AcquisitionEvidenceError(code)

def _canonical_value(value):
    if value is None or type(value) in (str, bool, int):
        return
    if isinstance(value, list):
        for item in value: _canonical_value(item)
        return
    if isinstance(value, dict) and all(type(k) is str for k in value):
        for item in value.values(): _canonical_value(item)
        return
    _fail('CANONICALIZATION_INVALID')

def canonical_bytes(value):
    try:
        _canonical_value(value)
        return json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError):
        _fail('CANONICALIZATION_INVALID')

def record_hash(record):
    if not isinstance(record, Mapping): _fail('CANONICALIZATION_INVALID')
    return hashlib.sha256(canonical_bytes({k:v for k,v in record.items() if k != 'record_hash'})).hexdigest()

def receipt_material_hash(record):
    excluded = {'receipt_id','receipt_hash','receipt_created_at','creator','provenance','record_hash'}
    return hashlib.sha256(canonical_bytes({k:v for k,v in record.items() if k not in excluded})).hexdigest()

def validate_mode_evidence(mode, *, credential_chain_present, transport, cas, receipt_kind):
    if mode not in MODES: _fail('MODE_NOT_EXPLICIT')
    if mode == MODES[0]: _fail('CREDENTIALLED_REQUIRES_ORIGINAL_CHAIN')
    if credential_chain_present is not False: _fail('NONCREDENTIAL_CHAIN_CONTRADICTION')
    if receipt_kind != 'noncredential' or not isinstance(transport, dict) or not isinstance(cas, dict):
        _fail('MODE_EVIDENCE_INCONCLUSIVE')
    if mode == MODES[2]:
        if transport: _fail('CAS_EXTERNAL_TRANSPORT_FORBIDDEN')
        if cas.get('read_observed') is not True or cas.get('components_complete') is not True:
            _fail('MODE_EVIDENCE_INCONCLUSIVE')
    else:
        if transport.get('credential_presentation_observed') is True or transport.get('credential_categories'):
            _fail('PUBLIC_CREDENTIAL_PRESENTATION_FORBIDDEN')
        if cas or any(transport.get(k) is not True for k in ('dispatched','response_observed','components_complete')) or transport.get('credential_presentation_observed') is not False:
            _fail('MODE_EVIDENCE_INCONCLUSIVE')
    # An admissible boundary yields no bytes, favourable proof or authority.
    return None

def resume_exact_completion(connection, *, execution_id, attempt_number, receipt_id, receipt_hash):
    """Read-only idempotent re-delivery; identity/hash disagreement is a conflict."""
    from sqlalchemy import text
    row = connection.execute(text('SELECT receipt_id, receipt_hash, artifact_hash FROM noncredential_acquisition_receipts WHERE acquisition_execution_id=:e AND attempt_number=:a'), {'e':execution_id,'a':attempt_number}).mappings().one_or_none()
    if row is None: _fail('IDEMPOTENT_PREDECESSOR_MISSING')
    if row['receipt_id'] != receipt_id or row['receipt_hash'] != receipt_hash:
        _fail('IDEMPOTENT_EVIDENCE_CONFLICT')
    connection.execute(text('SELECT b02_require_complete_unit(:e,:a,NULL,false)'), {'e':execution_id,'a':attempt_number})
    return dict(row)

def stage_completion(connection, *, binding, start, read_cas, build_evidence, retry_receipt=None, stage_authenticity=None):
    """Caller owns one transaction; callback supplies independent governed proof.

    Insertion order is fixed: binding, start, actual local read, receipt,
    verification, terminal, artifact. No commit/rollback here. A failure must
    propagate; the caller must roll back the encompassing transaction.
    No public-network acquisition is implemented by this mission.

    stage_authenticity is an explicitly opt-in, independently governed R5 real
    source callback. It must stage ONE already independently verified G4
    FOUNDER_ORIGIN authenticity row after artifact insertion, in the SAME
    caller-owned SQL transaction, before this function forces deferred
    completeness constraints. It cannot create an origin report, source grant,
    signer, policy or COMMIT. A database readback checks that the row exists.
    The existing synthetic path and idempotent retry remain unchanged.
    """
    from sqlalchemy import text
    if not connection.in_transaction(): _fail('OUTER_TRANSACTION_REQUIRED')
    row = connection.execute(text('SELECT current_database(), session_user, current_user')).one()
    if tuple(row) != ('solveris_b02_r4g_test','solveris_b02_writer','solveris_b02_writer'):
        _fail('ISOLATED_WRITER_REQUIRED')
    if retry_receipt is not None:
        return resume_exact_completion(connection, execution_id=binding['acquisition_execution_id'], attempt_number=binding['attempt_number'], **retry_receipt)
    from app.models import (AcquisitionModeBinding, NonCredentialAcquisitionReceipt,
                            NonCredentialSanitizationVerification, AcquisitionExecution,
                            NormativeArtifact)
    if binding.get('mode') != 'LOCAL_CAS_INCORPORATION': _fail('CAS_ONLY_EXECUTOR')
    # No caller-supplied omission or string can become an implicit synthetic
    # class. The existing SQL trigger rejects ambiguous provenance as well.
    provenance = binding.get('provenance')
    if type(provenance) is not dict or type(provenance.get('synthetic_only')) is not bool:
        _fail('EXPLICIT_SYNTHETIC_CLASS_REQUIRED')
    real = provenance['synthetic_only'] is False
    if real and stage_authenticity is None: _fail('REAL_AUTHENTICITY_STAGER_REQUIRED')
    if stage_authenticity is not None:
        if not real: _fail('REAL_AUTHENTICITY_ONLY')
        if not callable(stage_authenticity): _fail('AUTHENTICITY_STAGER_NOT_CALLABLE')
    result = connection.execute(AcquisitionModeBinding.__table__.insert().values(**binding).returning(AcquisitionModeBinding.__table__)).mappings().one()
    connection.execute(AcquisitionExecution.__table__.insert().values(**start))
    raw = read_cas()
    if type(raw) is not bytes or not raw: _fail('CAS_READ_INVALID')
    # The callback must use an independently authorised verifier. This service
    # never manufactures verification or policies from the bytes themselves.
    evidence = build_evidence(dict(result), raw)
    if set(evidence) != {'receipt','verification','terminal','artifact'}: _fail('COMPLETION_UNIT_INVALID')
    receipt = dict(evidence['receipt'])
    if receipt.get('artifact_hash') != hashlib.sha256(raw).hexdigest() or receipt.get('byte_size') != len(raw):
        _fail('CONTENT_DIVERGENCE')
    r = connection.execute(NonCredentialAcquisitionReceipt.__table__.insert().values(**receipt).returning(NonCredentialAcquisitionReceipt.__table__)).mappings().one()
    verification = dict(evidence['verification'])
    verification.update(receipt_id=r['receipt_id'], receipt_hash=r['receipt_hash'])
    v = connection.execute(NonCredentialSanitizationVerification.__table__.insert().values(**verification).returning(NonCredentialSanitizationVerification.__table__)).mappings().one()
    terminal = dict(evidence['terminal'])
    terminal['structured_result'] = dict(terminal['structured_result'], noncredential_receipt_id=r['receipt_id'], noncredential_receipt_hash=r['receipt_hash'], noncredential_verification_id=v['verification_id'], noncredential_verification_hash=v['record_hash'])
    terminal.pop('record_hash', None)  # Server hashes the complete stored row.
    connection.execute(AcquisitionExecution.__table__.insert().values(**terminal))
    artifact = dict(evidence['artifact'])
    if artifact.get('immutable_bytes') != raw: _fail('CONTENT_DIVERGENCE')
    artifact.pop('record_hash', None)
    connection.execute(NormativeArtifact.__table__.insert().values(**artifact))
    if stage_authenticity is not None:
        artifact_id = artifact.get('normative_artifact_id')
        if not isinstance(artifact_id, str) or not artifact_id: _fail('REAL_ARTIFACT_ID_REQUIRED')
        # A trusted caller must independently validate the current G4 origin,
        # and persist the exact favourable row; no callback response is trusted.
        stage_authenticity(connection, artifact_id, receipt['artifact_hash'], raw)
        # Cross-check the CURRENT G5 policy grant, not caller-declared or
        # transport-only evidence. This must match the exact signed G4 origin
        # tuple used by candidate 0064 b02g5_require_authenticity_in_unit().
        # The authoritative 0064 deferred constraint still validates it again.
        actual = connection.execute(text('''
            SELECT COUNT(*)
            FROM public.acquisition_mode_bindings b
            CROSS JOIN LATERAL jsonb_array_elements(
                (public.b02_policy_grant(
                    b.security_policy_binding, 'security', b.source_scope, b.mode
                ))->'g5_release'->'documents'
            ) doc
            JOIN public.artifact_verification_records v
              ON v.normative_artifact_id=:artifact_id
             AND v.verified_artifact_hash=:digest
            WHERE b.mode_binding_id=:binding_id
              AND b.record_hash=:binding_hash
              AND b.assigned_txid=pg_current_xact_id()::text
              AND doc->>'acquisition_execution_id'=b.acquisition_execution_id
              AND v.verification_type='authenticity'
              AND v.outcome='conclusivo_favoravel'
              AND v.verifier='SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN'
              AND v.verifier_version='1'
              AND v.verifier=doc->'g4'->'verifier'->>'id'
              AND v.verifier_version=doc->'g4'->'verifier'->>'version'
              AND v.evidence->'synthetic_only'='false'::jsonb
              AND v.evidence->'g4_origin_report_binding'=doc->'g4'->'origin_report_binding'
              AND v.evidence->>'authorized_verifier_hash'=doc->'g4'->'verifier'->>'hash'
        '''), {
            'binding_id':result['mode_binding_id'],
            'binding_hash':result['record_hash'],
            'artifact_id':artifact_id,
            'digest':receipt['artifact_hash']
        }).scalar_one()
        if actual != 1: _fail('EXACT_FOUNDER_AUTHENTICITY_ROW_REQUIRED')
    connection.execute(text('SET CONSTRAINTS ALL IMMEDIATE'))
    return {'receipt_id':r['receipt_id'], 'receipt_hash':r['receipt_hash'],
            'verification_id':v['verification_id'], 'artifact_hash':receipt['artifact_hash']}
