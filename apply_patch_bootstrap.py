path = r"C:\dev\solveris-b02-g5-v5-publicacao\materializar_cadeia_g5r1_389cce04.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = 'AUDITOR_ACTOR = "Miguel (funcao auditor nesta candidatura, sem terceiro independente)"\nPROPONENTE_ACTOR = "Miguel"\nRATIFICADOR_ACTOR = "Miguel"'
new = ('AUDITOR_ACTOR = "Miguel (funcao auditor nesta candidatura, sem terceiro independente)"\n'
       'PROPONENTE_ACTOR = "Miguel (funcao proponente nesta candidatura)"\n'
       'RATIFICADOR_ACTOR = "Miguel (funcao ratificador, autoridade constitucional final)"')
if old not in content: raise SystemExit("A_NOT_FOUND")
content = content.replace(old, new)

old2 = "        prev_id = None\n        decisions = ["
new2 = '''        import hashlib as _hl
        from app.services.enterprise_b02_noncredential_acquisition import canonical_bytes as _cb2
        bootstrap_evidence = {
            "source_kind": "bootstrap authority record for G5/R1 candidate 389cce04, Miguel in all three roles",
            "segregation_note": "Nao ha segregacao de terceiro nesta fase; funcoes distintas, mesma titularidade.",
            "no_historical_database_insertion_claim": False,
        }
        boot = models.BootstrapAuthorityRecord(
            bootstrap_authority_record_id="B02-389cce04-bootstrap-v1",
            policy_type=pv.policy_type, policy_id=pv.policy_id,
            policy_version=pv.policy_version, policy_hash=pv.policy_hash,
            domain=pv.domain, scope=pv.scope,
            actor_proponente=PROPONENTE_ACTOR, actor_auditor=AUDITOR_ACTOR,
            independent_audit_result="favoravel",
            constitutional_authority_declaration="Miguel, autoridade constitucional final do B02, declara esta autoridade de arranque para a candidata 389cce04, sem segregacao de terceiro.",
            actor_ratificador=RATIFICADOR_ACTOR,
            segregation_evidence={"distinct_functional_actors": [PROPONENTE_ACTOR, AUDITOR_ACTOR, RATIFICADOR_ACTOR], "same_natural_person": True},
            evidence=bootstrap_evidence,
            validity="valida", submission_mode="manual", audit_mode="manual",
            ratification_mode="manual", activation_mode="manual",
            provenance={"source": "SOLVERIS_B02_G5_R1_MATERIALIZATION", "synthetic_only": False},
            record_hash="0" * 64,
        )
        boot_material = {
            "bootstrap_authority_record_id": boot.bootstrap_authority_record_id,
            "policy_type": pv.policy_type, "policy_id": pv.policy_id,
            "policy_version": pv.policy_version, "policy_hash": pv.policy_hash,
            "domain": pv.domain, "scope": pv.scope,
            "actor_proponente": PROPONENTE_ACTOR, "actor_auditor": AUDITOR_ACTOR,
            "independent_audit_result": "favoravel",
            "constitutional_authority_declaration": boot.constitutional_authority_declaration,
            "actor_ratificador": RATIFICADOR_ACTOR,
            "segregation_evidence": boot.segregation_evidence,
            "evidence": bootstrap_evidence,
            "validity": "valida", "submission_mode": "manual", "audit_mode": "manual",
            "ratification_mode": "manual", "activation_mode": "manual",
            "provenance": {"source": "SOLVERIS_B02_G5_R1_MATERIALIZATION", "synthetic_only": False},
        }
        boot.record_hash = _hl.sha256(_cb2(boot_material)).hexdigest()
        session.add(boot); session.flush()
        print("BOOTSTRAP_RECORD_HASH =", boot.record_hash)

        prev_id = None
        decisions = ['''
if old2 not in content: raise SystemExit("B_NOT_FOUND")
content = content.replace(old2, new2)

old3 = '''        execution = dict(
            policy_activation_execution_id="B02-389cce04-execution-v1",
            policy_decision_id=last.decision_id,
            policy_decision_record_hash=last.record_hash,
            policy_type=pv.policy_type, policy_id=pv.policy_id,
            policy_version=pv.policy_version, policy_hash=pv.policy_hash,
            authorization_basis_type="active_policy_chain",'''
new3 = '''        execution = dict(
            policy_activation_execution_id="B02-389cce04-execution-v1",
            policy_decision_id=last.decision_id,
            policy_decision_record_hash=last.record_hash,
            policy_type=pv.policy_type, policy_id=pv.policy_id,
            policy_version=pv.policy_version, policy_hash=pv.policy_hash,
            authorization_basis_type="bootstrap_authority_record",
            bootstrap_authority_record_id=boot.bootstrap_authority_record_id,
            bootstrap_authority_record_hash=boot.record_hash,'''
if old3 not in content: raise SystemExit("C_NOT_FOUND")
content = content.replace(old3, new3)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("PATCHED")
