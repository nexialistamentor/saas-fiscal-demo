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
        if type(evento) is not dict or set(evento) != {
            "notification_id",
            "payment_id",
            "request_id",
        }:
            return False

        notification_id = evento["notification_id"]
        payment_id = evento["payment_id"]
        request_id = evento["request_id"]
        if (
            not self._decimal_ascii_canonico_positivo(notification_id)
            or not self._decimal_ascii_canonico_positivo(payment_id)
            or not isinstance(request_id, str)
            or not request_id.strip()
            or any(caractere.isspace() for caractere in request_id)
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
                data_id=payment_id,
                secret=self._secret,
            )
        except Exception:
            return False
        return resultado is True

    @staticmethod
    def _decimal_ascii_canonico_positivo(valor):
        return (
            isinstance(valor, str)
            and bool(valor)
            and valor.isascii()
            and valor.isdecimal()
            and valor[0] != "0"
        )
