"""Orquestracao offline do webhook do Mercado Pago."""


class MercadoPagoWebhookOrchestrationError(Exception):
    """Erro publico e sanitizado da orquestracao do webhook."""

    def __init__(self, *_args, **_kwargs):
        super().__init__("Falha ao processar webhook")


class MercadoPagoWebhookOrchestrator:
    """Coordena autenticacao, resolucao e confirmacao de um pagamento."""

    def __init__(
        self,
        verificador_assinatura,
        resolvedor_pagamento,
        checkout_core,
    ):
        try:
            verificar = verificador_assinatura.verificar
            resolver_pagamento = resolvedor_pagamento.resolver_pagamento
            confirmar_pagamento = checkout_core.confirmar_pagamento_autorizado
        except Exception:
            raise MercadoPagoWebhookOrchestrationError() from None

        if not all(
            callable(metodo)
            for metodo in (
                verificar,
                resolver_pagamento,
                confirmar_pagamento,
            )
        ):
            raise MercadoPagoWebhookOrchestrationError()

        self._verificar = verificar
        self._resolver_pagamento = resolver_pagamento
        self._confirmar_pagamento = confirmar_pagamento

    def processar(self, evento, assinatura):
        if type(evento) is not dict or set(evento) != {"event_id", "request_id"}:
            raise MercadoPagoWebhookOrchestrationError()

        event_id = evento["event_id"]
        request_id = evento["request_id"]
        if not self._identificador_valido(event_id) or not self._identificador_valido(
            request_id
        ):
            raise MercadoPagoWebhookOrchestrationError()

        try:
            autenticado = self._verificar(evento, assinatura)
        except Exception:
            raise MercadoPagoWebhookOrchestrationError() from None
        if autenticado is not True:
            raise MercadoPagoWebhookOrchestrationError()

        try:
            resolucao = self._resolver_pagamento(event_id, request_id)
        except Exception:
            raise MercadoPagoWebhookOrchestrationError() from None

        if resolucao is None:
            return None
        if type(resolucao) is not dict or set(resolucao) != {"ordem_id", "event_id"}:
            raise MercadoPagoWebhookOrchestrationError()

        ordem_id = resolucao["ordem_id"]
        if (
            isinstance(ordem_id, bool)
            or not isinstance(ordem_id, int)
            or ordem_id <= 0
            or resolucao["event_id"] != request_id
        ):
            raise MercadoPagoWebhookOrchestrationError()

        try:
            return self._confirmar_pagamento(ordem_id, request_id)
        except Exception:
            raise MercadoPagoWebhookOrchestrationError() from None

    @staticmethod
    def _identificador_valido(valor):
        return (
            isinstance(valor, str)
            and bool(valor)
            and not any(caractere.isspace() for caractere in valor)
        )
