import hashlib, json

def canonical_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False).encode('utf-8')

manifest = {
    "audit_scope": "SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE",
    "capability_root_id": "SOLVERIS-B02-SEFA-PR-G5-COMMIT-MIGUEL-V2",
    "documents": [
        {"byte_size": 1944929, "id": "101201900571", "sha256": "af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d"},
        {"byte_size": 258302, "id": "101202501245", "sha256": "e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832"}
    ],
    "g4_verifier": {"hash": "fab019b18d21f8e47e59ff96fd783dc9732cc3ae1d6e1ed429bddf957f0b9472", "id": "SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN", "version": "1"},
    "g5_policy_binding": {
        "decision_hash": "29b7d2e98abb876bb472f3ef67deec7056dfe8aa9fe0d960ae03e6bd5e1e77d6",
        "decision_id": "B02-389cce04-ratificada-v1",
        "policy_activation_id": "B02-389cce04-activation-v1",
        "policy_activation_record_hash": "6b495c284eb9d86c75a29ae0ae705603428daa45933a307786692a52cf7af5b8",
        "policy_hash": "389cce04dd249c5fb184fce7b876608651dd84ca3db64b7d778bb2de66a0c3d2",
        "policy_id": "SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE",
        "policy_type": "activation_authority",
        "policy_version": 3
    },
    "release_policy_hash": "389cce04dd249c5fb184fce7b876608651dd84ca3db64b7d778bb2de66a0c3d2",
    "schema": "B02_G5_TX_RELEASE_V1",
    "server": {
        "database_name": "solveris_b02_r4g_test", "database_oid": 40962,
        "system_identifier": "7688884600396267558",
        "writer_name": "solveris_b02_writer", "writer_oid": 40961
    },
    "synthetic_only": False
}
raw = canonical_bytes(manifest)
print("MANIFEST_SHA256 =", hashlib.sha256(raw).hexdigest())
print()

c_escaped = raw.decode("utf-8").replace("\\", "\\\\").replace('"', '\\"')
print("C_ESCAPED_CONSTRAINTS_JSON:")
print(c_escaped)
