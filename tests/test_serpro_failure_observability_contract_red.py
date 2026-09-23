import logging

import pytest

from app.services.serpro_oauth_session import OAuthSessionError, SerproOAuthSession
from app.services.serpro_pgmei_client import PgmeiClientError, SerproPgmeiClient


class StubResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class StubTransport:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def __call__(self, **kwargs):
        if self.error is not None:
            raise self.error
        return self.response


def _oauth_session(transport):
    return SerproOAuthSession(
        consumer_key="private-consumer-key",
        consumer_secret="private-consumer-secret",
        mtls_identity=object(),
        transport=transport,
        safe_window=10.0,
    )


def _pgmei_client(transport):
    return SerproPgmeiClient(
        endpoint="https://trial.invalid/integra-contador/v1/consultar",
        authentication={},
        timeout=5.0,
        transport=transport,
        contratante="private-contratante",
    )


def test_oauth_http_status_is_observable_without_private_data(caplog):
    caplog.set_level(logging.WARNING)
    private_body = "private-oauth-body"

    with pytest.raises(OAuthSessionError):
        _oauth_session(
            StubTransport(
                StubResponse(
                    status_code=412,
                    payload={"private": private_body},
                )
            )
        ).get_headers()

    assert "serpro_pgmei_failure stage=oauth_http provider_status=412" in caplog.text
    for private in (
        private_body,
        "private-consumer-key",
        "private-consumer-secret",
    ):
        assert private not in caplog.text


def test_oauth_transport_failure_has_sanitized_stage(caplog):
    caplog.set_level(logging.WARNING)
    private_error = "private-oauth-wire-detail"

    with pytest.raises(OAuthSessionError):
        _oauth_session(
            StubTransport(error=RuntimeError(private_error))
        ).get_headers()

    assert (
        "serpro_pgmei_failure stage=oauth_transport provider_status=unknown"
        in caplog.text
    )
    assert private_error not in caplog.text


def test_pgmei_http_status_is_observable_without_private_data(caplog):
    caplog.set_level(logging.WARNING)
    private_body = "private-pgmei-body"

    with pytest.raises(PgmeiClientError):
        _pgmei_client(
            StubTransport(
                StubResponse(
                    status_code=503,
                    payload={"private": private_body},
                )
            )
        ).request("GERARDASPDF21", "12345678000190", "202609")

    assert "serpro_pgmei_failure stage=pgmei_http provider_status=503" in caplog.text
    for private in (
        private_body,
        "12345678000190",
        "private-contratante",
    ):
        assert private not in caplog.text


def test_pgmei_transport_failure_has_sanitized_stage(caplog):
    caplog.set_level(logging.WARNING)
    private_error = "private-pgmei-wire-detail"

    with pytest.raises(PgmeiClientError):
        _pgmei_client(
            StubTransport(error=RuntimeError(private_error))
        ).request("GERARDASCODBARRA22", "12345678000190", "202609")

    assert (
        "serpro_pgmei_failure stage=pgmei_transport provider_status=unknown"
        in caplog.text
    )
    assert private_error not in caplog.text
    assert "12345678000190" not in caplog.text