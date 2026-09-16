"""RED: leitura canonica de uma aquisicao tax.report ja persistida."""

from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from inspect import getsource, signature

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app import models
from app.services.resultado_provenance_service import fingerprint_resultado_json


CAPABILITY = "tax.report"
USER_ID = 11
EMPRESA_ID = 21


def _future_contract():
    from app.services.tax_report_acquisition_reader import (  # noqa: PLC0415
        TaxReportAcquisitionReader,
        TaxReportAcquisitionReadError,
    )

    return TaxReportAcquisitionReader, TaxReportAcquisitionReadError


def _engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    models.Base.metadata.create_all(
        engine,
        tables=(
            models.User.__table__,
            models.Empresa.__table__,
            models.CheckoutOffer.__table__,
            models.OrdemCheckout.__table__,
            models.CheckoutOfferGrant.__table__,
            models.CheckoutOfferGrantConsumption.__table__,
            models.RelatorioAnalise.__table__,
            models.TaxReportAcquisitionBinding.__table__,
        ),
    )
    return engine


def _snapshot(tag="original"):
    return {"report": {"tag": tag, "items": [{"tributo": "DAS", "total": 125.75}]}}


def _seed(
    db,
    *,
    suffix=1,
    grant_state="active",
    usage_limit=2,
    usage_consumed=1,
    order_state="paid",
    order_user_id=USER_ID,
    order_empresa_id=EMPRESA_ID,
    consumption_user_id=USER_ID,
    consumption_empresa_id=EMPRESA_ID,
    capability=CAPABILITY,
    units=1,
    binding_fingerprint=None,
    consumption_fingerprint=None,
    consumption_id_override=None,
    grant_id_override=None,
    snapshot=None,
):
    offer_id = 100 + suffix
    order_id = 200 + suffix
    grant_id = 300 + suffix
    consumption_id = 400 + suffix
    report_id = 500 + suffix
    binding_id = 600 + suffix
    snapshot = deepcopy(snapshot if snapshot is not None else _snapshot(str(suffix)))
    fingerprint = (
        fingerprint_resultado_json(snapshot)
        if isinstance(snapshot, dict)
        else "a" * 64
    )
    binding_fingerprint = (
        fingerprint if binding_fingerprint is None else binding_fingerprint
    )
    consumption_fingerprint = (
        binding_fingerprint
        if consumption_fingerprint is None
        else consumption_fingerprint
    )

    offer = models.CheckoutOffer(
        id=offer_id,
        codigo=f"tax-report-read-{suffix}",
        nome_publico="Relatorio fiscal",
        vertical="tax",
        commercial_model="one_time",
        subject_type="company",
        estado="published",
        moeda="BRL",
        preco=Decimal("49.90"),
        billing_period=None,
        usage_unit="report",
        usage_limit=usage_limit,
        contract_version=1,
    )
    order = models.OrdemCheckout(
        id=order_id,
        user_id=order_user_id,
        empresa_id=order_empresa_id,
        plano_id=None,
        offer_id=offer_id,
        offer_code=offer.codigo,
        contract_version=1,
        vertical="tax",
        commercial_model="one_time",
        subject_type="company",
        subject_id=order_empresa_id,
        valor=Decimal("49.90"),
        moeda="BRL",
        estado=order_state,
        idempotency_key=f"read-order-{suffix}",
        billing_period=None,
        usage_unit="report",
        usage_limit=usage_limit,
    )
    grant = models.CheckoutOfferGrant(
        id=grant_id,
        ordem_id=order_id,
        usage_unit="report",
        usage_limit=usage_limit,
        usage_consumed=usage_consumed,
        estado=grant_state,
    )
    report = models.RelatorioAnalise(
        id=report_id,
        user_id=USER_ID,
        empresa_id=EMPRESA_ID,
        analysis_type="empresa_tax",
        status="ok",
        resultado_json=deepcopy(snapshot),
        fingerprint=fingerprint,
        pago=True,
    )
    consumption = models.CheckoutOfferGrantConsumption(
        id=consumption_id,
        grant_id=grant_id if grant_id_override is None else grant_id_override,
        user_id=consumption_user_id,
        empresa_id=consumption_empresa_id,
        capability=capability,
        idempotency_key=f"read-consumption-{suffix}",
        request_fingerprint=consumption_fingerprint,
        units=units,
        usage_before=0,
        usage_after=units,
    )
    binding = models.TaxReportAcquisitionBinding(
        id=binding_id,
        consumption_id=(
            consumption_id
            if consumption_id_override is None
            else consumption_id_override
        ),
        relatorio_analise_id=report_id,
        fingerprint=binding_fingerprint,
        resultado_json_snapshot=deepcopy(snapshot),
        created_at=datetime(2026, 1, 2, 3, 4, 5),
    )
    db.add_all((offer, order, grant, report, consumption, binding))
    db.commit()
    return binding, grant, report, snapshot


def _counts(db):
    return (
        db.scalar(select(func.count()).select_from(models.CheckoutOfferGrantConsumption)),
        db.scalar(select(func.count()).select_from(models.TaxReportAcquisitionBinding)),
    )


def _state(db, grant_id):
    return (*_counts(db), db.get(models.CheckoutOfferGrant, grant_id).usage_consumed)


def _read(reader_type, db, acquisition_id, *, user_id=USER_ID, empresa_id=EMPRESA_ID):
    return reader_type(db).read(
        user_id=user_id,
        empresa_id=empresa_id,
        acquisition_id=acquisition_id,
    )


def _assert_projection(result, binding, snapshot):
    assert result.acquisition_id == binding.id
    assert result.relatorio_analise_id == binding.relatorio_analise_id
    assert result.fingerprint == binding.fingerprint
    assert result.resultado_json_snapshot == snapshot
    assert result.resultado_json_snapshot is not binding.resultado_json_snapshot
    assert result.created_at == binding.created_at


def _assert_rejected_unchanged(reader_type, error_type, seed_options, read_options=None):
    engine = _engine()
    try:
        with Session(engine) as db:
            binding, grant, _, _ = _seed(db, **seed_options)
            before = _state(db, grant.id)
            options = dict(read_options or {})
            acquisition_id = options.pop("acquisition_id", binding.id)
            with pytest.raises(error_type):
                _read(reader_type, db, acquisition_id, **options)
            db.rollback()
            assert _state(db, grant.id) == before
    finally:
        engine.dispose()


def test_tax_report_acquisition_read_contract_red():
    reader_type, error_type = _future_contract()

    method = signature(reader_type.read)
    assert tuple(method.parameters) == (
        "self", "user_id", "empresa_id", "acquisition_id"
    )
    assert all(
        method.parameters[name].kind.name == "KEYWORD_ONLY"
        for name in ("user_id", "empresa_id", "acquisition_id")
    )
    source = getsource(reader_type)
    for forbidden in (
        "RelatorioAnalise", "consulta_paga", ".pago", "Entitlement",
    ):
        assert forbidden not in source

    # Active: re-download do snapshot adquirido, sem novo debito.
    engine = _engine()
    try:
        with Session(engine) as db:
            binding, grant, _, snapshot = _seed(db)
            before = _state(db, grant.id)
            result = _read(reader_type, db, binding.id)
            _assert_projection(result, binding, snapshot)
            result.resultado_json_snapshot["report"]["items"][0]["total"] = 999
            db.expire(binding, ["resultado_json_snapshot"])
            assert binding.resultado_json_snapshot == snapshot
            assert _state(db, grant.id) == before
    finally:
        engine.dispose()

    # Exhausted tambem permite re-download sem consumo.
    engine = _engine()
    try:
        with Session(engine) as db:
            binding, grant, _, snapshot = _seed(
                db, grant_state="exhausted", usage_limit=1, usage_consumed=1
            )
            before = _state(db, grant.id)
            _assert_projection(_read(reader_type, db, binding.id), binding, snapshot)
            assert _state(db, grant.id) == before
    finally:
        engine.dispose()

    # O RelatorioAnalise mutavel jamais substitui o snapshot historico.
    engine = _engine()
    try:
        with Session(engine) as db:
            binding, grant, report, snapshot = _seed(db)
            before = _state(db, grant.id)
            current = _snapshot("resultado-atual-alterado")
            report.resultado_json = current
            report.fingerprint = fingerprint_resultado_json(current)
            db.commit()
            _assert_projection(_read(reader_type, db, binding.id), binding, snapshot)
            assert _state(db, grant.id) == before
    finally:
        engine.dispose()

    # Revogar A bloqueia somente A; B, no mesmo escopo, continua independente.
    engine = _engine()
    try:
        with Session(engine) as db:
            binding_a, grant_a, _, _ = _seed(db, suffix=1)
            binding_b, grant_b, _, snapshot_b = _seed(db, suffix=2)
            grant_a.estado = "revoked"
            db.commit()
            before_a = _state(db, grant_a.id)
            before_b = _state(db, grant_b.id)
            with pytest.raises(error_type):
                _read(reader_type, db, binding_a.id)
            db.rollback()
            _assert_projection(_read(reader_type, db, binding_b.id), binding_b, snapshot_b)
            assert _state(db, grant_a.id) == before_a
            assert _state(db, grant_b.id) == before_b
    finally:
        engine.dispose()

    # Cada negativo e isolado e deve falhar fechado sem mutacao do ledger.
    negative_cases = (
        ({}, {"acquisition_id": 999999}),
        ({}, {"acquisition_id": 0}),
        ({}, {"acquisition_id": -1}),
        ({}, {"acquisition_id": True}),
        ({}, {"user_id": USER_ID + 1}),
        ({}, {"empresa_id": EMPRESA_ID + 1}),
        ({"consumption_id_override": 999999}, {}),
        ({"capability": "document.extract"}, {}),
        ({"units": 2}, {}),
        ({"consumption_fingerprint": "f" * 64}, {}),
        ({"grant_id_override": 999999}, {}),
        ({"grant_state": "revoked"}, {}),
        ({"grant_state": "active", "usage_limit": 1, "usage_consumed": 1}, {}),
        ({"grant_state": "exhausted", "usage_limit": 2, "usage_consumed": 1}, {}),
        ({"order_state": "pending"}, {}),
        ({"order_user_id": USER_ID + 1}, {}),
        ({"order_empresa_id": EMPRESA_ID + 1}, {}),
        ({"binding_fingerprint": "nao-e-sha256"}, {}),
        ({"snapshot": ["nao-e-dict"], "binding_fingerprint": "a" * 64}, {}),
        ({"binding_fingerprint": "0" * 64}, {}),
    )
    for seed_options, read_options in negative_cases:
        _assert_rejected_unchanged(
            reader_type, error_type, seed_options, read_options
        )
