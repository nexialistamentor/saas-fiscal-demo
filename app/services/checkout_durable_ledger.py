"""Persistencia transacional e duravel do checkout."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Empresa, Entitlement, EventoPagamento, OrdemCheckout, Pagamento


RegistroFinanceiro = Pagamento
_MENSAGEM_PUBLICA = "Nao foi possivel processar o checkout"


class CheckoutDurableLedgerError(Exception):
    """Falha publica deliberadamente opaca do ledger."""

    def __init__(self) -> None:
        super().__init__(_MENSAGEM_PUBLICA)


class CheckoutDurableLedger:
    def __init__(self, db: Session) -> None:
        if not isinstance(db, Session):
            raise CheckoutDurableLedgerError()
        self.db = db

    def criar_ou_obter_ordem(
        self,
        user_id,
        empresa_id,
        plano_id,
        valor,
        moeda,
        idempotency_key,
    ):
        self._id_positivo(user_id)
        self._id_positivo(empresa_id)
        self._id_positivo(plano_id)
        self._valor(valor)
        if moeda != "BRL":
            raise CheckoutDurableLedgerError()
        self._texto_canonico(idempotency_key, 255)

        try:
            with self.db.no_autoflush:
                empresa = self.db.get(Empresa, empresa_id)
                if empresa is None or empresa.user_id != user_id:
                    raise CheckoutDurableLedgerError()
                existente = self.db.scalar(
                    select(OrdemCheckout).where(
                        OrdemCheckout.idempotency_key == idempotency_key
                    )
                )
            if existente is not None:
                if not self._mesma_ordem(
                    existente, user_id, empresa_id, plano_id, valor, moeda
                ):
                    raise CheckoutDurableLedgerError()
                return existente

            ordem = OrdemCheckout(
                user_id=user_id,
                empresa_id=empresa_id,
                plano_id=plano_id,
                valor=valor,
                moeda=moeda,
                estado="pending",
                idempotency_key=idempotency_key,
            )
            try:
                with self.db.begin_nested():
                    self.db.add(ordem)
                    self.db.flush()
            except IntegrityError:
                with self.db.no_autoflush:
                    existente = self.db.scalar(
                        select(OrdemCheckout).where(
                            OrdemCheckout.idempotency_key == idempotency_key
                        )
                    )
                if existente is not None and self._mesma_ordem(
                    existente, user_id, empresa_id, plano_id, valor, moeda
                ):
                    return existente
                raise CheckoutDurableLedgerError() from None
            return ordem
        except CheckoutDurableLedgerError:
            raise
        except Exception:
            raise CheckoutDurableLedgerError() from None

    def registrar_preferencia(
        self,
        ordem_id,
        user_id,
        empresa_id,
        provider_order_id,
        checkout_url,
    ):
        self._id_positivo(ordem_id)
        self._id_positivo(user_id)
        self._id_positivo(empresa_id)
        self._texto_canonico(provider_order_id, 255)
        self._texto_canonico(checkout_url, 2000)
        if not checkout_url.startswith("https://"):
            raise CheckoutDurableLedgerError()

        try:
            ordem = self._ordem_do_proprietario(ordem_id, user_id, empresa_id)
            if ordem.estado != "pending":
                raise CheckoutDurableLedgerError()
            if ordem.provider_order_id is not None:
                if (
                    ordem.provider_order_id == provider_order_id
                    and ordem.checkout_url == checkout_url
                ):
                    return ordem
                raise CheckoutDurableLedgerError()
            with self.db.no_autoflush:
                colisao = self.db.scalar(
                    select(OrdemCheckout.id).where(
                        OrdemCheckout.provider_order_id == provider_order_id
                    )
                )
            if colisao is not None:
                raise CheckoutDurableLedgerError()
            try:
                with self.db.begin_nested():
                    ordem.provider_order_id = provider_order_id
                    ordem.checkout_url = checkout_url
                    self.db.flush()
            except Exception:
                raise CheckoutDurableLedgerError() from None
            return ordem
        except CheckoutDurableLedgerError:
            raise
        except Exception:
            raise CheckoutDurableLedgerError() from None

    def consultar_ordem(self, ordem_id, user_id, empresa_id):
        self._id_positivo(ordem_id)
        self._id_positivo(user_id)
        self._id_positivo(empresa_id)
        try:
            return self._ordem_do_proprietario(ordem_id, user_id, empresa_id)
        except CheckoutDurableLedgerError:
            raise
        except Exception:
            raise CheckoutDurableLedgerError() from None

    def obter_checkout_url(self, ordem_id, user_id, empresa_id):
        ordem = self.consultar_ordem(ordem_id, user_id, empresa_id)
        if ordem.estado != "pending" or not ordem.checkout_url:
            raise CheckoutDurableLedgerError()
        return ordem.checkout_url

    def confirmar_pagamento_aprovado(
        self,
        ordem_id,
        user_id,
        empresa_id,
        notification_id,
        payment_id,
    ):
        self._id_positivo(ordem_id)
        self._id_positivo(user_id)
        self._id_positivo(empresa_id)
        self._identificador_numerico(notification_id)
        self._identificador_numerico(payment_id)

        try:
            ordem = self._ordem_do_proprietario(ordem_id, user_id, empresa_id)
            with self.db.no_autoflush:
                evento_notification = self.db.scalar(
                    select(EventoPagamento).where(
                        EventoPagamento.notification_id == notification_id
                    )
                )
                ordem_payment = self.db.scalar(
                    select(OrdemCheckout).where(
                        OrdemCheckout.payment_id == payment_id
                    )
                )

            if evento_notification is not None:
                if (
                    evento_notification.ordem_id == ordem.id
                    and evento_notification.payment_id == payment_id
                    and ordem.estado == "paid"
                    and ordem.payment_id == payment_id
                ):
                    return ordem
                raise CheckoutDurableLedgerError()

            if ordem_payment is not None:
                if (
                    ordem_payment.id != ordem.id
                    or ordem.estado != "paid"
                    or ordem.payment_id != payment_id
                ):
                    raise CheckoutDurableLedgerError()
                try:
                    with self.db.begin_nested():
                        self.db.add(
                            EventoPagamento(
                                ordem_id=ordem.id,
                                notification_id=notification_id,
                                payment_id=payment_id,
                            )
                        )
                        self.db.flush()
                except Exception:
                    raise CheckoutDurableLedgerError() from None
                return ordem

            if ordem.estado != "pending" or ordem.payment_id is not None:
                raise CheckoutDurableLedgerError()

            try:
                with self.db.begin_nested():
                    ordem.estado = "paid"
                    ordem.payment_id = payment_id
                    self.db.add(
                        EventoPagamento(
                            ordem_id=ordem.id,
                            notification_id=notification_id,
                            payment_id=payment_id,
                        )
                    )
                    self.db.add(
                        RegistroFinanceiro(
                            ordem_checkout_id=ordem.id,
                            user_id=ordem.user_id,
                            plano_id=ordem.plano_id,
                            idempotency_key=f"checkout-ledger:{ordem.id}",
                            valor=ordem.valor,
                            status="approved",
                            mp_payment_id=payment_id,
                            mp_status_raw="approved",
                            payment_method_id="unknown",
                            gateway_provider="mercadopago",
                        )
                    )
                    self.db.add(
                        Entitlement(
                            ordem_id=ordem.id,
                            user_id=ordem.user_id,
                            empresa_id=ordem.empresa_id,
                            plano_id=ordem.plano_id,
                            estado="active",
                        )
                    )
                    self.db.flush()
            except Exception:
                raise CheckoutDurableLedgerError() from None
            return ordem
        except CheckoutDurableLedgerError:
            raise
        except (IntegrityError, SQLAlchemyError, Exception):
            raise CheckoutDurableLedgerError() from None

    def _ordem_do_proprietario(self, ordem_id, user_id, empresa_id):
        with self.db.no_autoflush:
            ordem = self.db.get(OrdemCheckout, ordem_id)
        if (
            ordem is None
            or ordem.user_id != user_id
            or ordem.empresa_id != empresa_id
        ):
            raise CheckoutDurableLedgerError()
        return ordem

    @staticmethod
    def _mesma_ordem(ordem, user_id, empresa_id, plano_id, valor, moeda):
        return (
            ordem.user_id == user_id
            and ordem.empresa_id == empresa_id
            and ordem.plano_id == plano_id
            and ordem.valor == valor
            and ordem.moeda == moeda
        )

    @staticmethod
    def _id_positivo(valor):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
            raise CheckoutDurableLedgerError()

    @staticmethod
    def _valor(valor):
        if (
            not isinstance(valor, Decimal)
            or not valor.is_finite()
            or valor <= Decimal("0")
        ):
            raise CheckoutDurableLedgerError()

    @staticmethod
    def _texto_canonico(valor, limite):
        if (
            not isinstance(valor, str)
            or not valor
            or valor != valor.strip()
            or len(valor) > limite
            or "\r" in valor
            or "\n" in valor
        ):
            raise CheckoutDurableLedgerError()

    @classmethod
    def _identificador_numerico(cls, valor):
        cls._texto_canonico(valor, 255)
        if not valor.isascii() or not valor.isdigit() or valor[0] == "0":
            raise CheckoutDurableLedgerError()


__all__ = [
    "Base",
    "CheckoutDurableLedger",
    "CheckoutDurableLedgerError",
    "Entitlement",
    "EventoPagamento",
    "OrdemCheckout",
    "RegistroFinanceiro",
]
