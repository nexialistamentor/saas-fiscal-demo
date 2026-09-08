"""Contrato RED da autoridade mutavel de publicacao do catalogo."""

from decimal import Decimal
from importlib import import_module

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _ambiente(models):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=True)


def _publicar(autoridade, **mudancas):
    dados = {
        "codigo": "tax-monthly-company",
        "nome_publico": "Assistencia fiscal mensal",
        "vertical": "tax",
        "commercial_model": "monthly",
        "subject_type": "company",
        "moeda": "BRL",
        "preco": Decimal("49.90"),
        "billing_period": "month",
        "usage_unit": None,
        "usage_limit": None,
        "capabilities": ("tax.calculate", "tax.report"),
    }
    dados.update(mudancas)
    return autoridade.publicar_oferta(**dados)


def _revisar(autoridade, **mudancas):
    dados = {
        "codigo": "tax-monthly-company",
        "expected_contract_version": 1,
        "nome_publico": "Assistencia fiscal mensal revisada",
        "vertical": "tax",
        "commercial_model": "monthly",
        "subject_type": "company",
        "moeda": "BRL",
        "preco": Decimal("59.90"),
        "billing_period": "month",
        "usage_unit": None,
        "usage_limit": None,
        "capabilities": ("tax.advisory", "tax.calculate"),
    }
    dados.update(mudancas)
    return autoridade.revisar_oferta(**dados)


def _oferta(Session, models, codigo):
    with Session() as db:
        oferta = db.scalar(
            select(models.CheckoutOffer).where(
                models.CheckoutOffer.codigo == codigo
            )
        )
        assert oferta is not None
        return {
            "id": oferta.id,
            "codigo": oferta.codigo,
            "nome_publico": oferta.nome_publico,
            "vertical": oferta.vertical,
            "commercial_model": oferta.commercial_model,
            "subject_type": oferta.subject_type,
            "estado": oferta.estado,
            "moeda": oferta.moeda,
            "preco": oferta.preco,
            "billing_period": oferta.billing_period,
            "usage_unit": oferta.usage_unit,
            "usage_limit": oferta.usage_limit,
            "contract_version": oferta.contract_version,
            "capabilities": tuple(
                sorted(capability.codigo for capability in oferta.capabilities)
            ),
        }


def _snapshot_persistido(Session, models):
    campos_oferta = (
        models.CheckoutOffer.id,
        models.CheckoutOffer.codigo,
        models.CheckoutOffer.nome_publico,
        models.CheckoutOffer.vertical,
        models.CheckoutOffer.commercial_model,
        models.CheckoutOffer.subject_type,
        models.CheckoutOffer.estado,
        models.CheckoutOffer.moeda,
        models.CheckoutOffer.preco,
        models.CheckoutOffer.billing_period,
        models.CheckoutOffer.usage_unit,
        models.CheckoutOffer.usage_limit,
        models.CheckoutOffer.contract_version,
        models.CheckoutOffer.criado_em,
        models.CheckoutOffer.atualizado_em,
    )
    campos_ordem = (
        models.OrdemCheckout.id,
        models.OrdemCheckout.offer_id,
        models.OrdemCheckout.offer_code,
        models.OrdemCheckout.contract_version,
        models.OrdemCheckout.vertical,
        models.OrdemCheckout.commercial_model,
        models.OrdemCheckout.subject_type,
        models.OrdemCheckout.subject_id,
        models.OrdemCheckout.valor,
        models.OrdemCheckout.moeda,
        models.OrdemCheckout.billing_period,
        models.OrdemCheckout.usage_unit,
        models.OrdemCheckout.usage_limit,
    )
    with Session() as db:
        ofertas = tuple(
            tuple(row)
            for row in db.execute(
                select(*campos_oferta).order_by(models.CheckoutOffer.id)
            )
        )
        capabilities = tuple(
            tuple(row)
            for row in db.execute(
                select(
                    models.CheckoutOfferCapability.offer_id,
                    models.CheckoutOfferCapability.codigo,
                ).order_by(
                    models.CheckoutOfferCapability.offer_id,
                    models.CheckoutOfferCapability.codigo,
                )
            )
        )
        ordens = tuple(
            tuple(row)
            for row in db.execute(
                select(*campos_ordem).order_by(models.OrdemCheckout.id)
            )
        )
        ordem_capabilities = tuple(
            tuple(row)
            for row in db.execute(
                select(
                    models.OrdemCheckoutCapability.ordem_id,
                    models.OrdemCheckoutCapability.codigo,
                ).order_by(
                    models.OrdemCheckoutCapability.ordem_id,
                    models.OrdemCheckoutCapability.codigo,
                )
            )
        )
    return ofertas, capabilities, ordens, ordem_capabilities


def _rejeita_sem_mutacao(Session, models, operacao):
    antes = _snapshot_persistido(Session, models)
    with pytest.raises(Exception):
        operacao()
    assert _snapshot_persistido(Session, models) == antes


def test_checkout_offer_catalog_publication_authority_contract_red():
    publication = import_module(
        "app.services.checkout_offer_catalog_publication"
    )
    models = import_module("app.models")
    catalog = import_module("app.services.checkout_offer_catalog")

    Session = _ambiente(models)
    autoridade = publication.CheckoutOfferCatalogPublicationAuthority(Session)

    # A operacao administrativa recebe os termos soberanos. Ela nao recebe id,
    # contract_version, estado ou qualquer valor escolhido pelo browser.
    _publicar(autoridade)
    mensal_v1 = _oferta(Session, models, "tax-monthly-company")
    assert mensal_v1 == {
        "id": mensal_v1["id"],
        "codigo": "tax-monthly-company",
        "nome_publico": "Assistencia fiscal mensal",
        "vertical": "tax",
        "commercial_model": "monthly",
        "subject_type": "company",
        "estado": "published",
        "moeda": "BRL",
        "preco": Decimal("49.90"),
        "billing_period": "month",
        "usage_unit": None,
        "usage_limit": None,
        "contract_version": 1,
        "capabilities": ("tax.calculate", "tax.report"),
    }
    assert mensal_v1["capabilities"] == tuple(
        sorted(set(mensal_v1["capabilities"]))
    )

    # O consumidor/browser continua escolhendo somente a identidade estavel.
    leitura = catalog.CheckoutOfferCatalog(Session)
    resolvida_v1 = leitura.resolver_oferta_para_checkout(
        "tax-monthly-company"
    )
    assert resolvida_v1.codigo == "tax-monthly-company"
    assert resolvida_v1.preco == Decimal("49.90")
    assert resolvida_v1.moeda == "BRL"
    assert resolvida_v1.contract_version == 1
    assert resolvida_v1.capabilities == ("tax.calculate", "tax.report")

    # Os tres, e somente os tres, modelos comerciais existentes sao validos.
    _publicar(
        autoridade,
        codigo="document-one-time-company",
        nome_publico="Processamento de documentos",
        vertical="document",
        commercial_model="one_time",
        moeda="BRL",
        preco=Decimal("79.50"),
        billing_period=None,
        usage_unit="document",
        usage_limit=5,
        capabilities=("document.validate", "document.extract"),
    )
    avulsa = _oferta(Session, models, "document-one-time-company")
    assert avulsa["contract_version"] == 1
    assert avulsa["commercial_model"] == "one_time"
    assert avulsa["moeda"] == "BRL"
    assert avulsa["preco"] == Decimal("79.50")
    assert avulsa["billing_period"] is None
    assert avulsa["usage_unit"] == "document"
    assert avulsa["usage_limit"] == 5
    assert avulsa["capabilities"] == (
        "document.extract",
        "document.validate",
    )

    _publicar(
        autoridade,
        codigo="tax-negotiated-institution",
        nome_publico="Programa fiscal institucional",
        commercial_model="negotiated",
        subject_type="institution",
        moeda=None,
        preco=None,
        billing_period=None,
        usage_unit=None,
        usage_limit=None,
        capabilities=("tax.audit",),
    )
    negociada = _oferta(Session, models, "tax-negotiated-institution")
    assert negociada["contract_version"] == 1
    assert negociada["commercial_model"] == "negotiated"
    assert negociada["moeda"] is None
    assert negociada["preco"] is None
    assert negociada["billing_period"] is None
    assert negociada["usage_unit"] is None
    assert negociada["usage_limit"] is None

    # Uma ordem ja criada conserva o snapshot comercial da versao comprada.
    with Session.begin() as db:
        oferta = db.scalar(
            select(models.CheckoutOffer).where(
                models.CheckoutOffer.codigo == "tax-monthly-company"
            )
        )
        ordem = models.OrdemCheckout(
            id=7001,
            user_id=71,
            empresa_id=701,
            plano_id=None,
            offer_id=oferta.id,
            offer_code=oferta.codigo,
            contract_version=oferta.contract_version,
            vertical=oferta.vertical,
            commercial_model=oferta.commercial_model,
            subject_type=oferta.subject_type,
            subject_id=701,
            valor=oferta.preco,
            moeda=oferta.moeda,
            estado="paid",
            idempotency_key="catalog-publication-old-order",
            billing_period=oferta.billing_period,
            usage_unit=oferta.usage_unit,
            usage_limit=oferta.usage_limit,
        )
        ordem.capabilities = [
            models.OrdemCheckoutCapability(codigo=capability.codigo)
            for capability in oferta.capabilities
        ]
        db.add(ordem)
    snapshot_ordem_v1 = _snapshot_persistido(Session, models)[2:]

    # A revisao usa o mesmo codigo, exige CAS exato e avanca uma unica versao.
    _revisar(autoridade)
    mensal_v2 = _oferta(Session, models, "tax-monthly-company")
    assert mensal_v2["id"] == mensal_v1["id"]
    assert mensal_v2["codigo"] == mensal_v1["codigo"]
    assert mensal_v2["contract_version"] == mensal_v1["contract_version"] + 1
    assert mensal_v2["preco"] == Decimal("59.90")
    assert mensal_v2["moeda"] == "BRL"
    assert mensal_v2["capabilities"] == (
        "tax.advisory",
        "tax.calculate",
    )
    capabilities_removidas = set(mensal_v1["capabilities"]) - {
        "tax.calculate"
    }
    assert capabilities_removidas.isdisjoint(mensal_v2["capabilities"])
    assert _snapshot_persistido(Session, models)[2:] == snapshot_ordem_v1

    resolvida_v2 = leitura.resolver_oferta_para_checkout(
        "tax-monthly-company"
    )
    assert resolvida_v2.codigo == resolvida_v1.codigo
    assert resolvida_v2.preco == Decimal("59.90")
    assert resolvida_v2.contract_version == 2
    assert resolvida_v1.preco == Decimal("49.90")
    assert resolvida_v1.contract_version == 1

    # Mismatch, inclusive valores que em Python se comparam a int, falha fechado.
    for versao_divergente in (0, 1, 3, True, None, "2"):
        _rejeita_sem_mutacao(
            Session,
            models,
            lambda versao=versao_divergente: _revisar(
                autoridade,
                expected_contract_version=versao,
                preco=Decimal("999.99"),
                capabilities=("tax.browser-injected",),
            ),
        )

    # Toda entrada invalida falha sem oferta, capability ou ordem parcial.
    publicacoes_invalidas = (
        {"codigo": "Tax-invalid-company"},
        {"codigo": "tax--invalid-company"},
        {"codigo": " tax-invalid-company"},
        {"codigo": "tax-invalid-price-zero", "preco": Decimal("0")},
        {"codigo": "tax-invalid-price-scale", "preco": Decimal("10.001")},
        {"codigo": "tax-invalid-currency", "moeda": "USD"},
        {"codigo": "tax-invalid-monthly-period", "billing_period": "year"},
        {
            "codigo": "document-invalid-one-time-unit",
            "vertical": "document",
            "commercial_model": "one_time",
            "billing_period": None,
            "usage_unit": None,
            "usage_limit": 1,
        },
        {
            "codigo": "tax-invalid-negotiated-price",
            "commercial_model": "negotiated",
            "moeda": None,
            "preco": Decimal("10.00"),
            "billing_period": None,
        },
        {"codigo": "tax-invalid-fourth-model", "commercial_model": "lifetime"},
        {"codigo": "tax-invalid-empty-capabilities", "capabilities": ()},
        {
            "codigo": "tax-invalid-duplicate-capabilities",
            "capabilities": ("tax.report", "tax.report"),
        },
        {
            "codigo": "tax-invalid-noncanonical-capabilities",
            "capabilities": ("Tax.Report",),
        },
        {
            "codigo": "tax-invalid-malformed-capabilities",
            "capabilities": ("tax report",),
        },
    )
    for caso in publicacoes_invalidas:
        _rejeita_sem_mutacao(
            Session,
            models,
            lambda caso=caso: _publicar(autoridade, **caso),
        )

    revisoes_invalidas = (
        {"preco": Decimal("0")},
        {"preco": Decimal("59.999")},
        {"moeda": "USD"},
        {"billing_period": "year"},
        {"commercial_model": "lifetime"},
        {"capabilities": ()},
        {"capabilities": ("tax.audit", "tax.audit")},
        {"capabilities": ("Tax.Audit",)},
        {"capabilities": ("tax audit",)},
    )
    for caso in revisoes_invalidas:
        _rejeita_sem_mutacao(
            Session,
            models,
            lambda caso=caso: _revisar(
                autoridade,
                expected_contract_version=2,
                **caso,
            ),
        )

    assert _oferta(Session, models, "tax-monthly-company") == mensal_v2
    assert _snapshot_persistido(Session, models)[2:] == snapshot_ordem_v1
