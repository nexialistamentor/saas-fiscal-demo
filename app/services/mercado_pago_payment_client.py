"""Cliente mínimo para consulta de pagamentos no Mercado Pago."""

import json
import math

import httpx


class MercadoPagoPaymentClientError(Exception):
    """Erro público e opaco da consulta de pagamentos."""

    _MESSAGE = "Falha ao consultar pagamento"

    def __init__(self, *_args, **_kwargs):
        super().__init__(self._MESSAGE)

    def __str__(self):
        return self._MESSAGE

    def __repr__(self):
        return "MercadoPagoPaymentClientError()"


class MercadoPagoPaymentClient:
    """Consulta um pagamento usando exclusivamente o transporte injetado."""

    def __init__(self, *, http_client, access_token, timeout_seconds):
        get = getattr(http_client, "get", None)
        if not callable(get):
            raise MercadoPagoPaymentClientError()

        if not self._token_canonico(access_token):
            raise MercadoPagoPaymentClientError()

        if not self._timeout_valido(timeout_seconds):
            raise MercadoPagoPaymentClientError()

        self._get = get
        self._authorization = f"Bearer {access_token}"
        self._timeout_seconds = timeout_seconds

    def __repr__(self):
        return "MercadoPagoPaymentClient()"

    def obter_pagamento(self, *, payment_id):
        if not self._payment_id_canonico(payment_id):
            raise MercadoPagoPaymentClientError()

        try:
            response = self._get(
                url=(
                    "https://api.mercadopago.com/v1/payments/"
                    f"{payment_id}"
                ),
                headers={
                    "Accept": "application/json",
                    "Authorization": self._authorization,
                },
                timeout=self._timeout_seconds,
                follow_redirects=False,
            )
        except httpx.HTTPError:
            raise MercadoPagoPaymentClientError() from None

        status_code = getattr(response, "status_code", None)
        if type(status_code) is not int or status_code != 200:
            raise MercadoPagoPaymentClientError()

        response_json = getattr(response, "json", None)
        if not callable(response_json):
            raise MercadoPagoPaymentClientError()

        try:
            payload = response_json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise MercadoPagoPaymentClientError() from None

        if type(payload) is not dict:
            raise MercadoPagoPaymentClientError()
        return dict(payload)

    @staticmethod
    def _token_canonico(value):
        return (
            type(value) is str
            and bool(value)
            and value.isascii()
            and all(0x21 <= ord(character) <= 0x7E for character in value)
        )

    @staticmethod
    def _timeout_valido(value):
        if type(value) is int:
            return value > 0
        if type(value) is float:
            return math.isfinite(value) and value > 0
        return False

    @staticmethod
    def _payment_id_canonico(value):
        return (
            type(value) is str
            and bool(value)
            and value.isascii()
            and value.isdecimal()
            and value[0] != "0"
        )
