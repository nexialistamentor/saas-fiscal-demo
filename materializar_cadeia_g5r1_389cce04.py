"""B02 G5/R1: materialize the policy chain for the ratified candidate 389cce04.
Dry-run by default; writes only inside an explicit transaction that the
caller controls. Miguel assumes all four institutional roles in this act,
with no third-party segregation -- declared explicitly in each decision's
evidence, never fabricated as a different real identity."""
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

CANDIDATE_PATH = r"C:\dev\solveris-b02-g5-v5-publicacao\POLICY_G5_CANDIDATO_SUCESSOR_V3_R1_SUBSTITUICAO_PROSPECTIVA_20261105.json"
POLICY_ID = "SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE"
POLICY_VERSION = 3
POLICY_HASH = "389cce04dd249c5fb184fce7b876608651dd84ca3db64b7d778bb2de66a0c3d2"
DOMAIN = "SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE"

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
        conn = session.connection()
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
            policy_version_record_id="B02-389cce04-policy-v3",
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

        import hashlib as _hl
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
            ("B02-389cce04-submetida-v1", "submetida", "proponente_institucional", PROPONENTE_ACTOR,
             "Submissao institucional da candidata G5/R1 389cce04, por Miguel."),
            ("B02-389cce04-auditoria-iniciada-v1", "auditoria_iniciada", "auditor_independente", AUDITOR_ACTOR,
             "Inicio de exame tecnico-documental, sem segregacao de terceiro nesta fase."),
            ("B02-389cce04-auditada-favoravelmente-v1", "auditada_favoravelmente", "auditor_independente", AUDITOR_ACTOR,
             "Conclusao favoravel do exame, mesmo ator que iniciou a auditoria."),
            ("B02-389cce04-ratificada-v1", "ratificada", "autoridade_constitucional_final", RATIFICADOR_ACTOR,
             "Ratificacao final por Miguel, autoridade constitucional do B02."),
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
            existing_d = session.query(models.PolicyDecision).filter_by(decision_id=decision_id).one_or_none()
            if existing_d is not None:
                d = existing_d
            else:
                session.add(d); session.flush()
            print(decision_id, "RECORD_HASH =", d.record_hash)
            prev_id = decision_id
            last = d

        execution = dict(
            policy_activation_execution_id="B02-389cce04-execution-v1",
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
            lease_id="B02-389cce04-lease-v1", fencing_token=1,
            idempotency_key="B02-389cce04-execution-v1-20261105",
            state="concluida",
            started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc),
            provenance={"source": "SOLVERIS_B02_G5_R1_MATERIALIZATION", "synthetic_only": False},
        )
        activation = dict(
            policy_activation_id="B02-389cce04-activation-v1",
            policy_type=pv.policy_type, policy_id=pv.policy_id,
            policy_version=pv.policy_version, policy_hash=pv.policy_hash,
            domain=DOMAIN, modality="LOCAL_CAS_INCORPORATION",
            operational_interval={"from": "2026-11-05T00:00:00+00:00", "until": "2027-11-05T00:00:00+00:00"},
            activated_at=datetime.now(timezone.utc), state="activa",
            provenance={"source": "SOLVERIS_B02_G5_R1_MATERIALIZATION", "synthetic_only": False},
        )
        session.flush()
        if execute:
            session.commit()
            print("DECISIONS_COMMITTED (or already were)")
        else:
            print("DRY_RUN: decisions NOT committed by this run (any reused rows were already committed earlier)")

    if not execute:
        print("DRY_RUN: stopping before activation stage. Re-run with --execute to attempt it for real.")
        sys.exit(0)

    with Session(writer_engine) as wsession:
        wsession.begin()
        wconn = wsession.connection()
        result = stage_policy_activation(
            wconn, execution=execution, activation=activation,
            generation_id="B02-389cce04-generation-v1",
            outbox_id="B02-389cce04-outbox-v1",
            provenance={"source": "SOLVERIS_B02_G5_R1_MATERIALIZATION", "synthetic_only": False},
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
