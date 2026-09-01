"""Contrato RED offline da aplicacao do checkout one-time baseado em oferta."""

import ast
from dataclasses import replace
from decimal import Decimal
from importlib import import_module
from inspect import Parameter, getsource, signature
from types import SimpleNamespace

import pytest


_USER_ID = 41
_EMPRESA_ID = 301
_OFFER_CODE = "document-one-time-company"
_IDEMPOTENCY_KEY = "application-order-document-301"
_ORDER_ID = 701
_PROVIDER_ORDER_ID = "provider-one-time-4719"
_CHECKOUT_URL = "https://checkout.example.invalid/one-time/provider-4719"
_PRIVATE_VALUES = (
    _OFFER_CODE,
    _IDEMPOTENCY_KEY,
    _PROVIDER_ORDER_ID,
    _CHECKOUT_URL,
    "79.50",
    "document.extract",
    "document.validate",
)


class _OrderComposerSpy:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def iniciar_checkout_empresa(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


class _DispatcherSpy:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def despachar(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


def _request(**changes):
    values = {
        "authenticated_user_id": _USER_ID,
        "empresa_id": _EMPRESA_ID,
        "offer_code": _OFFER_CODE,
        "idempotency_key": _IDEMPOTENCY_KEY,
    }
    values.update(changes)
    return values


def _order_snapshot(composition, **changes):
    snapshot = composition.CheckoutOfferOrderSnapshot(
        id=_ORDER_ID,
        offer_id=17,
        offer_code=_OFFER_CODE,
        contract_version=3,
        vertical="document",
        commercial_model="one_time",
        subject_type="company",
        subject_id=_EMPRESA_ID,
        user_id=_USER_ID,
        valor=Decimal("79.50"),
        moeda="BRL",
        billing_period=None,
        usage_unit="document",
        usage_limit=7,
        capabilities=("document.extract", "document.validate"),
        idempotency_key=_IDEMPOTENCY_KEY,
        estado="pending",
        plano_id=None,
    )
    return replace(snapshot, **changes)


def _dispatch_projection(dispatch, **changes):
    projection = dispatch.CheckoutOfferOneTimeDispatchProjection(
        ordem_id=_ORDER_ID,
        provider_order_id=_PROVIDER_ORDER_ID,
        checkout_url=_CHECKOUT_URL,
    )
    return replace(projection, **changes)


def _assert_opaque(error, application, public_args, *private_values):
    assert type(error) is application.CheckoutOfferOneTimeApplicationError
    assert error.args == public_args
    assert error.__cause__ is None
    if error.__context__ is not None:
        assert error.__suppress_context__ is True
    rendered = f"{error!s} {error!r}".lower()
    for marker in (
        "credential", "credencial", "payload", "secret", "segredo",
        "token", "traceback", "runtimeerror", "sql", "provider-one-time",
    ):
        assert marker not in rendered
    for value in (*_PRIVATE_VALUES, *private_values):
        assert str(value).lower() not in rendered


def _capture_error(application, public_args, operation, *private_values):
    with pytest.raises(
        application.CheckoutOfferOneTimeApplicationError
    ) as captured:
        operation()
    _assert_opaque(
        captured.value, application, public_args, *private_values
    )
    return captured.value


def test_payments_checkout_offer_one_time_application_contract_red():
    application = import_module(
        "app.services.checkout_offer_one_time_application"
    )
    composition = import_module("app.services.checkout_offer_order_composition")
    dispatch = import_module("app.services.checkout_offer_one_time_dispatch")

    assert set(application.__all__) == {
        "CheckoutOfferOneTimeApplicationError",
        "CheckoutOfferOneTimeApplication",
    }
    assert issubclass(
        application.CheckoutOfferOneTimeApplicationError, Exception
    )
    constructor = signature(
        application.CheckoutOfferOneTimeApplication.__init__
    ).parameters
    assert list(constructor) == ["self", "order_composer", "dispatcher"]
    assert all(
        value.default is Parameter.empty
        for name, value in constructor.items() if name != "self"
    )
    method = signature(
        application.CheckoutOfferOneTimeApplication.iniciar_checkout
    ).parameters
    assert list(method) == [
        "self", "authenticated_user_id", "empresa_id", "offer_code",
        "idempotency_key",
    ]
    assert all(
        value.kind is Parameter.KEYWORD_ONLY
        for name, value in method.items() if name != "self"
    )

    tree = ast.parse(getsource(application))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    blocked_roots = {
        "fastapi", "starlette", "sqlalchemy", "sqlite3", "os", "dotenv",
        "requests", "httpx", "socket", "logging", "time", "datetime",
        "tenacity", "backoff", "stripe", "mercadopago",
    }
    assert not {name.split(".")[0] for name in imported_modules} & blocked_roots
    assert not any(name == "app.models" for name in imported_modules)
    assert not any(
        name.startswith("urllib.") and name != "urllib.parse"
        for name in imported_modules
    )

    valid_snapshot = _order_snapshot(composition)
    valid_projection = _dispatch_projection(dispatch)
    untouched_dispatcher = _DispatcherSpy(valid_projection)
    with pytest.raises(
        application.CheckoutOfferOneTimeApplicationError
    ) as invalid_composer:
        application.CheckoutOfferOneTimeApplication(
            order_composer=SimpleNamespace(iniciar_checkout_empresa=17),
            dispatcher=untouched_dispatcher,
        )
    public_args = invalid_composer.value.args
    assert len(public_args) == 1
    assert type(public_args[0]) is str and public_args[0]
    _assert_opaque(invalid_composer.value, application, public_args)
    assert untouched_dispatcher.calls == []

    untouched_composer = _OrderComposerSpy(valid_snapshot)
    _capture_error(
        application,
        public_args,
        lambda: application.CheckoutOfferOneTimeApplication(
            order_composer=untouched_composer,
            dispatcher=SimpleNamespace(despachar=23),
        ),
    )
    assert untouched_composer.calls == []

    composer = _OrderComposerSpy(valid_snapshot)
    dispatcher = _DispatcherSpy(valid_projection)
    service = application.CheckoutOfferOneTimeApplication(
        order_composer=composer, dispatcher=dispatcher
    )
    result = service.iniciar_checkout(**_request())
    assert composer.calls == [_request()]
    assert dispatcher.calls == [{
        "authenticated_user_id": _USER_ID,
        "empresa_id": _EMPRESA_ID,
        "ordem_id": _ORDER_ID,
    }]
    assert type(result) is dict
    assert result == {"checkout_url": _CHECKOUT_URL}

    incoherent_snapshots = [
        SimpleNamespace(**vars(valid_snapshot)),
        _order_snapshot(composition, id=0),
        _order_snapshot(composition, offer_id=0),
        _order_snapshot(composition, offer_code="document-monthly-company"),
        _order_snapshot(composition, contract_version=0),
        _order_snapshot(composition, vertical="document.changed"),
        _order_snapshot(composition, commercial_model="monthly"),
        _order_snapshot(composition, subject_type="cpf"),
        _order_snapshot(composition, subject_id=302),
        _order_snapshot(composition, user_id=42),
        _order_snapshot(composition, valor=Decimal("-79.50")),
        _order_snapshot(composition, moeda="USD"),
        _order_snapshot(composition, billing_period="month"),
        _order_snapshot(composition, usage_unit=None),
        _order_snapshot(composition, usage_limit=0),
        _order_snapshot(
            composition,
            capabilities=("document.validate", "document.extract"),
        ),
        _order_snapshot(
            composition, idempotency_key="application-order-divergent-302"
        ),
        _order_snapshot(composition, estado="paid"),
        _order_snapshot(composition, plano_id=7),
    ]
    for snapshot in incoherent_snapshots:
        composer = _OrderComposerSpy(snapshot)
        dispatcher = _DispatcherSpy(valid_projection)
        service = application.CheckoutOfferOneTimeApplication(composer, dispatcher)
        _capture_error(
            application, public_args,
            lambda service=service: service.iniciar_checkout(**_request()),
        )
        assert composer.calls == [_request()]
        assert dispatcher.calls == []

    composer_secret = "composer-private-payload-token-9081"
    composer = _OrderComposerSpy(error=RuntimeError(composer_secret))
    dispatcher = _DispatcherSpy(valid_projection)
    service = application.CheckoutOfferOneTimeApplication(composer, dispatcher)
    _capture_error(
        application, public_args,
        lambda: service.iniciar_checkout(**_request()), composer_secret,
    )
    assert composer.calls == [_request()]
    assert dispatcher.calls == []

    invalid_projections = [
        SimpleNamespace(**vars(valid_projection)),
        _dispatch_projection(dispatch, ordem_id=702),
        _dispatch_projection(dispatch, provider_order_id=4719),
        _dispatch_projection(
            dispatch, checkout_url="http://checkout.example.invalid/pay"
        ),
        _dispatch_projection(dispatch, checkout_url="/checkout/provider-4719"),
        _dispatch_projection(
            dispatch, checkout_url="https:checkout.example.invalid/pay"
        ),
        _dispatch_projection(
            dispatch,
            checkout_url=(
                "https://owner:private-password@checkout.example.invalid/pay"
            ),
        ),
    ]
    for projection in invalid_projections:
        composer = _OrderComposerSpy(valid_snapshot)
        dispatcher = _DispatcherSpy(projection)
        service = application.CheckoutOfferOneTimeApplication(composer, dispatcher)
        _capture_error(
            application, public_args,
            lambda service=service: service.iniciar_checkout(**_request()),
            "private-password",
        )
        assert composer.calls == [_request()]
        assert dispatcher.calls == [{
            "authenticated_user_id": _USER_ID,
            "empresa_id": _EMPRESA_ID,
            "ordem_id": _ORDER_ID,
        }]

    dispatcher_secret = "dispatcher-private-credential-7741"
    composer = _OrderComposerSpy(valid_snapshot)
    dispatcher = _DispatcherSpy(error=RuntimeError(dispatcher_secret))
    service = application.CheckoutOfferOneTimeApplication(composer, dispatcher)
    _capture_error(
        application, public_args,
        lambda: service.iniciar_checkout(**_request()), dispatcher_secret,
    )
    assert composer.calls == [_request()]
    assert len(dispatcher.calls) == 1
