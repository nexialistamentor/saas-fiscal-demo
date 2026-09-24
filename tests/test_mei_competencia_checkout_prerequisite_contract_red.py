from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.services.checkout_offer_prerequisite import (
    CheckoutOfferPrerequisite,
    CheckoutOfferPrerequisiteError,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    session = Session()
    try:
        session.add(
            models.Plano(
                id=1,
                nome="teste",
                limite_cnpjs=1,
                limite_analises=1,
                preco=Decimal("0.00"),
                billing_type="monthly",
                ativo=True,
                tipo_acesso="relatorio",
            )
        )
        session.add_all(
            [
                models.User(
                    id=1,
                    email="mei-prerequisite@test.invalid",
                    hashed_password="not-a-real-password",
                    plano_id=1,
                ),
                models.User(
                    id=2,
                    email="mei-prerequisite-other@test.invalid",
                    hashed_password="not-a-real-password",
                    plano_id=1,
                ),
            ]
        )
        session.add_all(
            [
                models.Empresa(
                    id=41,
                    cnpj="12345678000190",
                    regime_tributario="mei",
                    user_id=1,
                    status_empresa="ativa",
                    porte="mei",
                ),
                models.Empresa(
                    id=42,
                    cnpj="98765432000110",
                    regime_tributario="mei",
                    user_id=2,
                    status_empresa="ativa",
                    porte="mei",
                ),
            ]
        )

        mei_offer = models.CheckoutOffer(
            id=10,
            codigo="mei-das-monthly-company",
            nome_publico="MEI DAS",
            vertical="tax",
            commercial_model="monthly",
            subject_type="company",
            estado="published",
            moeda="BRL",
            preco=Decimal("39.90"),
            billing_period="month",
            usage_unit=None,
            usage_limit=None,
            contract_version=1,
        )
        other_offer = models.CheckoutOffer(
            id=11,
            codigo="document-monthly-company",
            nome_publico="Documento",
            vertical="document",
            commercial_model="monthly",
            subject_type="company",
            estado="published",
            moeda="BRL",
            preco=Decimal("39.90"),
            billing_period="month",
            usage_unit=None,
            usage_limit=None,
            contract_version=1,
        )
        session.add_all((mei_offer, other_offer))
        session.flush()

        session.add_all(
            (
                models.CheckoutOfferCapability(
                    offer_id=10,
                    codigo="mei.das",
                ),
                models.CheckoutOfferCapability(
                    offer_id=11,
                    codigo="document.validate",
                ),
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def _require(db, *, key="mei-das-41-202609-v1", offer_code="mei-das-monthly-company"):
    return CheckoutOfferPrerequisite(db).require(
        authenticated_user_id=1,
        empresa_id=41,
        offer_code=offer_code,
        idempotency_key=key,
    )


def test_oferta_mei_das_sem_intencao_falha_fechado(db):
    with pytest.raises(CheckoutOfferPrerequisiteError):
        _require(db)


def test_oferta_mei_das_com_intencao_exata_autoriza_composicao(db):
    db.add(
        models.MeiCompetenciaCheckoutIntent(
            checkout_idempotency_key="mei-das-41-202609-v1",
            user_id=1,
            empresa_id=41,
            competencia="202609",
            capability="mei.das",
            offer_code="mei-das-monthly-company",
        )
    )
    db.commit()

    assert _require(db) is None


@pytest.mark.parametrize(
    ("user_id", "empresa_id", "offer_code"),
    [
        (2, 41, "mei-das-monthly-company"),
        (1, 42, "mei-das-monthly-company"),
        (1, 41, "mei-das-outra-oferta"),
    ],
)
def test_intencao_mei_das_nao_vaza_entre_identidades(
    db,
    user_id,
    empresa_id,
    offer_code,
):
    db.add(
        models.MeiCompetenciaCheckoutIntent(
            checkout_idempotency_key="mei-das-41-202609-v1",
            user_id=user_id,
            empresa_id=empresa_id,
            competencia="202609",
            capability="mei.das",
            offer_code=offer_code,
        )
    )
    db.commit()

    with pytest.raises(CheckoutOfferPrerequisiteError):
        _require(db)


def test_oferta_sem_mei_das_nao_exige_intencao_mei(db):
    assert _require(
        db,
        key="document-without-mei-intent",
        offer_code="document-monthly-company",
    ) is None
