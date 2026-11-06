"""Delta v6: adiciona sanitization.execution_proof_binding aos dois documentos.
Le o corpo da v5 diretamente da BD (fonte de verdade), nao do ficheiro local.
Mesma disciplina: dry-run por omissao, transacao explicita, idempotente."""
import hashlib, json, os, sys

sys.path.insert(0, r"C:\dev\solveris-b02-g5-v5-publicacao")
os.environ["DATABASE_URL"] = os.environ["SOLVERIS_B02_OWNER_DSN"]
DSN_OWNER = os.environ["SOLVERIS_B02_OWNER_DSN"]

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app import models
from app.services.enterprise_b02_noncredential_acquisition import canonical_bytes

V5_HASH = "0f919b362cb6c55c8c99296df58e96d3e3954d50ae68a3bc39dca27d4a6632a9"
V5_ACTIVATION_ID = "B02-0f919b-activation-v1"

EXEC_PROOF_BINDINGS = {
    "101202501245": {"id": "B02-G5-101202501245-V3-execproof", "hash": "d9d0c3cdcde9fc2d63f14661b32dfee5fc82e0531dcc99a9225a808316a1d021"},
    "101201900571": {"id": "B02-G5-101201900571-V3-execproof", "hash": "80684bcd4024ca4dc0ef10f258907d25fd7d62aa6faa15757f7ee3ddbe313432"},
}

AUDITOR_ACTOR = "Miguel (funcao auditor nesta candidatura, sem terceiro independente)"
PROPONENTE_ACTOR = "Miguel (funcao proponente nesta candidatura)"
RATIFICADOR_ACTOR = "Miguel (funcao ratificador, autoridade constitucional final)"

def evidence(role, note):
    return {
        "source_kind": "preparatory local draft; independent audit not established",
        "segregation_note": note,
        "actor_identity": {"actor_id": role},
        "no_historical_database_insertion_claim": True,
        "real_transaction": False,
    }

def run(owner_engine, execute: bool):
    if execute:
        raise SystemExit("STOP_B02_G5_V6_ACTOR_SEGREGATION_NOT_PROVEN")
    with Session(owner_engine) as session:
        session.begin()

        v5 = session.query(models.PolicyVersion).filter_by(
            policy_id="SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE", policy_hash=V5_HASH
        ).one()

        body = {
            "policy_type": v5.policy_type, "policy_id": v5.policy_id,
            "policy_version": 6, "domain": v5.domain, "scope": v5.scope,
            "declared_material_applicability": v5.declared_material_applicability,
            "modalities": v5.modalities,
            "permitted_authorization_classes": v5.permitted_authorization_classes,
            "permitted_execution_modes": v5.permitted_execution_modes,
            "gates": v5.gates, "roles": v5.roles,
            "segregation_of_duties": v5.segregation_of_duties,
            "limits": v5.limits,
            "rules": json.loads(json.dumps(v5.rules)),
            "exact_references": v5.exact_references,
            "origin_evidence": v5.origin_evidence,
        }

        docs = body["rules"]["b02_noncredential"]["security"]["g5_release"]["documents"]
        for doc in docs:
            doc_id = doc["document_id"]
            if doc_id not in EXEC_PROOF_BINDINGS:
                raise SystemExit(f"UNKNOWN_DOCUMENT_{doc_id}")
            doc["sanitization"]["execution_proof_binding"] = EXEC_PROOF_BINDINGS[doc_id]

        policy_hash = hashlib.sha256(canonical_bytes(body)).hexdigest()
        print("V6_POLICY_HASH =", policy_hash)

        pv = models.PolicyVersion(
            policy_type=body["policy_type"], policy_id=body["policy_id"],
            policy_version=6, policy_hash=policy_hash,
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
            policy_version_record_id=f"B02-{policy_hash[:8]}-policy-v6",
        )
        pv_material = {k: getattr(pv, k) for k in (
            "policy_type","policy_id","policy_version","policy_hash","domain","scope",
            "declared_material_applicability","modalities","permitted_authorization_classes",
            "permitted_execution_modes","gates","roles","segregation_of_duties","limits",
            "rules","exact_references","origin_evidence")}
        pv.record_hash = hashlib.sha256(canonical_bytes(pv_material)).hexdigest()

        existing_pv = session.query(models.PolicyVersion).filter_by(
            policy_id=pv.policy_id, policy_version=6
        ).one_or_none()
        if existing_pv is not None:
            if existing_pv.policy_hash != policy_hash:
                raise SystemExit(f"V6_ALREADY_EXISTS_WITH_DIFFERENT_HASH: {existing_pv.policy_hash}")
            pv = existing_pv
            print("POLICY_V6_REUSED, RECORD_HASH =", pv.record_hash)
        else:
            session.add(pv); session.flush()
            print("POLICY_V6_RECORD_HASH =", pv.record_hash)

        prefix = policy_hash[:8]
        if not execute:
            session.rollback()
            print("V6_POLICY_PREVIEW_ONLY: no institutional decisions emitted")
            return

        decisions = [
            (f"B02-{prefix}-submetida-v1", "submetida", "proponente_institucional", PROPONENTE_ACTOR,
             "Submissao institucional da v6 (execution_proof_binding), por Miguel."),
            (f"B02-{prefix}-auditoria-iniciada-v1", "auditoria_iniciada", "auditor_independente", AUDITOR_ACTOR,
             "Inicio de exame tecnico-documental, sem segregacao de terceiro nesta fase."),
            (f"B02-{prefix}-auditada-favoravelmente-v1", "auditada_favoravelmente", "auditor_independente", AUDITOR_ACTOR,
             "Conclusao favoravel do exame, mesmo ator que iniciou a auditoria."),
            (f"B02-{prefix}-ratificada-v1", "ratificada", "autoridade_constitucional_final", RATIFICADOR_ACTOR,
             "Ratificacao final por Miguel, autoridade constitucional do B02."),
        ]
        prev_id = None
        last = None
        for decision_id, event_name, role, actor, note in decisions:
            ev = evidence(actor, note)
            d_material = {
                "decision_id": decision_id, "decision_event": event_name,
                "policy_type": pv.policy_type, "policy_id": pv.policy_id,
                "policy_version": pv.policy_version, "policy_hash": pv.policy_hash,
                "actor": actor, "institutional_role": role,
                "evidence": ev, "rationale": note,
                "previous_decision_id": prev_id,
                "idempotency_key": decision_id,
            }
            record_hash = hashlib.sha256(canonical_bytes(d_material)).hexdigest()
            existing_d = session.query(models.PolicyDecision).filter_by(decision_id=decision_id).one_or_none()
            if existing_d is not None:
                d = existing_d
            else:
                d = models.PolicyDecision(
                    decision_id=decision_id, decision_event=event_name,
                    policy_type=pv.policy_type, policy_id=pv.policy_id,
                    policy_version=pv.policy_version, policy_hash=pv.policy_hash,
                    actor=actor, institutional_role=role,
                    evidence=ev, rationale=note,
                    previous_decision_id=prev_id,
                    idempotency_key=decision_id,
                    record_hash=record_hash,
                )
                session.add(d); session.flush()
            print(decision_id, "RECORD_HASH =", d.record_hash)
            prev_id = decision_id
            last = d

        if execute:
            session.commit()
            print("V6_DECISIONS_COMMITTED")
        else:
            print("DRY_RUN: V6 nao commitado, rollback no fim.")

    if not execute:
        print("DRY_RUN: parando antes da ativacao. Rodar com --execute para aplicar.")
        return

    from sqlalchemy.orm import Session as S2
    from app.services.enterprise_b02_policy_activation_atomicity import stage_policy_activation
    from datetime import datetime, timezone
    DSN_POLICY_WRITER = os.environ["SOLVERIS_B02_POLICY_WRITER_DSN"]
    writer_engine = create_engine(DSN_POLICY_WRITER)
    with S2(writer_engine) as wsession:
        wsession.begin()
        wconn = wsession.connection()
        execution = dict(
            policy_activation_execution_id=f"B02-{prefix}-execution-v1",
            policy_decision_id=last.decision_id, policy_decision_record_hash=last.record_hash,
            policy_type=pv.policy_type, policy_id=pv.policy_id,
            policy_version=pv.policy_version, policy_hash=pv.policy_hash,
            authorization_basis_type="active_policy_chain",
            activation_authority_policy_id=pv.policy_id,
            activation_authority_policy_version=5,
            activation_authority_policy_hash=V5_HASH,
            activation_authority_policy_activation_id=V5_ACTIVATION_ID,
            authorization_class="constitucional_reservada", execution_mode="manual",
            attempt_number=1, actor_or_worker="solveris_b02_policy_writer",
            lease_id=f"B02-{prefix}-lease-v1", fencing_token=1,
            idempotency_key=f"B02-{prefix}-execution-v1-20261106",
            state="concluida",
            started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc),
            provenance={"source": "SOLVERIS_B02_G5_R1_V6_EXECPROOF", "synthetic_only": False},
        )
        activation = dict(
            policy_activation_id=f"B02-{prefix}-activation-v1",
            policy_type=pv.policy_type, policy_id=pv.policy_id,
            policy_version=pv.policy_version, policy_hash=pv.policy_hash,
            domain="SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE", modality="LOCAL_CAS_INCORPORATION",
            operational_interval={"from": "2026-11-06T00:00:00+00:00", "until": "2027-11-06T00:00:00+00:00"},
            activated_at=datetime.now(timezone.utc), state="activa",
            provenance={"source": "SOLVERIS_B02_G5_R1_V6_EXECPROOF", "synthetic_only": False},
        )
        result = stage_policy_activation(
            wconn, execution=execution, activation=activation,
            generation_id=f"B02-{prefix}-generation-v1", outbox_id=f"B02-{prefix}-outbox-v1",
            provenance={"source": "SOLVERIS_B02_G5_R1_V6_EXECPROOF", "synthetic_only": False},
        )
        print("ACTIVATION_RESULT =", result)
        wsession.commit()
        print("V6_ACTIVATION_COMMITTED")

if __name__ == "__main__":
    owner_engine = create_engine(DSN_OWNER)
    execute = "--execute" in sys.argv
    run(owner_engine, execute)
