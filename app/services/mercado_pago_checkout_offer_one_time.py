"""Adaptador offline do Mercado Pago para ofertas de pagamento unico."""

from decimal import Decimal
import re
from urllib.parse import urlsplit


_MENSAGEM_PUBLICA = "Nao foi possivel criar a cobranca"
_OFFER_CODE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+", re.ASCII)


class MercadoPagoCheckoutOfferOneTimeError(Exception):
    """Falha publica deliberadamente opaca do adaptador."""

    def __init__(self) -> None:
        super().__init__(_MENSAGEM_PUBLICA)


class MercadoPagoCheckoutOfferOneTimeGateway:
    """Cria preferencias one-time por meio de um cliente injetado."""

    _BACK_URL_KEYS = {"success", "failure", "pending"}
    _CHECKOUT_DOMAIN = "mercadopago.com.br"

    def __init__(self, cliente_preferencias, notification_url, back_urls):
        if not callable(getattr(cliente_preferencias, "criar_preferencia", None)):
            raise MercadoPagoCheckoutOfferOneTimeError()
        if not self._url_https_absoluta(notification_url):
            raise MercadoPagoCheckoutOfferOneTimeError()
        if (
            not isinstance(back_urls, dict)
            or set(back_urls) != self._BACK_URL_KEYS
            or any(
                not self._url_https_absoluta(back_urls[chave])
                for chave in self._BACK_URL_KEYS
            )
        ):
            raise MercadoPagoCheckoutOfferOneTimeError()

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
        offer_code,
        valor,
        moeda,
        idempotency_key,
    ):
        for identificador in (ordem_id, user_id, empresa_id):
            if (
                isinstance(identificador, bool)
                or not isinstance(identificador, int)
                or identificador <= 0
            ):
                raise MercadoPagoCheckoutOfferOneTimeError()
        if (
            not isinstance(offer_code, str)
            or _OFFER_CODE.fullmatch(offer_code) is None
        ):
            raise MercadoPagoCheckoutOfferOneTimeError()
        if (
            not isinstance(valor, Decimal)
            or not valor.is_finite()
            or valor <= Decimal("0")
            or valor.as_tuple().exponent != -2
        ):
            raise MercadoPagoCheckoutOfferOneTimeError()
        if moeda != "BRL":
            raise MercadoPagoCheckoutOfferOneTimeError()
        if (
            not isinstance(idempotency_key, str)
            or not idempotency_key
            or idempotency_key != idempotency_key.strip()
            or "\r" in idempotency_key
            or "\n" in idempotency_key
        ):
            raise MercadoPagoCheckoutOfferOneTimeError()

        payload = {
            "external_reference": str(ordem_id),
            "items": [{
                "id": offer_code,
                "title": offer_code,
                "quantity": 1,
                "unit_price": float(valor),
                "currency_id": "BRL",
            }],
            "notification_url": self._notification_url,
            "back_urls": dict(self._back_urls),
        }
        try:
            resposta = self._cliente_preferencias.criar_preferencia(
                payload=payload,
                idempotency_key=idempotency_key,
            )
        except Exception:
            raise MercadoPagoCheckoutOfferOneTimeError() from None

        if not isinstance(resposta, dict):
            raise MercadoPagoCheckoutOfferOneTimeError()
        provider_order_id = resposta.get("id")
        checkout_url = resposta.get("init_point")
        if (
            not isinstance(provider_order_id, str)
            or not provider_order_id.strip()
            or "\r" in provider_order_id
            or "\n" in provider_order_id
            or not self._checkout_url_valida(checkout_url)
        ):
            raise MercadoPagoCheckoutOfferOneTimeError()
        return {
            "provider_order_id": provider_order_id,
            "checkout_url": checkout_url,
        }

    @staticmethod
    def _url_https_absoluta(url):
        if (
            not isinstance(url, str)
            or not url
            or "\r" in url
            or "\n" in url
        ):
            return False
        try:
            parsed = urlsplit(url)
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

    @classmethod
    def _checkout_url_valida(cls, url):
        if not cls._url_https_absoluta(url):
            return False
        try:
            hostname = urlsplit(url).hostname
        except (TypeError, ValueError):
            return False
        return hostname == cls._CHECKOUT_DOMAIN or hostname.endswith(
            "." + cls._CHECKOUT_DOMAIN
        )


__all__ = [
    "MercadoPagoCheckoutOfferOneTimeError",
    "MercadoPagoCheckoutOfferOneTimeGateway",
]
