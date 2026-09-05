"""Contrato RED: a superfície HTTP admin não exerce autoridade de schema."""

import pytest


def test_admin_http_surface_does_not_expose_schema_authority_routes(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ALEMBIC_RUNNING", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv(
        "SECRET_KEYS",
        "f1b-test=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )

    from app import main as app_main

    registered_routes = {
        (method, route.path)
        for route in app_main.app.routes
        for method in (getattr(route, "methods", None) or set())
    }

    forbidden_routes = {
        ("POST", "/admin/create-tables"),
        ("POST", "/admin/fix-usuarios-plano"),
        ("POST", "/admin/fix-planos"),
    }
    legitimate_control_routes = {
        ("POST", "/admin/set-role"),
        ("POST", "/admin/liberar-consulta"),
    }

    missing_controls = legitimate_control_routes - registered_routes
    if missing_controls:
        pytest.fail(
            f"ADMIN_LEGITIMATE_CONTROL_ROUTES_MISSING: {sorted(missing_controls)}",
            pytrace=False,
        )

    present_forbidden_routes = forbidden_routes & registered_routes
    if present_forbidden_routes:
        pytest.fail(
            "ADMIN_RUNTIME_SCHEMA_AUTHORITY_ROUTES_PRESENT: "
            f"{sorted(present_forbidden_routes)}",
            pytrace=False,
        )
