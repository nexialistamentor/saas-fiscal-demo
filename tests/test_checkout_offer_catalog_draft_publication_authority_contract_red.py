"""Contrato RED da autoridade de rascunho e publicacao do catalogo."""

from decimal import Decimal
from importlib import import_module
from inspect import signature

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


_CODIGO = "document-draft-company"


def _ambiente(models):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=True)


def _termos(**mudancas):
    dados = {
        "codigo": _CODIGO,
        "nome_publico": "Processamento fiscal avulso",
        "vertical": "document",
        "commercial_model": "one_time",
        "subject_type": "company",
        "moeda": "BRL",
        "preco": Decimal("39.90"),
        "billing_period": None,
        "usage_unit": "report",
        "usage_limit": 1,
        "capabilities": ("tax.report",),
    }
    dados.update(mudancas)
    return dados


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


def test_checkout_offer_catalog_draft_publication_authority_contract_red():
    publication = import_module(
        "app.services.checkout_offer_catalog_publication"
    )
    catalog = import_module("app.services.checkout_offer_catalog")
    models = import_module("app.models")

    Session = _ambiente(models)
    autoridade = publication.CheckoutOfferCatalogPublicationAuthority(Session)
    leitura = catalog.CheckoutOfferCatalog(Session)

    # O rascunho recebe os termos soberanos, mas nunca estado ou versao.
    assert tuple(signature(autoridade.criar_rascunho).parameters) == tuple(
        _termos()
    )
    assert tuple(signature(autoridade.publicar_rascunho).parameters) == (
        "codigo",
        "expected_contract_version",
    )

    criado = autoridade.criar_rascunho(**_termos())
    draft = _oferta(Session, models)
    assert draft == {
        "id": draft["id"],
        "codigo": _CODIGO,
        "nome_publico": "Processamento fiscal avulso",
        "vertical": "document",
        "commercial_model": "one_time",
        "subject_type": "company",
        "estado": "draft",
        "moeda": "BRL",
        "preco": Decimal("39.90"),
        "billing_period": None,
        "usage_unit": "report",
        "usage_limit": 1,
        "contract_version": 1,
        "criado_em": draft["criado_em"],
        "atualizado_em": draft["atualizado_em"],
        "capabilities": ("tax.report",),
    }
    assert criado.estado == "draft"
    assert criado.contract_version == 1

    # Um draft persiste, mas permanece invisivel ao checkout.
    _rejeita_sem_mutacao(
        Session,
        models,
        lambda: leitura.resolver_oferta_para_checkout(_CODIGO),
    )

    # Codigo duplicado e termos invalidos reutilizam o contrato canonico e
    # falham sem oferta ou capability parcial.
    _rejeita_sem_mutacao(
        Session,
        models,
        lambda: autoridade.criar_rascunho(**_termos()),
    )
    invalidos = (
        {"codigo": "Document-invalid-company"},
        {"preco": Decimal("0")},
        {"preco": Decimal("39.999")},
        {"moeda": "USD"},
        {"billing_period": "month"},
        {"usage_unit": None},
        {"usage_limit": 0},
        {"commercial_model": "lifetime"},
        {"capabilities": ()},
        {"capabilities": ("tax.report", "tax.report")},
        {"capabilities": ("Tax.Report",)},
        {"capabilities": ("tax report",)},
    )
    for indice, mudancas in enumerate(invalidos):
        dados = _termos(codigo=f"document-invalid-draft-{indice}")
        dados.update(mudancas)
        _rejeita_sem_mutacao(
            Session,
            models,
            lambda dados=dados: autoridade.criar_rascunho(**dados),
        )

    # Publicar usa CAS exato e nao aceita novamente termos comerciais.
    antes_publicacao = draft
    publicado = autoridade.publicar_rascunho(
        codigo=_CODIGO,
        expected_contract_version=1,
    )
    depois_publicacao = _oferta(Session, models)
    assert depois_publicacao["estado"] == "published"
    assert depois_publicacao["contract_version"] == 2
    assert depois_publicacao["atualizado_em"] != antes_publicacao["atualizado_em"]
    campos_preservados = (
        "id",
        "codigo",
        "nome_publico",
        "vertical",
        "commercial_model",
        "subject_type",
        "moeda",
        "preco",
        "billing_period",
        "usage_unit",
        "usage_limit",
        "criado_em",
        "capabilities",
    )
    assert {campo: depois_publicacao[campo] for campo in campos_preservados} == {
        campo: antes_publicacao[campo] for campo in campos_preservados
    }
    assert publicado.estado == "published"
    assert publicado.contract_version == 2

    resolvida = leitura.resolver_oferta_para_checkout(_CODIGO)
    assert resolvida.codigo == antes_publicacao["codigo"]
    assert resolvida.nome_publico == antes_publicacao["nome_publico"]
    assert resolvida.preco == antes_publicacao["preco"]
    assert resolvida.moeda == antes_publicacao["moeda"]
    assert resolvida.billing_period == antes_publicacao["billing_period"]
    assert resolvida.usage_unit == antes_publicacao["usage_unit"]
    assert resolvida.usage_limit == antes_publicacao["usage_limit"]
    assert resolvida.capabilities == antes_publicacao["capabilities"]
    assert resolvida.contract_version == 2

    # Toda falha de publicacao conserva exatamente o snapshot persistido.
    falhas = (
        ("document-inexistente-company", 1),
        (_CODIGO, 1),
        (_CODIGO, 0),
        (_CODIGO, True),
        (_CODIGO, None),
        (_CODIGO, "1"),
        (_CODIGO, 2),  # A oferta ja esta published, ainda que o CAS coincida.
    )
    for codigo, versao in falhas:
        _rejeita_sem_mutacao(
            Session,
            models,
            lambda codigo=codigo, versao=versao: autoridade.publicar_rascunho(
                codigo=codigo,
                expected_contract_version=versao,
            ),
        )
