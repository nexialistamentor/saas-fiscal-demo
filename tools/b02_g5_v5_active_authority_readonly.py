#!/usr/bin/env python3
"""Read-only inventory for G5 V5 active_policy_chain. Never decides eligibility by state alone."""
import json, os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

TARGET = "SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE"
def inspect(engine):
    with engine.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        identity = c.execute(text("SELECT current_database(), current_user")).one()
        if identity[0] != "solveris_b02_r4g_test":
            raise RuntimeError("STOP_WRONG_DATABASE")
        rows = c.execute(text("""
            SELECT a.policy_activation_id, a.policy_id, a.policy_version,
                   a.policy_hash, a.record_hash AS activation_hash,
                   a.state, a.domain, a.modality, a.operational_interval,
                   p.scope, p.permitted_authorization_classes,
                   p.permitted_execution_modes, p.gates, p.rules,
                   p.limits, p.declared_material_applicability,
                   d.decision_id, d.decision_event, d.record_hash AS decision_hash,
                   d.evidence AS decision_evidence
            FROM public.policy_activations a
            JOIN public.policy_versions p
              ON p.policy_id=a.policy_id AND p.policy_version=a.policy_version
             AND p.policy_hash=a.policy_hash
            JOIN public.policy_decisions d ON d.decision_id=a.policy_decision_id
            WHERE a.policy_type='activation_authority'
            ORDER BY a.policy_id,a.policy_version,a.policy_activation_id
        """)).mappings().all()
        c.rollback()
    return {"status":"READ_ONLY_INVENTORY","database":identity[0],
            "target_policy_id":TARGET,"candidates":[dict(r) for r in rows],
            "eligibility":"NOT_INFERRED_REQUIRES_SCOPE_DELEGATION_VALIDITY_AND_EXACT_LINK_REVIEW",
            "writes":0}
def main():
    dsn=os.environ.get("SOLVERIS_B02_POLICY_WRITER_DSN")
    if not dsn: raise RuntimeError("STOP_DSN_REQUIRED")
    engine=create_engine(dsn,poolclass=NullPool)
    try: print(json.dumps(inspect(engine),default=str,ensure_ascii=False,sort_keys=True))
    finally: engine.dispose()
if __name__=="__main__": main()
