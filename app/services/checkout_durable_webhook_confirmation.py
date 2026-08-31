"""Confirmacao transacional de pagamentos autenticados no ledger duravel."""

from dataclasses import dataclass
from decimal import Decimal

from app.models import OrdemCheckout
from app.services.checkout_durable_ledger import CheckoutDurableLedger


_MENSAGEM_PUBLICA = "Nao foi possivel confirmar o pagamento"


class CheckoutDurableWebhookConfirmationError(Exception):
    """Falha publica e deliberadamente opaca da confirmacao duravel."""

    def __init__(self, *_args, **_kwargs):
        super().__init__(_MENSAGEM_PUBLICA)


@dataclass(frozen=True)
class _ConfirmacaoPagamento:
    ordem_id: int
    user_id: int
    empresa_id: int
    estado: str
    payment_id: str


class CheckoutDurableWebhookConfirmer:
    """Executa a confirmacao numa unidade de trabalho propria."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    def confirmar_pagamento_autorizado(
        self, ordem_id, notification_id, payment_id, valor, moeda
    ):
        session = None
        try:
            session = self._session_factory()
            if (
                isinstance(ordem_id, bool)
                or not isinstance(ordem_id, int)
                or ordem_id <= 0
                or not self._decimal_ascii_canonico_positivo(notification_id)
                or not self._decimal_ascii_canonico_positivo(payment_id)
                or type(valor) is not Decimal
                or not valor.is_finite()
                or valor <= Decimal(0)
                or valor.as_tuple().exponent != -2
                or moeda != "BRL"
            ):
                raise CheckoutDurableWebhookConfirmationError()

            ordem = session.get(OrdemCheckout, ordem_id)
            if ordem is None:
                raise CheckoutDurableWebhookConfirmationError()
            if valor != ordem.valor or moeda != ordem.moeda:
                raise CheckoutDurableWebhookConfirmationError()

            confirmada = CheckoutDurableLedger(
                session
            ).confirmar_pagamento_aprovado(
                ordem_id=ordem_id,
                user_id=ordem.user_id,
                empresa_id=ordem.empresa_id,
                notification_id=notification_id,
                payment_id=payment_id,
            )
            projecao = _ConfirmacaoPagamento(
                ordem_id=confirmada.id,
                user_id=confirmada.user_id,
                empresa_id=confirmada.empresa_id,
                estado=confirmada.estado,
                payment_id=confirmada.payment_id,
            )
            session.commit()
            session.close()
            return projecao
        except Exception:
            if session is not None:
                try:
                    session.rollback()
                except Exception:
                    pass
                try:
                    session.close()
                except Exception:
                    pass
            raise CheckoutDurableWebhookConfirmationError() from None

    @staticmethod
    def _decimal_ascii_canonico_positivo(valor):
        return (
            isinstance(valor, str)
            and bool(valor)
            and valor.isascii()
            and valor.isdecimal()
            and valor[0] != "0"
        )
