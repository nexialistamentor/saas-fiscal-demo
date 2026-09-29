from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models


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
                limite_cnpjs=2,
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
                    email="mei-intent-owner@test.invalid",
                    hashed_password="not-a-real-password",
                    plano_id=1,
                ),
                models.User(
                    id=2,
                    email="mei-intent-other@test.invalid",
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
                models.Empresa(
                    id=43,
                    cnpj="11222333000144",
                    regime_tributario="simples",
                    user_id=1,
                    status_empresa="ativa",
                    porte="me",
                ),
                models.Empresa(
                    id=44,
                    cnpj="55666777000188",
                    regime_tributario="mei",
                    user_id=1,
                    status_empresa="suspensa",
                    porte="mei",
                ),
            ]
        )

        ofertas = [
            models.CheckoutOffer(
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
            ),
            models.CheckoutOffer(
                id=11,
                codigo="mei-das-draft-company",
                nome_publico="MEI DAS draft",
                vertical="tax",
                commercial_model="monthly",
                subject_type="company",
                estado="draft",
                moeda="BRL",
                preco=Decimal("39.90"),
                billing_period="month",
                usage_unit=None,
                usage_limit=None,
                contract_version=1,
            ),
            models.CheckoutOffer(
                id=12,
                codigo="tax-report-monthly-company",
                nome_publico="Relatorio",
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
            ),
            models.CheckoutOffer(
                id=13,
                codigo="document-mei-das-company",
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
            ),
            models.CheckoutOffer(
                id=14,
                codigo="mei-das-monthly-cpf",
                nome_publico="MEI DAS CPF",
                vertical="tax",
                commercial_model="monthly",
                subject_type="cpf",
                estado="published",
                moeda="BRL",
                preco=Decimal("39.90"),
                billing_period="month",
                usage_unit=None,
                usage_limit=None,
                contract_version=1,
            ),
        ]
        session.add_all(ofertas)
        session.flush()

        session.add_all(
            [
                models.CheckoutOfferCapability(
                    offer_id=10,
                    codigo="mei.das",
                ),
                models.CheckoutOfferCapability(
                    offer_id=11,
                    codigo="mei.das",
                ),
                models.CheckoutOfferCapability(
                    offer_id=12,
                    codigo="tax.report",
                ),
                models.CheckoutOfferCapability(
                    offer_id=13,
                    codigo="mei.das",
                ),
                models.CheckoutOfferCapability(
                    offer_id=14,
                    codigo="mei.das",
                ),
            ]
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def _service(db):
    from app.services.mei_competencia_checkout_intent import (
        MeiCompetenciaCheckoutIntent,
    )

    return MeiCompetenciaCheckoutIntent(db)


def _error():
    from app.services.mei_competencia_checkout_intent import (
        MeiCompetenciaCheckoutIntentError,
    )

    return MeiCompetenciaCheckoutIntentError


def _persist(service, **overrides):
    values = {
        "user_id": 1,
        "empresa_id": 41,
        "competencia": "202609",
        "offer_code": "mei-das-monthly-company",
        "checkout_idempotency_key": "mei-das-41-202609-v1",
    }
    values.update(overrides)
    return service.persist(**values)


def test_intencao_mei_competencia_persiste_escopo_exato(db):
    result = _persist(_service(db))

    assert result.intent_id > 0
    assert result.user_id == 1
    assert result.empresa_id == 41
    assert result.competencia == "202609"
    assert result.capability == "mei.das"
    assert result.offer_code == "mei-das-monthly-company"
    assert result.checkout_idempotency_key == "mei-das-41-202609-v1"
    assert result.created_at is not None

    persisted = db.get(
        models.MeiCompetenciaCheckoutIntent,
        result.intent_id,
    )
    assert persisted is not None
    assert persisted.competencia == "202609"
    assert persisted.capability == "mei.das"


def test_replay_identico_retorna_mesma_intencao_sem_duplicar(db):
    service = _service(db)

    first = _persist(service)
    second = _persist(service)

    assert second == first
    assert (
        db.query(models.MeiCompetenciaCheckoutIntent).count()
        == 1
    )


def test_replay_divergente_com_mesma_idempotency_key_falha_fechado(db):
    service = _service(db)
    _persist(service)

    with pytest.raises(_error()):
        _persist(
            service,
            competencia="202610",
        )

    assert (
        db.query(models.MeiCompetenciaCheckoutIntent).count()
        == 1
    )


@pytest.mark.parametrize(
    "competencia",
    [
        "",
        "20269",
        "202600",
        "202613",
        "2026AA",
        "２０２６０９",
    ],
)
def test_competencia_invalida_falha_fechado(db, competencia):
    with pytest.raises(_error()):
        _persist(
            _service(db),
            competencia=competencia,
            checkout_idempotency_key=f"invalid-{repr(competencia)}",
        )


@pytest.mark.parametrize(
    "offer_code",
    [
        "mei-das-draft-company",
        "tax-report-monthly-company",
        "document-mei-das-company",
        "mei-das-monthly-cpf",
        "oferta-inexistente",
    ],
)
def test_oferta_sem_autoridade_mei_das_company_publicada_falha_fechado(
    db,
    offer_code,
):
    with pytest.raises(_error()):
        _persist(
            _service(db),
            offer_code=offer_code,
            checkout_idempotency_key=f"invalid-offer-{offer_code}",
        )


@pytest.mark.parametrize(
    "empresa_id",
    [42, 43, 44],
)
def test_empresa_fora_do_escopo_mei_ativo_do_usuario_falha_fechado(
    db,
    empresa_id,
):
    with pytest.raises(_error()):
        _persist(
            _service(db),
            empresa_id=empresa_id,
            checkout_idempotency_key=f"invalid-company-{empresa_id}",
        )
