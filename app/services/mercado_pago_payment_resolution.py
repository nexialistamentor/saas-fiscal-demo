"""Resolvedor offline de pagamentos do Mercado Pago."""


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

    def resolver_pagamento(self, data_id, request_id):
        if not self._decimal_ascii_canonico_positivo(data_id):
            raise MercadoPagoPaymentResolutionError()
        if (
            not isinstance(request_id, str)
            or not request_id
            or any(caractere.isspace() for caractere in request_id)
        ):
            raise MercadoPagoPaymentResolutionError()

        try:
            resposta = self._obter_pagamento(payment_id=data_id)
        except Exception:
            raise MercadoPagoPaymentResolutionError() from None

        if not isinstance(resposta, dict):
            raise MercadoPagoPaymentResolutionError()

        payment_id = resposta.get("id")
        if isinstance(payment_id, bool):
            raise MercadoPagoPaymentResolutionError()
        if isinstance(payment_id, int):
            id_corresponde = payment_id > 0 and str(payment_id) == data_id
        else:
            id_corresponde = (
                self._decimal_ascii_canonico_positivo(payment_id)
                and payment_id == data_id
            )
        if not id_corresponde:
            raise MercadoPagoPaymentResolutionError()

        external_reference = resposta.get("external_reference")
        if not self._decimal_ascii_canonico_positivo(external_reference):
            raise MercadoPagoPaymentResolutionError()
        ordem_id = int(external_reference)

        status = resposta.get("status")
        if status == "approved":
            return {"ordem_id": ordem_id, "event_id": request_id}
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
