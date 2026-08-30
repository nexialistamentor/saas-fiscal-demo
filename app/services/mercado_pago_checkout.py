"""Adaptador offline para o Mercado Pago Checkout Pro."""

from decimal import Decimal
from urllib.parse import urlparse


class MercadoPagoCheckoutError(Exception):
    """Erro público e sanitizado do adaptador Mercado Pago."""


class MercadoPagoCheckoutGateway:
    """Cria preferências de pagamento por meio de um cliente injetado."""

    _BACK_URL_KEYS = {"success", "failure", "pending"}
    _CHECKOUT_DOMAIN = "mercadopago.com.br"

    def __init__(self, cliente_preferencias, notification_url, back_urls):
        criar_preferencia = getattr(
            cliente_preferencias, "criar_preferencia", None
        )
        if not callable(criar_preferencia):
            raise MercadoPagoCheckoutError("Configuração inválida")
        if not self._url_https_absoluta(notification_url):
            raise MercadoPagoCheckoutError("Configuração inválida")
        if (
            not isinstance(back_urls, dict)
            or set(back_urls) != self._BACK_URL_KEYS
            or any(
                not self._url_https_absoluta(back_urls[chave])
                for chave in self._BACK_URL_KEYS
            )
        ):
            raise MercadoPagoCheckoutError("Configuração inválida")

        self._cliente_preferencias = cliente_preferencias
        self._notification_url = notification_url
        self._back_urls = {
            chave: back_urls[chave]
            for chave in ("success", "failure", "pending")
        }

    def criar_cobranca(
        self,
        ordem_id,
        user_id,
        empresa_id,
        plano_id,
        valor,
        moeda,
        idempotency_key,
    ):
        for identificador in (ordem_id, user_id, empresa_id, plano_id):
            if (
                isinstance(identificador, bool)
                or not isinstance(identificador, int)
                or identificador <= 0
            ):
                raise MercadoPagoCheckoutError("Dados inválidos")
        if (
            not isinstance(valor, Decimal)
            or not valor.is_finite()
            or valor <= Decimal("0")
        ):
            raise MercadoPagoCheckoutError("Dados inválidos")
        if moeda != "BRL":
            raise MercadoPagoCheckoutError("Dados inválidos")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise MercadoPagoCheckoutError("Dados inválidos")

        payload = {
            "external_reference": str(ordem_id),
            "items": [
                {
                    "id": str(plano_id),
                    "quantity": 1,
                    "unit_price": valor,
                    "currency_id": "BRL",
                }
            ],
            "notification_url": self._notification_url,
            "back_urls": dict(self._back_urls),
        }
        try:
            resposta = self._cliente_preferencias.criar_preferencia(
                payload=payload,
                idempotency_key=idempotency_key,
            )
        except Exception:
            raise MercadoPagoCheckoutError("Falha no provedor") from None

        if not isinstance(resposta, dict):
            raise MercadoPagoCheckoutError("Resposta inválida")
        provider_order_id = resposta.get("provider_order_id")
        checkout_url = resposta.get("checkout_url")
        if (
            not isinstance(provider_order_id, str)
            or not provider_order_id.strip()
            or not self._checkout_url_valida(checkout_url)
        ):
            raise MercadoPagoCheckoutError("Resposta inválida")
        return {
            "provider_order_id": provider_order_id,
            "checkout_url": checkout_url,
        }

    @staticmethod
    def _url_https_absoluta(url):
        if not isinstance(url, str) or not url:
            return False
        try:
            parsed = urlparse(url)
            return (
                parsed.scheme == "https"
                and bool(parsed.netloc)
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
            )
        except ValueError:
            return False

    @classmethod
    def _checkout_url_valida(cls, url):
        if not cls._url_https_absoluta(url):
            return False
        try:
            hostname = urlparse(url).hostname
        except ValueError:
            return False
        return hostname == cls._CHECKOUT_DOMAIN or hostname.endswith(
            "." + cls._CHECKOUT_DOMAIN
        )
