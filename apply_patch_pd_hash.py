path = r"C:\dev\solveris-b02-g5-v5-publicacao\materializar_cadeia_g5r1_389cce04.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = """            d = models.PolicyDecision(
                decision_id=decision_id, decision_event=event_name,
                policy_type=pv.policy_type, policy_id=pv.policy_id,
                policy_version=pv.policy_version, policy_hash=pv.policy_hash,
                actor=actor, institutional_role=role,
                evidence=evidence(actor, note), rationale=note,
                previous_decision_id=prev_id,
                idempotency_key=decision_id,
            )
            session.add(d); session.flush()"""

new = """            ev = evidence(actor, note)
            d = models.PolicyDecision(
                decision_id=decision_id, decision_event=event_name,
                policy_type=pv.policy_type, policy_id=pv.policy_id,
                policy_version=pv.policy_version, policy_hash=pv.policy_hash,
                actor=actor, institutional_role=role,
                evidence=ev, rationale=note,
                previous_decision_id=prev_id,
                idempotency_key=decision_id,
                record_hash="0" * 64,
            )
            import hashlib
            from app.services.enterprise_b02_noncredential_acquisition import canonical_bytes as _cb
            d_material = {
                "decision_id": decision_id, "decision_event": event_name,
                "policy_type": pv.policy_type, "policy_id": pv.policy_id,
                "policy_version": pv.policy_version, "policy_hash": pv.policy_hash,
                "actor": actor, "institutional_role": role,
                "evidence": ev, "rationale": note,
                "previous_decision_id": prev_id,
                "idempotency_key": decision_id,
            }
            d.record_hash = hashlib.sha256(_cb(d_material)).hexdigest()
            session.add(d); session.flush()"""

if old not in content:
    raise SystemExit("PATCH_TARGET_NOT_FOUND")
content = content.replace(old, new)
with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("PATCHED")
