"""
PagamentoService — domínio financeiro soberano.

Responsabilidades:
- Criar intenção de pagamento (persistir antes de chamar gateway)
- Registar tentativas em PagamentoTentativa (ledger auditável)
- Mapear status gateway → estado interno soberano
- Nunca confiar em notificação passiva — validar activamente via API

Máquina de estados soberana:
  created → gateway_requested → redirected → pending →
  authorized → approved → [expired | cancelled | rejected | refunded | chargeback]

Princípio: persistir primeiro → enriquecer depois → só então usar inteligência.
"""

from decimal import Decimal
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.models import Pagamento, PagamentoTentativa


# ---------------------------------------------------------------------------
# Máquina de estados soberana com transições válidas
# ---------------------------------------------------------------------------
ESTADOS_VALIDOS = {
    "created",
    "gateway_requested",
    "redirected",
    "pending",
    "authorized",
    "approved",
    "expired",
    "cancelled",
    "rejected",
    "refunded",
    "chargeback",
    "reconciliation_failed",
}

TRANSICOES_VALIDAS: dict[str, set] = {
    "created": {"gateway_requested", "cancelled"},
    "gateway_requested": {"redirected", "pending", "rejected", "expired"},
    "redirected": {"pending", "cancelled", "expired", "rejected"},
    "pending": {"authorized", "approved", "expired", "cancelled", "reconciliation_failed"},
    "authorized": {"approved", "cancelled", "refunded"},
    "approved": {"refunded", "chargeback"},
    "expired": set(),
    "cancelled": set(),
    "rejected": set(),
    "refunded": set(),
    "chargeback": set(),
    "reconciliation_failed": {"pending", "approved", "rejected"},
}

# Origens de erro controladas
ERROR_ORIGINS_VALIDOS = {
    "gateway",
    "plataforma",
    "network",
    "antifraud",
    "issuer",
    "user",
    "reconciliation",
}


def _sanitizar_external_reference(tipo_perfil: str, perfil_id: str, contexto: str) -> str:
    """
    Gera external_reference sanitizada para o gateway.

    Mantém semântica mas garante formato seguro (max 256 chars, só alfanumérico e hífens).
    """
    raw = f"{tipo_perfil}-{perfil_id}-{contexto}"
    sanitized = "".join(c if c.isalnum() or c == "-" else "-" for c in raw)
    return sanitized[:256]


# Mapeamento status bruto gateway → estado interno soberano
_MP_STATUS_MAP = {
    "approved": "approved",
    "authorized": "authorized",
    "in_process": "pending",
    "pending": "pending",
    "cancelled": "cancelled",
    "refunded": "refunded",
    "charged_back": "chargeback",
    "expired": "expired",
    "rejected": "rejected",
}


def _mapear_status_gateway(mp_status_raw: str) -> str:
    """Mapeia status bruto do gateway para estado interno soberano."""
    return _MP_STATUS_MAP.get(mp_status_raw, "reconciliation_failed")


# ---------------------------------------------------------------------------
# Excepções de domínio
# ---------------------------------------------------------------------------
class PagamentoError(Exception):
    def __init__(self, mensagem: str = "Erro no processamento do pagamento"):
        self.mensagem = mensagem
        super().__init__(mensagem)


class PagamentoDuplicadoError(PagamentoError):
    def __init__(self):
        super().__init__("Pagamento aprovado já existe para esta chave de idempotência")


class TransicaoEstadoInvalidaError(PagamentoError):
    def __init__(self, de: str, para: str):
        super().__init__(f"Transição inválida: {de} → {para}")


# ---------------------------------------------------------------------------
# Idempotência
# ---------------------------------------------------------------------------
def _gerar_idempotency_key(user_id: int, perfil_id: str, tipo_perfil: str, contexto: str) -> str:
    """
    Gera chave de idempotência por contexto explícito de checkout.
    contexto: identificador único da sessão/invoice (ex: UUID gerado no router).
    Não usa data — a granularidade é controlada pelo chamador.
    """
    base = f"{user_id}:{tipo_perfil}:{perfil_id}:{contexto}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, base))


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------
def criar_intencao_pagamento(
    db: Session,
    user_id: int,
    perfil_id: str,
    tipo_perfil: str,
    valor: Decimal,
    contexto_idempotencia: str,
    plano_id: Optional[int] = None,
    gateway_payment_type: str = "pix",
    gateway_provider: str = "mercadopago",
) -> Pagamento:
    """
    Cria registo de Pagamento antes de qualquer chamada ao gateway.
    Princípio soberano: persistir primeiro.
    Devolve pagamento existente se ainda não aprovado (idempotente).
    """
    idempotency_key = _gerar_idempotency_key(user_id, perfil_id, tipo_perfil, contexto_idempotencia)

    existente = db.query(Pagamento).filter(
        Pagamento.idempotency_key == idempotency_key
    ).first()

    if existente:
        if existente.status == "approved":
            raise PagamentoDuplicadoError()
        return existente

    pagamento = Pagamento(
        user_id=user_id,
        plano_id=plano_id,
        idempotency_key=idempotency_key,
        valor=valor,
        status="created",
        gateway_provider=gateway_provider,
        gateway_payment_type=gateway_payment_type,
        gateway_external_reference=f"{tipo_perfil}:{perfil_id}:{contexto_idempotencia}",
        payment_method_id=gateway_payment_type,
    )
    db.add(pagamento)
    db.flush()
    return pagamento


def registar_tentativa(
    db: Session,
    pagamento: Pagamento,
    gateway_provider: str,
    payment_type: str,
    status: str,
    request_payload: Optional[dict] = None,
    response_payload: Optional[dict] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    error_origin: Optional[str] = None,
    http_status: Optional[int] = None,
    finished_at: Optional[datetime] = None,
) -> PagamentoTentativa:
    """
    Regista cada tentativa de cobrança no ledger auditável.
    Chamado antes E depois da chamada ao gateway.
    """
    tentativa = PagamentoTentativa(
        pagamento_id=pagamento.id,
        user_id=pagamento.user_id,
        gateway_provider=gateway_provider,
        payment_type=payment_type,
        status=status,
        request_payload=request_payload,
        response_payload=response_payload,
        error_code=error_code,
        error_message=error_message,
        error_origin=error_origin,
        http_status=http_status,
        started_at=datetime.utcnow(),
        finished_at=finished_at,
    )
    db.add(tentativa)
    db.flush()
    return tentativa


def transitar_estado(
    db: Session,
    pagamento: Pagamento,
    novo_status: str,
) -> Pagamento:
    """
    Transita o Pagamento para um novo estado soberano.

    Valida existência do estado E que a transição é permitida.
    """
    if novo_status not in ESTADOS_VALIDOS:
        raise TransicaoEstadoInvalidaError(pagamento.status, novo_status)

    permitidos = TRANSICOES_VALIDAS.get(pagamento.status, set())
    if novo_status not in permitidos:
        raise TransicaoEstadoInvalidaError(pagamento.status, novo_status)

    pagamento.status = novo_status

    if novo_status == "approved":
        pagamento.confirmado_em = datetime.utcnow()

    db.flush()
    return pagamento


def enriquecer_com_resposta_gateway(
    db: Session,
    pagamento: Pagamento,
    mp_payment_id: str,
    mp_status_raw: str,
    gateway_payload: dict,
    checkout_url: Optional[str] = None,
    checkout_expires_at: Optional[datetime] = None,
    boleto_url: Optional[str] = None,
    boleto_barcode: Optional[str] = None,
    qr_code: Optional[str] = None,
    qr_code_base64: Optional[str] = None,
) -> Pagamento:
    """
    Enriquece o Pagamento após resposta confirmada do gateway.
    Regista tentativa de confirmação no ledger.
    Princípio soberano: enriquecer depois.
    """
    novo_status = _mapear_status_gateway(mp_status_raw)

    pagamento.mp_payment_id = mp_payment_id
    pagamento.mp_status_raw = mp_status_raw
    pagamento.gateway_payload = gateway_payload

    if checkout_url:
        pagamento.checkout_url = checkout_url
    if checkout_expires_at:
        pagamento.checkout_expires_at = checkout_expires_at
    if boleto_url:
        pagamento.boleto_url = boleto_url
    if boleto_barcode:
        pagamento.boleto_barcode = boleto_barcode
    if qr_code:
        pagamento.qr_code = qr_code
    if qr_code_base64:
        pagamento.qr_code_base64 = qr_code_base64

    registar_tentativa(
        db=db,
        pagamento=pagamento,
        gateway_provider=pagamento.gateway_provider or "mercadopago",
        payment_type=pagamento.gateway_payment_type or "pix",
        status=novo_status,
        response_payload=gateway_payload,
        http_status=200,
        finished_at=datetime.utcnow(),
    )

    return transitar_estado(db, pagamento, novo_status)


def rejeitar_pagamento(
    db: Session,
    pagamento: Pagamento,
    error_code: str,
    error_message: str,
    error_origin: str = "gateway",
    gateway_payload: Optional[dict] = None,
    http_status: Optional[int] = None,
) -> Pagamento:
    """
    Rejeita pagamento com evidência auditável no ledger.
    """
    registar_tentativa(
        db=db,
        pagamento=pagamento,
        gateway_provider=pagamento.gateway_provider or "mercadopago",
        payment_type=pagamento.gateway_payment_type or "pix",
        status="rejected",
        response_payload=gateway_payload,
        error_code=error_code,
        error_message=error_message,
        error_origin=error_origin,
        http_status=http_status,
        finished_at=datetime.utcnow(),
    )

    return transitar_estado(db, pagamento, "rejected")
