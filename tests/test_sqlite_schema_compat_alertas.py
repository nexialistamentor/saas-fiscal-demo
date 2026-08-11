"""RED: compatibilidade SQLite legada de alertas_fiscais preserva idempotência física."""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app import database


def _create_legacy_alertas_table(engine, *, with_effect_key: bool) -> None:
    effect_column = (
        "effect_idempotency_key VARCHAR(64),"
        if with_effect_key
        else ""
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE alertas_fiscais (
                    id INTEGER PRIMARY KEY,
                    {effect_column}
                    agente VARCHAR,
                    tipo VARCHAR,
                    descricao VARCHAR,
                    nivel VARCHAR,
                    empresa_id INTEGER,
                    relatorio_analise_id INTEGER,
                    criado_em DATETIME,
                    silenciado BOOLEAN,
                    processado BOOLEAN NOT NULL DEFAULT 0,
                    processado_em DATETIME,
                    processado_por VARCHAR(100),
                    notas_resolucao VARCHAR(1000)
                )
                """
            )
        )


def _install_temp_sqlite(
    monkeypatch,
    tmp_path,
    *,
    with_effect_key: bool,
):
    db_path = tmp_path / "legacy_alertas.db"
    url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(url)

    _create_legacy_alertas_table(
        engine,
        with_effect_key=with_effect_key,
    )

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "DATABASE_URL", url)

    return engine


def test_sqlite_schema_compat_adds_alert_effect_idempotency_column(
    monkeypatch,
    tmp_path,
):
    engine = _install_temp_sqlite(
        monkeypatch,
        tmp_path,
        with_effect_key=False,
    )

    try:
        database.ensure_sqlite_schema_compat()

        columns = {
            column["name"]
            for column in inspect(engine).get_columns("alertas_fiscais")
        }

        assert "effect_idempotency_key" in columns
    finally:
        engine.dispose()


def test_sqlite_schema_compat_rejects_duplicate_non_null_effect_key(
    monkeypatch,
    tmp_path,
):
    engine = _install_temp_sqlite(
        monkeypatch,
        tmp_path,
        with_effect_key=True,
    )

    try:
        database.ensure_sqlite_schema_compat()

        key = "a" * 64

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO alertas_fiscais (effect_idempotency_key)
                    VALUES (:key)
                    """
                ),
                {"key": key},
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO alertas_fiscais (effect_idempotency_key)
                        VALUES (:key)
                        """
                    ),
                    {"key": key},
                )
    finally:
        engine.dispose()


def test_sqlite_schema_compat_allows_multiple_null_effect_keys(
    monkeypatch,
    tmp_path,
):
    engine = _install_temp_sqlite(
        monkeypatch,
        tmp_path,
        with_effect_key=True,
    )

    try:
        database.ensure_sqlite_schema_compat()

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO alertas_fiscais (effect_idempotency_key)
                    VALUES (NULL), (NULL)
                    """
                )
            )

            count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM alertas_fiscais
                    WHERE effect_idempotency_key IS NULL
                    """
                )
            ).scalar_one()

        assert count == 2
    finally:
        engine.dispose()
