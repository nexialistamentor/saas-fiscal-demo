"""Contrato RED offline do despacho de ordem one_time baseada em oferta.

O primeiro ponto causal e a importacao direta do modulo futuro. Este contrato
nao usa rede, SDK, credenciais, webhook, rota publica ou catalogo no despacho.
"""

from dataclasses import FrozenInstanceError
from decimal import Decimal
from inspect import Parameter, signature

import pytest
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


CHECKOUT_URL = "https://checkout.example.invalid/one-time/provider-4719"


class _GatewayEspiao:
    def __init__(self, resposta=None, erro=None):
        self.resposta = resposta or {
            "provider_order_id": "provider-one-time-4719",
            "checkout_url": CHECKOUT_URL,
        }
        self.erro = erro
        self.chamadas = []

    def criar_cobranca(self, **kwargs):
        self.chamadas.append(kwargs)
        if self.erro is not None:
            raise self.erro
        return self.resposta


def _oferta(models, *, identificador, codigo, commercial_model="one_time"):
    mensal = commercial_model == "monthly"
    oferta = models.CheckoutOffer(
        id=identificador,
        codigo=codigo,
        nome_publico=f"Oferta {identificador}",
        vertical="document",
        commercial_model=commercial_model,
        subject_type="company",
        estado="published",
        moeda="BRL",
        preco=Decimal("79.50") if not mensal else Decimal("49.90"),
        billing_period="month" if mensal else None,
        usage_unit=None if mensal else "document",
        usage_limit=None if mensal else 7,
        contract_version=3,
    )
    oferta.capabilities = [
        models.CheckoutOfferCapability(codigo="document.extract"),
        models.CheckoutOfferCapability(codigo="document.validate"),
    ]
    return oferta


def _ambiente(models):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=True)
    with Session.begin() as db:
        db.add(models.Plano(
            id=7, nome="Legado", limite_cnpjs=1, limite_analises=1,
            preco=Decimal("29.90"), billing_type="monthly",
        ))
        db.add_all([
            models.User(id=41, email="owner@example.invalid", hashed_password="hash"),
            models.User(id=42, email="other@example.invalid", hashed_password="hash"),
            models.Empresa(id=301, razao_social="Owned", user_id=41),
            models.Empresa(id=302, razao_social="Other", user_id=42),
            models.Empresa(id=303, razao_social="Also owned", user_id=41),
            _oferta(models, identificador=1, codigo="document-one-time-company"),
            _oferta(
                models, identificador=3,
                codigo="document-one-time-mutated-company",
            ),
            _oferta(
                models, identificador=2, codigo="document-monthly-company",
                commercial_model="monthly",
            ),
        ])
    return engine, Session


def _criar_ordem(composition, Session, *, empresa_id=301,
                 offer_code="document-one-time-company", chave="dispatch-order-301"):
    return composition.CheckoutOfferOrderComposer(Session).iniciar_checkout_empresa(
        authenticated_user_id=41,
        empresa_id=empresa_id,
        offer_code=offer_code,
        idempotency_key=chave,
    )


def _contagens(Session, models):
    with Session() as db:
        return (
            db.scalar(select(func.count()).select_from(models.Pagamento)),
            db.scalar(select(func.count()).select_from(models.Entitlement)),
        )


def _estado_soberano(Session, models, ordem_id):
    with Session() as db:
        ordem = db.get(models.OrdemCheckout, ordem_id)
        user = db.get(models.User, 41)
        return {
            "provider_order_id": ordem.provider_order_id,
            "checkout_url": ordem.checkout_url,
            "estado": ordem.estado,
            "plano_id": user.plano_id,
            "consulta_paga": user.consulta_paga,
            "contagens": _contagens(Session, models),
        }


def _assert_limpa(Session, models, ordem_id):
    estado = _estado_soberano(Session, models, ordem_id)
    assert estado == {
        "provider_order_id": None,
        "checkout_url": None,
        "estado": "pending",
        "plano_id": None,
        "consulta_paga": False,
        "contagens": (0, 0),
    }


def _assert_sanitizado(erro, dispatch, *proibidos):
    assert type(erro) is dispatch.CheckoutOfferOneTimeDispatchError
    for representacao in (str(erro), repr(erro)):
        texto_publico = representacao.lower()
        for marcador in (
            "token", "segredo", "secret", "payload", "select ", "sql",
            "credencial", "credential", "interno",
        ):
            assert marcador not in texto_publico
        for proibido in proibidos:
            assert str(proibido).lower() not in texto_publico


def _despachar(dispatcher, *, user_id=41, empresa_id=301, ordem_id):
    return dispatcher.despachar(
        authenticated_user_id=user_id,
        empresa_id=empresa_id,
        ordem_id=ordem_id,
    )


def test_payments_multi_vertical_one_time_dispatch_contract_red(monkeypatch):
    import app.services.checkout_offer_one_time_dispatch as dispatch

    from app import models
    from app.services import checkout_offer_order_composition as composition

    assert issubclass(dispatch.CheckoutOfferOneTimeDispatchError, Exception)
    parametros = signature(
        dispatch.CheckoutOfferOneTimeDispatcher.despachar
    ).parameters
    assert list(parametros) == [
        "self", "authenticated_user_id", "empresa_id", "ordem_id",
    ]
    assert all(
        parametro.kind is Parameter.KEYWORD_ONLY
        for nome, parametro in parametros.items() if nome != "self"
    )

    engine, Session = _ambiente(models)
    ordem = _criar_ordem(
        composition, Session,
        offer_code="document-one-time-mutated-company",
    )
    snapshot_gateway = {
        "ordem_id": ordem.id,
        "user_id": ordem.user_id,
        "empresa_id": 301,
        "offer_code": ordem.offer_code,
        "valor": ordem.valor,
        "moeda": ordem.moeda,
        "idempotency_key": ordem.idempotency_key,
    }

    # Alterar e aposentar o catalogo prova que o despacho nao o consulta nem
    # reconstroi preco ou capabilities a partir da oferta corrente.
    with Session.begin() as db:
        oferta = db.get(models.CheckoutOffer, ordem.offer_id)
        oferta.preco = Decimal("999.99")
        oferta.estado = "retired"
        oferta.capabilities[:] = [
            models.CheckoutOfferCapability(codigo="document.changed")
        ]
    comandos = []
    event.listen(
        engine, "before_cursor_execute",
        lambda _c, _u, statement, _p, _x, _m: comandos.append(statement),
    )
    gateway = _GatewayEspiao()
    dispatcher = dispatch.CheckoutOfferOneTimeDispatcher(
        session_factory=Session, gateway=gateway
    )
    entrega = _despachar(dispatcher, ordem_id=ordem.id)

    assert gateway.chamadas == [snapshot_gateway]
    assert "plano_id" not in gateway.chamadas[0]
    assert not any("checkout_offers" in comando.lower() for comando in comandos)
    assert vars(entrega) == {
        "ordem_id": ordem.id,
        "provider_order_id": "provider-one-time-4719",
        "checkout_url": CHECKOUT_URL,
    }
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        entrega.checkout_url = "https://browser.example.invalid/changed"
    persistida = _estado_soberano(Session, models, ordem.id)
    assert persistida == {
        "provider_order_id": "provider-one-time-4719",
        "checkout_url": CHECKOUT_URL,
        "estado": "pending",
        "plano_id": None,
        "consulta_paga": False,
        "contagens": (0, 0),
    }

    # Retry usa somente a vinculacao duravel e nunca cria segunda cobranca.
    comandos.clear()
    repetida = _despachar(dispatcher, ordem_id=ordem.id)
    assert repetida == entrega
    assert gateway.chamadas == [snapshot_gateway]
    assert not any("checkout_offers" in comando.lower() for comando in comandos)
    assert _estado_soberano(Session, models, ordem.id) == persistida

    # Dados comerciais e estados do browser nem sequer pertencem a API.
    for extra in (
        {"offer_code": "browser-offer"}, {"preco": Decimal("0.01")},
        {"valor": Decimal("0.01")}, {"moeda": "USD"}, {"plano_id": 7},
        {"commercial_model": "monthly"},
        {"capabilities": ("browser.injected",)},
        {"idempotency_key": "browser-key"},
        {"provider_order_id": "browser-provider"},
        {"checkout_url": "https://browser.example.invalid"},
        {"status": "paid"}, {"estado": "paid"},
    ):
        with pytest.raises(TypeError):
            dispatcher.despachar(
                authenticated_user_id=41, empresa_id=301,
                ordem_id=ordem.id, **extra,
            )
    assert gateway.chamadas == [snapshot_gateway]

    # Falhas anteriores ao gateway: identidade, propriedade, modelo, estado e
    # snapshots/vinculacoes parciais nunca podem produzir cobranca.
    negativos = []
    mensal = _criar_ordem(
        composition, Session, offer_code="document-monthly-company",
        chave="monthly-order-301",
    )
    negativos.append((mensal.id, 41, 301))
    with Session.begin() as db:
        legada = models.OrdemCheckout(
            user_id=41, empresa_id=301, plano_id=7, valor=Decimal("29.90"),
            moeda="BRL", estado="pending", idempotency_key="legacy-order-301",
        )
        db.add(legada)
        db.flush()
        negativos.append((legada.id, 41, 301))
    negativos.extend([
        (999999, 41, 301),
        (ordem.id, 42, 301),
        (ordem.id, 999999, 301),
        (ordem.id, 41, 999999),
        (ordem.id, 41, 302),
    ])
    outra_empresa = _criar_ordem(
        composition, Session, empresa_id=303, chave="other-company-order-303"
    )
    negativos.append((outra_empresa.id, 41, 301))
    for estado in ("paid", "cancelled"):
        candidata = _criar_ordem(
            composition, Session, chave=f"state-{estado}-301"
        )
        with Session.begin() as db:
            db.get(models.OrdemCheckout, candidata.id).estado = estado
        negativos.append((candidata.id, 41, 301))

    # As tres corrupcoes seguintes simulam dados legados/incoerentes que o
    # banco atual permite parcialmente; o dispatcher deve rejeita-los.
    sem_offer = _criar_ordem(composition, Session, chave="missing-offer-301")
    incoerente = _criar_ordem(composition, Session, chave="incoherent-301")
    so_provider = _criar_ordem(composition, Session, chave="only-provider-301")
    so_url = _criar_ordem(composition, Session, chave="only-url-301")
    with engine.begin() as conn:
        conn.execute(text("PRAGMA ignore_check_constraints = ON"))
        conn.execute(text(
            "UPDATE ordens_checkout SET offer_id = NULL WHERE id = :id"
        ), {"id": sem_offer.id})
        conn.execute(text(
            "UPDATE ordens_checkout SET offer_code = '' WHERE id = :id"
        ), {"id": incoerente.id})
        conn.execute(text(
            "UPDATE ordens_checkout SET provider_order_id = 'partial-provider' "
            "WHERE id = :id"
        ), {"id": so_provider.id})
        conn.execute(text(
            "UPDATE ordens_checkout SET checkout_url = :url WHERE id = :id"
        ), {"id": so_url.id, "url": CHECKOUT_URL})
        conn.execute(text("PRAGMA ignore_check_constraints = OFF"))
    negativos.extend([
        (sem_offer.id, 41, 301), (incoerente.id, 41, 301),
        (so_provider.id, 41, 301), (so_url.id, 41, 301),
    ])
    chamadas_antes = list(gateway.chamadas)
    for ordem_id, user_id, empresa_id in negativos:
        with pytest.raises(dispatch.CheckoutOfferOneTimeDispatchError) as erro:
            _despachar(
                dispatcher, user_id=user_id, empresa_id=empresa_id,
                ordem_id=ordem_id,
            )
        _assert_sanitizado(erro.value, dispatch)
        assert gateway.chamadas == chamadas_antes
    assert _contagens(Session, models) == (0, 0)

    # Toda resposta invalida e atomica: nunca persiste metade da vinculacao.
    respostas_invalidas = (
        None,
        [],
        {},
        {"provider_order_id": "", "checkout_url": CHECKOUT_URL},
        {"provider_order_id": 4719, "checkout_url": CHECKOUT_URL},
        {"provider_order_id": "provider\r\nheader", "checkout_url": CHECKOUT_URL},
        {"provider_order_id": "provider", "checkout_url": ""},
        {"provider_order_id": "provider", "checkout_url": 4719},
        {"provider_order_id": "provider", "checkout_url": "http://inseguro"},
        {"provider_order_id": "provider", "checkout_url": "https://ok.invalid/\r\nheader"},
    )
    for numero, resposta in enumerate(respostas_invalidas):
        candidata = _criar_ordem(
            composition, Session, chave=f"invalid-response-{numero}"
        )
        gateway_invalido = _GatewayEspiao(resposta={"unused": True})
        gateway_invalido.resposta = resposta
        dispatcher_invalido = dispatch.CheckoutOfferOneTimeDispatcher(
            session_factory=Session, gateway=gateway_invalido
        )
        with pytest.raises(dispatch.CheckoutOfferOneTimeDispatchError) as erro:
            _despachar(dispatcher_invalido, ordem_id=candidata.id)
        _assert_sanitizado(erro.value, dispatch)
        assert len(gateway_invalido.chamadas) == 1
        _assert_limpa(Session, models, candidata.id)

    colisao = _criar_ordem(composition, Session, chave="provider-collision-owner")
    candidata = _criar_ordem(composition, Session, chave="provider-collision-candidate")
    with Session.begin() as db:
        db.get(models.OrdemCheckout, colisao.id).provider_order_id = "provider-collision"
        db.get(models.OrdemCheckout, colisao.id).checkout_url = CHECKOUT_URL
    gateway_colisao = _GatewayEspiao(resposta={
        "provider_order_id": "provider-collision", "checkout_url": CHECKOUT_URL,
    })
    dispatcher_colisao = dispatch.CheckoutOfferOneTimeDispatcher(Session, gateway_colisao)
    with pytest.raises(dispatch.CheckoutOfferOneTimeDispatchError) as erro:
        _despachar(dispatcher_colisao, ordem_id=candidata.id)
    _assert_sanitizado(erro.value, dispatch)
    assert len(gateway_colisao.chamadas) == 1
    _assert_limpa(Session, models, candidata.id)

    segredo = "SELECT token=ultrassecreto payload={'preco':'0.01'} SQL interno"
    candidata = _criar_ordem(composition, Session, chave="gateway-failure-301")
    gateway_falho = _GatewayEspiao(erro=RuntimeError(segredo))
    dispatcher_falho = dispatch.CheckoutOfferOneTimeDispatcher(Session, gateway_falho)
    with pytest.raises(dispatch.CheckoutOfferOneTimeDispatchError) as erro:
        _despachar(dispatcher_falho, ordem_id=candidata.id)
    _assert_sanitizado(erro.value, dispatch, segredo, "ultrassecreto", "0.01")
    assert len(gateway_falho.chamadas) == 1
    _assert_limpa(Session, models, candidata.id)

    # Falha de persistencia apos resposta exige rollback. O retry recebe a
    # mesma chave duravel; o espiao representa a idempotencia logica externa.
    candidata = _criar_ordem(composition, Session, chave="persistence-retry-301")
    gateway_retry = _GatewayEspiao(resposta={
        "provider_order_id": "provider-persistence-retry-4719",
        "checkout_url": CHECKOUT_URL,
    })
    dispatcher_retry = dispatch.CheckoutOfferOneTimeDispatcher(Session, gateway_retry)

    def falhar_update(_c, _u, statement, _p, _x, _m):
        if statement.lstrip().lower().startswith("update ordens_checkout"):
            raise RuntimeError(segredo)

    event.listen(engine, "before_cursor_execute", falhar_update)
    try:
        with pytest.raises(dispatch.CheckoutOfferOneTimeDispatchError) as erro:
            _despachar(dispatcher_retry, ordem_id=candidata.id)
        _assert_sanitizado(erro.value, dispatch, segredo)
    finally:
        event.remove(engine, "before_cursor_execute", falhar_update)
    _assert_limpa(Session, models, candidata.id)

    recuperada = _despachar(dispatcher_retry, ordem_id=candidata.id)
    assert recuperada.provider_order_id == "provider-persistence-retry-4719"
    assert len(gateway_retry.chamadas) == 2
    assert {chamada["idempotency_key"] for chamada in gateway_retry.chamadas} == {
        "persistence-retry-301"
    }
    assert _contagens(Session, models) == (0, 0)
