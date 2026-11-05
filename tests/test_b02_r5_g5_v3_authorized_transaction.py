"""Only NEW R5 V3 orchestration checks; no PostgreSQL or protected writes."""
import base64
from types import SimpleNamespace

import pytest
from sqlalchemy.pool import NullPool
from tools import b02_r5_g5_v3_authorized_transaction as m

def approval():
    return {k: (k if k in {"approval_id", "release_id"} else "a"*64)
            for k in m.FIELDS}

def test_r5_specific_commit_required_before_connections():
    with pytest.raises(m.R5Stop, match="SPECIFIC_PROTECTED_COMMIT_AUTHORITY_MISSING"):
        m.execute_authorized_r5(None, units=[], approval=approval(),
                                independently_verify_acts=lambda _: {},
                                competent_sign_manifest=lambda _: {})

def test_r5_reviewer_and_root_pins_not_assumed():
    d=approval(); d["native_root_sha256"]="not-verified"
    with pytest.raises(m.R5Stop, match="APPROVAL_HASHES_REQUIRED"):
        m.validate_approval(d)

def test_r5_signed_manifest_must_match_database_bytes():
    raw=b'{"signed":"from-server"}'
    envelope={
        "key_id":"test-only",
        "signed_message_base64":base64.b64encode(raw+b"!").decode("ascii"),
        "signature_base64":base64.b64encode(b"x"*64).decode("ascii"),
    }
    with pytest.raises(m.R5Stop, match="SIGNED_DB_MANIFEST_DIVERGENCE"):
        m.validate_envelope(envelope, raw)

def test_r5_requires_independent_physical_connections():
    engine=SimpleNamespace(pool=object())
    with pytest.raises(m.R5Stop, match="INDEPENDENT_SESSION_NULLPOOL_REQUIRED"):
        m.execute_authorized_r5(engine, units=[], approval=approval(),
                                specifically_authorized_commit=True,
                                independently_verify_acts=lambda _: {},
                                competent_sign_manifest=lambda _: {})

def test_r5_current_authority_not_inferred_from_transport():
    engine=SimpleNamespace(pool=NullPool(lambda: None))
    with pytest.raises(m.R5Stop, match="CURRENT_G5_V3_R1_AUTHORITY_NOT_VERIFIED"):
        m.execute_authorized_r5(engine, units=[], approval=approval(),
                                specifically_authorized_commit=True,
                                independently_verify_acts=lambda _: {"status":"CURRENT_VERIFIED",
                                                                        "g5_policy_hash":"b"*64},
                                competent_sign_manifest=lambda _: {})
