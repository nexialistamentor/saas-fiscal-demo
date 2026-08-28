from collections.abc import Mapping

import pytest

from app.services.serpro_authenticated_transport import (
    AuthenticatedTransportError,
    SerproAuthenticatedTransport,
)
from app.services.serpro_oauth_session import SerproOAuthSession
from app.services.serpro_pgmei_client import (
    PgmeiClientError,
    PgmeiResult,
    SerproPgmeiClient,
)


PGMEI_ENDPOINT = "https://trial.invalid/integra-contador/v1/consultar"
ACCESS_A = "synthetic-access-A"
JWT_A = "synthetic-jwt-A"
ACCESS_B = "synthetic-access-B"
JWT_B = "synthetic-jwt-B"
SERVICE = "GERARDASPDF21"


class StubResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class QueueTransport:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)


def oauth_payload(access_token, jwt_token):
    return {
        "access_token": access_token,
        "jwt_token": jwt_token,
        "token_type": "Bearer",
        "expires_in": 120,
    }


def envelope():
    return {
        "status": 200,
        "mensagens": [],
        "dados": "nominal",
        "sistema": "PGMEI",
        "servico": SERVICE,
    }


def productive_session(auth_transport):
    return SerproOAuthSession(
        consumer_key="synthetic-key",
        consumer_secret="synthetic-secret",
        mtls_identity=object(),
        transport=auth_transport,
        clock=lambda: 100.0,
        safe_window=10.0,
    )


def productive_client(transport):
    return SerproPgmeiClient(
        endpoint=PGMEI_ENDPOINT,
        authentication={},
        timeout=7.5,
        transport=transport,
        contratante="12ABC34501DE67",
    )


def call_client(client):
    return client.request(SERVICE, "98XYZ76501AB43", "202608")


def test_productive_composition_refreshes_once_after_401():
    auth = QueueTransport(
        [
            StubResponse(payload=oauth_payload(ACCESS_A, JWT_A)),
            StubResponse(payload=oauth_payload(ACCESS_B, JWT_B)),
        ]
    )
    pgmei = QueueTransport(
        [StubResponse(status_code=401), StubResponse(payload=envelope())]
    )
    result = call_client(
        productive_client(
            SerproAuthenticatedTransport(
                session=productive_session(auth), downstream=pgmei
            )
        )
    )

    assert isinstance(result, PgmeiResult)
    assert result.data == "nominal"
    assert len(auth.calls) == 2
    assert len(pgmei.calls) == 2
    assert pgmei.calls[0]["headers"] == {
        "Authorization": f"Bearer {ACCESS_A}",
        "jwt_token": JWT_A,
        "Content-Type": "application/json",
    }
    assert pgmei.calls[1]["headers"] == {
        "Authorization": f"Bearer {ACCESS_B}",
        "jwt_token": JWT_B,
        "Content-Type": "application/json",
    }
    assert ACCESS_A not in repr(pgmei.calls[1])
    for field in ("url", "json", "timeout"):
        assert pgmei.calls[1][field] == pgmei.calls[0][field]
    assert pgmei.calls[1]["json"] is pgmei.calls[0]["json"]


def test_nominal_200_does_not_refresh_or_retry():
    auth = QueueTransport([StubResponse(payload=oauth_payload(ACCESS_A, JWT_A))])
    pgmei = QueueTransport([StubResponse(payload=envelope())])
    result = call_client(
        productive_client(
            SerproAuthenticatedTransport(productive_session(auth), pgmei)
        )
    )
    assert isinstance(result, PgmeiResult)
    assert len(auth.calls) == 1
    assert len(pgmei.calls) == 1


def test_second_401_stops_sanitized_without_third_attempt():
    auth = QueueTransport(
        [
            StubResponse(payload=oauth_payload(ACCESS_A, JWT_A)),
            StubResponse(payload=oauth_payload(ACCESS_B, JWT_B)),
        ]
    )
    pgmei = QueueTransport([StubResponse(401), StubResponse(401)])
    client = productive_client(
        SerproAuthenticatedTransport(productive_session(auth), pgmei)
    )
    with pytest.raises(PgmeiClientError, match="http status invalido") as caught:
        call_client(client)
    rendered = f"{caught.value!r} {caught.value}"
    assert all(secret not in rendered for secret in (ACCESS_A, JWT_A, ACCESS_B, JWT_B))
    assert len(auth.calls) == 2
    assert len(pgmei.calls) == 2


class SessionStub:
    def __init__(self, headers=None, error=None):
        self.headers = headers
        self.error = error
        self.get_calls = 0
        self.invalidations = 0

    def get_headers(self):
        self.get_calls += 1
        if self.error is not None:
            raise self.error
        return self.headers

    def invalidate(self):
        self.invalidations += 1


def valid_session_headers():
    return {"Authorization": f"Bearer {ACCESS_A}", "jwt_token": JWT_A}


@pytest.mark.parametrize(
    "session_headers",
    [
        None,
        [],
        {},
        {"Authorization": "", "jwt_token": JWT_A},
        {"Authorization": "   ", "jwt_token": JWT_A},
        {"Authorization": f"Bearer {ACCESS_A}"},
        {"Authorization": f"Bearer {ACCESS_A}", "jwt_token": ""},
        {"Authorization": f"Bearer {ACCESS_A}", "jwt_token": "  "},
        {**valid_session_headers(), "unexpected": "value"},
        {"Authorization": f"Bearer {ACCESS_A}", "authorization": "duplicate", "jwt_token": JWT_A},
    ],
)
def test_invalid_session_headers_fail_closed_before_downstream(session_headers):
    downstream = QueueTransport([StubResponse()])
    transport = SerproAuthenticatedTransport(SessionStub(session_headers), downstream)
    with pytest.raises(AuthenticatedTransportError, match="credenciais de sessao invalidas"):
        transport(url="u", json={"x": 1}, headers={}, timeout=3)
    assert downstream.calls == []


@pytest.mark.parametrize(
    "session_headers",
    [
        {"Authorization": f"Basic {ACCESS_A}", "jwt_token": JWT_A},
        {"Authorization": "Bearer", "jwt_token": JWT_A},
        {"Authorization": f"Bearer access token", "jwt_token": JWT_A},
        {"Authorization": f"Bearer {ACCESS_A}\r", "jwt_token": JWT_A},
        {"Authorization": f"Bearer {ACCESS_A}\n", "jwt_token": JWT_A},
        {"Authorization": f"Bearer {ACCESS_A}", "jwt_token": f"{JWT_A}\r"},
        {"Authorization": f"Bearer {ACCESS_A}", "jwt_token": f"{JWT_A}\n"},
        {"Authorization": f"Bearer {ACCESS_A}", "jwt_token": "jwt token"},
    ],
    ids=[
        "authorization-basic",
        "authorization-bearer-without-token",
        "authorization-token-whitespace",
        "authorization-cr",
        "authorization-lf",
        "jwt-token-cr",
        "jwt-token-lf",
        "jwt-token-whitespace",
    ],
)
def test_malformed_authenticated_headers_fail_before_downstream(session_headers):
    downstream = QueueTransport([StubResponse()])
    transport = SerproAuthenticatedTransport(SessionStub(session_headers), downstream)
    with pytest.raises(AuthenticatedTransportError, match="credenciais de sessao invalidas"):
        transport(url="u", json={"x": 1}, headers={}, timeout=3)
    assert downstream.calls == []


@pytest.mark.parametrize(
    "caller_headers",
    [
        {"Authorization": "caller"},
        {"authorization": "caller"},
        {"jwt_token": "caller"},
        {"JWT_TOKEN": "caller"},
        {"Content-Type": "text/plain"},
        {"content-type": "application/json", "Content-Type": "application/json"},
        {"X-Test": "one", "x-test": "two"},
    ],
)
def test_caller_sensitive_divergent_or_duplicate_headers_fail_closed(caller_headers):
    session = SessionStub(valid_session_headers())
    downstream = QueueTransport([StubResponse()])
    transport = SerproAuthenticatedTransport(session, downstream)
    original = dict(caller_headers)
    with pytest.raises(AuthenticatedTransportError, match="headers da requisicao invalidos"):
        transport(url="u", json={}, headers=caller_headers, timeout=3)
    assert caller_headers == original
    assert session.get_calls == 0
    assert downstream.calls == []


@pytest.mark.parametrize(
    "caller_headers",
    [
        {1: "value"},
        {"X-Test": 1},
        {"": "value"},
        {"   ": "value"},
        {"X-Test\rInjected": "value"},
        {"X-Test\nInjected": "value"},
        {"X-Test": "value\rInjected"},
        {"X-Test": "value\nInjected"},
    ],
    ids=[
        "non-string-key",
        "non-string-value",
        "empty-name",
        "whitespace-only-name",
        "name-cr",
        "name-lf",
        "value-cr",
        "value-lf",
    ],
)
def test_malformed_caller_headers_fail_before_downstream(caller_headers):
    session = SessionStub(valid_session_headers())
    downstream = QueueTransport([StubResponse()])
    transport = SerproAuthenticatedTransport(session, downstream)
    with pytest.raises(AuthenticatedTransportError, match="headers da requisicao invalidos"):
        transport(url="u", json={}, headers=caller_headers, timeout=3)
    assert session.get_calls == 0
    assert downstream.calls == []


def test_preserves_inputs_and_non_sensitive_headers_without_mutation():
    session_headers = valid_session_headers()
    caller_headers = {"X-Correlation": "abc", "Content-Type": "application/json"}
    payload = {"nested": [1, 2]}
    downstream = QueueTransport([StubResponse(200)])
    response = SerproAuthenticatedTransport(
        SessionStub(session_headers), downstream
    )(url="u", json=payload, headers=caller_headers, timeout=4.5)
    assert response.status_code == 200
    assert caller_headers == {
        "X-Correlation": "abc",
        "Content-Type": "application/json",
    }
    assert session_headers == valid_session_headers()
    assert downstream.calls[0] == {
        "url": "u",
        "json": payload,
        "headers": {
            "X-Correlation": "abc",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ACCESS_A}",
            "jwt_token": JWT_A,
        },
        "timeout": 4.5,
    }
    assert downstream.calls[0]["json"] is payload


@pytest.mark.parametrize("status", [403, 409, 429, 500, 503])
def test_only_401_invalidates_and_retries(status):
    session = SessionStub(valid_session_headers())
    downstream = QueueTransport([StubResponse(status), StubResponse(200)])
    response = SerproAuthenticatedTransport(session, downstream)(
        url="u", json={}, headers={}, timeout=3
    )
    assert response.status_code == status
    assert session.invalidations == 0
    assert session.get_calls == 1
    assert len(downstream.calls) == 1


def test_session_and_downstream_exceptions_are_sanitized_without_retry():
    for source in (SessionStub(error=RuntimeError(ACCESS_A)),):
        downstream = QueueTransport([StubResponse()])
        transport = SerproAuthenticatedTransport(source, downstream)
        with pytest.raises(AuthenticatedTransportError) as caught:
            transport(url="u", json={}, headers={}, timeout=3)
        assert ACCESS_A not in f"{caught.value!r} {caught.value}"
        assert caught.value.__cause__ is None
        assert downstream.calls == []

    session = SessionStub(valid_session_headers())
    downstream = QueueTransport(error=RuntimeError(JWT_A))
    transport = SerproAuthenticatedTransport(session, downstream)
    with pytest.raises(AuthenticatedTransportError) as caught:
        transport(url="u", json={}, headers={}, timeout=3)
    assert JWT_A not in f"{caught.value!r} {caught.value} {transport!r}"
    assert caught.value.__cause__ is None
    assert session.invalidations == 0
    assert len(downstream.calls) == 1


def test_wrapper_keeps_only_session_and_downstream_without_token_copies():
    session = SessionStub(valid_session_headers())
    downstream = QueueTransport([StubResponse(200)])
    transport = SerproAuthenticatedTransport(session, downstream)
    transport(url="u", json={}, headers={}, timeout=3)
    assert vars(transport) == {"_session": session, "_downstream": downstream}
    assert ACCESS_A not in repr(transport)
    assert JWT_A not in repr(transport)
    assert isinstance(session.headers, Mapping)
