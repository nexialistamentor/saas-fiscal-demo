"""Autenticador offline de webhooks do Mercado Pago."""


class MercadoPagoWebhookError(Exception):
    """Erro público e sanitizado do autenticador de webhook."""


class MercadoPagoWebhookSignatureVerifier:
    """Valida assinaturas por meio de um validador injetado."""

    def __init__(self, validador, secret):
        if (
            not callable(validador)
            or not isinstance(secret, str)
            or not secret.strip()
        ):
            raise MercadoPagoWebhookError("Configuração inválida")

        self._validador = validador
        self._secret = secret

    def verificar(self, evento, assinatura):
        if not isinstance(evento, dict):
            return False

        event_id = evento.get("event_id")
        request_id = evento.get("request_id")
        if (
            not isinstance(event_id, str)
            or not event_id.strip()
            or not isinstance(request_id, str)
            or not request_id.strip()
            or not isinstance(assinatura, str)
            or not assinatura.strip()
            or "\r" in assinatura
            or "\n" in assinatura
        ):
            return False

        try:
            resultado = self._validador(
                x_signature=assinatura,
                x_request_id=request_id,
                data_id=event_id,
                secret=self._secret,
            )
        except Exception:
            return False
        return resultado is True
