"""Contrato RED offline do catalogo duravel de ofertas multi-vertical."""

from dataclasses import FrozenInstanceError
from decimal import Decimal
from importlib import import_module
from inspect import signature

import pytest
from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def test_payments_multi_vertical_checkout_catalog_contract_red():
    catalog = import_module("app.services.checkout_offer_catalog")
    models = import_module("app.models")

    assert list(signature(catalog.CheckoutOfferCatalog).parameters) == [
        "session_factory"
    ]
    assert list(
        signature(catalog.CheckoutOfferCatalog.listar_ofertas_publicadas).parameters
    ) == ["self"]
    assert list(
        signature(catalog.CheckoutOfferCatalog.obter_oferta_publicada).parameters
    ) == ["self", "codigo"]
    assert list(
        signature(catalog.CheckoutOfferCatalog.resolver_oferta_para_checkout).parameters
    ) == ["self", "codigo"]

    assert models.CheckoutOffer.__table__.metadata is models.Base.metadata
    assert models.CheckoutOfferCapability.__table__.metadata is models.Base.metadata
    colunas = set(sa_inspect(models.CheckoutOffer).columns.keys())
    assert not colunas.intersection(
        {
            "access_token",
            "credential",
            "credencial",
            "gateway_payload",
            "payload",
            "secret",
            "segredo",
            "token",
        }
    )
    assert all("mei" not in coluna.lower() for coluna in colunas)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=True)

    with Session.begin() as db:
        ofertas = [
            models.CheckoutOffer(
                id=1,
                codigo="tax-monthly-cpf",
                nome_publico="Assistencia fiscal mensal",
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
            models.CheckoutOffer(
                id=2,
                codigo="document-one-time-company",
                nome_publico="Processamento documental",
                vertical="document",
                commercial_model="one_time",
                subject_type="company",
                estado="published",
                moeda="BRL",
                preco=Decimal("79.50"),
                billing_period=None,
                usage_unit="document",
                usage_limit=5,
                contract_version=2,
            ),
            models.CheckoutOffer(
                id=3,
                codigo="tax-negotiated-institution",
                nome_publico="Programa fiscal institucional",
                vertical="tax",
                commercial_model="negotiated",
                subject_type="institution",
                estado="published",
                moeda=None,
                preco=None,
                billing_period=None,
                usage_unit=None,
                usage_limit=None,
                contract_version=3,
            ),
            models.CheckoutOffer(
                id=4,
                codigo="tax-draft-company",
                nome_publico="Oferta em preparacao",
                vertical="tax",
                commercial_model="monthly",
                subject_type="company",
                estado="draft",
                moeda="BRL",
                preco=Decimal("11.00"),
                billing_period="month",
                contract_version=1,
            ),
            models.CheckoutOffer(
                id=5,
                codigo="document-retired-cpf",
                nome_publico="Oferta retirada",
                vertical="document",
                commercial_model="one_time",
                subject_type="cpf",
                estado="retired",
                moeda="BRL",
                preco=Decimal("12.00"),
                usage_unit="document",
                usage_limit=1,
                contract_version=1,
            ),
        ]
        db.add_all(ofertas)
        db.flush()
        db.add_all(
            [
                models.CheckoutOfferCapability(offer_id=1, codigo="tax.advisory"),
                models.CheckoutOfferCapability(offer_id=1, codigo="tax.report"),
                models.CheckoutOfferCapability(offer_id=2, codigo="document.extract"),
                models.CheckoutOfferCapability(offer_id=2, codigo="document.validate"),
                models.CheckoutOfferCapability(offer_id=3, codigo="tax.audit"),
                models.CheckoutOfferCapability(offer_id=4, codigo="tax.draft"),
                models.CheckoutOfferCapability(offer_id=5, codigo="document.legacy"),
            ]
        )

    servico = catalog.CheckoutOfferCatalog(Session)
    publicadas = servico.listar_ofertas_publicadas()
    assert isinstance(publicadas, tuple)
    assert [oferta.codigo for oferta in publicadas] == [
        "document-one-time-company",
        "tax-monthly-cpf",
        "tax-negotiated-institution",
    ]
    assert {oferta.estado for oferta in publicadas} == {"published"}
    assert {oferta.vertical for oferta in publicadas} == {"tax", "document"}
    assert {oferta.subject_type for oferta in publicadas} == {
        "cpf",
        "company",
        "institution",
    }
    assert all(sa_inspect(oferta, raiseerr=False) is None for oferta in publicadas)

    mensal = servico.obter_oferta_publicada("tax-monthly-cpf")
    assert mensal.nome_publico == "Assistencia fiscal mensal"
    assert mensal.commercial_model == "monthly"
    assert mensal.moeda == "BRL"
    assert mensal.preco == Decimal("39.90")
    assert mensal.billing_period == "month"
    assert mensal.capabilities == ("tax.advisory", "tax.report")
    assert mensal.capabilities == tuple(sorted(set(mensal.capabilities)))
    assert all("mei" not in campo.lower() for campo in vars(mensal))
    assert mensal.contract_version == 1
    assert mensal.criado_em is not None
    assert mensal.atualizado_em is not None

    avulsa = servico.resolver_oferta_para_checkout(
        "document-one-time-company"
    )
    assert avulsa.commercial_model == "one_time"
    assert avulsa.moeda == "BRL"
    assert avulsa.preco == Decimal("79.50")
    assert avulsa.usage_unit == "document"
    assert avulsa.usage_limit == 5
    assert avulsa.capabilities == ("document.extract", "document.validate")
    assert avulsa.capabilities == tuple(sorted(set(avulsa.capabilities)))

    mensal_checkout = servico.resolver_oferta_para_checkout("tax-monthly-cpf")
    assert mensal_checkout.preco == Decimal("39.90")
    assert mensal_checkout.moeda == "BRL"
    assert mensal_checkout.vertical == "tax"
    assert mensal_checkout.subject_type == "cpf"
    assert mensal_checkout.capabilities == ("tax.advisory", "tax.report")

    negociada = servico.obter_oferta_publicada(
        "tax-negotiated-institution"
    )
    assert negociada.commercial_model == "negotiated"
    assert negociada.preco is None
    assert negociada.moeda is None
    assert negociada.checkout_mode == "proposal"

    erro_publico = catalog.CheckoutOfferCatalogError
    for codigo in (
        "tax-draft-company",
        "document-retired-cpf",
        "tax-negotiated-institution",
    ):
        with pytest.raises(erro_publico) as capturada:
            servico.resolver_oferta_para_checkout(codigo)
        _assert_erro_publico_sanitizado(capturada.value)
        assert "mercado pago" not in str(capturada.value).lower()

    for codigo in ("tax-draft-company", "document-retired-cpf"):
        with pytest.raises(erro_publico):
            servico.obter_oferta_publicada(codigo)

    # Snapshot imutavel, independente da identidade e do ciclo da entidade ORM.
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        mensal.preco = Decimal("0.01")
    with pytest.raises((AttributeError, TypeError)):
        mensal.capabilities += ("browser.injected",)

    with Session.begin() as db:
        persistida = db.get(models.CheckoutOffer, 1)
        persistida.nome_publico = "Nome alterado depois do snapshot"
        persistida.preco = Decimal("44.90")

    assert mensal.nome_publico == "Assistencia fiscal mensal"
    assert mensal.preco == Decimal("39.90")
    assert mensal.capabilities == ("tax.advisory", "tax.report")
    str(mensal)
    repr(mensal)
    with Session() as db:
        assert db.get(models.CheckoutOffer, 1).preco == Decimal("44.90")
    assert servico.obter_oferta_publicada("tax-monthly-cpf").preco == Decimal(
        "44.90"
    )

    # O browser fornece apenas o codigo; valores comerciais nao fazem parte da API.
    for metodo in (
        servico.obter_oferta_publicada,
        servico.resolver_oferta_para_checkout,
    ):
        with pytest.raises(TypeError):
            metodo("tax-monthly-cpf", preco=Decimal("0.01"))
        with pytest.raises(TypeError):
            metodo("tax-monthly-cpf", moeda="USD")
        with pytest.raises(TypeError):
            metodo("tax-monthly-cpf", token="segredo-browser")

    invalidos = (
        "",
        " ",
        " tax-monthly-cpf",
        "tax-monthly-cpf ",
        "tax monthly cpf",
        "tax_monthly_cpf",
        "Tax-monthly-cpf",
        "tax--monthly-cpf",
        "tax-monthly-cpf\n",
        "tax-monthly-cpf\r",
        "táx-monthly-cpf",
        "文档-one-time-company",
    )
    for codigo in invalidos:
        with pytest.raises(erro_publico) as capturada:
            servico.obter_oferta_publicada(codigo)
        _assert_erro_publico_sanitizado(capturada.value)

    # Existencia nao publica automaticamente uma oferta nova.
    with Session.begin() as db:
        db.add(
            models.CheckoutOffer(
                codigo="document-existing-company",
                nome_publico="Existe mas nao foi publicada",
                vertical="document",
                commercial_model="one_time",
                subject_type="company",
                estado="draft",
                moeda="BRL",
                preco=Decimal("25.00"),
                usage_unit="document",
                usage_limit=1,
                contract_version=1,
            )
        )
    assert "document-existing-company" not in {
        oferta.codigo for oferta in servico.listar_ofertas_publicadas()
    }

    _provar_configuracoes_invalidas_falham_fechadas(
        Session, models, catalog
    )


def _provar_configuracoes_invalidas_falham_fechadas(Session, models, catalog):
    casos = (
        ("invalid-monthly-zero", "monthly", "BRL", Decimal("0"), "month", None, None, ("tax.report",)),
        ("invalid-monthly-currency", "monthly", "USD", Decimal("10"), "month", None, None, ("tax.report",)),
        ("invalid-monthly-period", "monthly", "BRL", Decimal("10"), "year", None, None, ("tax.report",)),
        ("invalid-one-time-limit", "one_time", "BRL", Decimal("10"), None, "document", 0, ("document.extract",)),
        ("invalid-negotiated-price", "negotiated", "BRL", Decimal("10"), None, None, None, ("tax.audit",)),
        ("invalid-empty-capabilities", "monthly", "BRL", Decimal("10"), "month", None, None, ()),
    )
    for numero, caso in enumerate(casos, start=100):
        codigo, modelo, moeda, preco, periodo, unidade, limite, capacidades = caso
        with Session.begin() as db:
            oferta = models.CheckoutOffer(
                id=numero,
                codigo=codigo,
                nome_publico="Configuracao invalida",
                vertical="tax",
                commercial_model=modelo,
                subject_type="company",
                estado="published",
                moeda=moeda,
                preco=preco,
                billing_period=periodo,
                usage_unit=unidade,
                usage_limit=limite,
                contract_version=1,
            )
            db.add(oferta)
            db.flush()
            db.add_all(
                models.CheckoutOfferCapability(offer_id=numero, codigo=capacidade)
                for capacidade in capacidades
            )

        with pytest.raises(catalog.CheckoutOfferCatalogError) as capturada:
            catalog.CheckoutOfferCatalog(Session).obter_oferta_publicada(codigo)
        _assert_erro_publico_sanitizado(
            capturada.value,
            "SELECT checkout_offers",
            "segredo-ultrassecreto-9931",
            "0.01",
        )


def _assert_erro_publico_sanitizado(erro, *proibidos):
    assert type(erro).__name__ == "CheckoutOfferCatalogError"
    for representacao in (str(erro), repr(erro)):
        texto = representacao.lower()
        for marcador in (
            "credential",
            "credencial",
            "payload",
            "secret",
            "segredo",
            "select ",
            "sqlalchemy",
            "token",
        ):
            assert marcador not in texto
        for proibido in proibidos:
            assert str(proibido).lower() not in texto
