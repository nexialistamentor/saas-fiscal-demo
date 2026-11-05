"""Prospective B02 G5/R1 mandated-agent evidence guard (not policy ratification).

Uses Ed25519 as existing B02 signing contracts do. All trust anchors, the
registered grant and observed result must originate outside the signed payload.
No SQL, R5 activation, R7 release or migration is performed by this module.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from collections.abc import Callable, Mapping
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

VERIFIER_ID = "SOLVERIS_B02_G5_MANDATED_EXECUTION"
VERIFIER_VERSION = 1
SCHEMA_MANDATE = "SOLVERIS_B02_SIGNED_AGENT_MANDATE_V1"
SCHEMA_RECEIPT = "SOLVERIS_B02_SIGNED_AGENT_RECEIPT_V1"
ALLOWED_OPERATIONS = frozenset({
    "G5_R1_ADMISSION", "G5_R1_SANITIZATION", "G5_R1_AUTHORITY_EVIDENCE",
    "G5_R1_SEGREGATED_REVIEW", "R6_PIPELINE_SYNTHETIC",
})
SHA = re.compile(r"[0-9a-f]{64}\Z")
MANDATE_FIELDS = frozenset({"schema", "mandate_id", "issuer_id", "agent_id",
    "agent_role", "object_sha256", "verifier_id", "verifier_version",
    "operations", "issued_at", "valid_from", "valid_until", "nonce",
    "revoked", "synthetic_r6_allowed"})
RECEIPT_FIELDS = frozenset({"schema", "mandate_id", "mandate_sha256",
    "agent_id", "object_sha256", "verifier_id", "verifier_version",
    "operation", "execution_id", "executed_at", "nonce", "result_sha256",
    "outcome", "synthetic_only"})


def stop(code):
    raise ValueError("STOP_B02_G5_AGENT_EVIDENCE_" + code)


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def digest_ok(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def when(value):
    if not isinstance(value, str):
        stop("TIME_FORMAT")
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        stop("TIME_FORMAT")
    if t.tzinfo is None:
        stop("TIMEZONE_REQUIRED")
    return t.astimezone(timezone.utc)


def exact(value, fields, code):
    if type(value) is not dict or set(value) != fields:
        stop(code)
    return value


def verify_envelope(envelope, public_key):
    exact(envelope, {"body", "signature_base64"}, "ENVELOPE_SCHEMA")
    if type(public_key) is not bytes or len(public_key) != 32:
        stop("TRUSTED_KEY_INVALID")
    try:
        signature = base64.b64decode(envelope["signature_base64"], validate=True)
        if len(signature) != 64:
            stop("SIGNATURE_LENGTH")
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, canonical_bytes(envelope["body"]))
    except (InvalidSignature, ValueError, TypeError, base64.binascii.Error):
        stop("SIGNATURE_INVALID")
    return envelope["body"]


def verify_mandated_execution(*, signed_mandate: Mapping,
                               signed_receipt: Mapping, trusted: Mapping,
                               requested_operation: str, now: datetime,
                               observed_result: Callable):
    """Fail-closed focal gate. Caller must source trusted from SOLVERIS custody.

    trusted must be independently verified and NOT derived from the payload:
    approved_mandate_sha256, issuer_public_key, agent_public_key,
    ratifier_public_key, object_sha256, authorized_agent_id,
    revoked_mandate_ids, consumed_execution_ids, issued_nonces.
    The observer must independently read the durable execution result, never
    simply echo the asserted receipt. The caller must atomically reserve
    execution_id/nonce with the SOLVERIS ledger to prevent concurrent replay.
    """
    if not isinstance(trusted, Mapping) or set(trusted) != {
        "approved_mandate_sha256", "issuer_public_key", "agent_public_key",
        "ratifier_public_key", "object_sha256", "authorized_agent_id",
        "revoked_mandate_ids", "consumed_execution_ids", "issued_nonces",
    }:
        stop("EXTERNAL_TRUST_CONTEXT_REQUIRED")
    if not all(digest_ok(trusted[k]) for k in
               ("approved_mandate_sha256", "object_sha256")):
        stop("TRUST_PINS_INVALID")
    for k in ("issuer_public_key", "agent_public_key", "ratifier_public_key"):
        if type(trusted[k]) is not bytes or len(trusted[k]) != 32:
            stop("TRUSTED_KEY_INVALID")
    if len({trusted["issuer_public_key"], trusted["agent_public_key"],
            trusted["ratifier_public_key"]}) != 3:
        stop("AGENT_ISSUER_RATIFIER_KEY_COLLISION")
    if any(type(trusted[k]) not in (set, frozenset) for k in
           ("revoked_mandate_ids", "consumed_execution_ids", "issued_nonces")):
        stop("TRUSTED_LEDGER_UNAVAILABLE")
    if now.tzinfo is None:
        stop("TRUSTED_CLOCK_REQUIRED")
    clock = now.astimezone(timezone.utc)
    if requested_operation not in ALLOWED_OPERATIONS:
        stop("OPERATION_NOT_SUPPORTED")
    mandate = verify_envelope(signed_mandate, trusted["issuer_public_key"])
    exact(mandate, MANDATE_FIELDS, "MANDATE_SCHEMA")
    if sha256(mandate) != trusted["approved_mandate_sha256"]:
        stop("MANDATE_NOT_IN_TRUSTED_REGISTRY")
    if (mandate["schema"] != SCHEMA_MANDATE
            or mandate["verifier_id"] != VERIFIER_ID
            or mandate["verifier_version"] != VERIFIER_VERSION
            or mandate["object_sha256"] != trusted["object_sha256"]
            or mandate["agent_id"] != trusted["authorized_agent_id"]
            or not mandate["mandate_id"] or not mandate["issuer_id"]
            or not mandate["agent_id"] or not mandate["agent_role"]
            or not mandate["nonce"]):
        stop("MANDATE_BINDING_INVALID")
    if (type(mandate["operations"]) is not list or not mandate["operations"]
            or len(set(mandate["operations"])) != len(mandate["operations"])
            or not set(mandate["operations"]) <= ALLOWED_OPERATIONS
            or requested_operation not in mandate["operations"]):
        stop("OPERATION_OUTSIDE_MANDATE")
    if mandate["revoked"] is not False or mandate["mandate_id"] in trusted["revoked_mandate_ids"]:
        stop("MANDATE_REVOKED")
    issued, start, end = (when(mandate[k]) for k in
                          ("issued_at", "valid_from", "valid_until"))
    if not (issued <= start <= clock < end):
        stop("MANDATE_NOT_CURRENT")
    if mandate["nonce"] not in trusted["issued_nonces"]:
        stop("NONCE_NOT_ISSUED_BY_SOLVERIS")
    receipt = verify_envelope(signed_receipt, trusted["agent_public_key"])
    exact(receipt, RECEIPT_FIELDS, "RECEIPT_SCHEMA")
    if (receipt["schema"] != SCHEMA_RECEIPT
            or receipt["mandate_id"] != mandate["mandate_id"]
            or receipt["mandate_sha256"] != sha256(mandate)
            or receipt["agent_id"] != mandate["agent_id"]
            or receipt["object_sha256"] != mandate["object_sha256"]
            or receipt["verifier_id"] != VERIFIER_ID
            or receipt["verifier_version"] != VERIFIER_VERSION
            or receipt["operation"] != requested_operation
            or receipt["nonce"] != mandate["nonce"]
            or not isinstance(receipt["execution_id"], str)
            or not receipt["execution_id"]
            or receipt["execution_id"] in trusted["consumed_execution_ids"]
            or not digest_ok(receipt["result_sha256"])
            or receipt["outcome"] != "PASS"):
        stop("RECEIPT_BINDING_OR_REPLAY_INVALID")
    if not (start <= when(receipt["executed_at"]) <= clock < end):
        stop("EXECUTION_OUTSIDE_MANDATE")
    synthetic = requested_operation == "R6_PIPELINE_SYNTHETIC"
    if (receipt["synthetic_only"] is not synthetic
            or (synthetic and mandate["synthetic_r6_allowed"] is not True)
            or (not synthetic and mandate["synthetic_r6_allowed"] not in (True, False))):
        stop("SYNTHETIC_SCOPE_MISMATCH")
    if not callable(observed_result):
        stop("INDEPENDENT_RESULT_OBSERVER_REQUIRED")
    observed = observed_result(receipt["execution_id"], requested_operation)
    if (not isinstance(observed, Mapping) or set(observed) !=
            {"execution_id", "operation", "result_sha256", "synthetic_only"}
            or observed["execution_id"] != receipt["execution_id"]
            or observed["operation"] != requested_operation
            or observed["result_sha256"] != receipt["result_sha256"]
            or observed["synthetic_only"] is not synthetic):
        stop("INDEPENDENT_RESULT_MISMATCH")
    return {
        "status": "SIGNED_MANDATED_EXECUTION_VERIFIED_NOT_RATIFICATION",
        "object_sha256": trusted["object_sha256"],
        "mandate_sha256": sha256(mandate),
        "receipt_sha256": sha256(receipt),
        "execution_id": receipt["execution_id"],
        "operation": requested_operation,
        "verifier_id": VERIFIER_ID,
        "verifier_version": VERIFIER_VERSION,
        "synthetic_only": synthetic,
        "fiscal_authority_granted": False,
        "r5_commit_authorized": False,
        "r7_closed": False,
        "b03_released": False,
    }
