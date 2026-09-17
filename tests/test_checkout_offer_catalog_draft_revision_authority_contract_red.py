"""Contrato RED da autoridade de revisao de rascunho do catalogo."""

from decimal import Decimal
from importlib import import_module
from inspect import signature

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


_CODIGO = "tax-report-one-time-company"


def _ambiente(models):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=True)


def _termos_revisados(**mudancas):
    dados = {
        "codigo": _CODIGO,
        "expected_contract_version": 1,
        "nome_publico": "Diagnóstico Fiscal MEI",
        "vertical": "tax",
        "commercial_model": "one_time",
        "subject_type": "company",
        "moeda": "BRL",
        "preco": Decimal("49.90"),
        "billing_period": None,
        "usage_unit": "report",
        "usage_limit": 1,
        "capabilities": ("tax.calculate", "tax.report"),
    }
    dados.update(mudancas)
    return dados


def _criar_rascunho(autoridade):
    return autoridade.criar_rascunho(
        codigo=_CODIGO,
        nome_publico="Diagn?stico Fiscal MEI",
        vertical="tax",
        commercial_model="one_time",
        subject_type="company",
        moeda="BRL",
        preco=Decimal("39.90"),
        billing_period=None,
        usage_unit="diagnostic",
        usage_limit=1,
        capabilities=("tax.diagnostic",),
    )


def _oferta(Session, models, codigo=_CODIGO):
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
            "criado_em": oferta.criado_em,
            "atualizado_em": oferta.atualizado_em,
            "capabilities": tuple(
                sorted(capability.codigo for capability in oferta.capabilities)
            ),
        }


def _snapshot_persistido(Session, models):
    campos = (
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
    with Session() as db:
        ofertas = tuple(
            tuple(row)
            for row in db.execute(
                select(*campos).order_by(models.CheckoutOffer.id)
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
    return ofertas, capabilities


def _rejeita_sem_mutacao(Session, models, operacao):
    antes = _snapshot_persistido(Session, models)
    with pytest.raises(Exception):
        operacao()
    assert _snapshot_persistido(Session, models) == antes


def test_checkout_offer_catalog_draft_revision_authority_contract_red():
    publication = import_module(
        "app.services.checkout_offer_catalog_publication"
    )
    catalog = import_module("app.services.checkout_offer_catalog")
    models = import_module("app.models")

    Session = _ambiente(models)
    autoridade = publication.CheckoutOfferCatalogPublicationAuthority(Session)
    leitura = catalog.CheckoutOfferCatalog(Session)
    _criar_rascunho(autoridade)

    # RED intencional: a autoridade dedicada ainda nao existe.
    revisar_rascunho = autoridade.revisar_rascunho
    assert tuple(signature(revisar_rascunho).parameters) == tuple(
        _termos_revisados()
    )

    antes = _oferta(Session, models)
    revisado = revisar_rascunho(**_termos_revisados())
    depois = _oferta(Session, models)

    assert depois == {
        "id": antes["id"],
        "codigo": antes["codigo"],
        "nome_publico": "Diagnóstico Fiscal MEI",
        "vertical": "tax",
        "commercial_model": "one_time",
        "subject_type": "company",
        "estado": "draft",
        "moeda": "BRL",
        "preco": Decimal("49.90"),
        "billing_period": None,
        "usage_unit": "report",
        "usage_limit": 1,
        "contract_version": antes["contract_version"] + 1,
        "criado_em": antes["criado_em"],
        "atualizado_em": depois["atualizado_em"],
        "capabilities": ("tax.calculate", "tax.report"),
    }
    assert depois["atualizado_em"] != antes["atualizado_em"]
    assert revisado.id == antes["id"]
    assert revisado.codigo == antes["codigo"]
    assert revisado.estado == "draft"
    assert revisado.contract_version == 2
    assert revisado.criado_em == antes["criado_em"]
    assert revisado.capabilities == ("tax.calculate", "tax.report")

    # Mesmo revisado, o rascunho permanece invisivel ao checkout.
    _rejeita_sem_mutacao(
        Session,
        models,
        lambda: leitura.resolver_oferta_para_checkout(_CODIGO),
    )

    # CAS e validacoes canonicas/comerciais falham fechado e atomicamente.
    falhas = (
        {"expected_contract_version": 1},
        {"expected_contract_version": 3},
        {"expected_contract_version": True},
        {"expected_contract_version": "2"},
        {"expected_contract_version": None},
        {"expected_contract_version": 0},
        {"codigo": "tax-report-inexistente-company", "expected_contract_version": 2},
        {"nome_publico": ""},
        {"vertical": "accounting"},
        {"commercial_model": "lifetime"},
        {"subject_type": "person"},
        {"moeda": "USD"},
        {"preco": Decimal("0")},
        {"preco": Decimal("49.999")},
        {"billing_period": "month"},
        {"usage_unit": None},
        {"usage_limit": 0},
        {"capabilities": ()},
        {"capabilities": ("tax.report", "tax.report")},
        {"capabilities": ("Tax.Report",)},
        {"capabilities": ("tax report",)},
    )
    for mudancas in falhas:
        dados = _termos_revisados(expected_contract_version=2)
        dados.update(mudancas)
        _rejeita_sem_mutacao(
            Session,
            models,
            lambda dados=dados: revisar_rascunho(**dados),
        )

    # Uma oferta ja publicada nunca pode ser revisada por esta autoridade.
    autoridade.publicar_rascunho(
        codigo=_CODIGO,
        expected_contract_version=2,
    )
    _rejeita_sem_mutacao(
        Session,
        models,
        lambda: revisar_rascunho(
            **_termos_revisados(expected_contract_version=3)
        ),
    )
