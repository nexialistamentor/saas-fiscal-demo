"""Cliente HTTP injetado para criar preferencias no Mercado Pago."""

from copy import deepcopy
from json import JSONDecodeError
from math import isfinite

from httpx import HTTPError


_PREFERENCES_URL = "https://api.mercadopago.com/checkout/preferences"


class MercadoPagoPreferenceClientError(Exception):
    """Erro publico e sem detalhes privados do cliente de preferencias."""

    PUBLIC_MESSAGE = "mercado_pago_preference_client_error"

    def __init__(self):
        super().__init__(self.PUBLIC_MESSAGE)


def _is_visible_ascii(value):
    return (
        type(value) is str
        and bool(value)
        and all(33 <= ord(character) <= 126 for character in value)
    )


def _is_positive_finite_number(value):
    if type(value) is int:
        return value > 0
    if type(value) is float:
        return value > 0 and isfinite(value)
    return False


def _is_json_compatible(value, active_containers=None):
    value_type = type(value)

    if value is None or value_type in (bool, int, str):
        return True
    if value_type is float:
        return isfinite(value)
    if value_type not in (dict, list):
        return False

    if active_containers is None:
        active_containers = set()

    identity = id(value)
    if identity in active_containers:
        return False

    active_containers.add(identity)
    if value_type is list:
        valid = all(
            _is_json_compatible(item, active_containers) for item in value
        )
    else:
        valid = all(
            type(key) is str
            and _is_json_compatible(item, active_containers)
            for key, item in value.items()
        )
    active_containers.remove(identity)
    return valid


class MercadoPagoPreferenceClient:
    """Adaptador minimo para o endpoint de preferencias."""

    def __init__(self, *, http_client, access_token, timeout_seconds):
        if not callable(getattr(http_client, "post", None)):
            raise MercadoPagoPreferenceClientError()
        if not _is_visible_ascii(access_token):
            raise MercadoPagoPreferenceClientError()
        if not _is_positive_finite_number(timeout_seconds):
            raise MercadoPagoPreferenceClientError()

        self._http_client = http_client
        self._access_token = access_token
        self._timeout_seconds = timeout_seconds

    def criar_preferencia(self, *, payload, idempotency_key):
        if type(payload) is not dict or not payload:
            raise MercadoPagoPreferenceClientError()
        if not _is_json_compatible(payload):
            raise MercadoPagoPreferenceClientError()
        if not _is_visible_ascii(idempotency_key):
            raise MercadoPagoPreferenceClientError()

        transport_failed = False
        try:
            response = self._http_client.post(
                url=_PREFERENCES_URL,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                    "X-Idempotency-Key": idempotency_key,
                },
                json=deepcopy(payload),
                timeout=self._timeout_seconds,
                follow_redirects=False,
            )
        except HTTPError:
            transport_failed = True

        if transport_failed:
            raise MercadoPagoPreferenceClientError()

        status_code = getattr(response, "status_code", None)
        if type(status_code) is not int or status_code != 201:
            raise MercadoPagoPreferenceClientError()

        response_json = getattr(response, "json", None)
        if not callable(response_json):
            raise MercadoPagoPreferenceClientError()

        decoding_failed = False
        try:
            response_payload = response_json()
        except (JSONDecodeError, UnicodeDecodeError):
            decoding_failed = True

        if decoding_failed or type(response_payload) is not dict:
            raise MercadoPagoPreferenceClientError()

        return deepcopy(response_payload)
