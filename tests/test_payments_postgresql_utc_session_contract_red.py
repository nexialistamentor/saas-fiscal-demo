import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg2


ROOT = Path(__file__).resolve().parents[1]


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
    container_started = False

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
            "127.0.0.1::5432",
            "postgres:16-alpine",
        )
        assert result.returncode == 0, result.stderr
        container_started = True

        published = _run("docker", "port", container, "5432/tcp")
        assert published.returncode == 0, published.stderr
        mappings = [line.strip() for line in published.stdout.splitlines() if line.strip()]
        assert len(mappings) == 1, mappings
        host, separator, raw_port = mappings[0].rpartition(":")
        assert separator == ":", mappings[0]
        assert host == "127.0.0.1", host
        assert raw_port.isascii() and raw_port.isdigit(), raw_port
        host_port = int(raw_port)
        assert 1 <= host_port <= 65535, host_port

        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            connection = None
            try:
                connection = psycopg2.connect(
                    host="127.0.0.1",
                    port=host_port,
                    dbname=database,
                    user="postgres",
                    password=password,
                    connect_timeout=1,
                )
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    readiness_probe = cursor.fetchone()
                assert readiness_probe == (1,), readiness_probe
                break
            except psycopg2.Error:
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(min(0.25, remaining))
            finally:
                if connection is not None:
                    connection.close()
        else:
            raise AssertionError("PostgreSQL 16 Alpine did not become ready over published TCP")

        configuration_connection = psycopg2.connect(
            host="127.0.0.1",
            port=host_port,
            dbname="postgres",
            user="postgres",
            password=password,
            connect_timeout=1,
        )
        try:
            configuration_connection.autocommit = True
            with configuration_connection.cursor() as cursor:
                cursor.execute(
                    "ALTER DATABASE mei_utc_contract SET TIME ZONE 'America/Sao_Paulo'"
                )
        finally:
            configuration_connection.close()

        default_connection = psycopg2.connect(
            host="127.0.0.1",
            port=host_port,
            dbname=database,
            user="postgres",
            password=password,
            connect_timeout=1,
        )
        try:
            with default_connection.cursor() as cursor:
                cursor.execute("SHOW TIME ZONE")
                non_utc_default = cursor.fetchone()
            assert non_utc_default == ("America/Sao_Paulo",), non_utc_default
        finally:
            default_connection.close()

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
                    f"@127.0.0.1:{host_port}/{database}?sslmode=disable"
                ),
                "ENVIRONMENT": "development",
                "PYTHONPATH": str(ROOT),
            }
        )
        contract = _run(sys.executable, "-c", probe, env=env)
        assert contract.returncode == 0, contract.stderr
    finally:
        if container_started:
            _run("docker", "rm", "--force", container)
