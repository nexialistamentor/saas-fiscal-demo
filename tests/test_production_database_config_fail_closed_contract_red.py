"""Contrato RED: configuracao produtiva de banco falha fechada."""

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

import pytest


ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = ROOT / "alembic.ini"
DATABASE_CONFIG_ERROR_TYPE = "app.database.DatabaseConfigError"

RUNTIME_REJECTION_PROBE = r"""
import importlib
import sys
import traceback

try:
    importlib.import_module("app.database")
except Exception as exc:
    error_type = f"{type(exc).__module__}.{type(exc).__name__}"
    if error_type == "app.database.DatabaseConfigError":
        print("DATABASE_CONFIG_ERROR_REJECTED")
        raise SystemExit(0)
    print(f"INCIDENTAL_ERROR_TYPE={error_type}")
    traceback.print_exc()
    raise SystemExit(20)

print(sys.argv[1])
raise SystemExit(10)
"""

RUNTIME_ACCEPTANCE_PROBE = r"""
import importlib

importlib.import_module("app.database")
print("DATABASE_CONFIG_ACCEPTED")
"""


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(ROOT), env.get("PYTHONPATH", "")) if part
    )
    return env


def _run_runtime_probe(
    *, environment: str, database_url: str | None, rejection_marker: str | None
) -> subprocess.CompletedProcess[str]:
    env = _base_env()
    env["ENVIRONMENT"] = environment
    env.pop("ALEMBIC_RUNNING", None)
    if database_url is None:
        env.pop("DATABASE_URL", None)
    else:
        env["DATABASE_URL"] = database_url

    probe = RUNTIME_REJECTION_PROBE if rejection_marker else RUNTIME_ACCEPTANCE_PROBE
    command = [sys.executable, "-c", probe]
    if rejection_marker:
        command.append(rejection_marker)

    with TemporaryDirectory(ignore_cleanup_errors=True) as temporary_directory:
        return subprocess.run(
            command,
            cwd=temporary_directory,
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in (result.stdout, result.stderr) if part).strip()


def _require_runtime_rejection(
    *, environment: str, database_url: str | None, marker: str
) -> None:
    result = _run_runtime_probe(
        environment=environment,
        database_url=database_url,
        rejection_marker=marker,
    )
    output = _combined_output(result)
    if result.returncode == 10 and marker in output:
        pytest.fail(marker, pytrace=False)
    if result.returncode != 0:
        pytest.fail(
            f"STOP_NON_CAUSAL_RUNTIME: returncode={result.returncode}\n{output}",
            pytrace=False,
        )
    assert "DATABASE_CONFIG_ERROR_REJECTED" in output


def _require_runtime_acceptance(
    *, environment: str, database_url: str, alembic_running: bool = False
) -> None:
    env = _base_env()
    env["ENVIRONMENT"] = environment
    env["DATABASE_URL"] = database_url
    if alembic_running:
        env["ALEMBIC_RUNNING"] = "1"
    else:
        env.pop("ALEMBIC_RUNNING", None)

    with TemporaryDirectory(ignore_cleanup_errors=True) as temporary_directory:
        result = subprocess.run(
            [sys.executable, "-c", RUNTIME_ACCEPTANCE_PROBE],
            cwd=temporary_directory,
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )

    output = _combined_output(result)
    if result.returncode != 0:
        pytest.fail(
            f"STOP_NON_CAUSAL_RUNTIME_CONTROL: returncode={result.returncode}\n{output}",
            pytrace=False,
        )
    assert "DATABASE_CONFIG_ACCEPTED" in output


def _run_alembic_current(
    *, environment: str, database_url: str | None
) -> subprocess.CompletedProcess[str]:
    env = _base_env()
    env["ENVIRONMENT"] = environment
    env.pop("ALEMBIC_RUNNING", None)
    if database_url is None:
        env.pop("DATABASE_URL", None)
    else:
        env["DATABASE_URL"] = database_url

    with TemporaryDirectory(ignore_cleanup_errors=True) as temporary_directory:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                str(ALEMBIC_INI),
                "current",
            ],
            cwd=temporary_directory,
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )


def _require_alembic_rejection(*, database_url: str | None, marker: str) -> None:
    result = _run_alembic_current(
        environment="production",
        database_url=database_url,
    )
    output = _combined_output(result)
    if result.returncode == 0:
        pytest.fail(marker, pytrace=False)
    if DATABASE_CONFIG_ERROR_TYPE not in output:
        pytest.fail(
            f"STOP_NON_CAUSAL_ALEMBIC: returncode={result.returncode}\n{output}",
            pytrace=False,
        )


def test_runtime_production_rejects_missing_database_url() -> None:
    _require_runtime_rejection(
        environment="production",
        database_url=None,
        marker="PRODUCTION_DATABASE_URL_MISSING_ACCEPTED",
    )


def test_runtime_production_rejects_sqlite_database_url() -> None:
    _require_runtime_rejection(
        environment="production",
        database_url="sqlite:///:memory:",
        marker="PRODUCTION_SQLITE_DATABASE_ACCEPTED",
    )


def test_runtime_development_accepts_sqlite_control() -> None:
    _require_runtime_acceptance(
        environment="development",
        database_url="sqlite:///:memory:",
        alembic_running=True,
    )


def test_runtime_production_accepts_secure_postgresql_control() -> None:
    _require_runtime_acceptance(
        environment="production",
        database_url=(
            "postgresql://f1c:f1c@127.0.0.1:1/f1c?sslmode=verify-full"
        ),
    )


def test_alembic_production_rejects_missing_database_url() -> None:
    _require_alembic_rejection(
        database_url=None,
        marker="ALEMBIC_PRODUCTION_DATABASE_URL_MISSING_ACCEPTED",
    )


def test_alembic_production_rejects_sqlite_database_url() -> None:
    _require_alembic_rejection(
        database_url="sqlite:///:memory:",
        marker="ALEMBIC_PRODUCTION_SQLITE_DATABASE_ACCEPTED",
    )


def test_alembic_development_accepts_sqlite_control() -> None:
    result = _run_alembic_current(
        environment="development",
        database_url="sqlite:///./f1c-development-control.db",
    )
    output = _combined_output(result)
    if result.returncode != 0:
        pytest.fail(
            f"STOP_NON_CAUSAL_ALEMBIC_CONTROL: returncode={result.returncode}\n{output}",
            pytrace=False,
        )
