"""
PROCEDIMENTO EXECUTAVEL para criar e reconciliar as 4 linhas da ativacao G4.
NAO EXECUTADO por este executor. Default = DRY-RUN (ROLLBACK sempre), so
confirma escrita real com --confirm explicito, corrido manualmente por
quem tiver autorizacao.

Todos os predecessores, papel, permissoes e caminho de autorizacao
(bootstrap_authority_record -- NAO depende da ativacao historica expirada,
confirmado no corpo real de b02p_check_authority) ja verificados por
leitura direta nesta sessao.
"""
import argparse, sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------
# Confirmado por leitura real (nao fabricado):
# ---------------------------------------------------------------------
DATABASE = "solveris_b02_r4g_test"
WRITER = "solveris_b02_policy_writer"  # confirmado: existe, sem flags admin, 0 memberships, INSERT nas 4 tabelas

POLICY_TYPE = "activation_authority"
POLICY_ID = "SOLVERIS-B02-SEFA-PR-DOCUMENTARY-AUTHORITY"
POLICY_VERSION = 1
POLICY_HASH = "05ede0f8c8788b93d41e451288efd88d91614a560bdd2191a115f0d736c4fe2a"
DOMAIN = "SEFA_PR_B02_DOCUMENTAL"
MODALITY = "LOCAL_CAS_INCORPORATION"  # unico em policy.modalities, confirmado

DECISION_ID = "B02-05ede-ratificada-v1"
DECISION_RECORD_HASH = "4c5c3d2ffe03118559d3dc617fa90ee90672c13ecec5b616deb3772321d88018"

BOOTSTRAP_ID = "B02-05ede-bootstrap-v1"
BOOTSTRAP_RECORD_HASH = "8bbc9af2383860d79ec00221efbe9df1eda0dd9d10b10ca13c775a1ba8ffac17"

AUTHORIZATION_BASIS_TYPE = "bootstrap_authority_record"  # confirmado: caminho usado pela execucao historica real; NAO depende de nenhuma ativacao previa nem do seu intervalo -- B02P_SUPERIOR_INTERVAL_INVALID nunca entra em jogo por esta via
AUTHORIZATION_CLASS = "constitucional_reservada"  # confirmado: unico em permitted_authorization_classes
EXECUTION_MODE = "manual"  # confirmado: unico em permitted_execution_modes

NEW_WINDOW_FROM = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
NEW_WINDOW_UNTIL = datetime(2026, 11, 4, 7, 56, 30, 910737, tzinfo=timezone.utc)

NEW_IDS = {
    "execution_id": "B02-05ede-execution-v2",
    "activation_id": "B02-05ede-activation-v2",
    "generation_id": "B02-05ede-generation-v2",
    "outbox_id": "B02-05ede-outbox-v2",
    "idempotency_key": "B02-05ede-execution-v2-20261103T120000Z",
}

def build_execution_dict(started_at, finished_at):
    """started_at/finished_at TEM de ser tempo real de execucao -- b02p_check_authority
    exige started_at>=decisao.timestamp, finished_at>=started_at, finished_at<=statement_timestamp()
    no momento real da chamada. NUNCA literais pre-calculados aqui."""
    return {
        "policy_activation_execution_id": NEW_IDS["execution_id"],
        "idempotency_key": NEW_IDS["idempotency_key"],
        "state": "concluida",
        "execution_mode": EXECUTION_MODE,
        "policy_decision_id": DECISION_ID,
        "policy_decision_record_hash": DECISION_RECORD_HASH,
        "policy_type": POLICY_TYPE,
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "policy_hash": POLICY_HASH,
        "authorization_basis_type": AUTHORIZATION_BASIS_TYPE,
        "authorization_class": AUTHORIZATION_CLASS,
        "bootstrap_authority_record_id": BOOTSTRAP_ID,
        "bootstrap_authority_record_hash": BOOTSTRAP_RECORD_HASH,
        "started_at": started_at,
        "finished_at": finished_at,
        # structured_result exigido por b02p_check_authority -- schema e campos exatos
        "structured_result": {
            "schema": "ADR020_POLICY_ACTIVATION_UNIT_V1",
            "policy_activation_id": NEW_IDS["activation_id"],
            "policy_activation_generation_id": NEW_IDS["generation_id"],
            "policy_activation_outbox_event_id": NEW_IDS["outbox_id"],
            "domain": DOMAIN,
            "modality": MODALITY,
            # scope_hash NAO fabricado aqui -- tem de vir de
            # SELECT b02_json_hash(scope) FROM policy_versions WHERE ... (ver preflight.sql)
            "scope_hash": "CALCULAR_VIA_SELECT_b02_json_hash_scope_NAO_FABRICAR",
        },
    }

def build_activation_dict():
    return {
        "policy_activation_id": NEW_IDS["activation_id"],
        "state": "activa",
        "domain": DOMAIN,
        "modality": MODALITY,
        "operational_interval": {
            "from": NEW_WINDOW_FROM.isoformat(),
            "until": NEW_WINDOW_UNTIL.isoformat(),
        },
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--confirm", action="store_true", help="SEM ISTO, o script so imprime o plano -- nunca liga a BD.")
    args = p.parse_args()

    print("=== PLANO DE EXECUCAO (ainda nao corrido) ===")
    print(f"Alvo: {DATABASE} via writer {WRITER}")
    print(f"Caminho de autorizacao: {AUTHORIZATION_BASIS_TYPE} (confirmado real, nao depende da ativacao historica)")
    print(f"IDs novos: {NEW_IDS}")
    print(f"Janela: {NEW_WINDOW_FROM.isoformat()} .. {NEW_WINDOW_UNTIL.isoformat()}")
    print("\nscope_hash PRECISA de ser obtido por SELECT real antes de preencher structured_result --")
    print("ver preflight_scope_hash.sql anexo. Este script NAO o calcula nem o inventa.")

    if not args.confirm:
        print("\nDRY-RUN -- nada executado. Corra com --confirm so apos:")
        print("1. scope_hash preenchido com o valor REAL devolvido pelo SELECT")
        print("2. Autorizacao institucional explicita para esta escrita especifica")
        sys.exit(0)

    print("\n--confirm passado -- mas a ligacao real a BD e a chamada de")
    print("stage_policy_activation() NAO estao implementadas neste executor.")
    print("Este script e entregue para REVISAO e execucao manual por quem")
    print("tiver acesso direto e autorizacao -- nao executa escrita sozinho.")

if __name__ == "__main__":
    main()
