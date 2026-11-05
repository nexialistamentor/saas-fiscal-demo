"""Only new G5/R1 mandate guard focal tests; historical tests are untouched."""
import base64
from datetime import datetime, timezone
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from tools import b02_g5_mandated_execution_v1 as g

NOW = datetime(2026,11,5,13,0,0,tzinfo=timezone.utc)
H = "a"*64

def public(key):
    return key.public_key().public_bytes(serialization.Encoding.Raw,
        serialization.PublicFormat.Raw)

def sign(body,key):
    return {"body":body,"signature_base64":base64.b64encode(
        key.sign(g.canonical_bytes(body))).decode("ascii")}

def example(operation="G5_R1_SANITIZATION", synthetic=False):
    issuer,agent,ratifier=[Ed25519PrivateKey.generate() for _ in range(3)]
    mandate={"schema":g.SCHEMA_MANDATE,"mandate_id":"m1",
        "issuer_id":"SOLVERIS","agent_id":"SOLVERIS-controlled-agent-01",
        "agent_role":"operator","object_sha256":H,"verifier_id":g.VERIFIER_ID,
        "verifier_version":g.VERIFIER_VERSION,
        "operations":[operation],"issued_at":"2026-11-05T12:00:00Z",
        "valid_from":"2026-11-05T12:00:00Z",
        "valid_until":"2026-11-06T00:00:00Z", "nonce":"solv:one-shot:01",
        "revoked":False,"synthetic_r6_allowed":synthetic}
    receipt={"schema":g.SCHEMA_RECEIPT,"mandate_id":"m1",
        "mandate_sha256":g.sha256(mandate),"agent_id":mandate["agent_id"],
        "object_sha256":H,"verifier_id":g.VERIFIER_ID,
        "verifier_version":g.VERIFIER_VERSION,"operation":operation,
        "execution_id":"run-01","executed_at":"2026-11-05T12:15:00Z",
        "nonce":mandate["nonce"],"result_sha256":"b"*64,
        "outcome":"PASS","synthetic_only":synthetic}
    trusted={"approved_mandate_sha256":g.sha256(mandate),
        "issuer_public_key":public(issuer),"agent_public_key":public(agent),
        "ratifier_public_key":public(ratifier),"object_sha256":H,
        "authorized_agent_id":mandate["agent_id"],
        "revoked_mandate_ids":set(),"consumed_execution_ids":set(),
        "issued_nonces":{mandate["nonce"]}}
    observer=lambda run,op:{"execution_id":run,"operation":op,
        "result_sha256":"b"*64,"synthetic_only":synthetic}
    return issuer,agent,mandate,receipt,trusted,observer

def call(f, *, operation="G5_R1_SANITIZATION", **overrides):
    issuer,agent,mandate,receipt,trusted,observer=f
    arguments={"signed_mandate":sign(mandate,issuer),
               "signed_receipt":sign(receipt,agent),"trusted":trusted,
               "requested_operation":operation,"now":NOW,
               "observed_result":observer}
    arguments.update(overrides)
    return g.verify_mandated_execution(**arguments)

def test_signed_authorized_and_independent_readback():
    out=call(example())
    assert out["status"].startswith("SIGNED_MANDATED_EXECUTION_VERIFIED")
    assert out["r5_commit_authorized"] is False and out["r7_closed"] is False

def test_missing_evidence_rejected():
    with pytest.raises(ValueError,match="ENVELOPE_SCHEMA"):
        call(example(),signed_receipt={})

def test_adulterated_signed_receipt_rejected():
    f=example(); signed=sign(f[3],f[1]);signed["body"]["result_sha256"]="c"*64
    with pytest.raises(ValueError,match="SIGNATURE_INVALID"):
        call(f,signed_receipt=signed)

def test_unpinned_mandate_rejected_even_if_signature_valid():
    f=example();f[4]["approved_mandate_sha256"]="f"*64
    with pytest.raises(ValueError,match="MANDATE_NOT_IN_TRUSTED_REGISTRY"):
        call(f)

def test_expired_mandate_rejected():
    f=example();f[2]["valid_until"]="2026-11-05T12:45:00Z";
    f[4]["approved_mandate_sha256"]=g.sha256(f[2]);f[3]["mandate_sha256"]=g.sha256(f[2]);
    with pytest.raises(ValueError,match="MANDATE_NOT_CURRENT"):
        call(f)

def test_revoked_mandate_rejected():
    f=example();f[4]["revoked_mandate_ids"].add("m1")
    with pytest.raises(ValueError,match="MANDATE_REVOKED"):
        call(f)

def test_agent_key_cannot_equal_ratifier_key():
    f=example();f[4]["ratifier_public_key"]=f[4]["agent_public_key"]
    with pytest.raises(ValueError,match="KEY_COLLISION"):
        call(f)

def test_operation_outside_grant_rejected():
    with pytest.raises(ValueError,match="OPERATION_OUTSIDE_MANDATE"):
        call(example(),operation="G5_R1_AUTHORITY_EVIDENCE")

def test_replay_rejected():
    f=example();f[4]["consumed_execution_ids"].add("run-01")
    with pytest.raises(ValueError,match="REPLAY_INVALID"):
        call(f)

def test_unissued_nonce_rejected():
    f=example();f[4]["issued_nonces"].clear()
    with pytest.raises(ValueError,match="NONCE_NOT_ISSUED"):
        call(f)

def test_wrong_verifier_version_rejected():
    f=example();f[2]["verifier_version"]=999
    f[4]["approved_mandate_sha256"]=g.sha256(f[2]);f[3]["mandate_sha256"]=g.sha256(f[2]);
    with pytest.raises(ValueError,match="MANDATE_BINDING_INVALID"):
        call(f)

def test_result_readback_mismatch_rejected():
    f=example();f[3]["result_sha256"]="c"*64
    with pytest.raises(ValueError,match="INDEPENDENT_RESULT_MISMATCH"):
        call(f)

def test_synthetic_r6_explicit_no_fiscal_authority():
    out=call(example("R6_PIPELINE_SYNTHETIC",True),operation="R6_PIPELINE_SYNTHETIC")
    assert out["synthetic_only"] is True
    assert out["fiscal_authority_granted"] is False and out["r7_closed"] is False

def test_synthetic_not_smuggled_into_real_g5():
    f=example();f[3]["synthetic_only"]=True
    with pytest.raises(ValueError,match="SYNTHETIC_SCOPE_MISMATCH"):
        call(f)

def test_synthetic_r6_requires_mandate_permission():
    f=example("R6_PIPELINE_SYNTHETIC",False)
    f[3]["synthetic_only"]=True
    with pytest.raises(ValueError,match="SYNTHETIC_SCOPE_MISMATCH"):
        call(f,operation="R6_PIPELINE_SYNTHETIC")

def test_no_independent_observer_rejected():
    with pytest.raises(ValueError,match="INDEPENDENT_RESULT_OBSERVER_REQUIRED"):
        call(example(),observed_result=None)
