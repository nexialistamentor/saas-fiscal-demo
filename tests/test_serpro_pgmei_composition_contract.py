import base64
import builtins
import copy
import math
import sys

import pytest


SECRETS = {
    "SERPRO_CONSUMER_KEY": "consumer-key-classified",
    "SERPRO_CONSUMER_SECRET": "consumer-secret-classified",
    "SERPRO_PKCS12_FILE": "synthetic-certificate.pfx",
    "SERPRO_PKCS12_PASSWORD": "pkcs12-password-classified",
    "SERPRO_PGMEI_ENDPOINT": "https://pgmei.invalid/consultar",
    "SERPRO_CONTRATANTE": "CONTRATANTE-SYNTHETIC",
}


def enabled_config():
    return {
        "SERPRO_PGMEI_ENABLED": "true",
        **SECRETS,
        "SERPRO_OAUTH_TIMEOUT": "11.5",
        "SERPRO_PGMEI_TIMEOUT": "17.25",
        "SERPRO_OAUTH_SAFE_WINDOW": "4",
    }


class Response:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class QueueRequest:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


def test_missing_or_disabled_gate_has_no_construction_import_certificate_or_io(monkeypatch):
    import app.services.serpro_pgmei_composition as composition

    effects = []
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "requests_pkcs12":
            effects.append("import")
            raise AssertionError("requests_pkcs12 must stay lazy")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(composition, "Pkcs12Identity", lambda **kwargs: effects.append("identity"))
    request = lambda *args, **kwargs: effects.append("io")

    assert composition.compose_serpro_pgmei({}, request=request) is None
    assert composition.compose_serpro_pgmei(
        {"SERPRO_PGMEI_ENABLED": "false"}, request=request
    ) is None
    assert effects == []


@pytest.mark.parametrize("value", ["TRUE", "1", "yes", "on", " false ", True, 1, "invalid"])
def test_invalid_gate_fails_closed(value):
    from app.services.serpro_pgmei_composition import (
        SerproPgmeiCompositionError,
        compose_serpro_pgmei,
    )

    with pytest.raises(SerproPgmeiCompositionError, match="configuracao SERPRO invalida"):
        compose_serpro_pgmei({"SERPRO_PGMEI_ENABLED": value}, request=lambda: None)


@pytest.mark.parametrize("gate", [
    pytest.param(
        type("FalseSpoof", (), {"__eq__": lambda self, other: other == "false"})(),
        id="non-string-equal-to-false",
    ),
    pytest.param(
        type(
            "ExplosiveEquality",
            (),
            {
                "__eq__": lambda self, other: (_ for _ in ()).throw(
                    RuntimeError("private-gate-detail")
                )
            },
        )(),
        id="non-string-equality-raises",
    ),
])
def test_non_string_gate_fails_sanitized_before_construction_import_or_io(
    monkeypatch, gate
):
    import app.services.serpro_pgmei_composition as composition

    effects = []
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "requests_pkcs12":
            effects.append("import")
            raise AssertionError("requests_pkcs12 must stay lazy")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(
        composition,
        "Pkcs12Identity",
        lambda **kwargs: effects.append("identity"),
    )
    request = lambda *args, **kwargs: effects.append("io")

    with pytest.raises(composition.SerproPgmeiCompositionError) as caught:
        composition.compose_serpro_pgmei(
            {"SERPRO_PGMEI_ENABLED": gate}, request=request
        )

    assert caught.value.args == ("configuracao SERPRO invalida",)
    assert caught.value.__cause__ is None
    assert "private-gate-detail" not in f"{caught.value!r} {caught.value}"
    assert effects == []


@pytest.mark.parametrize("missing", sorted(SECRETS))
def test_each_required_setting_is_rejected_before_transport(monkeypatch, missing):
    import app.services.serpro_pgmei_composition as composition

    config = enabled_config()
    config.pop(missing)
    constructed = []
    monkeypatch.setattr(
        composition,
        "SerproPkcs12Transport",
        lambda **kwargs: constructed.append(kwargs),
    )
    with pytest.raises(composition.SerproPgmeiCompositionError):
        composition.compose_serpro_pgmei(config, request=lambda: None)
    assert constructed == []


@pytest.mark.parametrize(
    "name,value",
    [
        ("SERPRO_OAUTH_TIMEOUT", "0"),
        ("SERPRO_OAUTH_TIMEOUT", "nan"),
        ("SERPRO_PGMEI_TIMEOUT", "inf"),
        ("SERPRO_PGMEI_TIMEOUT", "-1"),
        ("SERPRO_OAUTH_SAFE_WINDOW", "-0.1"),
        ("SERPRO_OAUTH_SAFE_WINDOW", "not-a-number"),
    ],
)
def test_invalid_numeric_configuration_fails_before_transport(monkeypatch, name, value):
    import app.services.serpro_pgmei_composition as composition

    config = enabled_config()
    config[name] = value
    constructed = []
    monkeypatch.setattr(
        composition,
        "SerproPkcs12Transport",
        lambda **kwargs: constructed.append(kwargs),
    )
    with pytest.raises(composition.SerproPgmeiCompositionError):
        composition.compose_serpro_pgmei(config, request=lambda: None)
    assert constructed == []


def test_nominal_offline_topology_by_identity_and_input_preservation():
    from app.services.serpro_pgmei_composition import compose_serpro_pgmei
    from app.services.serpro_pgmei_client import SerproPgmeiClient

    config = enabled_config()
    original = copy.deepcopy(config)
    request = QueueRequest([])
    client = compose_serpro_pgmei(config, request=request)

    assert isinstance(client, SerproPgmeiClient)
    authenticated = vars(client)["_transport"]
    session = vars(authenticated)["_session"]
    pkcs12_transport = vars(authenticated)["_downstream"]
    identity = vars(pkcs12_transport)["_mtls_identity"]
    assert vars(session)["_transport"] is pkcs12_transport
    assert vars(session)["_mtls_identity"] is identity
    assert vars(pkcs12_transport)["_request"] is request
    assert vars(client)["_authentication"] == {}
    assert vars(client)["_timeout"] == 17.25
    assert vars(session)["_timeout"] == 11.5
    assert vars(session)["_safe_window"] == 4.0
    assert config == original
    assert request.calls == []


def test_two_call_flow_uses_basic_then_session_bearer_and_same_mtls():
    from app.services.serpro_pgmei_composition import compose_serpro_pgmei

    service = "GERARDASPDF21"
    oauth = Response(
        {
            "access_token": "access-token-synthetic",
            "jwt_token": "jwt-token-synthetic",
            "expires_in": 300,
            "token_type": "Bearer",
        }
    )
    envelope = {
        "status": 200,
        "mensagens": [],
        "dados": "pgmei-result",
        "sistema": "PGMEI",
        "servico": service,
    }
    request = QueueRequest([oauth, Response(envelope)])
    client = compose_serpro_pgmei(enabled_config(), request=request)
    result = client.request(service, "CONTRIBUINTE-SYNTHETIC", "202608")

    assert result.data == "pgmei-result"
    assert len(request.calls) == 2
    auth_call, pgmei_call = request.calls
    expected_basic = base64.b64encode(
        b"consumer-key-classified:consumer-secret-classified"
    ).decode("ascii")
    assert auth_call["headers"] == {
        "Authorization": f"Basic {expected_basic}",
        "role-type": "TERCEIROS",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    assert auth_call["data"] == "grant_type=client_credentials"
    assert auth_call["pkcs12_filename"] == "synthetic-certificate.pfx"
    assert auth_call["pkcs12_password"] == "pkcs12-password-classified"
    assert pgmei_call["headers"]["Authorization"] == "Bearer access-token-synthetic"
    assert pgmei_call["headers"]["jwt_token"] == "jwt-token-synthetic"
    assert pgmei_call["headers"]["Content-Type"] == "application/json"
    assert pgmei_call["pkcs12_filename"] == auth_call["pkcs12_filename"]
    assert pgmei_call["pkcs12_password"] == auth_call["pkcs12_password"]
    assert "json" in pgmei_call and "data" not in pgmei_call
    rendered_payload = repr(pgmei_call["json"])
    for secret in (
        "consumer-key-classified",
        "consumer-secret-classified",
        "pkcs12-password-classified",
        "access-token-synthetic",
        "jwt-token-synthetic",
    ):
        assert secret not in rendered_payload


def test_defaults_are_safe_finite_and_no_environment_is_read_at_import(monkeypatch):
    monkeypatch.setattr("os.getenv", lambda *args, **kwargs: pytest.fail("import read env"))
    sys.modules.pop("app.services.serpro_pgmei_composition", None)
    import app.services.serpro_pgmei_composition as composition

    config = enabled_config()
    for name in (
        "SERPRO_OAUTH_TIMEOUT",
        "SERPRO_PGMEI_TIMEOUT",
        "SERPRO_OAUTH_SAFE_WINDOW",
    ):
        config.pop(name)
    client = composition.compose_serpro_pgmei(config, request=QueueRequest([]))
    session = vars(vars(client)["_transport"])["_session"]
    assert math.isfinite(vars(client)["_timeout"]) and vars(client)["_timeout"] > 0
    assert math.isfinite(vars(session)["_timeout"]) and vars(session)["_timeout"] > 0
    assert math.isfinite(vars(session)["_safe_window"])
    assert vars(session)["_safe_window"] >= 0


def test_constructor_failure_is_public_sanitized_and_has_no_cause(monkeypatch):
    import app.services.serpro_pgmei_composition as composition

    def fail(**kwargs):
        raise RuntimeError("consumer-secret-classified pkcs12-password-classified")

    monkeypatch.setattr(composition, "SerproOAuthSession", fail)
    with pytest.raises(composition.SerproPgmeiCompositionError) as caught:
        composition.compose_serpro_pgmei(enabled_config(), request=lambda: None)
    rendered = f"{caught.value!r} {caught.value}"
    for secret in SECRETS.values():
        assert secret not in rendered
    assert caught.value.__cause__ is None


def test_composed_objects_hide_all_classified_values():
    from app.services.serpro_pgmei_composition import compose_serpro_pgmei

    client = compose_serpro_pgmei(enabled_config(), request=QueueRequest([]))
    authenticated = vars(client)["_transport"]
    session = vars(authenticated)["_session"]
    downstream = vars(authenticated)["_downstream"]
    identity = vars(downstream)["_mtls_identity"]
    rendered = " ".join(f"{value!r} {value}" for value in (client, authenticated, session, downstream, identity))
    for secret in SECRETS.values():
        assert secret not in rendered
