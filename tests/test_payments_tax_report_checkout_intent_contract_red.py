"""RED: intencao duravel e append-only do checkout ``tax.report``.

Este contrato cobre apenas o congelamento da correspondencia entre uma chave de
checkout e um relatorio persistido. Nao cobre criacao/pagamento de ordem,
grants, aquisicao, Mercado Pago, HTTP, PDF, frontend ou publicacao da oferta.
"""

from dataclasses import FrozenInstanceError, fields, is_dataclass
from inspect import getsource, signature
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import InvalidRequestError, SQLAlchemyError
from sqlalchemy.orm import Session

from app import models
from app.services.resultado_provenance_service import (
    fingerprint_resultado_json,
    selar_resultado_nao_mei,
)


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations/versions/0053_tax_report_checkout_intents.py"
SERVICE = ROOT / "app/services/tax_report_checkout_intent.py"
OFFER_CODE = "tax-report-one-time-company"
RESULT_FIELDS = (
    "intent_id",
    "checkout_idempotency_key",
    "user_id",
    "empresa_id",
    "relatorio_analise_id",
    "offer_code",
    "request_fingerprint",
    "created_at",
)


def _future_contract():
    assert hasattr(models, "TaxReportCheckoutIntent"), (
        "ausente modelo append-only TaxReportCheckoutIntent"
    )
    from app.services.tax_report_checkout_intent import (  # noqa: PLC0415
        TaxReportCheckoutIntent,
        TaxReportCheckoutIntentError,
        TaxReportCheckoutIntentResult,
    )

    return (
        models.TaxReportCheckoutIntent,
        TaxReportCheckoutIntent,
        TaxReportCheckoutIntentError,
        TaxReportCheckoutIntentResult,
    )


def _engine(model):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    models.Base.metadata.create_all(
        engine,
        tables=(models.RelatorioAnalise.__table__, model.__table__),
    )
    return engine


def _seed_report(
    db,
    *,
    report_id=501,
    user_id=11,
    empresa_id=21,
    status="ok",
    valid_provenance=True,
    stored_fingerprint=None,
):
    payload = {"tributo": "DAS", "total": 125.75}
    if valid_provenance:
        payload = selar_resultado_nao_mei(payload, producer_id="app.tax.engine")
    fingerprint = fingerprint_resultado_json(payload)
    if stored_fingerprint is not None:
        fingerprint = stored_fingerprint
    report = models.RelatorioAnalise(
        id=report_id,
        user_id=user_id,
        empresa_id=empresa_id,
        analysis_type="empresa_tax",
        status=status,
        resultado_json=payload,
        fingerprint=fingerprint,
        pago=False,
    )
    db.add(report)
    db.commit()
    return fingerprint


def _persist(service_type, db, *, fingerprint, **changes):
    values = {
        "user_id": 11,
        "empresa_id": 21,
        "relatorio_id": 501,
        "offer_code": OFFER_CODE,
        "checkout_idempotency_key": "checkout-intent-1",
        "request_fingerprint": fingerprint,
    }
    values.update(changes)
    return service_type(db).persist(**values)


def test_model_contract_red():
    model, _, _, _ = _future_contract()
    table = model.__table__
    assert table.name == "tax_report_checkout_intents"
    assert set(table.columns.keys()) == {
        "id",
        "checkout_idempotency_key",
        "user_id",
        "empresa_id",
        "relatorio_analise_id",
        "offer_code",
        "request_fingerprint",
        "created_at",
    }
    assert table.c.id.primary_key
    assert table.c.checkout_idempotency_key.type.length == 255
    assert table.c.checkout_idempotency_key.nullable is False
    assert table.c.checkout_idempotency_key.unique
    assert table.c.offer_code.type.length == 120
    assert table.c.request_fingerprint.type.length == 64
    assert table.c.created_at.nullable is False
    assert table.c.created_at.server_default is not None
    for column, target in (
        (table.c.user_id, "usuarios.id"),
        (table.c.empresa_id, "empresas.id"),
        (table.c.relatorio_analise_id, "relatorios_analise.id"),
    ):
        assert column.nullable is False
        assert column.index
        foreign_keys = tuple(column.foreign_keys)
        assert len(foreign_keys) == 1
        assert foreign_keys[0].target_fullname == target


def test_migration_is_narrow_and_append_only_red():
    assert MIGRATION.is_file(), "ausente migration 0053 da intencao duravel"
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "0053_tax_report_checkout_intents"' in source
    assert 'down_revision: str = "0052_tax_report_acquisition_bindings"' in source
    assert source.count("op.create_table(") == 1
    assert '"tax_report_checkout_intents"' in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "CREATE FUNCTION" in source and "CREATE TRIGGER" in source
    assert "DROP TRIGGER" in source and "DROP FUNCTION" in source
    assert "op.drop_index(" in source and "op.drop_table(" in source
    for existing_table in (
        "ordens_checkout",
        "checkout_offer_grants",
        "checkout_offer_grant_consumptions",
        "tax_report_acquisition_bindings",
    ):
        assert f'op.alter_column("{existing_table}"' not in source
        assert f'op.drop_table("{existing_table}"' not in source


def test_service_api_projection_and_authority_boundary_red():
    _, service_type, error_type, result_type = _future_contract()
    assert issubclass(error_type, Exception)
    assert tuple(signature(service_type.persist).parameters) == (
        "self",
        "user_id",
        "empresa_id",
        "relatorio_id",
        "offer_code",
        "checkout_idempotency_key",
        "request_fingerprint",
    )
    assert is_dataclass(result_type)
    assert tuple(field.name for field in fields(result_type)) == RESULT_FIELDS
    assert result_type.__dataclass_params__.frozen

    source = SERVICE.read_text(encoding="utf-8")
    assert "verificar_resultado_persistido" in source
    assert "compare_digest" in source
    assert ".commit(" not in source
    assert ".rollback(" not in source
    for forbidden in (
        "OrdemCheckout",
        "CheckoutOfferGrant",
        "TaxReportAcquisitionBinding",
        "MercadoPago",
        "mercado_pago",
        "consulta_paga",
        ".pago",
        "payment_id",
        "requests.",
        "httpx.",
    ):
        assert forbidden not in source


def test_valid_persistence_exact_retry_divergence_and_no_commit_red():
    model, service_type, error_type, result_type = _future_contract()
    engine = _engine(model)
    try:
        with Session(engine) as setup:
            fingerprint = _seed_report(setup)
        with Session(engine) as db:
            result = _persist(service_type, db, fingerprint=fingerprint)
            assert isinstance(result, result_type)
            assert tuple(vars(result)) == RESULT_FIELDS
            assert result.intent_id is not None
            assert result.request_fingerprint == fingerprint
            with pytest.raises(FrozenInstanceError):
                result.offer_code = "adulterado"

            replay = _persist(service_type, db, fingerprint=fingerprint)
            assert replay == result
            assert db.scalar(select(func.count()).select_from(model)) == 1

            for changed in (
                {"user_id": 12},
                {"empresa_id": 22},
                {"relatorio_id": 502},
                {"offer_code": "outro"},
                {"request_fingerprint": "f" * 64},
            ):
                with pytest.raises(error_type):
                    _persist(service_type, db, fingerprint=fingerprint, **changed)
                assert db.scalar(select(func.count()).select_from(model)) == 1
            intent_id = result.intent_id
            db.rollback()

        with Session(engine) as verification:
            assert verification.get(model, intent_id) is None, (
                "persist() fez commit; rollback do chamador deveria remover a intencao"
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("report_changes", "call_changes"),
    (
        ({"user_id": 99}, {}),
        ({"empresa_id": 99}, {}),
        ({"status": "processando"}, {}),
        ({"valid_provenance": False}, {}),
        ({"stored_fingerprint": "0" * 64}, {}),
        ({}, {"request_fingerprint": "f" * 64}),
    ),
)
def test_report_authority_fails_closed_red(report_changes, call_changes):
    model, service_type, error_type, _ = _future_contract()
    engine = _engine(model)
    try:
        with Session(engine) as db:
            fingerprint = _seed_report(db, **report_changes)
            with pytest.raises(error_type):
                _persist(service_type, db, fingerprint=fingerprint, **call_changes)
            db.rollback()
            assert db.scalar(select(func.count()).select_from(model)) == 0
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "changes",
    (
        {"user_id": True},
        {"user_id": 0},
        {"empresa_id": -1},
        {"relatorio_id": False},
        {"checkout_idempotency_key": ""},
        {"checkout_idempotency_key": "x" * 256},
        {"checkout_idempotency_key": " chave"},
        {"checkout_idempotency_key": "chave\ncontrole"},
        {"offer_code": "tax.report"},
        {"request_fingerprint": "A" * 64},
        {"request_fingerprint": "g" * 64},
        {"request_fingerprint": "a" * 63},
    ),
)
def test_input_validation_fails_closed_red(changes):
    model, service_type, error_type, _ = _future_contract()
    engine = _engine(model)
    try:
        with Session(engine) as db:
            fingerprint = _seed_report(db)
            with pytest.raises(error_type):
                _persist(service_type, db, fingerprint=fingerprint, **changes)
            db.rollback()
            assert db.scalar(select(func.count()).select_from(model)) == 0
    finally:
        engine.dispose()


def test_intent_is_append_only_at_orm_boundary_red():
    model, service_type, _, _ = _future_contract()
    engine = _engine(model)
    try:
        with Session(engine) as db:
            fingerprint = _seed_report(db)
            result = _persist(service_type, db, fingerprint=fingerprint)
            db.commit()
            row = db.get(model, result.intent_id)
            row.offer_code = "adulterado"
            with pytest.raises(InvalidRequestError):
                db.flush()
            db.rollback()
            db.delete(db.get(model, result.intent_id))
            with pytest.raises(InvalidRequestError):
                db.flush()
            db.rollback()
            assert db.get(model, result.intent_id) is not None
    finally:
        engine.dispose()


def test_sqlalchemy_failure_is_opaque_and_does_not_rollback_caller_red(monkeypatch):
    model, service_type, error_type, _ = _future_contract()
    engine = _engine(model)
    try:
        with Session(engine) as db:
            fingerprint = _seed_report(db)
            rollback_calls = 0

            def forbidden_rollback():
                nonlocal rollback_calls
                rollback_calls += 1

            monkeypatch.setattr(db, "rollback", forbidden_rollback)

            def broken_flush(*_args, **_kwargs):
                raise SQLAlchemyError("secret-row-and-driver-detail")

            monkeypatch.setattr(db, "flush", broken_flush)
            with pytest.raises(error_type) as captured:
                _persist(service_type, db, fingerprint=fingerprint)
            assert "secret-row-and-driver-detail" not in str(captured.value)
            assert rollback_calls == 0
    finally:
        engine.dispose()
