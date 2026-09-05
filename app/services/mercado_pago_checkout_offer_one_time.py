"""Adaptador offline do Mercado Pago para ofertas de pagamento unico."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlsplit


_MENSAGEM_PUBLICA = "Nao foi possivel criar a cobranca"
_OFFER_CODE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+", re.ASCII)
_PREFERENCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}", re.ASCII)


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
        expiration_date_from=None,
        expiration_date_to=None,
    ):
        self._validate_request(
            ordem_id=ordem_id,
            user_id=user_id,
            empresa_id=empresa_id,
            offer_code=offer_code,
            valor=valor,
            moeda=moeda,
            idempotency_key=idempotency_key,
            expiration_date_from=expiration_date_from,
            expiration_date_to=expiration_date_to,
        )

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
        if expiration_date_from is not None:
            payload.update({
                "expires": True,
                "expiration_date_from": expiration_date_from.replace(
                    tzinfo=timezone.utc
                ).isoformat(timespec="milliseconds"),
                "expiration_date_to": expiration_date_to.replace(
                    tzinfo=timezone.utc
                ).isoformat(timespec="milliseconds"),
            })
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

    def reconciliar_cobranca(
        self,
        ordem_id,
        user_id,
        empresa_id,
        offer_code,
        valor,
        moeda,
        idempotency_key,
        expiration_date_from=None,
        expiration_date_to=None,
    ):
        self._validate_request(
            ordem_id=ordem_id,
            user_id=user_id,
            empresa_id=empresa_id,
            offer_code=offer_code,
            valor=valor,
            moeda=moeda,
            idempotency_key=idempotency_key,
            expiration_date_from=expiration_date_from,
            expiration_date_to=expiration_date_to,
        )
        try:
            candidates = self._cliente_preferencias.buscar_preferencias(
                external_reference=str(ordem_id),
            )
            if type(candidates) is not list:
                raise MercadoPagoCheckoutOfferOneTimeError()
            if not candidates:
                return None
            if len(candidates) != 1 or type(candidates[0]) is not dict:
                raise MercadoPagoCheckoutOfferOneTimeError()

            candidate = candidates[0]
            if not self._partial_candidate_coherent(
                candidate,
                ordem_id=ordem_id,
                offer_code=offer_code,
                valor=valor,
                moeda=moeda,
                expiration_date_from=expiration_date_from,
                expiration_date_to=expiration_date_to,
            ):
                raise MercadoPagoCheckoutOfferOneTimeError()
            if not self._candidate_complete(
                candidate,
                campaign=expiration_date_from is not None,
            ):
                candidate_id = candidate.get("id")
                candidate = self._cliente_preferencias.obter_preferencia(
                    preference_id=candidate_id,
                )
                if (
                    type(candidate) is not dict
                    or candidate.get("id") != candidate_id
                ):
                    raise MercadoPagoCheckoutOfferOneTimeError()

            if (
                not self._candidate_complete(
                    candidate,
                    campaign=expiration_date_from is not None,
                )
                or not self._partial_candidate_coherent(
                    candidate,
                    ordem_id=ordem_id,
                    offer_code=offer_code,
                    valor=valor,
                    moeda=moeda,
                    expiration_date_from=expiration_date_from,
                    expiration_date_to=expiration_date_to,
                )
            ):
                raise MercadoPagoCheckoutOfferOneTimeError()
        except MercadoPagoCheckoutOfferOneTimeError:
            raise
        except Exception:
            raise MercadoPagoCheckoutOfferOneTimeError() from None

        return {
            "provider_order_id": candidate["id"],
            "checkout_url": candidate["init_point"],
        }

    @staticmethod
    def _validate_request(
        *,
        ordem_id,
        user_id,
        empresa_id,
        offer_code,
        valor,
        moeda,
        idempotency_key,
        expiration_date_from,
        expiration_date_to,
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
        if (expiration_date_from is None) != (expiration_date_to is None):
            raise MercadoPagoCheckoutOfferOneTimeError()
        if expiration_date_from is not None and (
            type(expiration_date_from) is not datetime
            or type(expiration_date_to) is not datetime
            or expiration_date_from.tzinfo is not None
            or expiration_date_to.tzinfo is not None
            or expiration_date_from >= expiration_date_to
        ):
            raise MercadoPagoCheckoutOfferOneTimeError()

    def _partial_candidate_coherent(
        self,
        candidate,
        *,
        ordem_id,
        offer_code,
        valor,
        moeda,
        expiration_date_from,
        expiration_date_to,
    ):
        preference_id = candidate.get("id")
        if (
            type(preference_id) is not str
            or _PREFERENCE_ID.fullmatch(preference_id) is None
        ):
            return False
        if (
            "external_reference" in candidate
            and candidate["external_reference"] != str(ordem_id)
        ):
            return False
        if (
            "init_point" in candidate
            and not self._checkout_url_valida(candidate["init_point"])
        ):
            return False
        if (
            "notification_url" in candidate
            and candidate["notification_url"] != self._notification_url
        ):
            return False
        if (
            "back_urls" in candidate
            and candidate["back_urls"] != self._back_urls
        ):
            return False

        if "items" in candidate:
            items = candidate["items"]
            if (
                type(items) is not list
                or len(items) != 1
                or type(items[0]) is not dict
            ):
                return False
            item = items[0]
            for key, expected in (
                ("id", offer_code),
                ("title", offer_code),
                ("currency_id", moeda),
            ):
                if key in item and (
                    type(item[key]) is not str or item[key] != expected
                ):
                    return False
            if "quantity" in item and (
                type(item["quantity"]) is not int
                or item["quantity"] != 1
            ):
                return False
            if (
                "unit_price" in item
                and not self._numeric_amount_matches(item["unit_price"], valor)
            ):
                return False

        campaign = expiration_date_from is not None
        if campaign:
            if (
                "expires" in candidate
                and candidate["expires"] is not True
            ):
                return False
            for key, expected in (
                ("expiration_date_from", expiration_date_from),
                ("expiration_date_to", expiration_date_to),
            ):
                if (
                    key in candidate
                    and not self._provider_instant_matches(
                        candidate[key], expected
                    )
                ):
                    return False
        elif any(
            candidate.get(key) not in (None, False)
            for key in (
                "expires",
                "expiration_date_from",
                "expiration_date_to",
            )
        ):
            return False
        return True

    @staticmethod
    def _candidate_complete(candidate, *, campaign):
        required = {
            "id",
            "init_point",
            "external_reference",
            "items",
            "notification_url",
            "back_urls",
        }
        if not required.issubset(candidate):
            return False
        items = candidate.get("items")
        if (
            type(items) is not list
            or len(items) != 1
            or type(items[0]) is not dict
            or not {
                "id",
                "title",
                "quantity",
                "unit_price",
                "currency_id",
            }.issubset(items[0])
        ):
            return False
        if campaign:
            if (
                "expires" not in candidate
                or candidate["expires"] is not True
                or not {
                    "expiration_date_from",
                    "expiration_date_to",
                }.issubset(candidate)
            ):
                return False
        return True

    @staticmethod
    def _numeric_amount_matches(value, expected):
        if isinstance(value, bool):
            return False
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return False
        return parsed.is_finite() and parsed == expected

    @staticmethod
    def _provider_instant_matches(value, expected):
        if type(value) is not str or type(expected) is not datetime:
            return False
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return False
        if parsed.tzinfo is None or expected.tzinfo is not None:
            return False
        return parsed.astimezone(timezone.utc) == expected.replace(
            tzinfo=timezone.utc
        )

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
