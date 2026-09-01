"""Roteamento read-only da confirmacao pelo snapshot comercial duravel."""

import re

from app.models import OrdemCheckout


_PUBLIC_ERROR = "operacao recusada"
_CANONICAL = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*\Z", re.ASCII)


class CheckoutDurableWebhookConfirmationRoutingError(Exception):
    """Erro publico opaco do roteador de confirmacao."""


def _fail():
    raise CheckoutDurableWebhookConfirmationRoutingError(_PUBLIC_ERROR)


def _positive_int(value):
    return type(value) is int and value > 0


def _canonical(value):
    return type(value) is str and _CANONICAL.fullmatch(value) is not None


class CheckoutDurableWebhookConfirmationRouter:
    def __init__(self, session_factory, legacy_confirmer, one_time_confirmer):
        try:
            legacy_method = legacy_confirmer.confirmar_pagamento_autorizado
            one_time_method = one_time_confirmer.confirmar_pagamento_autorizado
            if not all(
                callable(value)
                for value in (session_factory, legacy_method, one_time_method)
            ):
                _fail()
        except CheckoutDurableWebhookConfirmationRoutingError:
            raise
        except Exception:
            _fail()

        self._session_factory = session_factory
        self._legacy_method = legacy_method
        self._one_time_method = one_time_method

    def confirmar_pagamento_autorizado(
        self, ordem_id, notification_id, payment_id, valor, moeda
    ):
        if not _positive_int(ordem_id):
            _fail()

        session = None
        try:
            session = self._session_factory()
            ordem = session.get(OrdemCheckout, ordem_id)
            method = self._route(ordem)
        except Exception:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass
            raise CheckoutDurableWebhookConfirmationRoutingError(
                _PUBLIC_ERROR
            ) from None

        try:
            session.close()
        except Exception:
            raise CheckoutDurableWebhookConfirmationRoutingError(
                _PUBLIC_ERROR
            ) from None

        try:
            return method(ordem_id, notification_id, payment_id, valor, moeda)
        except Exception:
            raise CheckoutDurableWebhookConfirmationRoutingError(
                _PUBLIC_ERROR
            ) from None

    def _route(self, ordem):
        if ordem is None:
            _fail()

        capabilities = tuple(item.codigo for item in ordem.capabilities)
        if self._is_legacy(ordem, capabilities):
            return self._legacy_method
        if self._is_one_time(ordem, capabilities):
            return self._one_time_method
        _fail()

    @staticmethod
    def _is_legacy(ordem, capabilities):
        return (
            _positive_int(ordem.plano_id)
            and ordem.offer_id is None
            and ordem.offer_code is None
            and ordem.contract_version is None
            and ordem.vertical is None
            and ordem.commercial_model is None
            and ordem.subject_type is None
            and ordem.subject_id is None
            and ordem.billing_period is None
            and ordem.usage_unit is None
            and ordem.usage_limit is None
            and not capabilities
        )

    @staticmethod
    def _is_one_time(ordem, capabilities):
        return (
            ordem.plano_id is None
            and _positive_int(ordem.offer_id)
            and _canonical(ordem.offer_code)
            and _positive_int(ordem.contract_version)
            and _canonical(ordem.vertical)
            and ordem.commercial_model == "one_time"
            and ordem.subject_type == "company"
            and _positive_int(ordem.subject_id)
            and ordem.subject_id == ordem.empresa_id
            and _positive_int(ordem.user_id)
            and _positive_int(ordem.empresa_id)
            and ordem.billing_period is None
            and _canonical(ordem.usage_unit)
            and _positive_int(ordem.usage_limit)
            and bool(capabilities)
            and all(_canonical(value) for value in capabilities)
            and len(capabilities) == len(set(capabilities))
        )
