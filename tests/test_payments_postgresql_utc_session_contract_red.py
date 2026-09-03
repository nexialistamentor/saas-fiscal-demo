import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_payments_postgresql_utc_session_contract_red() -> None:
    container = f"mei-0049d0-utc-{uuid.uuid4().hex[:12]}"
    database = "mei_utc_contract"
    password = uuid.uuid4().hex
    port = _free_port()

    try:
        result = _run(
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            container,
            "-e",
            f"POSTGRES_PASSWORD={password}",
            "-e",
            f"POSTGRES_DB={database}",
            "-p",
            f"127.0.0.1:{port}:5432",
            "postgres:16-alpine",
        )
        assert result.returncode == 0, result.stderr

        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            ready = _run(
                "docker",
                "exec",
                container,
                "pg_isready",
                "-U",
                "postgres",
                "-d",
                database,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise AssertionError("PostgreSQL 16 Alpine did not become ready")

        configured = _run(
            "docker",
            "exec",
            container,
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
            "-c",
            f"ALTER DATABASE {database} SET TIME ZONE 'America/Sao_Paulo'",
        )
        assert configured.returncode == 0, configured.stderr

        non_utc_default = _run(
            "docker",
            "exec",
            container,
            "psql",
            "-XAt",
            "-U",
            "postgres",
            "-d",
            database,
            "-c",
            "SHOW TIME ZONE",
        )
        assert non_utc_default.returncode == 0, non_utc_default.stderr
        assert non_utc_default.stdout.strip() == "America/Sao_Paulo"

        probe = """
from sqlalchemy import text

from app.database import engine

with engine.connect() as connection:
    first_timezone = connection.execute(text("SHOW TIME ZONE")).scalar_one()
    assert first_timezone == "UTC", first_timezone
    first_pid = connection.execute(text("SELECT pg_backend_pid()")).scalar_one()
    connection.execute(text("SET TIME ZONE 'America/Sao_Paulo'"))
    connection.commit()

with engine.connect() as connection:
    second_pid = connection.execute(text("SELECT pg_backend_pid()")).scalar_one()
    assert second_pid == first_pid, (first_pid, second_pid)
    second_timezone = connection.execute(text("SHOW TIME ZONE")).scalar_one()
    assert second_timezone == "UTC", second_timezone
    transaction_probe = connection.execute(text("SELECT 1")).scalar_one()
    assert transaction_probe == 1, transaction_probe
    connection.rollback()
    timezone_after_rollback = connection.execute(text("SHOW TIME ZONE")).scalar_one()
    assert timezone_after_rollback == "UTC", timezone_after_rollback

engine.dispose()
"""
        env = os.environ.copy()
        env.update(
            {
                "DATABASE_URL": (
                    f"postgresql+psycopg2://postgres:{password}"
                    f"@127.0.0.1:{port}/{database}?sslmode=disable"
                ),
                "ENVIRONMENT": "development",
                "PYTHONPATH": str(ROOT),
            }
        )
        contract = _run(sys.executable, "-c", probe, env=env)
        assert contract.returncode == 0, contract.stderr
    finally:
        _run("docker", "rm", "--force", container)
