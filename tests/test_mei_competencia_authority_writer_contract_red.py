"""Contrato RED do writer de autoridade economica por competencia MEI."""

import inspect
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app import models
from app.services.mei_competencia_authority_writer import (
    MeiCompetenciaAuthorityWriter,
    MeiCompetenciaAuthorityWriterError,
    MeiCompetenciaAuthorityWriterResult,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    session = Session()
    try:
        session.add(
            models.Plano(
                id=1,
                nome="controle legado",
                limite_cnpjs=1,
                limite_analises=1,
                preco=Decimal("29.90"),
                billing_type="monthly",
                ativo=True,
                tipo_acesso="relatorio",
            )
        )
        session.add_all(
            (
                models.User(
                    id=1,
                    email="mei-writer-owner@example.invalid",
                    hashed_password="hash",
                    plano_id=1,
                ),
                models.User(
                    id=2,
                    email="mei-writer-other@example.invalid",
                    hashed_password="hash",
                    plano_id=1,
                ),
            )
        )
        session.add_all(
            (
                models.Empresa(
                    id=41,
                    user_id=1,
                    regime_tributario="mei",
                    porte="mei",
                    status_empresa="ativa",
                ),
                models.Empresa(
                    id=42,
                    user_id=2,
                    regime_tributario="mei",
                    porte="mei",
                    status_empresa="ativa",
                ),
            )
        )

        offer = models.CheckoutOffer(
            id=10,
            codigo="mei-das-one-time-company",
            nome_publico="MEI DAS",
            vertical="tax",
            commercial_model="one_time",
            subject_type="company",
            estado="published",
            moeda="BRL",
            preco=Decimal("39.90"),
            billing_period=None,
            usage_unit="competence",
            usage_limit=1,
            contract_version=1,
        )
        offer.capabilities = [
            models.CheckoutOfferCapability(codigo="mei.das")
        ]
        session.add(offer)
        session.commit()

        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_chain(
    db,
    *,
    ordem_id=701,
    key="mei-writer-202609-701",
    competencia="202609",
    include_intent=True,
    intent_offer_code="mei-das-one-time-company",
    estado="paid",
    include_capability=True,
    payment_status="approved",
    payment_value=Decimal("39.90"),
    payment_user_id=1,
    revoked_grant=False,
):
    if include_intent:
        db.add(
            models.MeiCompetenciaCheckoutIntent(
                checkout_idempotency_key=key,
                user_id=1,
                empresa_id=41,
                competencia=competencia,
                capability="mei.das",
                offer_code=intent_offer_code,
            )
        )

    ordem = models.OrdemCheckout(
        id=ordem_id,
        user_id=1,
        empresa_id=41,
        plano_id=None,
        offer_id=10,
        offer_code="mei-das-one-time-company",
        contract_version=1,
        vertical="tax",
        commercial_model="one_time",
        subject_type="company",
        subject_id=41,
        valor=Decimal("39.90"),
        moeda="BRL",
        billing_period=None,
        usage_unit="competence",
        usage_limit=1,
        idempotency_key=key,
        estado=estado,
        payment_id=f"47{ordem_id}",
    )
    if include_capability:
        ordem.capabilities = [
            models.OrdemCheckoutCapability(codigo="mei.das")
        ]
    db.add(ordem)
    db.flush()

    db.add(
        models.Pagamento(
            ordem_checkout_id=ordem_id,
            user_id=payment_user_id,
            plano_id=None,
            idempotency_key=f"notification-{ordem_id}",
            valor=payment_value,
            mp_payment_id=f"47{ordem_id}",
            status=payment_status,
            confirmado_em=datetime.utcnow(),
        )
    )

    if revoked_grant:
        grant = models.CheckoutOfferGrant(
            ordem_id=ordem_id,
            usage_unit="competence",
            usage_limit=1,
            usage_consumed=0,
            estado="revoked",
        )
        grant.capabilities = [
            models.CheckoutOfferGrantCapability(codigo="mei.das")
        ]
        db.add(grant)

    db.commit()
    return ordem


def _count_bindings(db):
    return db.scalar(
        select(func.count()).select_from(
            models.MeiCompetenciaAuthorityBinding
        )
    )


def test_writer_api_nao_aceita_competencia_do_chamador():
    parameters = tuple(
        inspect.signature(
            MeiCompetenciaAuthorityWriter.materialize
        ).parameters
    )
    assert parameters == ("self", "ordem_id")


def test_cadeia_exata_materializa_binding(db):
    _seed_chain(db)

    result = MeiCompetenciaAuthorityWriter(db).materialize(
        ordem_id=701
    )

    assert type(result) is MeiCompetenciaAuthorityWriterResult
    assert result.binding_id > 0
    assert result.ordem_id == 701
    assert result.empresa_id == 41
    assert result.competencia == "202609"
    assert result.capability == "mei.das"
    assert result.created_at is not None

    binding = db.scalar(
        select(models.MeiCompetenciaAuthorityBinding).where(
            models.MeiCompetenciaAuthorityBinding.id
            == result.binding_id
        )
    )
    assert binding is not None
    assert binding.ordem_id == 701
    assert binding.empresa_id == 41
    assert binding.competencia == "202609"
    assert binding.capability == "mei.das"
    assert _count_bindings(db) == 1


def test_replay_da_mesma_ordem_e_idempotente(db):
    _seed_chain(db)
    writer = MeiCompetenciaAuthorityWriter(db)

    first = writer.materialize(ordem_id=701)
    second = writer.materialize(ordem_id=701)

    assert second == first
    assert _count_bindings(db) == 1


def test_sem_intencao_exata_nao_materializa(db):
    _seed_chain(db, include_intent=False)

    with pytest.raises(MeiCompetenciaAuthorityWriterError):
        MeiCompetenciaAuthorityWriter(db).materialize(ordem_id=701)

    assert _count_bindings(db) == 0


def test_intencao_de_outra_oferta_nao_materializa(db):
    _seed_chain(
        db,
        intent_offer_code="outra-oferta-mei-das",
    )

    with pytest.raises(MeiCompetenciaAuthorityWriterError):
        MeiCompetenciaAuthorityWriter(db).materialize(ordem_id=701)

    assert _count_bindings(db) == 0


def test_ordem_pending_nao_materializa(db):
    _seed_chain(db, estado="pending")

    with pytest.raises(MeiCompetenciaAuthorityWriterError):
        MeiCompetenciaAuthorityWriter(db).materialize(ordem_id=701)

    assert _count_bindings(db) == 0


def test_ordem_sem_mei_das_nao_materializa(db):
    _seed_chain(db, include_capability=False)

    with pytest.raises(MeiCompetenciaAuthorityWriterError):
        MeiCompetenciaAuthorityWriter(db).materialize(ordem_id=701)

    assert _count_bindings(db) == 0


@pytest.mark.parametrize(
    ("payment_status", "payment_value", "payment_user_id"),
    (
        ("refunded", Decimal("39.90"), 1),
        ("approved", Decimal("39.91"), 1),
        ("approved", Decimal("39.90"), 2),
    ),
)
def test_pagamento_invalido_nao_materializa(
    db,
    payment_status,
    payment_value,
    payment_user_id,
):
    _seed_chain(
        db,
        payment_status=payment_status,
        payment_value=payment_value,
        payment_user_id=payment_user_id,
    )

    with pytest.raises(MeiCompetenciaAuthorityWriterError):
        MeiCompetenciaAuthorityWriter(db).materialize(ordem_id=701)

    assert _count_bindings(db) == 0


def test_grant_revogado_nao_materializa(db):
    _seed_chain(db, revoked_grant=True)

    with pytest.raises(MeiCompetenciaAuthorityWriterError):
        MeiCompetenciaAuthorityWriter(db).materialize(ordem_id=701)

    assert _count_bindings(db) == 0


def test_ordem_inexistente_falha_fechado(db):
    with pytest.raises(MeiCompetenciaAuthorityWriterError):
        MeiCompetenciaAuthorityWriter(db).materialize(ordem_id=999999)

    assert _count_bindings(db) == 0
