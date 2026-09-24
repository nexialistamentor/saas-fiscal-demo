from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.services.mei_competencia_authority import (
    tem_autoridade_economica_mei_competencia,
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
        session.add(
            models.User(
                id=1,
                email="mei-authority@test.invalid",
                hashed_password="not-a-real-password",
                plano_id=1,
            )
        )
        session.add(
            models.Empresa(
                id=41,
                cnpj="12345678000190",
                regime_tributario="mei",
                user_id=1,
                status_empresa="ativa",
                porte="mei",
            )
        )
        session.flush()
        yield session
    finally:
        session.close()
        engine.dispose()


def _criar_autoridade(
    db,
    *,
    estado="paid",
    competencia="202609",
    capability="mei.das",
    payment_status="approved",
    incluir_capability_ordem=True,
    grant_estado=None,
):
    ordem = models.OrdemCheckout(
        user_id=1,
        empresa_id=41,
        plano_id=1,
        valor=Decimal("39.90"),
        moeda="BRL",
        estado=estado,
        idempotency_key=(
            f"mei-authority-{estado}-{competencia}-{capability}-"
            f"{payment_status}-{incluir_capability_ordem}-{grant_estado}"
        ),
    )
    db.add(ordem)
    db.flush()

    if incluir_capability_ordem:
        db.add(
            models.OrdemCheckoutCapability(
                ordem_id=ordem.id,
                codigo=capability,
            )
        )

    db.add(
        models.Pagamento(
            user_id=1,
            plano_id=None,
            ordem_checkout_id=ordem.id,
            idempotency_key=f"mei-payment-{ordem.id}",
            valor=Decimal("39.90"),
            status=payment_status,
            confirmado_em=datetime.utcnow(),
            mp_payment_id=f"900000{ordem.id}",
        )
    )

    if grant_estado is not None:
        db.add(
            models.CheckoutOfferGrant(
                ordem_id=ordem.id,
                usage_unit="competencia",
                usage_limit=1,
                usage_consumed=0,
                estado=grant_estado,
            )
        )

    db.add(
        models.MeiCompetenciaAuthorityBinding(
            ordem_id=ordem.id,
            empresa_id=41,
            competencia=competencia,
            capability=capability,
        )
    )
    db.commit()


def test_autoridade_exata_paga_autoriza(db):
    _criar_autoridade(db)

    assert tem_autoridade_economica_mei_competencia(
        db,
        empresa_id=41,
        competencia="202609",
        capability="mei.das",
    ) is True


@pytest.mark.parametrize(
    ("competencia", "capability"),
    [
        ("202608", "mei.das"),
        ("202610", "mei.das"),
        ("202609", "mei.outro"),
    ],
)
def test_autoridade_nao_vaza_entre_competencias_ou_capabilities(
    db, competencia, capability
):
    _criar_autoridade(db)

    assert tem_autoridade_economica_mei_competencia(
        db,
        empresa_id=41,
        competencia=competencia,
        capability=capability,
    ) is False


def test_ordem_nao_paga_nao_autoriza(db):
    _criar_autoridade(db, estado="pending")

    assert tem_autoridade_economica_mei_competencia(
        db,
        empresa_id=41,
        competencia="202609",
        capability="mei.das",
    ) is False


def test_ordem_paga_sem_capability_comercial_nao_autoriza(db):
    _criar_autoridade(
        db,
        incluir_capability_ordem=False,
    )

    assert tem_autoridade_economica_mei_competencia(
        db,
        empresa_id=41,
        competencia="202609",
        capability="mei.das",
    ) is False


def test_pagamento_refunded_nao_autoriza_mesmo_com_ordem_paid(db):
    _criar_autoridade(
        db,
        estado="paid",
        payment_status="refunded",
    )

    assert tem_autoridade_economica_mei_competencia(
        db,
        empresa_id=41,
        competencia="202609",
        capability="mei.das",
    ) is False


def test_grant_revoked_nao_autoriza_mesmo_com_ordem_e_pagamento_validos(db):
    _criar_autoridade(
        db,
        estado="paid",
        payment_status="approved",
        grant_estado="revoked",
    )

    assert tem_autoridade_economica_mei_competencia(
        db,
        empresa_id=41,
        competencia="202609",
        capability="mei.das",
    ) is False
