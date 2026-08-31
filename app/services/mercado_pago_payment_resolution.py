"""Resolvedor offline de pagamentos do Mercado Pago."""

from decimal import Decimal, DecimalException


class MercadoPagoPaymentResolutionError(Exception):
    """Erro publico e sanitizado da resolucao de pagamentos."""

    def __init__(self, *_args, **_kwargs):
        super().__init__("Falha ao resolver pagamento")


class MercadoPagoPaymentResolver:
    """Resolve a ordem associada a um pagamento consultado no provedor."""

    _ESTADOS_NAO_APROVADOS = {
        "pending",
        "authorized",
        "in_process",
        "in_mediation",
        "rejected",
        "cancelled",
        "refunded",
        "charged_back",
    }

    def __init__(self, cliente_pagamentos):
        try:
            obter_pagamento = cliente_pagamentos.obter_pagamento
        except Exception:
            raise MercadoPagoPaymentResolutionError() from None
        if not callable(obter_pagamento):
            raise MercadoPagoPaymentResolutionError()

        self._obter_pagamento = obter_pagamento

    def resolver_pagamento(self, payment_id, notification_id):
        if not self._decimal_ascii_canonico_positivo(payment_id):
            raise MercadoPagoPaymentResolutionError()
        if not self._decimal_ascii_canonico_positivo(notification_id):
            raise MercadoPagoPaymentResolutionError()

        try:
            resposta = self._obter_pagamento(payment_id=payment_id)
        except Exception:
            raise MercadoPagoPaymentResolutionError() from None

        if not isinstance(resposta, dict):
            raise MercadoPagoPaymentResolutionError()

        resposta_payment_id = resposta.get("id")
        if isinstance(resposta_payment_id, bool):
            raise MercadoPagoPaymentResolutionError()
        if isinstance(resposta_payment_id, int):
            id_corresponde = (
                resposta_payment_id > 0
                and str(resposta_payment_id) == payment_id
            )
        else:
            id_corresponde = (
                self._decimal_ascii_canonico_positivo(resposta_payment_id)
                and resposta_payment_id == payment_id
            )
        if not id_corresponde:
            raise MercadoPagoPaymentResolutionError()

        external_reference = resposta.get("external_reference")
        if not self._decimal_ascii_canonico_positivo(external_reference):
            raise MercadoPagoPaymentResolutionError()
        ordem_id = int(external_reference)

        status = resposta.get("status")
        if status == "approved":
            valor = self._normalizar_valor_aprovado(
                resposta.get("transaction_amount")
            )
            if resposta.get("currency_id") != "BRL":
                raise MercadoPagoPaymentResolutionError()
            return {
                "ordem_id": ordem_id,
                "event_id": notification_id,
                "valor": valor,
                "moeda": "BRL",
            }
        if status in self._ESTADOS_NAO_APROVADOS:
            return None
        raise MercadoPagoPaymentResolutionError()

    @staticmethod
    def _decimal_ascii_canonico_positivo(valor):
        return (
            isinstance(valor, str)
            and bool(valor)
            and valor.isascii()
            and valor.isdecimal()
            and valor[0] != "0"
        )

    @staticmethod
    def _normalizar_valor_aprovado(valor):
        if isinstance(valor, bool) or not isinstance(
            valor, (str, int, float, Decimal)
        ):
            raise MercadoPagoPaymentResolutionError()

        try:
            valor_decimal = Decimal(str(valor))
            if not valor_decimal.is_finite() or valor_decimal <= 0:
                raise MercadoPagoPaymentResolutionError()
            valor_canonico = valor_decimal.quantize(Decimal("0.01"))
        except MercadoPagoPaymentResolutionError:
            raise
        except (DecimalException, TypeError, ValueError):
            raise MercadoPagoPaymentResolutionError() from None

        if valor_canonico != valor_decimal:
            raise MercadoPagoPaymentResolutionError()
        return valor_canonico
