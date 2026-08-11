"""RED: classificacao de violacao idempotente deve ser exacta e fail-closed."""

import sqlite3

from sqlalchemy.exc import IntegrityError

from app.agents import patrol_effect_gate


class _Diag:
    def __init__(self, constraint_name):
        self.constraint_name = constraint_name


class _PgOrig(Exception):
    def __init__(self, constraint_name):
        super().__init__("postgres integrity error")
        self.diag = _Diag(constraint_name)


def _integrity_error(orig):
    return IntegrityError(
        statement="INSERT INTO alertas_fiscais ...",
        params={},
        orig=orig,
    )


def test_patrol_alert_effect_contract_version_is_single_explicit_source():
    assert patrol_effect_gate.PATROL_ALERT_EFFECT_CONTRACT_VERSION == "1.0"


def test_classifier_accepts_exact_postgresql_constraint_name():
    exc = _integrity_error(
        _PgOrig("uq_alertas_fiscais_effect_idempotency_key")
    )

    assert patrol_effect_gate._is_effect_idempotency_unique_violation(exc) is True


def test_classifier_rejects_other_postgresql_constraint():
    exc = _integrity_error(
        _PgOrig("fk_alertas_fiscais_relatorio_analise_id")
    )

    assert patrol_effect_gate._is_effect_idempotency_unique_violation(exc) is False


def test_classifier_rejects_postgresql_without_constraint_name():
    exc = _integrity_error(_PgOrig(None))

    assert patrol_effect_gate._is_effect_idempotency_unique_violation(exc) is False


def test_classifier_does_not_fallback_to_sqlite_text_when_pg_diag_exists():
    exc = _integrity_error(
        _PgOrig(None)
    )
    exc.orig.args = (
        "UNIQUE constraint failed: "
        "alertas_fiscais.effect_idempotency_key",
    )

    assert patrol_effect_gate._is_effect_idempotency_unique_violation(exc) is False


def test_classifier_accepts_exact_sqlite_unique_signature():
    exc = _integrity_error(
        sqlite3.IntegrityError(
            "UNIQUE constraint failed: "
            "alertas_fiscais.effect_idempotency_key"
        )
    )

    assert patrol_effect_gate._is_effect_idempotency_unique_violation(exc) is True


def test_classifier_rejects_other_sqlite_unique():
    exc = _integrity_error(
        sqlite3.IntegrityError(
            "UNIQUE constraint failed: alertas_fiscais.tipo"
        )
    )

    assert patrol_effect_gate._is_effect_idempotency_unique_violation(exc) is False


def test_classifier_rejects_non_unique_integrity_error():
    exc = _integrity_error(
        sqlite3.IntegrityError(
            "NOT NULL constraint failed: alertas_fiscais.tipo"
        )
    )

    assert patrol_effect_gate._is_effect_idempotency_unique_violation(exc) is False
