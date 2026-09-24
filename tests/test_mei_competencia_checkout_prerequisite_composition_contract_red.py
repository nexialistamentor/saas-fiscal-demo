from decimal import Decimal

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app import models
from app.services import checkout_offer_order_composition as composition
from app.services.checkout_offer_prerequisite import CheckoutOfferPrerequisite


def test_composer_entrega_capability_snapshot_ao_prerequisite(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    try:
        with Session.begin() as db:
            db.add(
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
            db.add(
                models.User(
                    id=1,
                    email="mei-composer-prerequisite@test.invalid",
                    hashed_password="not-a-real-password",
                    plano_id=1,
                )
            )
            db.add(
                models.Empresa(
                    id=41,
                    cnpj="12345678000190",
                    regime_tributario="mei",
                    user_id=1,
                    status_empresa="ativa",
                    porte="mei",
                )
            )

            offer = models.CheckoutOffer(
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
            offer.capabilities = [
                models.CheckoutOfferCapability(codigo="mei.das")
            ]
            db.add(offer)

        observed = []

        def _require(
            self,
            *,
            authenticated_user_id,
            empresa_id,
            offer_code,
            idempotency_key,
            **kwargs,
        ):
            observed.append(
                (
                    authenticated_user_id,
                    empresa_id,
                    offer_code,
                    idempotency_key,
                    tuple(kwargs.get("capabilities", ())),
                )
            )

        monkeypatch.setattr(
            CheckoutOfferPrerequisite,
            "require",
            _require,
        )

        composer = composition.CheckoutOfferOrderComposer(Session)

        first = composer.iniciar_checkout_empresa(
            authenticated_user_id=1,
            empresa_id=41,
            offer_code="mei-das-monthly-company",
            idempotency_key="mei-das-41-202609-v1",
        )

        assert first.capabilities == ("mei.das",)

        with Session.begin() as db:
            db.execute(
                delete(models.CheckoutOfferCapability).where(
                    models.CheckoutOfferCapability.offer_id == 10
                )
            )
            db.add(
                models.CheckoutOfferCapability(
                    offer_id=10,
                    codigo="tax.report",
                )
            )

        replay = composer.iniciar_checkout_empresa(
            authenticated_user_id=1,
            empresa_id=41,
            offer_code="mei-das-monthly-company",
            idempotency_key="mei-das-41-202609-v1",
        )

        assert replay.id == first.id
        assert replay.capabilities == ("mei.das",)

        assert observed == [
            (
                1,
                41,
                "mei-das-monthly-company",
                "mei-das-41-202609-v1",
                ("mei.das",),
            ),
            (
                1,
                41,
                "mei-das-monthly-company",
                "mei-das-41-202609-v1",
                ("mei.das",),
            ),
        ]
    finally:
        engine.dispose()
