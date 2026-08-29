import builtins
import math
import sys
from types import SimpleNamespace

import pytest

from app.services.serpro_pkcs12_transport import (
    Pkcs12Identity,
    SerproPkcs12Transport,
    SerproPkcs12TransportError,
)


HTTPS_URL = "https://servicos.invalid/endpoint"


class StubResponse:
    status_code = 200


class RecordingRequest:
    def __init__(self, response=None, error=None):
        self.response = response or StubResponse()
        self.error = error
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.response


def identity():
    return Pkcs12Identity(
        pkcs12_data=b"opaque-test-container",
        pkcs12_password="opaque-test-password",
    )


def transport(request=None, mtls_identity=None):
    return SerproPkcs12Transport(
        mtls_identity=mtls_identity or identity(),
        request=request or RecordingRequest(),
    )


def test_delegates_exact_oauth_call_and_returns_same_response():
    request = RecordingRequest()
    mtls = identity()
    adapter = transport(request, mtls)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    body = "grant_type=client_credentials"

    response = adapter(
        method="POST",
        url=HTTPS_URL,
        headers=headers,
        data=body,
        mtls_identity=mtls,
        timeout=7.5,
    )

    assert response is request.response
    assert request.calls == [
        (
            ("POST", HTTPS_URL),
            {
                "headers": headers,
                "data": body,
                "timeout": 7.5,
                "pkcs12_data": mtls.pkcs12_data,
                "pkcs12_password": mtls.pkcs12_password,
            },
        )
    ]
    call = request.calls[0][1]
    assert call["headers"] is headers
    assert call["data"] is body
    assert call["pkcs12_data"] is mtls.pkcs12_data
    assert call["pkcs12_password"] is mtls.pkcs12_password


def test_bound_identity_supports_authenticated_transport_json_signature():
    request = RecordingRequest()
    mtls = identity()
    adapter = transport(request, mtls)
    headers = {"Content-Type": "application/json"}
    payload = {"nested": [1, 2]}

    response = adapter(
        url=HTTPS_URL,
        json=payload,
        headers=headers,
        timeout=3,
    )

    assert response is request.response
    assert request.calls[0] == (
        ("POST", HTTPS_URL),
        {
            "headers": headers,
            "json": payload,
            "timeout": 3,
            "pkcs12_data": mtls.pkcs12_data,
            "pkcs12_password": mtls.pkcs12_password,
        },
    )
    assert request.calls[0][1]["json"] is payload


def test_filename_identity_is_forwarded_without_conversion_and_repr_is_closed():
    request = RecordingRequest()
    mtls = Pkcs12Identity(
        pkcs12_filename="C:/opaque/location/client.p12",
        pkcs12_password="opaque-file-password",
    )
    adapter = transport(request, mtls)

    adapter(url=HTTPS_URL, json=None, headers={}, timeout=2)

    kwargs = request.calls[0][1]
    assert kwargs["pkcs12_filename"] is mtls.pkcs12_filename
    assert kwargs["pkcs12_password"] is mtls.pkcs12_password
    assert "pkcs12_data" not in kwargs
    rendered = f"{mtls!r} {mtls} {adapter!r} {adapter}"
    assert mtls.pkcs12_filename not in rendered
    assert mtls.pkcs12_password not in rendered


def test_json_and_data_are_distinct_and_omitted_when_not_supplied():
    request = RecordingRequest()
    adapter = transport(request)

    adapter(url=HTTPS_URL, headers={}, timeout=1, data=None)
    assert "data" in request.calls[0][1]
    assert request.calls[0][1]["data"] is None
    assert "json" not in request.calls[0][1]

    adapter(url=HTTPS_URL, headers={}, timeout=1)
    assert "data" not in request.calls[1][1]
    assert "json" not in request.calls[1][1]


def test_inputs_are_not_modified():
    request = RecordingRequest()
    mtls = identity()
    adapter = transport(request, mtls)
    headers = {"X-Test": "value"}
    payload = {"items": [1]}
    original_headers = dict(headers)
    original_payload = {"items": list(payload["items"])}

    adapter(url=HTTPS_URL, json=payload, headers=headers, timeout=4)

    assert headers == original_headers
    assert payload == original_payload
    assert request.calls[0][1]["headers"] is headers
    assert request.calls[0][1]["json"] is payload


@pytest.mark.parametrize(
    "url",
    [
        "http://servicos.invalid/path",
        "servicos.invalid/path",
        "https://",
        "https:///path",
        "https://host.invalid:bad/path",
        "https://user@host.invalid/path",
        "https://host.invalid/path#fragment",
        "https://host.invalid/path\rnext",
        None,
    ],
)
def test_invalid_or_non_https_url_fails_before_transport(url):
    request = RecordingRequest()
    with pytest.raises(SerproPkcs12TransportError, match="requisicao SERPRO invalida"):
        transport(request)(url=url, json={}, headers={}, timeout=3)
    assert request.calls == []


@pytest.mark.parametrize(
    "timeout",
    [True, False, 0, -1, math.nan, math.inf, -math.inf, "3", None],
)
def test_invalid_timeout_fails_before_transport(timeout):
    request = RecordingRequest()
    with pytest.raises(SerproPkcs12TransportError, match="requisicao SERPRO invalida"):
        transport(request)(url=HTTPS_URL, json={}, headers={}, timeout=timeout)
    assert request.calls == []


@pytest.mark.parametrize(
    "headers",
    [
        None,
        [],
        {1: "value"},
        {"X-Test": 1},
        {"": "value"},
        {"   ": "value"},
        {"X-Test\rInjected": "value"},
        {"X-Test\nInjected": "value"},
        {"X-Test": "value\rInjected"},
        {"X-Test": "value\nInjected"},
    ],
)
def test_invalid_headers_fail_before_transport(headers):
    request = RecordingRequest()
    with pytest.raises(SerproPkcs12TransportError, match="requisicao SERPRO invalida"):
        transport(request)(url=HTTPS_URL, json={}, headers=headers, timeout=3)
    assert request.calls == []


class DuplicateHeaders(dict):
    def items(self):
        return [("X-Test", "one"), ("x-test", "two")]


def test_case_insensitive_duplicate_headers_fail_before_transport():
    request = RecordingRequest()
    headers = DuplicateHeaders()
    with pytest.raises(SerproPkcs12TransportError, match="requisicao SERPRO invalida"):
        transport(request)(url=HTTPS_URL, json={}, headers=headers, timeout=3)
    assert request.calls == []


class PostEqualNonString:
    def __eq__(self, other):
        return other == "POST"


class RaisingMethodEquality:
    def __eq__(self, other):
        raise RuntimeError("private-method-comparison-detail")


@pytest.mark.parametrize("method", [PostEqualNonString(), RaisingMethodEquality()])
def test_non_string_method_fails_closed_before_transport(method):
    request = RecordingRequest()

    with pytest.raises(SerproPkcs12TransportError, match="requisicao SERPRO invalida"):
        transport(request)(
            method=method, url=HTTPS_URL, json={}, headers={}, timeout=3
        )

    assert request.calls == []


@pytest.mark.parametrize("method", [None, "", "GET\rInjected", 1])
def test_invalid_method_fails_before_transport(method):
    request = RecordingRequest()
    with pytest.raises(SerproPkcs12TransportError, match="requisicao SERPRO invalida"):
        transport(request)(
            method=method, url=HTTPS_URL, json={}, headers={}, timeout=3
        )
    assert request.calls == []


def test_conflicting_body_forms_fail_before_transport():
    request = RecordingRequest()
    with pytest.raises(SerproPkcs12TransportError, match="requisicao SERPRO invalida"):
        transport(request)(
            url=HTTPS_URL, json={}, data="body", headers={}, timeout=3
        )
    assert request.calls == []


@pytest.mark.parametrize(
    "mtls",
    [
        object(),
        Pkcs12Identity(pkcs12_data=b"", pkcs12_password="password"),
        Pkcs12Identity(pkcs12_data=b"container", pkcs12_password=""),
        Pkcs12Identity(
            pkcs12_data=b"container",
            pkcs12_filename="client.p12",
            pkcs12_password="password",
        ),
        Pkcs12Identity(pkcs12_password="password"),
    ],
)
def test_invalid_identity_fails_before_transport(mtls):
    request = RecordingRequest()
    with pytest.raises(SerproPkcs12TransportError, match="configuracao mTLS invalida"):
        SerproPkcs12Transport(mtls_identity=mtls, request=request)
    assert request.calls == []


def test_mismatched_explicit_identity_fails_before_transport():
    request = RecordingRequest()
    adapter = transport(request)
    with pytest.raises(SerproPkcs12TransportError, match="configuracao mTLS invalida"):
        adapter(
            url=HTTPS_URL,
            data="body",
            headers={},
            timeout=3,
            mtls_identity=identity(),
        )
    assert request.calls == []


def test_library_failure_is_sanitized_with_internal_chaining():
    mtls = identity()
    request = RecordingRequest(error=RuntimeError("opaque-library-detail"))
    adapter = transport(request, mtls)

    with pytest.raises(SerproPkcs12TransportError, match="falha no transporte SERPRO") as caught:
        adapter(url=HTTPS_URL, json={}, headers={}, timeout=3)

    rendered = f"{caught.value!r} {caught.value} {adapter!r} {adapter}"
    assert mtls.pkcs12_password not in rendered
    assert mtls.pkcs12_data.decode() not in rendered
    assert "opaque-library-detail" not in rendered
    assert caught.value.__cause__ is request.error
    assert len(request.calls) == 1


def test_no_retry_is_added():
    request = RecordingRequest(error=OSError("opaque-wire-detail"))
    with pytest.raises(SerproPkcs12TransportError):
        transport(request)(url=HTTPS_URL, json={}, headers={}, timeout=3)
    assert len(request.calls) == 1


@pytest.mark.parametrize(
    "method",
    [
        "post",
        " POST",
        "POST ",
        "GET",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
        "HEAD",
        "TRACE",
        "CONNECT",
        "POST\r",
        "POST\n",
        b"POST",
        object(),
    ],
)
def test_only_inventoried_post_method_is_accepted(method):
    request = RecordingRequest()

    with pytest.raises(SerproPkcs12TransportError, match="requisicao SERPRO invalida"):
        transport(request)(
            method=method, url=HTTPS_URL, json={}, headers={}, timeout=3
        )

    assert request.calls == []


@pytest.mark.parametrize(
    "mtls",
    [
        object(),
        Pkcs12Identity(pkcs12_data=b"", pkcs12_password="password"),
        Pkcs12Identity(pkcs12_filename="", pkcs12_password="password"),
        Pkcs12Identity(pkcs12_filename="   ", pkcs12_password="password"),
        Pkcs12Identity(pkcs12_filename=b"\t", pkcs12_password="password"),
        Pkcs12Identity(
            pkcs12_data=b"container",
            pkcs12_filename="client.p12",
            pkcs12_password="password",
        ),
        Pkcs12Identity(pkcs12_password="password"),
    ],
)
def test_invalid_identity_fails_in_constructor_before_default_import(monkeypatch, mtls):
    real_import = builtins.__import__
    imports = []

    def controlled_import(name, *args, **kwargs):
        if name == "requests_pkcs12":
            imports.append(name)
            raise AssertionError("default import must not be attempted")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", controlled_import)

    with pytest.raises(SerproPkcs12TransportError, match="configuracao mTLS invalida"):
        SerproPkcs12Transport(mtls_identity=mtls)

    assert imports == []


@pytest.mark.parametrize("injected_request", [False, 0, "request", object()])
def test_non_callable_injected_request_fails_in_constructor(injected_request):
    with pytest.raises(SerproPkcs12TransportError, match="configuracao mTLS invalida"):
        SerproPkcs12Transport(mtls_identity=identity(), request=injected_request)


def test_default_boundary_delegates_to_requests_pkcs12_request_offline(monkeypatch):
    synthetic_request = RecordingRequest()
    synthetic_module = SimpleNamespace(request=synthetic_request)
    monkeypatch.setitem(sys.modules, "requests_pkcs12", synthetic_module)
    mtls = identity()
    adapter = SerproPkcs12Transport(mtls_identity=mtls)
    headers = {"X-Test": "value"}
    payload = {"opaque": [1]}

    response = adapter(
        method="POST",
        url=HTTPS_URL,
        json=payload,
        headers=headers,
        timeout=4,
    )

    assert response is synthetic_request.response
    assert synthetic_request.calls == [
        (
            ("POST", HTTPS_URL),
            {
                "headers": headers,
                "json": payload,
                "timeout": 4,
                "pkcs12_data": mtls.pkcs12_data,
                "pkcs12_password": mtls.pkcs12_password,
            },
        )
    ]


def test_default_boundary_import_failure_is_publicly_sanitized(monkeypatch):
    real_import = builtins.__import__
    private_detail = "private-import-detail"

    def controlled_import(name, *args, **kwargs):
        if name == "requests_pkcs12":
            raise ImportError(private_detail)
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "requests_pkcs12", raising=False)
    monkeypatch.setattr(builtins, "__import__", controlled_import)

    with pytest.raises(SerproPkcs12TransportError, match="configuracao mTLS invalida") as caught:
        SerproPkcs12Transport(mtls_identity=identity())

    assert private_detail not in str(caught.value)
    assert private_detail not in repr(caught.value)
