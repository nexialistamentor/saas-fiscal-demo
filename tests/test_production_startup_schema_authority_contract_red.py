"""Contrato RED: startup produtivo não exerce autoridade sobre o schema."""

import asyncio

import pytest


class _InertSession:
    def close(self) -> None:
        pass


def test_production_startup_does_not_mutate_database_schema(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ALEMBIC_RUNNING", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv(
        "SECRET_KEYS",
        "f1a-test=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )

    from app import main as app_main

    if hasattr(app_main, "_PROD"):
        monkeypatch.setattr(app_main, "_PROD", True)

    CREATE_ALL_CALLS = 0
    RUN_MIGRATIONS_CALLS = 0
    STARTUP_BOUNDARY_REACHED = 0

    def record_create_all(*args, **kwargs) -> None:
        nonlocal CREATE_ALL_CALLS
        CREATE_ALL_CALLS += 1

    def record_run_migrations(*args, **kwargs) -> None:
        nonlocal RUN_MIGRATIONS_CALLS
        RUN_MIGRATIONS_CALLS += 1

    def reach_startup_boundary(*args, **kwargs) -> _InertSession:
        nonlocal STARTUP_BOUNDARY_REACHED
        STARTUP_BOUNDARY_REACHED += 1
        return _InertSession()

    def no_op(*args, **kwargs) -> None:
        pass

    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(
        app_main.models.Base.metadata,
        "create_all",
        record_create_all,
    )
    monkeypatch.setattr(app_main, "run_migrations", record_run_migrations)
    monkeypatch.setattr(app_main, "SessionLocal", reach_startup_boundary)
    monkeypatch.setattr(app_main, "ensure_planos", no_op)
    monkeypatch.setattr(app_main, "_startup_purge_request_logs_sync", no_op)
    monkeypatch.setattr(app_main.asyncio, "to_thread", run_inline)
    monkeypatch.setattr(app_main, "ativar_mercado_pago", no_op)

    async def enter_lifespan() -> None:
        async with app_main.lifespan(app_main.app):
            pass

    startup_error = None
    try:
        asyncio.run(enter_lifespan())
    except Exception as exc:  # pragma: no cover - diagnostic preservation
        startup_error = exc

    if STARTUP_BOUNDARY_REACHED != 1:
        pytest.fail("PRODUCTION_STARTUP_BOUNDARY_NOT_REACHED", pytrace=False)

    if startup_error is not None:
        raise startup_error

    if CREATE_ALL_CALLS != 0 or RUN_MIGRATIONS_CALLS != 0:
        pytest.fail(
            "PRODUCTION_STARTUP_RUNTIME_SCHEMA_DDL_PRESENT",
            pytrace=False,
        )

    assert CREATE_ALL_CALLS == 0
    assert RUN_MIGRATIONS_CALLS == 0
    assert STARTUP_BOUNDARY_REACHED == 1
