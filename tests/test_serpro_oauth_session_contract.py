import base64
import threading
import time

import pytest

from app.services.serpro_oauth_session import OAuthSessionError, SerproOAuthSession


ENDPOINT = "https://autenticacao.sapi.serpro.gov.br/authenticate"
CONSUMER_KEY = "synthetic-consumer-key"
CONSUMER_SECRET = "synthetic-consumer-secret"
ACCESS_TOKEN = "synthetic-access-token"
JWT_TOKEN = "synthetic-jwt-token"


class OpaqueMtlsIdentity:
    def __repr__(self):
        return "synthetic-mtls-identity-secret"


MTLS_IDENTITY = OpaqueMtlsIdentity()


class StubResponse:
    def __init__(self, status_code=200, payload=None, json_error=None):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class RecordingTransport:
    def __init__(self, responses=None, error=None, barrier=None):
        self.responses = list(responses or [])
        self.error = error
        self.barrier = barrier
        self.calls = []
        self._lock = threading.Lock()

    def __call__(self, **kwargs):
        with self._lock:
            self.calls.append(kwargs)
            response = self.responses.pop(0) if self.responses else None
        if self.barrier is not None:
            self.barrier.wait(timeout=2)
        if self.error is not None:
            raise self.error
        return response


class Clock:
    def __init__(self, value=100.0):
        self.value = value

    def __call__(self):
        return self.value


def valid_payload(access_token=ACCESS_TOKEN, jwt_token=JWT_TOKEN, expires_in=120):
    return {
        "access_token": access_token,
        "jwt_token": jwt_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
    }


def make_session(transport, clock=None, safe_window=10.0):
    return SerproOAuthSession(
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        mtls_identity=MTLS_IDENTITY,
        transport=transport,
        clock=clock or Clock(),
        safe_window=safe_window,
    )


def test_exact_authentication_request_and_consumption_headers():
    transport = RecordingTransport([StubResponse(payload=valid_payload())])
    session = make_session(transport)

    headers = session.get_headers()

    expected_basic = base64.b64encode(
        f"{CONSUMER_KEY}:{CONSUMER_SECRET}".encode("utf-8")
    ).decode("ascii")
    assert "\n" not in expected_basic
    assert transport.calls == [
        {
            "url": ENDPOINT,
            "method": "POST",
            "headers": {
                "Authorization": f"Basic {expected_basic}",
                "role-type": "TERCEIROS",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            "data": "grant_type=client_credentials",
            "mtls_identity": MTLS_IDENTITY,
            "timeout": 30.0,
        }
    ]
    assert transport.calls[0]["mtls_identity"] is MTLS_IDENTITY
    assert headers == {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "jwt_token": JWT_TOKEN,
    }


def test_cache_reuse_safe_window_expiration_and_explicit_invalidation():
    clock = Clock()
    transport = RecordingTransport(
        [
            StubResponse(payload=valid_payload("access-1", "jwt-1", 100)),
            StubResponse(payload=valid_payload("access-2", "jwt-2", 100)),
            StubResponse(payload=valid_payload("access-3", "jwt-3", 100)),
        ]
    )
    session = make_session(transport, clock=clock, safe_window=10)

    assert session.get_headers()["Authorization"] == "Bearer access-1"
    clock.value = 189.9
    assert session.get_headers()["Authorization"] == "Bearer access-1"
    clock.value = 190.0
    assert session.get_headers()["Authorization"] == "Bearer access-2"
    session.invalidate()
    assert session.get_headers()["Authorization"] == "Bearer access-3"
    assert len(transport.calls) == 3


def test_token_is_immutable():
    transport = RecordingTransport([StubResponse(payload=valid_payload())])
    token = make_session(transport)._get_token()
    with pytest.raises((AttributeError, TypeError)):
        token.access_token = "changed"


def test_concurrent_header_calls_share_one_authentication():
    entered = threading.Event()
    release = threading.Event()

    class BlockingTransport(RecordingTransport):
        def __call__(self, **kwargs):
            with self._lock:
                self.calls.append(kwargs)
            entered.set()
            assert release.wait(timeout=2)
            return StubResponse(payload=valid_payload())

    transport = BlockingTransport()
    session = make_session(transport)
    results = []
    errors = []

    def obtain_headers():
        try:
            results.append(session.get_headers())
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=obtain_headers) for _ in range(8)]
    for thread in threads:
        thread.start()
    assert entered.wait(timeout=2)
    time.sleep(0.05)
    release.set()
    for thread in threads:
        thread.join(timeout=2)

    assert errors == []
    assert len(results) == 8
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "response",
    [
        StubResponse(status_code=201, payload=valid_payload()),
        StubResponse(json_error=ValueError("response-body-secret")),
        StubResponse(payload=[]),
        StubResponse(payload={**valid_payload(), "token_type": "MAC"}),
        StubResponse(payload={key: value for key, value in valid_payload().items() if key != "access_token"}),
        StubResponse(payload={**valid_payload(), "access_token": ""}),
        StubResponse(payload={**valid_payload(), "access_token": 123}),
        StubResponse(payload={key: value for key, value in valid_payload().items() if key != "jwt_token"}),
        StubResponse(payload={**valid_payload(), "jwt_token": ""}),
        StubResponse(payload={**valid_payload(), "jwt_token": 123}),
        StubResponse(payload={key: value for key, value in valid_payload().items() if key != "expires_in"}),
        StubResponse(payload={**valid_payload(), "expires_in": True}),
        StubResponse(payload={**valid_payload(), "expires_in": 1.5}),
        StubResponse(payload={**valid_payload(), "expires_in": 0}),
        StubResponse(payload={**valid_payload(), "expires_in": -1}),
    ],
)
def test_invalid_responses_fail_closed_and_are_not_cached(response):
    transport = RecordingTransport(
        [response, StubResponse(payload=valid_payload("recovered-access", "recovered-jwt"))]
    )
    session = make_session(transport)
    with pytest.raises(OAuthSessionError):
        session.get_headers()
    assert session.get_headers() == {
        "Authorization": "Bearer recovered-access",
        "jwt_token": "recovered-jwt",
    }
    assert len(transport.calls) == 2


@pytest.mark.parametrize(
    "error", [TimeoutError("transport-secret"), RuntimeError("identity-secret")]
)
def test_transport_and_identity_failures_are_sanitized_and_not_cached(error):
    class FailOnceTransport(RecordingTransport):
        def __call__(self, **kwargs):
            if not self.calls:
                self.calls.append(kwargs)
                raise error
            self.calls.append(kwargs)
            return StubResponse(payload=valid_payload())

    transport = FailOnceTransport()
    session = make_session(transport)
    with pytest.raises(OAuthSessionError) as caught:
        session.get_headers()
    rendered = f"{caught.value!r} {caught.value} {session!r}"
    for secret in (
        CONSUMER_KEY,
        CONSUMER_SECRET,
        ACCESS_TOKEN,
        JWT_TOKEN,
        "synthetic-mtls-identity-secret",
        "transport-secret",
        "identity-secret",
    ):
        assert secret not in rendered
    assert caught.value.__cause__ is error
    assert session.get_headers()["Authorization"] == f"Bearer {ACCESS_TOKEN}"
    assert len(transport.calls) == 2


def test_tokens_and_credentials_are_absent_from_repr_and_public_errors():
    transport = RecordingTransport(
        [StubResponse(payload={**valid_payload(), "token_type": ACCESS_TOKEN})]
    )
    session = make_session(transport)
    with pytest.raises(OAuthSessionError) as caught:
        session.get_headers()
    rendered = f"{session!r} {session} {caught.value!r} {caught.value}"
    for secret in (
        CONSUMER_KEY,
        CONSUMER_SECRET,
        ACCESS_TOKEN,
        JWT_TOKEN,
        "synthetic-mtls-identity-secret",
    ):
        assert secret not in rendered


def test_token_repr_and_str_redact_both_token_values():
    transport = RecordingTransport([StubResponse(payload=valid_payload())])
    token = make_session(transport)._get_token()

    rendered = f"{token!r} {token}"

    assert ACCESS_TOKEN not in rendered
    assert JWT_TOKEN not in rendered


def test_authentication_transport_receives_exact_configured_timeout():
    transport = RecordingTransport([StubResponse(payload=valid_payload())])
    session = SerproOAuthSession(
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        mtls_identity=MTLS_IDENTITY,
        transport=transport,
        clock=Clock(),
        safe_window=10.0,
        timeout=7.5,
    )

    session.get_headers()

    assert transport.calls[0]["timeout"] == 7.5


def test_invalid_timeout_and_safe_window_fail_sanitized_before_transport():
    invalid_configurations = (
        {"timeout": True},
        {"timeout": 0},
        {"timeout": -1},
        {"timeout": float("inf")},
        {"timeout": float("nan")},
        {"timeout": "10"},
        {"safe_window": True},
        {"safe_window": -1},
        {"safe_window": float("inf")},
        {"safe_window": float("nan")},
        {"safe_window": "10"},
    )

    for configuration in invalid_configurations:
        transport = RecordingTransport([StubResponse(payload=valid_payload())])
        with pytest.raises(OAuthSessionError) as caught:
            SerproOAuthSession(
                consumer_key=CONSUMER_KEY,
                consumer_secret=CONSUMER_SECRET,
                mtls_identity=MTLS_IDENTITY,
                transport=transport,
                **configuration,
            )
        assert str(caught.value) == "configuracao OAuth SERPRO invalida"
        assert transport.calls == []


@pytest.mark.parametrize("field", ["access_token", "jwt_token"])
@pytest.mark.parametrize("value", ["", " ", "\t\r\n"])
def test_empty_or_whitespace_tokens_are_rejected(field, value):
    transport = RecordingTransport(
        [StubResponse(payload={**valid_payload(), field: value})]
    )
    session = make_session(transport)

    with pytest.raises(OAuthSessionError):
        session.get_headers()
