"""B02 G5/R1 delta: materialize policy v4 = v3 (389cce04) + g4.verifier filled
for both documents, with evidence from the real, hash-verified origin reports
(B02_G4_ORIGIN_REPORT_SUCCESSOR_*_20261102.json). Dry-run by default; Miguel
assumes all four institutional roles, declared explicitly, never fabricated
as a different real identity. Ratified by Miguel 2026-11-06 ("RATIFICO")."""
import json, os, sys
from datetime import datetime, timezone

sys.path.insert(0, r"C:\dev\solveris-b02-g5-v5-publicacao")
os.environ["DATABASE_URL"] = "postgresql+psycopg2://solveris_test:solveris_test@localhost:55432/solveris_b02_r4g_test"
DSN_OWNER = "postgresql+psycopg2://solveris_test:solveris_test@localhost:55432/solveris_b02_r4g_test"
DSN_POLICY_WRITER = "postgresql+psycopg2://solveris_b02_policy_writer:solveris_policy_writer_local@localhost:55432/solveris_b02_r4g_test"

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app import models
from app.services.enterprise_b02_policy_activation_atomicity import stage_policy_activation

CANDIDATE_PATH = r"C:\dev\solveris-b02-g5-v5-publicacao\POLICY_G5_CANDIDATO_V4_G4_VERIFIER_DELTA_20261106.json"
POLICY_ID = "SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE"
POLICY_VERSION = 4
POLICY_HASH = "b6055f7e69ca5bd236373a152a9acb2bafb48128cdba6560d58d5813e5beed9d"
DOMAIN = "SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE"
PREFIX = "B02-b6055f"

AUDITOR_ACTOR = "Miguel (funcao auditor nesta candidatura, sem terceiro independente)"
PROPONENTE_ACTOR = "Miguel (funcao proponente nesta candidatura)"
RATIFICADOR_ACTOR = "Miguel (funcao ratificador, autoridade constitucional final)"

def load_body():
    with open(CANDIDATE_PATH, encoding="utf-8") as f:
        obj = json.load(f)
    return obj["policy_candidate_body"]

def evidence(role, note):
    return {
        "source_kind": "documentary act materialized directly by Miguel, no third-party segregation claimed",
        "segregation_note": note,
        "actor_identity": {"actor_id": role},
        "no_historical_database_insertion_claim": False,
        "real_transaction": True,
    }

def run(owner_engine, writer_engine, execute: bool):
    with Session(owner_engine) as session:
        session.begin()
        body = load_body()
        pv = models.PolicyVersion(
            policy_type=body["policy_type"], policy_id=body["policy_id"],
            policy_version=body["policy_version"], policy_hash=POLICY_HASH,
            domain=body["domain"], scope=body["scope"],
            declared_material_applicability=body["declared_material_applicability"],
            modalities=body["modalities"],
            permitted_authorization_classes=body["permitted_authorization_classes"],
            permitted_execution_modes=body["permitted_execution_modes"],
            gates=body["gates"], roles=body["roles"],
            segregation_of_duties=body["segregation_of_duties"],
            limits=body["limits"], rules=body["rules"],
            exact_references=body["exact_references"],
            origin_evidence=body["origin_evidence"],
            policy_version_record_id=f"{PREFIX}-policy-v4",
        )
        import hashlib
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
        existing_pv = session.query(models.PolicyVersion).filter_by(
            policy_id=pv.policy_id, policy_version=pv.policy_version, policy_hash=pv.policy_hash
        ).one_or_none()
        if existing_pv is not None:
            pv = existing_pv
            print("POLICY_VERSION_REUSED, RECORD_HASH =", pv.record_hash)
        else:
            session.add(pv); session.flush()
            print("POLICY_VERSION_RECORD_HASH =", pv.record_hash)

        bootstrap_evidence = {
            "source_kind": "bootstrap authority record for G5 delta b6055f (g4.verifier fill), Miguel in all three roles",
            "segregation_note": "Nao ha segregacao de terceiro nesta fase; funcoes distintas, mesma titularidade.",
            "no_historical_database_insertion_claim": False,
        }
        boot = models.BootstrapAuthorityRecord(
            bootstrap_authority_record_id=f"{PREFIX}-bootstrap-v1",
            policy_type=pv.policy_type, policy_id=pv.policy_id,
            policy_version=pv.policy_version, policy_hash=pv.policy_hash,
            domain=pv.domain, scope=pv.scope,
            actor_proponente=PROPONENTE_ACTOR, actor_auditor=AUDITOR_ACTOR,
            independent_audit_result="favoravel",
            constitutional_authority_declaration="Miguel, autoridade constitucional final do B02, declara esta autoridade de arranque para o delta b6055f (preenchimento g4.verifier com evidencia real verificada por hash), sem segregacao de terceiro.",
            actor_ratificador=RATIFICADOR_ACTOR,
            segregation_evidence={"distinct_functional_actors": [PROPONENTE_ACTOR, AUDITOR_ACTOR, RATIFICADOR_ACTOR], "same_natural_person": True},
            evidence=bootstrap_evidence,
            validity="valida", submission_mode="manual", audit_mode="manual",
            ratification_mode="manual", activation_mode="manual",
            provenance={"source": "SOLVERIS_B02_G5_DELTA_G4_VERIFIER", "synthetic_only": False},
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
            "provenance": {"source": "SOLVERIS_B02_G5_DELTA_G4_VERIFIER", "synthetic_only": False},
        }
        boot.record_hash = hashlib.sha256(_cb(boot_material)).hexdigest()
        existing_boot = session.query(models.BootstrapAuthorityRecord).filter_by(
            bootstrap_authority_record_id=boot.bootstrap_authority_record_id
        ).one_or_none()
        if existing_boot is not None:
            boot = existing_boot
            print("BOOTSTRAP_REUSED, RECORD_HASH =", boot.record_hash)
        else:
            session.add(boot); session.flush()
            print("BOOTSTRAP_RECORD_HASH =", boot.record_hash)

        prev_id = None
        decisions = [
            (f"{PREFIX}-submetida-v1", "submetida", "proponente_institucional", PROPONENTE_ACTOR,
             "Submissao institucional do delta g4.verifier (b6055f), por Miguel."),
            (f"{PREFIX}-auditoria-iniciada-v1", "auditoria_iniciada", "auditor_independente", AUDITOR_ACTOR,
             "Inicio de exame tecnico-documental do delta, sem segregacao de terceiro nesta fase."),
            (f"{PREFIX}-auditada-favoravelmente-v1", "auditada_favoravelmente", "auditor_independente", AUDITOR_ACTOR,
             "Conclusao favoravel do exame: delta confirmado como unico (so g4.verifier), evidencia real verificada por hash contra os relatorios de origem 20261102."),
            (f"{PREFIX}-ratificada-v1", "ratificada", "autoridade_constitucional_final", RATIFICADOR_ACTOR,
             'Ratificacao final por Miguel ("RATIFICO", 2026-11-06), autoridade constitucional do B02.'),
        ]
        last = None
        for decision_id, event_name, role, actor, note in decisions:
            ev = evidence(actor, note)
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
            existing_d = session.query(models.PolicyDecision).filter_by(decision_id=decision_id).one_or_none()
            if existing_d is not None:
                d = existing_d
            else:
                session.add(d); session.flush()
            print(decision_id, "RECORD_HASH =", d.record_hash)
            prev_id = decision_id
            last = d

        execution = dict(
            policy_activation_execution_id=f"{PREFIX}-execution-v1",
            policy_decision_id=last.decision_id,
            policy_decision_record_hash=last.record_hash,
            policy_type=pv.policy_type, policy_id=pv.policy_id,
            policy_version=pv.policy_version, policy_hash=pv.policy_hash,
            authorization_basis_type="bootstrap_authority_record",
            bootstrap_authority_record_id=boot.bootstrap_authority_record_id,
            bootstrap_authority_record_hash=boot.record_hash,
            authorization_class="constitucional_reservada",
            execution_mode="manual",
            attempt_number=1, actor_or_worker="solveris_b02_policy_writer",
            lease_id=f"{PREFIX}-lease-v1", fencing_token=1,
            idempotency_key=f"{PREFIX}-execution-v1-20261106",
            state="concluida",
            started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc),
            provenance={"source": "SOLVERIS_B02_G5_DELTA_G4_VERIFIER", "synthetic_only": False},
        )
        activation = dict(
            policy_activation_id=f"{PREFIX}-activation-v1",
            policy_type=pv.policy_type, policy_id=pv.policy_id,
            policy_version=pv.policy_version, policy_hash=pv.policy_hash,
            domain=DOMAIN, modality="LOCAL_CAS_INCORPORATION",
            operational_interval={"from": "2026-11-06T00:00:00+00:00", "until": "2026-11-15T00:00:00+00:00"},
            activated_at=datetime.now(timezone.utc), state="activa",
            provenance={"source": "SOLVERIS_B02_G5_DELTA_G4_VERIFIER", "synthetic_only": False},
        )
        session.flush()
        if execute:
            session.commit()
            print("DECISIONS_COMMITTED (or already were)")
        else:
            session.rollback()
            print("DRY_RUN: decisions ROLLED BACK (not committed)")

    if not execute:
        print("DRY_RUN: stopping before activation stage. Re-run with --execute to attempt it for real.")
        sys.exit(0)

    with Session(writer_engine) as wsession:
        wsession.begin()
        wconn = wsession.connection()
        result = stage_policy_activation(
            wconn, execution=execution, activation=activation,
            generation_id=f"{PREFIX}-generation-v1",
            outbox_id=f"{PREFIX}-outbox-v1",
            provenance={"source": "SOLVERIS_B02_G5_DELTA_G4_VERIFIER", "synthetic_only": False},
        )
        print("ACTIVATION_RESULT =", result)
        if execute:
            wsession.commit()
            print("ACTIVATION_COMMITTED")
        else:
            wsession.rollback()
            print("ACTIVATION_ROLLED_BACK (dry-run)")


if __name__ == "__main__":
    owner_engine = create_engine(DSN_OWNER)
    writer_engine = create_engine(DSN_POLICY_WRITER)
    execute = "--execute" in sys.argv
    run(owner_engine, writer_engine, execute)
