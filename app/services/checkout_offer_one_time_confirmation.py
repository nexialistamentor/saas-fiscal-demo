"""Confirmacao atomica de pagamentos de ofertas avulsas.

O snapshot persistido em ``OrdemCheckout`` e a unica autoridade comercial
usada por este servico.  Em particular, a confirmacao e o replay nao leem o
catalogo mutavel de ofertas.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import re
from urllib.parse import urlsplit

from sqlalchemy import select

from app import models


_PUBLIC_ERROR = "confirmacao recusada"
_IDENTITY = re.compile(r"[1-9][0-9]*\Z")
_CANONICAL = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*\Z")


class CheckoutOfferOneTimeConfirmationError(Exception):
    """Erro publico opaco de confirmacao."""


@dataclass(frozen=True)
class _ConfirmationProjection:
    ordem_id: int
    user_id: int
    empresa_id: int
    estado: str
    payment_id: str
    grant_id: int
    usage_unit: str
    usage_limit: int
    usage_consumed: int
    capabilities: tuple


def _fail():
    raise CheckoutOfferOneTimeConfirmationError(_PUBLIC_ERROR)


def _positive_int(value):
    return type(value) is int and value > 0


def _identity(value):
    return type(value) is str and _IDENTITY.fullmatch(value) is not None


def _canonical(value):
    return type(value) is str and _CANONICAL.fullmatch(value) is not None


def _safe_rollback(session):
    if session is not None:
        try:
            session.rollback()
        except Exception:
            pass


def _safe_close(session):
    if session is not None:
        try:
            session.close()
        except Exception:
            pass


def _valid_checkout_url(value):
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or "\r" in value
        or "\n" in value
    ):
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and bool(parsed.netloc)
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.fragment
        )
    except (TypeError, ValueError):
        return False


class CheckoutOfferOneTimeConfirmer:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def confirmar_pagamento_autorizado(
        self, ordem_id, notification_id, payment_id, valor, moeda
    ):
        session = None
        try:
            session = self.session_factory()
            self._validate_inputs(
                ordem_id, notification_id, payment_id, valor, moeda
            )
            ordem = session.scalar(
                select(models.OrdemCheckout)
                .where(models.OrdemCheckout.id == ordem_id)
                .with_for_update()
            )
            if ordem is None:
                _fail()
            capabilities = self._validate_order(session, ordem, valor, moeda)
            self._observe_provider_payment(
                session, ordem, notification_id, payment_id
            )

            if ordem.estado == "paid":
                _, _, grant = self._validate_paid_commercial_state(
                    session, ordem, capabilities
                )
                result = self._projection(ordem, grant, capabilities)
                session.commit()
                return result

            self._reject_collisions(session, notification_id, payment_id)
            ordem.estado = "paid"
            ordem.payment_id = payment_id

            event = models.EventoPagamento(
                ordem_id=ordem.id,
                notification_id=notification_id,
                payment_id=payment_id,
            )
            payment = models.Pagamento(
                ordem_checkout_id=ordem.id,
                user_id=ordem.user_id,
                plano_id=None,
                idempotency_key=notification_id,
                valor=ordem.valor,
                mp_payment_id=payment_id,
                status="approved",
                confirmado_em=datetime.utcnow(),
            )
            grant = models.CheckoutOfferGrant(
                ordem_id=ordem.id,
                usage_unit=ordem.usage_unit,
                usage_limit=ordem.usage_limit,
                usage_consumed=0,
                estado="active",
            )
            grant.capabilities = [
                models.CheckoutOfferGrantCapability(codigo=code)
                for code in capabilities
            ]
            session.add_all((event, payment, grant))
            session.flush()
            result = self._projection(ordem, grant, capabilities)
            session.commit()
            return result
        except CheckoutOfferOneTimeConfirmationError:
            _safe_rollback(session)
            raise
        except Exception:
            _safe_rollback(session)
            raise CheckoutOfferOneTimeConfirmationError(_PUBLIC_ERROR) from None
        finally:
            _safe_close(session)

    @staticmethod
    def _validate_inputs(ordem_id, notification_id, payment_id, valor, moeda):
        if not _positive_int(ordem_id):
            _fail()
        if not _identity(notification_id) or not _identity(payment_id):
            _fail()
        if type(valor) is not Decimal:
            _fail()
        if not valor.is_finite() or valor <= 0 or valor.as_tuple().exponent != -2:
            _fail()
        if type(moeda) is not str or moeda != "BRL":
            _fail()

    @staticmethod
    def _validate_order(session, ordem, valor, moeda):
        if ordem.estado not in ("pending", "paid"):
            _fail()
        if not all(
            _positive_int(value)
            for value in (
                ordem.id,
                ordem.user_id,
                ordem.empresa_id,
                ordem.offer_id,
                ordem.contract_version,
                ordem.subject_id,
                ordem.usage_limit,
            )
        ):
            _fail()
        if ordem.plano_id is not None:
            _fail()
        if not _canonical(ordem.offer_code) or not _canonical(ordem.vertical):
            _fail()
        if ordem.commercial_model != "one_time":
            _fail()
        if ordem.subject_type != "company" or ordem.subject_id != ordem.empresa_id:
            _fail()
        if ordem.billing_period is not None or not _canonical(ordem.usage_unit):
            _fail()
        if ordem.valor != valor or ordem.moeda != moeda or ordem.moeda != "BRL":
            _fail()
        if (
            type(ordem.provider_order_id) is not str
            or not ordem.provider_order_id
            or ordem.provider_order_id != ordem.provider_order_id.strip()
            or "\r" in ordem.provider_order_id
            or "\n" in ordem.provider_order_id
            or not _valid_checkout_url(ordem.checkout_url)
        ):
            _fail()
        empresa = session.get(models.Empresa, ordem.empresa_id)
        if empresa is None or empresa.user_id != ordem.user_id:
            _fail()
        capabilities = tuple(item.codigo for item in ordem.capabilities)
        if not capabilities or any(not _canonical(code) for code in capabilities):
            _fail()
        if len({code.lower() for code in capabilities}) != len(capabilities):
            _fail()
        return capabilities

    @staticmethod
    def _reject_collisions(session, notification_id, payment_id):
        if session.scalar(
            select(models.EventoPagamento.id).where(
                models.EventoPagamento.notification_id == notification_id
            )
        ) is not None:
            _fail()
        if session.scalar(
            select(models.EventoPagamento.id).where(
                models.EventoPagamento.payment_id == payment_id
            )
        ) is not None:
            _fail()
        if session.scalar(
            select(models.Pagamento.id).where(
                models.Pagamento.mp_payment_id == payment_id
            )
        ) is not None:
            _fail()

    @staticmethod
    def _observe_provider_payment(
        session, ordem, notification_id, payment_id
    ):
        observation = session.scalar(
            select(models.MercadoPagoPaymentObservation).where(
                models.MercadoPagoPaymentObservation.notification_id
                == notification_id
            )
        )
        if observation is not None:
            if (
                observation.ordem_id != ordem.id
                or observation.payment_id != payment_id
                or observation.status != "approved"
                or observation.valor != ordem.valor
                or observation.moeda != "BRL"
            ):
                _fail()

        event_by_notification = session.scalar(
            select(models.EventoPagamento).where(
                models.EventoPagamento.notification_id == notification_id
            )
        )
        if event_by_notification is not None and (
            event_by_notification.ordem_id != ordem.id
            or event_by_notification.payment_id != payment_id
        ):
            _fail()

        event_orders_by_payment = session.scalars(
            select(models.EventoPagamento.ordem_id).where(
                models.EventoPagamento.payment_id == payment_id
            )
        ).all()
        if any(event_ordem_id != ordem.id for event_ordem_id in event_orders_by_payment):
            _fail()

        payment_orders = session.scalars(
            select(models.Pagamento.ordem_checkout_id).where(
                models.Pagamento.mp_payment_id == payment_id
            )
        ).all()
        if any(payment_ordem_id != ordem.id for payment_ordem_id in payment_orders):
            _fail()

        payment_observations = session.scalars(
            select(models.MercadoPagoPaymentObservation).where(
                models.MercadoPagoPaymentObservation.payment_id == payment_id
            )
        ).all()
        if any(
            existing.ordem_id != ordem.id
            or existing.status != "approved"
            or existing.valor != ordem.valor
            or existing.moeda != "BRL"
            for existing in payment_observations
        ):
            _fail()

        if observation is not None:
            return observation

        observation = models.MercadoPagoPaymentObservation(
            ordem_id=ordem.id,
            notification_id=notification_id,
            payment_id=payment_id,
            status="approved",
            valor=ordem.valor,
            moeda="BRL",
        )
        session.add(observation)
        return observation

    @classmethod
    def _validate_paid_commercial_state(cls, session, ordem, capabilities):
        if not _identity(ordem.payment_id):
            _fail()
        events = session.scalars(
            select(models.EventoPagamento).where(
                models.EventoPagamento.ordem_id == ordem.id
            )
        ).all()
        payments = session.scalars(
            select(models.Pagamento).where(
                models.Pagamento.ordem_checkout_id == ordem.id
            )
        ).all()
        grants = session.scalars(
            select(models.CheckoutOfferGrant).where(
                models.CheckoutOfferGrant.ordem_id == ordem.id
            )
        ).all()
        if len(events) != 1 or len(payments) != 1 or len(grants) != 1:
            _fail()
        event, payment, grant = events[0], payments[0], grants[0]
        if (
            event.ordem_id != ordem.id
            or not _identity(event.notification_id)
            or not _identity(event.payment_id)
            or event.payment_id != ordem.payment_id
            or payment.ordem_checkout_id != ordem.id
            or payment.user_id != ordem.user_id
            or payment.plano_id is not None
            or payment.valor != ordem.valor
            or ordem.moeda != "BRL"
            or payment.mp_payment_id != ordem.payment_id
            or payment.status != "approved"
            or payment.confirmado_em is None
            or grant.ordem_id != ordem.id
            or grant.usage_unit != ordem.usage_unit
            or grant.usage_limit != ordem.usage_limit
            or type(grant.usage_consumed) is not int
            or not 0 <= grant.usage_consumed <= grant.usage_limit
            or grant.estado not in ("active", "exhausted", "revoked")
            or (
                grant.estado == "active"
                and grant.usage_consumed == grant.usage_limit
            )
            or (
                grant.estado == "exhausted"
                and grant.usage_consumed != grant.usage_limit
            )
        ):
            _fail()
        grant_capabilities = tuple(item.codigo for item in grant.capabilities)
        if grant_capabilities != capabilities:
            _fail()
        return event, payment, grant

    @classmethod
    def _replay(cls, session, ordem, notification_id, payment_id, capabilities):
        if ordem.payment_id != payment_id:
            _fail()
        event, _, grant = cls._validate_paid_commercial_state(
            session, ordem, capabilities
        )
        if (
            event.notification_id != notification_id
            or event.payment_id != payment_id
        ):
            _fail()
        return cls._projection(ordem, grant, capabilities)

    @staticmethod
    def _projection(ordem, grant, capabilities):
        return _ConfirmationProjection(
            ordem_id=ordem.id,
            user_id=ordem.user_id,
            empresa_id=ordem.empresa_id,
            estado="paid",
            payment_id=ordem.payment_id,
            grant_id=grant.id,
            usage_unit=grant.usage_unit,
            usage_limit=grant.usage_limit,
            usage_consumed=grant.usage_consumed,
            capabilities=tuple(capabilities),
        )
