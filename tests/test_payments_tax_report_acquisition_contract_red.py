"""RED: aquisicao canonica de resultado fiscal persistido por tax.report.

Este contrato e deliberadamente separado de CheckoutOfferGrantUsage, que
permanece exclusivo de document.extract. Nao cobre HTTP, download, PDF,
frontend, catalogo de preco nem publicacao de oferta.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from inspect import getsource, signature

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session

from app import models
from app.services.resultado_provenance_service import (
    fingerprint_resultado_json,
    selar_resultado_nao_mei,
)


CAPABILITY = "tax.report"


def _future_contract():
    """Carrega somente a futura implementacao exigida por este RED."""
    assert hasattr(models, "TaxReportAcquisitionBinding"), (
        "ausente binding append-only entre o consumo tax.report e o snapshot "
        "adquirido (relatorio_analise_id + fingerprint + snapshot)"
    )
    from app.services.tax_report_acquisition import (  # noqa: PLC0415
        TaxReportAcquisition,
        TaxReportAcquisitionError,
    )

    return (
        models.TaxReportAcquisitionBinding,
        TaxReportAcquisition,
        TaxReportAcquisitionError,
    )


def _schema(binding):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    tables = (
        models.User.__table__,
        models.Empresa.__table__,
        models.CheckoutOffer.__table__,
        models.OrdemCheckout.__table__,
        models.CheckoutOfferGrant.__table__,
        models.CheckoutOfferGrantCapability.__table__,
        models.CheckoutOfferGrantConsumption.__table__,
        models.RelatorioAnalise.__table__,
        binding.__table__,
    )
    models.Base.metadata.create_all(engine, tables=tables)
    return engine


def _seed(
    db,
    *,
    report_id=501,
    report_user=11,
    report_company=21,
    report_status="ok",
    report_fingerprint="valid",
    valid_provenance=True,
    grants=(),
):
    payload = {"tributo": "DAS", "total": 125.75}
    if valid_provenance:
        payload = selar_resultado_nao_mei(payload, producer_id="app.tax.engine")
    fingerprint = fingerprint_resultado_json(payload)
    if report_fingerprint == "missing":
        fingerprint = None
    elif report_fingerprint == "malformed":
        fingerprint = "nao-e-sha256"
    elif report_fingerprint == "divergent":
        fingerprint = "0" * 64

    report = models.RelatorioAnalise(
        id=report_id,
        user_id=report_user,
        empresa_id=report_company,
        analysis_type="empresa_tax",
        status=report_status,
        resultado_json=payload,
        fingerprint=fingerprint,
        pago=False,  # campo legado nao concede nem impede autoridade
    )
    db.add(report)

    now = datetime(2026, 1, 1, 12, 0, 0)
    for position, spec in enumerate(grants):
        order_id = spec.get("order_id", 700 + position)
        grant_id = spec.get("grant_id", 800 + position)
        order = models.OrdemCheckout(
            id=order_id,
            user_id=spec.get("user_id", 11),
            empresa_id=spec.get("empresa_id", 21),
            offer_id=None,
            valor=Decimal("49.90"),
            moeda="BRL",
            estado=spec.get("order_state", "paid"),
            idempotency_key=f"order-{order_id}",
        )
        grant = models.CheckoutOfferGrant(
            id=grant_id,
            ordem=order,
            usage_unit="report",
            usage_limit=spec.get("limit", 1),
            usage_consumed=spec.get("consumed", 0),
            estado=spec.get("state", "active"),
            created_at=spec.get("created_at", now + timedelta(seconds=position)),
        )
        grant.capabilities.append(
            models.CheckoutOfferGrantCapability(
                codigo=spec.get("capability", CAPABILITY)
            )
        )
        db.add(grant)
    db.commit()
    return report, fingerprint


def _counts(db, binding):
    return (
        db.scalar(select(func.count()).select_from(models.CheckoutOfferGrantConsumption)),
        db.scalar(select(func.count()).select_from(binding)),
    )


def _acquire(service_type, db, *, report_id=501, fingerprint, key="acq-1",
             user_id=11, empresa_id=21):
    return service_type(db).acquire(
        user_id=user_id,
        empresa_id=empresa_id,
        relatorio_id=report_id,
        idempotency_key=key,
        request_fingerprint=fingerprint,
    )


def test_tax_report_persisted_result_acquisition_contract_red():
    binding, service_type, error_type = _future_contract()

    # A API aceita explicitamente todo o escopo e nao permite capability livre.
    assert tuple(signature(service_type.acquire).parameters) == (
        "self", "user_id", "empresa_id", "relatorio_id",
        "idempotency_key", "request_fingerprint",
    )
    source = getsource(service_type)
    assert ".with_for_update(" in source
    assert "created_at.asc()" in source and ".id.asc()" in source
    assert source.index("_selecionar_grant_com_lock(") < source.index("grant.usage_consumed")
    columns = set(binding.__table__.columns.keys())
    assert {
        "id", "consumption_id", "relatorio_analise_id", "fingerprint",
        "resultado_json_snapshot", "created_at",
    } <= columns
    assert binding.__table__.c.consumption_id.unique
    assert binding.__table__.c.consumption_id.nullable is False
    assert binding.__table__.c.relatorio_analise_id.nullable is False
    assert binding.__table__.c.fingerprint.nullable is False
    assert binding.__table__.c.resultado_json_snapshot.nullable is False
    consumption_fk = tuple(binding.__table__.c.consumption_id.foreign_keys)
    report_fk = tuple(binding.__table__.c.relatorio_analise_id.foreign_keys)
    assert len(consumption_fk) == 1
    assert consumption_fk[0].target_fullname == (
        "checkout_offer_grant_consumptions.id"
    )
    assert consumption_fk[0].ondelete != "CASCADE"
    assert len(report_fk) == 1
    assert report_fk[0].target_fullname == "relatorios_analise.id"
    assert report_fk[0].ondelete != "CASCADE"

    engine = _schema(binding)
    try:
        # Caminho feliz: um debito, ledger canonico e binding ao consumo concreto.
        with Session(engine) as db:
            report, fingerprint = _seed(
                db, grants=[{"grant_id": 810, "limit": 1, "consumed": 0}]
            )
            acquired_snapshot = dict(report.resultado_json)
            result = _acquire(service_type, db, fingerprint=fingerprint)
            db.commit()
            consumption = db.scalars(select(models.CheckoutOfferGrantConsumption)).one()
            link = db.scalars(select(binding)).one()
            grant = db.get(models.CheckoutOfferGrant, 810)
            assert result.id == link.id
            assert grant.usage_consumed == 1
            assert grant.estado == "exhausted"
            assert consumption.capability == CAPABILITY
            assert consumption.units == 1
            assert consumption.usage_before == 0
            assert consumption.usage_after == 1
            assert link.consumption_id == consumption.id
            assert link.relatorio_analise_id == 501
            assert link.fingerprint == fingerprint
            assert link.resultado_json_snapshot == acquired_snapshot
            assert (
                fingerprint_resultado_json(link.resultado_json_snapshot)
                == link.fingerprint
            )

            # O resultado comprado sobrevive a alteracoes legitimas posteriores.
            report.resultado_json = selar_resultado_nao_mei(
                {"tributo": "DAS", "total": 999.99},
                producer_id="app.tax.engine",
            )
            report.fingerprint = fingerprint_resultado_json(report.resultado_json)
            db.commit()
            db.refresh(link)
            assert link.resultado_json_snapshot == acquired_snapshot
            assert link.fingerprint == fingerprint

            # Replay identico resolve antes de procurar novo grant elegivel.
            replay = _acquire(service_type, db, fingerprint=fingerprint)
            db.commit()
            assert replay.id == result.id
            assert grant.usage_consumed == 1
            assert grant.estado == "exhausted"
            assert _counts(db, binding) == (1, 1)

            # Colisao idempotente em qualquer dimensao falha fechada e imutavel.
            for changed in (
                {"user_id": 12}, {"empresa_id": 22}, {"report_id": 502},
                {"fingerprint": "f" * 64},
            ):
                args = dict(report_id=501, fingerprint=fingerprint, key="acq-1",
                            user_id=11, empresa_id=21)
                args.update(changed)
                with pytest.raises(error_type):
                    _acquire(service_type, db, **args)
                db.rollback()
                assert grant.usage_consumed == 1
                assert _counts(db, binding) == (1, 1)

            # O fingerprint apresentado tambem e fail-closed.
            for number, invalid in enumerate((None, "nao-e-sha256", "f" * 64)):
                with pytest.raises(error_type):
                    _acquire(service_type, db, fingerprint=invalid,
                             key=f"invalid-request-fingerprint-{number}")
                db.rollback()
                assert grant.usage_consumed == 1
                assert _counts(db, binding) == (1, 1)

            # Ledger e binding sao append-only.
            link.resultado_json_snapshot = {"adulterado": True}
            with pytest.raises(InvalidRequestError):
                db.flush()
            db.rollback()
            link.fingerprint = "a" * 64
            with pytest.raises(InvalidRequestError):
                db.flush()
            db.rollback()
            db.delete(db.get(binding, result.id))
            with pytest.raises(InvalidRequestError):
                db.flush()
            db.rollback()

        # Cada controle negativo deve falhar sem consumo nem binding.
        negative_cases = (
            ("report-processing", {"report_status": "processando"}, [{"grant_id": 817}]),
            ("report-error", {"report_status": "erro"}, [{"grant_id": 818}]),
            ("report-cancelled", {"report_status": "cancelado"}, [{"grant_id": 819}]),
            ("revoked", {}, [{"state": "revoked"}]),
            ("exhausted", {}, [{"state": "exhausted", "consumed": 1}]),
            ("order-not-paid", {}, [{"order_state": "pending"}]),
            ("wrong-capability", {}, [{"capability": "document.extract"}]),
            ("missing-report", {"report_id": 999}, [{"grant_id": 820}]),
            ("other-user-report", {"report_user": 99}, [{"grant_id": 821}]),
            ("other-company-report", {"report_company": 99}, [{"grant_id": 822}]),
            ("missing-fingerprint", {"report_fingerprint": "missing"}, [{"grant_id": 823}]),
            ("malformed-fingerprint", {"report_fingerprint": "malformed"}, [{"grant_id": 824}]),
            ("divergent-fingerprint", {"report_fingerprint": "divergent"}, [{"grant_id": 825}]),
            ("invalid-provenance", {"valid_provenance": False}, [{"grant_id": 826}]),
            ("no-authority", {}, []),
        )
        for number, (name, report_spec, grant_specs) in enumerate(negative_cases):
            local_engine = _schema(binding)
            try:
                with Session(local_engine) as db:
                    report_id = report_spec.pop("report_id", 501)
                    _, fingerprint = _seed(db, grants=grant_specs, **report_spec)
                    with pytest.raises(error_type, match=".+"):
                        _acquire(service_type, db, report_id=report_id,
                                 fingerprint=fingerprint, key=f"negative-{number}-{name}")
                    db.rollback()
                    assert _counts(db, binding) == (0, 0)
                    assert all(g.usage_consumed == grant_specs[i].get("consumed", 0)
                               for i, g in enumerate(db.scalars(
                                   select(models.CheckoutOfferGrant).order_by(
                                       models.CheckoutOfferGrant.id)).all()))
            finally:
                local_engine.dispose()

        # Grants invalidos sao ignorados; o elegivel mais antigo vence created_at/id.
        with Session(engine) as db:
            models.Base.metadata.drop_all(engine)
            models.Base.metadata.create_all(engine, tables=(
                models.User.__table__, models.Empresa.__table__,
                models.CheckoutOffer.__table__, models.OrdemCheckout.__table__,
                models.CheckoutOfferGrant.__table__,
                models.CheckoutOfferGrantCapability.__table__,
                models.CheckoutOfferGrantConsumption.__table__,
                models.RelatorioAnalise.__table__, binding.__table__,
            ))
            old = datetime(2025, 1, 1)
            _, fingerprint = _seed(db, grants=[
                {"grant_id": 830, "state": "revoked", "created_at": old},
                {"grant_id": 831, "state": "exhausted", "consumed": 1, "created_at": old},
                {"grant_id": 833, "created_at": old + timedelta(days=1)},
                {"grant_id": 832, "created_at": old + timedelta(days=1)},
            ])
            _acquire(service_type, db, fingerprint=fingerprint, key="deterministic")
            db.commit()
            consumed = db.scalars(select(models.CheckoutOfferGrantConsumption)).one()
            assert consumed.grant_id == 832
            assert db.get(models.CheckoutOfferGrant, 830).usage_consumed == 0
            assert db.get(models.CheckoutOfferGrant, 831).usage_consumed == 1
            assert db.get(models.CheckoutOfferGrant, 833).usage_consumed == 0

        # A transacao pertence ao chamador: rollback desfaz debito, ledger e binding.
        with Session(engine) as db:
            before = _counts(db, binding)
            report = db.get(models.RelatorioAnalise, 501)
            _acquire(service_type, db, fingerprint=report.fingerprint, key="rollback")
            db.rollback()
            assert _counts(db, binding) == before
    finally:
        engine.dispose()

    # Nova analise/snapshot nao herda aquisicao: relatorio e fingerprint fazem
    # parte da identidade idempotente e o binding congela ambos.
    # A selecao concorrente exige row lock antes do debito, verificado acima.
