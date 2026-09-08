import importlib
import inspect


def test_checkout_offer_catalog_main_wiring_contract_red(monkeypatch):
    monkeypatch.setenv("ALEMBIC_RUNNING", "1")

    main = importlib.import_module("app.main")
    catalog_module = importlib.import_module(
        "app.services.checkout_offer_catalog"
    )

    matching_routes = [
        route
        for route in main.app.routes
        if getattr(route, "path", None) == "/checkout/offers"
    ]

    assert len(matching_routes) == 1, (
        "GET /checkout/offers is absent from main.app.routes"
    )

    route = matching_routes[0]
    assert route.methods == {"GET"}
    assert [
        dependency.call for dependency in route.dependant.dependencies
    ] == [main.get_usuario_atual]

    closure = inspect.getclosurevars(route.endpoint)
    catalog_service = closure.nonlocals.get("catalog_service")

    assert type(catalog_service) is catalog_module.CheckoutOfferCatalog
    assert catalog_service._session_factory is main.SessionLocal
