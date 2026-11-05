import hashlib

path = r"C:\dev\solveris-b02-g5-v5-publicacao\materializar_cadeia_g5r1_389cce04.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = """        session.add(pv); session.flush()
        print("POLICY_VERSION_RECORD_HASH =", pv.record_hash)"""

new = """        import hashlib
        from app.services.enterprise_b02_noncredential_acquisition import canonical_bytes as _cb
        pv_material = {
            "policy_type": pv.policy_type, "policy_id": pv.policy_id,
            "policy_version": pv.policy_version, "policy_hash": pv.policy_hash,
            "domain": pv.domain, "scope": pv.scope,
            "declared_material_applicability": pv.declared_material_applicability,
            "modalities": pv.modalities,
            "permitted_authorization_classes": pv.permitted_authorization_classes,
            "permitted_execution_modes": pv.permitted_execution_modes,
            "gates": pv.gates, "roles": pv.roles,
            "segregation_of_duties": pv.segregation_of_duties,
            "limits": pv.limits, "rules": pv.rules,
            "exact_references": pv.exact_references,
            "origin_evidence": pv.origin_evidence,
        }
        pv.record_hash = hashlib.sha256(_cb(pv_material)).hexdigest()
        session.add(pv); session.flush()
        print("POLICY_VERSION_RECORD_HASH =", pv.record_hash)"""

if old not in content:
    raise SystemExit("PATCH_TARGET_NOT_FOUND")
content = content.replace(old, new)
with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("PATCHED")
