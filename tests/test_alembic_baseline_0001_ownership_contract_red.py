"""Contrato RED para ownership historico entre as revisions 0000 e 0001."""

import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

import pytest


ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = ROOT / "alembic.ini"
TARGET_PLANOS_COLUMNS = {
    "preco",
    "billing_type",
    "ativo",
    "tipo_acesso",
}


def _database_url(database_path: Path) -> str:
    return f"sqlite:///{database_path.resolve().as_posix()}"


def _run_alembic(
    database_path: Path, *arguments: str
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ENVIRONMENT"] = "development"
    env["DATABASE_URL"] = _database_url(database_path)
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(ROOT), env.get("PYTHONPATH", "")) if part
    )

    return subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ALEMBIC_INI),
            *arguments,
        ],
        cwd=database_path.parent,
        env=env,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in (result.stdout, result.stderr) if part).strip()


def _planos_columns(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(planos)").fetchall()
        }


def _revision(database_path: Path) -> str | None:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
    return None if row is None else str(row[0])


def _require_baseline(database_path: Path) -> None:
    result = _run_alembic(database_path, "upgrade", "0000_baseline")
    output = _combined_output(result)
    if result.returncode != 0:
        pytest.fail(
            f"STOP_NON_CAUSAL_BASELINE: returncode={result.returncode}\n{output}",
            pytrace=False,
        )

    columns = _planos_columns(database_path)
    if not columns or not TARGET_PLANOS_COLUMNS.issubset(columns):
        pytest.fail("STOP_NON_CAUSAL_BASELINE: planos schema mismatch", pytrace=False)
    if _revision(database_path) != "0000_baseline":
        pytest.fail("STOP_NON_CAUSAL_BASELINE: revision mismatch", pytrace=False)


def test_0000_baseline_owns_planos_financial_columns() -> None:
    with TemporaryDirectory(ignore_cleanup_errors=True) as temporary_directory:
        database_path = Path(temporary_directory) / "baseline.db"
        _require_baseline(database_path)


def test_upgrade_0000_to_0001_is_a_planos_financial_columns_noop() -> None:
    with TemporaryDirectory(ignore_cleanup_errors=True) as temporary_directory:
        database_path = Path(temporary_directory) / "upgrade.db"
        _require_baseline(database_path)

        result = _run_alembic(database_path, "upgrade", "0001_expand_planos")
        output = _combined_output(result)
        if result.returncode != 0:
            normalized_output = output.lower()
            duplicate_column = (
                "duplicate column" in normalized_output
                or "already exists" in normalized_output
            )
            target_named = any(
                column in normalized_output for column in TARGET_PLANOS_COLUMNS
            )
            if duplicate_column and target_named:
                pytest.fail(
                    "ALEMBIC_0001_REAPPLIES_BASELINE_PLANOS_COLUMNS",
                    pytrace=False,
                )
            pytest.fail(
                f"STOP_NON_CAUSAL_0001_UPGRADE: returncode={result.returncode}\n"
                f"{output}",
                pytrace=False,
            )

        columns = _planos_columns(database_path)
        if not TARGET_PLANOS_COLUMNS.issubset(columns):
            pytest.fail(
                "STOP_NON_CAUSAL_0001_UPGRADE: planos schema mismatch",
                pytrace=False,
            )
        if _revision(database_path) != "0001_expand_planos":
            pytest.fail(
                "STOP_NON_CAUSAL_0001_UPGRADE: revision mismatch",
                pytrace=False,
            )


def test_downgrade_0001_to_0000_preserves_baseline_planos_columns() -> None:
    with TemporaryDirectory(ignore_cleanup_errors=True) as temporary_directory:
        database_path = Path(temporary_directory) / "downgrade.db"
        _require_baseline(database_path)

        stamp_result = _run_alembic(
            database_path, "stamp", "0001_expand_planos"
        )
        stamp_output = _combined_output(stamp_result)
        if stamp_result.returncode != 0:
            pytest.fail(
                "STOP_NON_CAUSAL_0001_DOWNGRADE: "
                f"stamp returncode={stamp_result.returncode}\n{stamp_output}",
                pytrace=False,
            )
        if _revision(database_path) != "0001_expand_planos":
            pytest.fail(
                "STOP_NON_CAUSAL_0001_DOWNGRADE: stamp revision mismatch",
                pytrace=False,
            )

        result = _run_alembic(database_path, "downgrade", "0000_baseline")
        output = _combined_output(result)
        if result.returncode != 0:
            pytest.fail(
                f"STOP_NON_CAUSAL_0001_DOWNGRADE: returncode={result.returncode}\n"
                f"{output}",
                pytrace=False,
            )
        if _revision(database_path) != "0000_baseline":
            pytest.fail(
                "STOP_NON_CAUSAL_0001_DOWNGRADE: revision mismatch",
                pytrace=False,
            )

        columns = _planos_columns(database_path)
        if not TARGET_PLANOS_COLUMNS.issubset(columns):
            pytest.fail(
                "ALEMBIC_0001_DOWNGRADE_DROPS_BASELINE_PLANOS_COLUMNS",
                pytrace=False,
            )
