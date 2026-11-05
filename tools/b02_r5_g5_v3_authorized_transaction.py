"""SOLVERIS B02 R5/G5 V3 -- separately authorised transaction coordinator.

Candidate executable interface, not authority, migration installer or CLI COMMIT.
No synthetic facts, signer, ROOT, hidden retry, V5 harness modification or SQL
execution on import. Inject real CAS/evidence/FOUNDER_ORIGIN callbacks; independent
authority assessment and a competent Ed25519 signer are mandatory.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence

from sqlalchemy import text
from sqlalchemy.pool import NullPool
from app.services.enterprise_b02_g5_two_unit_stage import (
    C3_DOCUMENTS, _validate_units, stage_two_real_c3_units,
)

class R5Stop(ValueError):
    pass

def stop(code):
    raise R5Stop("STOP_B02_R5_G5_V3_" + code)

DATABASE = "solveris_b02_r4g_test"
WRITER = "solveris_b02_writer"
REVISION = "0065_b02_g5_one_shot_real"
PROFILE = "REAL_PROFILE_COMPILED_APPROVED_ROOTS"
FIELDS = frozenset({
    "approval_id", "release_id", "operator_sha256",
    "decision_document_sha256", "g5_policy_hash", "review_act_sha256",
    "ratification_act_sha256", "native_root_sha256", "native_elf_sha256",
    "install_act_sha256",
})
HEXDIGEST = re.compile(r"[0-9a-f]{64}\Z")
SIG_FIELDS = frozenset({"key_id", "signed_message_base64", "signature_base64"})

ROW_SQL = text("""
SELECT b.acquisition_execution_id, b.assigned_txid,
 b.record_hash AS binding_record_hash,
 r.receipt_id, r.receipt_hash, r.record_hash AS receipt_record_hash,
 v.verification_id, v.record_hash AS verification_record_hash,
 e.record_hash AS terminal_record_hash,
 a.normative_artifact_id, a.record_hash AS normative_artifact_record_hash,
 a.artifact_hash, a.byte_size,
 avr.artifact_verification_record_id, avr.record_hash AS authenticity_record_hash
FROM public.acquisition_mode_bindings b
JOIN public.noncredential_acquisition_receipts r
 ON r.mode_binding_id=b.mode_binding_id AND r.mode_binding_hash=b.record_hash
 AND r.acquisition_execution_id=b.acquisition_execution_id
 AND r.attempt_number=b.attempt_number AND r.assigned_txid=b.assigned_txid
JOIN public.noncredential_sanitization_verifications v
 ON v.receipt_id=r.receipt_id AND v.receipt_hash=r.receipt_hash
 AND v.assigned_txid=b.assigned_txid AND v.verification_outcome='verified_sanitized'
JOIN public.acquisition_executions e
 ON e.acquisition_execution_id=b.acquisition_execution_id
 AND e.attempt_number=b.attempt_number
 AND e.execution_event='conclusao' AND e.projected_state='concluida'
JOIN public.normative_artifacts a
 ON a.acquisition_execution_record_id=e.acquisition_execution_record_id
 AND a.acquisition_execution_id=e.acquisition_execution_id
 AND a.acquisition_attempt_number=e.attempt_number
 AND a.artifact_hash=r.artifact_hash AND a.byte_size=r.byte_size
JOIN public.artifact_verification_records avr
 ON avr.normative_artifact_id=a.normative_artifact_id
 AND avr.verified_artifact_hash=r.artifact_hash
 AND avr.verification_type='authenticity' AND avr.outcome='conclusivo_favoravel'
WHERE b.assigned_txid=:txid AND b.mode='LOCAL_CAS_INCORPORATION'
 AND b.provenance->>'synthetic_only'='false'
ORDER BY b.acquisition_execution_id
""")

def validate_approval(approval):
    if not isinstance(approval, Mapping) or set(approval) != FIELDS:
        stop("EXACT_APPROVAL_BINDINGS_REQUIRED")
    if any(not isinstance(approval[k], str) or not approval[k] or len(approval[k]) > 128
           for k in ("approval_id", "release_id")):
        stop("APPROVAL_IDS_INVALID")
    if any(not isinstance(approval[k], str) or not HEXDIGEST.fullmatch(approval[k])
           for k in FIELDS - {"approval_id", "release_id"}):
        stop("APPROVAL_HASHES_REQUIRED")

def validate_envelope(envelope, manifest_bytes):
    if not isinstance(envelope, Mapping) or set(envelope) != SIG_FIELDS:
        stop("EXACT_ED25519_ENVELOPE_REQUIRED")
    if not isinstance(envelope["key_id"], str) or not envelope["key_id"]:
        stop("SIGNER_KEY_ID_REQUIRED")
    try:
        message = base64.b64decode(envelope["signed_message_base64"], validate=True)
        signature = base64.b64decode(envelope["signature_base64"], validate=True)
    except (ValueError, TypeError, base64.binascii.Error):
        stop("SIGNATURE_BASE64_INVALID")
    if message != manifest_bytes or len(signature) != 64:
        stop("SIGNED_DB_MANIFEST_DIVERGENCE")
    return json.dumps(dict(envelope), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)

def _identity(c, *, readback=False):
    q = """SELECT current_database(), session_user, current_user,
            current_setting('transaction_isolation'),
            current_setting('transaction_read_only'),
            current_setting('server_version_num')::integer"""
    ident = tuple(c.execute(text(q)).one())
    expected = (DATABASE, WRITER, WRITER, "repeatable read" if readback
                else "read committed", "on" if readback else "off", 170010)
    if ident != expected:
        stop("EXACT_PG1710_RESTRICTED_TRANSACTION_IDENTITY_REQUIRED")
    if not readback:
        if c.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one() != REVISION:
            stop("0064_0065_NOT_INSTALLED_BY_AUTHORISED_INSTALLER")
        if c.execute(text("SELECT public.b02g5_native_profile()")).scalar_one() != PROFILE:
            stop("REAL_NATIVE_PROFILE_OR_APPROVED_ROOT_NOT_PRESENT")

def _rows(c, txid, units):
    rows = [dict(r) for r in c.execute(ROW_SQL, {"txid": txid}).mappings().all()]
    expected = {u["binding"]["acquisition_execution_id"]: u["document_id"] for u in units}
    if len(expected) != 2 or len(rows) != 2:
        stop("EXACT_TWO_PHYSICAL_C3_UNITS_REQUIRED")
    if len({r["acquisition_execution_id"] for r in rows}) != 2:
        stop("DUPLICATE_EXECUTION_IN_READBACK")
    for r in rows:
        doc_id = expected.get(r["acquisition_execution_id"])
        if doc_id not in C3_DOCUMENTS or r["assigned_txid"] != txid:
            stop("PHYSICAL_EXECUTION_NOT_APPROVED")
        digest, size = C3_DOCUMENTS[doc_id]
        if (r["artifact_hash"], r["byte_size"]) != (digest, size):
            stop("PHYSICAL_C3_SHA_OR_SIZE_MISMATCH")
        for key in ("binding_record_hash", "receipt_hash",
                    "receipt_record_hash", "verification_record_hash",
                    "terminal_record_hash", "normative_artifact_record_hash",
                    "authenticity_record_hash"):
            if not isinstance(r[key], str) or not HEXDIGEST.fullmatch(r[key]):
                stop("EXACT_PHYSICAL_RECORD_HASH_REQUIRED")
        if not r["normative_artifact_id"] or not r["artifact_verification_record_id"]:
            stop("PHYSICAL_ARTIFACT_OR_ORIGIN_MISSING")
        r["document_id"] = doc_id
    return rows

def _independent_readback(engine, txid, units, approval):
    # A NullPool engine guarantees a fresh physical connection after COMMIT.
    with engine.connect() as c:
        with c.begin():
            c.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            _identity(c, readback=True)
            receipt = c.execute(text("""
                SELECT approval_id, release_id, assigned_txid,
                       trim(operator_sha256) AS operator_sha256,
                       trim(decision_document_sha256) AS decision_document_sha256,
                       writer_name, database_name
                FROM public.b02_g5_operational_approval_uses
                WHERE approval_id=:approval_id AND release_id=:release_id
                  AND assigned_txid=:txid
            """), {**approval, "txid": txid}).mappings().one()
            for k in ("approval_id", "release_id", "operator_sha256",
                      "decision_document_sha256"):
                if receipt[k] != approval[k]:
                    stop("ONE_SHOT_READBACK_MISMATCH")
            if (receipt["writer_name"], receipt["database_name"]) != (WRITER, DATABASE):
                stop("READBACK_WRITER_OR_DATABASE_MISMATCH")
            rows = _rows(c, txid, units)
    return {
        "status": "R5_COMMITTED_INDEPENDENT_READBACK_EXACT",
        "database": DATABASE, "writer": WRITER, "alembic_revision": REVISION,
        "approval_id": approval["approval_id"], "release_id": approval["release_id"],
        "assigned_txid": txid, "g5_policy_hash": approval["g5_policy_hash"],
        "units": rows, "r6_fiscal_authority": False,
        "b02_closed": False, "b03_released": False,
    }

def execute_authorized_r5(engine, *, units: Sequence[Mapping], approval: Mapping,
                          independently_verify_acts: Callable,
                          competent_sign_manifest: Callable,
                          specifically_authorized_commit: bool = False):
    """Call only after G5 V3/R1 and specific installation/one-shot acts.

    independently_verify_acts(approval) must verify independent reviewer,
    ratification, current root, ELF and installation/COMMIT evidence and return
    {'status':'CURRENT_VERIFIED','g5_policy_hash':<matching final hash>}.
    This declaration is not itself authority; the DB/natively compiled roots
    must independently authenticate the actual signed manifest at PRE_COMMIT.
    """
    validate_approval(approval)
    if specifically_authorized_commit is not True:
        stop("SPECIFIC_PROTECTED_COMMIT_AUTHORITY_MISSING")
    if not isinstance(getattr(engine, "pool", None), NullPool):
        stop("INDEPENDENT_SESSION_NULLPOOL_REQUIRED")
    if not callable(independently_verify_acts) or not callable(competent_sign_manifest):
        stop("INDEPENDENT_ACT_CHECK_AND_REAL_SIGNER_REQUIRED")
    evidence = independently_verify_acts(approval)
    if (not isinstance(evidence, Mapping)
            or evidence.get("status") != "CURRENT_VERIFIED"
            or evidence.get("g5_policy_hash") != approval["g5_policy_hash"]):
        stop("CURRENT_G5_V3_R1_AUTHORITY_NOT_VERIFIED")
    _validate_units(units)
    txid = None
    try:
        with engine.begin() as c:
            _identity(c)
            c.execute(text("SELECT public.b02g5_lock_authority_snapshot()"))
            existing = c.execute(text("""
                SELECT count(*) FROM public.b02_g5_operational_approval_uses
                WHERE approval_id=:approval_id OR release_id=:release_id
            """), approval).scalar_one()
            if existing:
                stop("ONE_SHOT_PREEXISTS_NO_RETRY")
            staged = stage_two_real_c3_units(c, units=units)
            txid = c.execute(text("SELECT pg_current_xact_id()::text")).scalar_one()
            physical = _rows(c, txid, units)
            sources = {s["artifact_hash"]: s for s in staged}
            if len(sources) != 2:
                stop("STAGED_UNITS_NOT_DISTINCT")
            for r in physical:
                s = sources.get(r["artifact_hash"])
                if s is None or any(s[k] != r[k] for k in
                                    ("receipt_id", "receipt_hash", "verification_id")):
                    stop("R5_ARTIFACT_STAGING_LINK_NOT_PROVED")
            reserved = c.execute(text("""
                SELECT public.b02_g5_reserve_operational_decision(
                    CAST(:approval_id AS varchar(128)),
                    CAST(:release_id AS varchar(128)),
                    CAST(:operator_sha256 AS character(64)),
                    CAST(:decision_document_sha256 AS character(64)))
            """), approval).scalar_one()
            if reserved != txid:
                stop("ONE_SHOT_TXID_MISMATCH")
            manifest = c.execute(text("SELECT public.b02g5_capability_manifest()")).scalar_one()
            if not isinstance(manifest, str):
                stop("SERVER_MANIFEST_NOT_CANONICAL_TEXT")
            material = json.loads(manifest)
            one_shot = material.get("g5_one_shot", {})
            if (one_shot.get("assigned_txid") != txid
                    or one_shot.get("approval_id") != approval["approval_id"]
                    or one_shot.get("release_id") != approval["release_id"]
                    or material.get("release_policy_hash") != approval["g5_policy_hash"]):
                stop("MANIFEST_CURRENT_AUTHORITY_MISMATCH")
            signed = competent_sign_manifest(manifest.encode("utf-8"))
            envelope = validate_envelope(signed, manifest.encode("utf-8"))
            c.execute(text("""
                SELECT set_config('solveris.g5_signed_capability', :envelope, true)
            """), {"envelope": envelope})
            c.execute(text("SELECT public.b02g5_assert_transaction_capability()"))
            # Context COMMIT must pass the native PRE_COMMIT veto.
    except Exception as exc:
        raise R5Stop(
            "STOP_B02_R5_G5_V3_TX_FAILED_OR_ACK_UNCERTAIN_"
            "INDEPENDENT_READBACK_REQUIRED_NEVER_AUTORETRY"
        ) from exc
    try:
        receipt = _independent_readback(engine, txid, units, approval)
    except Exception as exc:
        raise R5Stop(
            "STOP_B02_R5_G5_V3_POSTCOMMIT_READBACK_UNCERTAIN_NEVER_AUTORETRY"
        ) from exc
    receipt["signed_manifest_sha256"] = hashlib.sha256(
        manifest.encode("utf-8")).hexdigest()
    return receipt

def main():
    # Deliberately no --commit/DSN transport or private key in this CLI.
    print(json.dumps({
        "status": "R5_EXECUTABLE_PREPARED_NO_SQL",
        "database": DATABASE, "writer": WRITER, "required_revision": REVISION,
        "required_authority_bindings": sorted(FIELDS),
        "real_callbacks": ["read_cas", "build_evidence", "stage_authenticity",
                           "independently_verify_acts", "competent_sign_manifest"],
        "physical_installation_and_specific_commit_act_still_required": True,
        "v5_harness_not_modified": True,
    }, sort_keys=True))

if __name__ == "__main__":
    main()
