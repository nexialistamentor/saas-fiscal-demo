"""Read-only institutional evidence adapter for the unchanged R2 projection.

No keys, authority or records are provisioned here. The private root registry is
empty until an EXPRESS institutional deployment provisions approved public keys
and exact decisions. Request payloads, environment variables and evidence files
cannot provide trust roots. Ed25519 support is a capability, not an approved
institutional mechanism. Existing canonical serialization is reused.
"""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from datetime import datetime, timezone
from app.agents.contracts.canonical import canonical_json
from app.services.sefa_pr_policy_projection import (
    PolicyProofError, dt, subject, validate_institutional_chain,
)

# Deliberately no real identity or authorization is inferred from this release.
_TRUST_ROOTS = MappingProxyType({})
_MAX_EVIDENCE_BYTES = 4 * 1024 * 1024

def deny(code): raise PolicyProofError(code)
def digest(data): return hashlib.sha256(data).hexdigest()
def canonical_bytes(value): return canonical_json(value).encode('utf-8')

def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: deny('EVIDENCE_DUPLICATE_KEY')
        result[key] = value
    return result

class PreservedEvidenceStore:
    """Untrusted storage, authenticated by exact external byte pins and signatures.

    New evidence-store layout is an adapter input convention, NOT a migration,
    policy type, authority ledger, CAS rewrite or automatic historical conversion.
    """
    def __init__(self, root): self.root = Path(root).resolve()
    def resolve_json(self, pin, *, signed_identity=True):
        if not isinstance(pin, dict) or set(pin) != {'id', 'sha256'}:
            deny('EVIDENCE_PIN_INVALID')
        h = pin['sha256']
        if not isinstance(h, str) or len(h) != 64 or any(c not in '0123456789abcdef' for c in h):
            deny('EVIDENCE_PIN_INVALID')
        path = self.root / 'sha256' / h[:2] / (h + '.json')
        if not path.is_file() or path.is_symlink(): deny('IMMUTABLE_EVIDENCE_MISSING')
        if self.root not in path.resolve().parents: deny('EVIDENCE_PATH_ESCAPE')
        with path.open('rb') as stream: raw = stream.read(_MAX_EVIDENCE_BYTES + 1)
        if len(raw) > _MAX_EVIDENCE_BYTES or digest(raw) != h: deny('EVIDENCE_BYTES_ALTERED')
        try: envelope = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique)
        except PolicyProofError: raise
        except (ValueError, UnicodeError): deny('EVIDENCE_JSON_INVALID')
        if not isinstance(envelope, dict): deny('EVIDENCE_JSON_INVALID')
        if signed_identity and (not isinstance(envelope.get('payload'),dict) or envelope['payload'].get('id') != pin['id']):
            deny('EVIDENCE_ID_DIVERGENCE')
        return envelope
    def resolve(self, pin):
        return self.resolve_json(pin)

def _verify_signed(envelope, key, *, kind, now, synthetic):
    """Verifies actual signature bytes; no echoed boolean/status is accepted."""
    if not isinstance(envelope, dict) or set(envelope) != {'payload', 'signature'}:
        deny('SIGNED_EVIDENCE_INVALID')
    payload = envelope['payload']; signature = envelope['signature']
    if not isinstance(payload, dict) or payload.get('kind') != kind:
        deny('EVIDENCE_KIND_DIVERGENCE')
    if payload.get('synthetic_only') is not synthetic:
        deny('SYNTHETIC_EVIDENCE_FORBIDDEN')
    if not isinstance(signature, dict) or set(signature) != {'algorithm', 'key_sha256', 'value'}:
        deny('EVIDENCE_SIGNATURE_MISSING')
    if signature['algorithm'] != 'Ed25519' or signature['key_sha256'] != digest(key):
        deny('EVIDENCE_SIGNER_NOT_AUTHORIZED')
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        signed = base64.b64decode(signature['value'], validate=True)
        Ed25519PublicKey.from_public_bytes(key).verify(signed, canonical_bytes(payload))
    except Exception:
        deny('EVIDENCE_SIGNATURE_INVALID')
    try:
        if not dt(payload['valid_from']) <= now < dt(payload['valid_until']): deny('EVIDENCE_NOT_CURRENT')
    except (KeyError, TypeError, ValueError): deny('EVIDENCE_VALIDITY_INVALID')
    return payload

def _root_for(policy_subject, now):
    roots = [r for r in _TRUST_ROOTS.values() if r['policy_subject'] == policy_subject]
    if len(roots) != 1: deny('REAL_INSTITUTIONAL_TRUST_ANCHOR_MISSING')
    root = roots[0]
    if root.get('synthetic_only') is not False or root.get('mechanism') != 'Ed25519' or not root.get('ratification_binding'):
        deny('REAL_INSTITUTIONAL_TRUST_ANCHOR_MISSING')
    if not dt(root['valid_from']) <= now < dt(root['valid_until']): deny('INSTITUTIONAL_ROOT_NOT_CURRENT')
    return root

def _verify_chain_bytes(store, expected, decisions, *, root, now, synthetic):
    """Pure verifier, usable in isolated synthetic tests; not an authority entrypoint."""
    if root.get('synthetic_only') is not synthetic or root['policy_subject'] != expected['policy_subject']:
        deny('TRUST_ANCHOR_SUBJECT_DIVERGENCE')
    issuer = bytes.fromhex(root['identity_issuer_public_key_hex'])
    identities = {}
    pins = expected['actor_identity_bindings'] + [expected['technical_author']]
    for item in pins:
        p = _verify_signed(store.resolve(item['binding']), issuer, kind='institutional_identity', now=now, synthetic=synthetic)
        if p.get('policy_subject') != expected['policy_subject']: deny('IDENTITY_POLICY_DIVERGENCE')
        if p.get('actor_id') != item['actor_id'] or not isinstance(p.get('roles'), list): deny('INSTITUTIONAL_IDENTITY_DIVERGENCE')
        try: key = bytes.fromhex(p['public_key_hex'])
        except (KeyError, ValueError, TypeError): deny('IDENTITY_KEY_MISSING')
        if len(key) != 32: deny('IDENTITY_KEY_INVALID')
        if item['actor_id'] in identities and identities[item['actor_id']] != p: deny('INSTITUTIONAL_IDENTITY_AMBIGUOUS')
        identities[item['actor_id']] = p
    actors = [expected['actor_identity_bindings'][i]['actor_id'] for i in (0,1,3)]
    if len({identities[a]['public_key_hex'] for a in actors}) != 3 or identities[actors[1]]['public_key_hex'] == identities[expected['technical_author']['actor_id']]['public_key_hex']:
        deny('INSTITUTIONAL_SIGNING_KEYS_NOT_SEGREGATED')
    if root.get('ratification_binding') != expected['decision_bindings'][-1]: deny('TRUST_ANCHOR_DECISION_DIVERGENCE')
    # R2 provides structural segregation and the exact predecessor event chain.
    rows = {d['decision_id']: d for d in decisions}
    if len(rows) != len(decisions): deny('DECISION_AMBIGUOUS')
    for binding, pin in zip(expected['decision_bindings'], expected['record_evidence_bindings'], strict=True):
        row = rows.get(binding['id'])
        if row is None or row['record_hash'] != binding['sha256']: deny('DECISION_MISSING')
        identity = identities.get(row['actor'])
        if identity is None or row['institutional_role'] not in identity['roles']: deny('DECISION_SIGNER_NOT_ENABLED')
        key = bytes.fromhex(identity['public_key_hex'])
        p = _verify_signed(store.resolve(pin), key, kind='policy_decision_evidence', now=now, synthetic=synthetic)
        fields = ('decision_id', 'policy_type', 'policy_id', 'policy_version', 'policy_hash',
                  'decision_event', 'institutional_role', 'actor', 'previous_decision_id')
        if p.get('decision') != {k:row.get(k) for k in fields}: deny('SIGNED_DECISION_DIVERGENCE')
        if dt(p.get('decision_timestamp')) != dt(row['timestamp']): deny('SIGNED_DECISION_TIME_DIVERGENCE')
        if p.get('previous_decision_record_hash') != row['evidence']['previous_decision_record_hash']:
            deny('SIGNED_PREDECESSOR_DIVERGENCE')
    auditor = decisions[1]['actor']
    report = _verify_signed(store.resolve(expected['audit_report_binding']), bytes.fromhex(identities[auditor]['public_key_hex']),
                            kind='independent_policy_audit', now=now, synthetic=synthetic)
    if (report.get('policy_subject') != expected['policy_subject'] or report.get('auditor_id') != auditor
        or report.get('outcome') != 'favoravel' or report.get('decision_bindings') != expected['decision_bindings'][:2]
        or report.get('technical_author_id') != expected['technical_author']['actor_id']
        or report.get('scope') != 'SEFA_PR_B02_DOCUMENTAL_AUTHENTICATION_ONLY'):
        deny('INDEPENDENT_AUDIT_DIVERGENCE')
    return {'status':'verified_synthetic' if synthetic else 'verified', 'verified_bindings':expected}

class _InstitutionalAdapter:
    __slots__ = ('_store', '_now')
    def __init__(self, store, now):
        if type(store) is not PreservedEvidenceStore: deny('TRUSTED_STORE_REQUIRED')
        self._store = store; self._now = now
    def verify_exact_chain(self, *, connection, expected):
        if connection is None or not connection.in_transaction(): deny('READ_TRANSACTION_REQUIRED')
        from sqlalchemy import text
        identity = tuple(connection.execute(text("SELECT current_database(),session_user,current_user,current_setting('transaction_read_only')")).one())
        if identity != ('solveris_b02_r4g_test','solveris_b02_writer','solveris_b02_writer','on'):
            deny('RESTRICTED_READ_IDENTITY_REQUIRED')
        root = _root_for(expected['policy_subject'], self._now)
        binding = expected['decision_bindings'][-1]
        rows = list(connection.execute(text('''SELECT d.* FROM public.policy_decisions d
 WHERE d.policy_type=:policy_type AND d.policy_id=:policy_id AND d.policy_version=:policy_version AND d.policy_hash=:policy_hash'''),
            expected['policy_subject']).mappings().all())
        # Reconstruct from actual rows; expected structures cannot manufacture decisions.
        full_binding = dict(expected['policy_subject'], decision_id=binding['id'], decision_hash=binding['sha256'])
        structural = validate_institutional_chain(rows, full_binding, now=self._now,
            technical_actor=expected['technical_actor'], activated_at=self._now)
        actual = {k:v for k,v in structural.items() if k != 'institutional_evidence_verified'}
        if actual != expected: deny('INSTITUTIONAL_DB_CHAIN_DIVERGENCE')
        ordered = [{d['decision_id']:d for d in rows}[p['id']] for p in expected['decision_bindings']]
        return _verify_chain_bytes(self._store, actual, ordered, root=root, now=self._now, synthetic=False)

def admit_with_preserved_institutional_proofs(evidence, *, connection, evidence_directory, now=None):
    """The trusted entrypoint; no callback, client key or authority flag argument.

    The R2 low-level injectable function remains unchanged for compatibility.
    Production callers must use this entrypoint, not supply their own verifier.
    """
    from app.services.sefa_pr_documentary_admission import admit_documentary_verification
    now = now or datetime.now(timezone.utc)
    adapter = _InstitutionalAdapter(PreservedEvidenceStore(evidence_directory), now)
    return admit_documentary_verification(evidence, connection=connection, now=now, institutional_proof_verifier=adapter)
