"""Contrato RED offline da composicao atomica de ordem baseada em oferta.

O primeiro ponto causal e a importacao direta do modulo futuro. Nao ha
fallback, mock do modulo, gateway, rede, pagamento ou concessao de acesso.
"""

from dataclasses import FrozenInstanceError
from decimal import Decimal
from importlib import import_module
from inspect import Parameter, signature

import pytest
from sqlalchemy import create_engine, event, func, inspect as sa_inspect, select
from sqlalchemy.orm import Session as SASession, sessionmaker
from sqlalchemy.pool import StaticPool


class _SessionRastreada(SASession):
    eventos = []
    instancias = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.numero = 1 + sum(nome == "open" for nome, _ in self.eventos)
        self.fechada = False
        self.instancias.append(self)
        self.eventos.append(("open", self.numero))

    def close(self):
        self.fechada = True
        self.eventos.append(("close", self.numero))
        return super().close()


@event.listens_for(_SessionRastreada, "after_commit")
def _registar_commit(sessao):
    sessao.eventos.append(("commit", sessao.numero))


@event.listens_for(_SessionRastreada, "after_rollback")
def _registar_rollback(sessao):
    sessao.eventos.append(("rollback", sessao.numero))


def _oferta(models, *, identificador, codigo, vertical="tax",
            commercial_model="monthly", subject_type="company",
            estado="published", preco=Decimal("49.90"),
            contract_version=1, capabilities=("tax.calculate", "tax.report")):
    mensal = commercial_model == "monthly"
    negociada = commercial_model == "negotiated"
    oferta = models.CheckoutOffer(
        id=identificador,
        codigo=codigo,
        nome_publico=f"Oferta {identificador}",
        vertical=vertical,
        commercial_model=commercial_model,
        subject_type=subject_type,
        estado=estado,
        moeda=None if negociada else "BRL",
        preco=None if negociada else preco,
        billing_period="month" if mensal else None,
        usage_unit=None if mensal or negociada else "document",
        usage_limit=None if mensal or negociada else 7,
        contract_version=contract_version,
    )
    oferta.capabilities = [
        models.CheckoutOfferCapability(codigo=codigo_capability)
        for codigo_capability in capabilities
    ]
    return oferta


def _ambiente(models):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(
        bind=engine, class_=_SessionRastreada, expire_on_commit=True
    )
    with Session.begin() as db:
        db.add_all([
            models.User(id=41, email="owner@example.invalid", hashed_password="hash"),
            models.User(id=42, email="other@example.invalid", hashed_password="hash"),
            models.Empresa(id=301, razao_social="Owned", user_id=41),
            models.Empresa(id=302, razao_social="Other", user_id=42),
            models.Empresa(id=303, razao_social="Also owned", user_id=41),
        ])
        db.add_all([
            _oferta(models, identificador=1, codigo="tax-monthly-company"),
            _oferta(
                models, identificador=2, codigo="document-one-time-company",
                vertical="document", commercial_model="one_time",
                preco=Decimal("79.50"), contract_version=3,
                capabilities=("document.extract", "document.validate"),
            ),
            _oferta(models, identificador=3, codigo="tax-draft-company",
                    estado="draft"),
            _oferta(models, identificador=4, codigo="tax-retired-company",
                    estado="retired"),
            _oferta(models, identificador=5, codigo="tax-negotiated-company",
                    commercial_model="negotiated"),
            _oferta(models, identificador=6, codigo="tax-monthly-cpf",
                    subject_type="cpf"),
            _oferta(models, identificador=7, codigo="tax-monthly-institution",
                    subject_type="institution"),
            _oferta(models, identificador=8, codigo="tax-empty-capabilities-company",
                    capabilities=()),
            _oferta(models, identificador=9, codigo="tax-invalid-capabilities-company",
                    capabilities=("invalid",)),
        ])
    _SessionRastreada.eventos = []
    _SessionRastreada.instancias = []
    return engine, Session


def _sessoes_desde(indice):
    return _SessionRastreada.instancias[indice:]


def _assert_sessoes_fechadas(sessoes):
    assert all(sessao.fechada for sessao in sessoes)
    assert all(not sessao.in_transaction() for sessao in sessoes)
    assert all(
        ("close", sessao.numero) in _SessionRastreada.eventos
        for sessao in sessoes
    )


def _contagens(Session, models):
    with Session() as db:
        return (
            db.scalar(select(func.count()).select_from(models.OrdemCheckout)),
            db.scalar(select(func.count()).select_from(models.OrdemCheckoutCapability)),
            db.scalar(select(func.count()).select_from(models.Pagamento)),
            db.scalar(select(func.count()).select_from(models.Entitlement)),
        )


def _assert_erro_sanitizado(erro, composition, *proibidos):
    assert type(erro) is composition.CheckoutOfferOrderCompositionError
    for representacao in (str(erro), repr(erro)):
        texto = representacao.lower()
        for marcador in (
            "credential", "credencial", "payload", "secret", "segredo",
            "select ", "sqlalchemy", "token",
        ):
            assert marcador not in texto
        for proibido in proibidos:
            assert str(proibido).lower() not in texto


def _iniciar(composer, *, user_id=41, empresa_id=301,
             offer_code="tax-monthly-company", idempotency_key="order-tax-301"):
    return composer.iniciar_checkout_empresa(
        authenticated_user_id=user_id,
        empresa_id=empresa_id,
        offer_code=offer_code,
        idempotency_key=idempotency_key,
    )


def _assert_snapshot(entrega, esperado):
    assert sa_inspect(entrega, raiseerr=False) is None
    assert vars(entrega) == esperado
    assert isinstance(entrega.capabilities, tuple)
    assert entrega.capabilities == tuple(sorted(set(entrega.capabilities)))
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        entrega.valor = Decimal("0.01")
    with pytest.raises((AttributeError, TypeError)):
        entrega.capabilities += ("browser.injected",)


def test_payments_multi_vertical_order_snapshot_contract_red():
    composition = import_module("app.services.checkout_offer_order_composition")
    models = import_module("app.models")

    assert issubclass(composition.CheckoutOfferOrderCompositionError, Exception)
    parametros = signature(
        composition.CheckoutOfferOrderComposer.iniciar_checkout_empresa
    ).parameters
    assert list(parametros) == [
        "self", "authenticated_user_id", "empresa_id", "offer_code",
        "idempotency_key",
    ]
    assert all(
        parametro.kind is Parameter.KEYWORD_ONLY
        for nome, parametro in parametros.items() if nome != "self"
    )

    engine, Session = _ambiente(models)
    comandos = []
    event.listen(engine, "before_cursor_execute",
                 lambda _c, _u, statement, _p, _x, _m: comandos.append(statement))
    composer = composition.CheckoutOfferOrderComposer(session_factory=Session)

    instancias_antes = len(_SessionRastreada.instancias)
    tax = _iniciar(composer)
    sessoes_sucesso = _sessoes_desde(instancias_antes)
    _assert_snapshot(tax, {
        "id": tax.id, "offer_id": 1, "offer_code": "tax-monthly-company",
        "contract_version": 1, "vertical": "tax",
        "commercial_model": "monthly", "subject_type": "company",
        "subject_id": 301, "user_id": 41, "valor": Decimal("49.90"),
        "moeda": "BRL", "billing_period": "month", "usage_unit": None,
        "usage_limit": None, "capabilities": ("tax.calculate", "tax.report"),
        "idempotency_key": "order-tax-301", "estado": "pending",
        "plano_id": None,
    })
    assert any("checkout_offers" in comando.lower() for comando in comandos)
    assert any("ordens_checkout" in comando.lower() and
               "insert" in comando.lower() for comando in comandos)
    _assert_sessoes_fechadas(sessoes_sucesso)
    assert any(
        ("commit", sessao.numero) in _SessionRastreada.eventos
        for sessao in sessoes_sucesso
    )

    # A confirmacao e observada semanticamente: uma sessao nova enxerga toda a
    # ordem e as capabilities, independentemente de commit() ou begin().
    with Session() as db:
        ordem_visivel = db.get(models.OrdemCheckout, tax.id)
        assert ordem_visivel is not None
        assert tuple(cap.codigo for cap in ordem_visivel.capabilities) == tax.capabilities

    document = _iniciar(
        composer, offer_code="document-one-time-company",
        idempotency_key="order-document-301",
    )
    _assert_snapshot(document, {
        "id": document.id, "offer_id": 2,
        "offer_code": "document-one-time-company", "contract_version": 3,
        "vertical": "document", "commercial_model": "one_time",
        "subject_type": "company", "subject_id": 301, "user_id": 41,
        "valor": Decimal("79.50"), "moeda": "BRL", "billing_period": None,
        "usage_unit": "document", "usage_limit": 7,
        "capabilities": ("document.extract", "document.validate"),
        "idempotency_key": "order-document-301", "estado": "pending",
        "plano_id": None,
    })
    assert _contagens(Session, models) == (2, 4, 0, 0)

    with Session() as db:
        ordem = db.get(models.OrdemCheckout, tax.id)
        assert ordem.offer_id == 1
        assert ordem.plano_id is None
        assert sa_inspect(models.OrdemCheckout).relationships["offer"].mapper.class_ \
            is models.CheckoutOffer
        assert tuple(cap.codigo for cap in ordem.capabilities) == tax.capabilities
        assert all(cap.ordem_id == ordem.id for cap in ordem.capabilities)

    mesma = _iniciar(composer)
    assert mesma == tax
    assert mesma.id == tax.id
    assert _contagens(Session, models) == (2, 4, 0, 0)

    with Session.begin() as db:
        oferta = db.get(models.CheckoutOffer, 1)
        oferta.preco = Decimal("99.90")
        oferta.contract_version = 2
        oferta.estado = "retired"
        oferta.capabilities[:] = [
            models.CheckoutOfferCapability(codigo="tax.changed")
        ]
    retry = _iniciar(composer)
    assert retry == tax
    assert retry.valor == Decimal("49.90")
    assert retry.contract_version == 1
    assert retry.capabilities == ("tax.calculate", "tax.report")

    for alteracao in (
        {"offer_code": "document-one-time-company"},
        {"empresa_id": 303},
    ):
        antes = _contagens(Session, models)
        with pytest.raises(composition.CheckoutOfferOrderCompositionError) as erro:
            _iniciar(composer, **alteracao)
        _assert_erro_sanitizado(erro.value, composition)
        assert _contagens(Session, models) == antes

    with Session() as db:
        assert db.get(models.Empresa, 303).user_id == 41
        assert db.get(models.Empresa, 302).user_id == 42

    negativos = (
        {"user_id": 41, "empresa_id": 302, "offer_code": "document-one-time-company"},
        {"empresa_id": 999, "offer_code": "document-one-time-company"},
        {"user_id": 999, "offer_code": "document-one-time-company"},
        {"offer_code": "tax-draft-company"},
        {"offer_code": "tax-retired-company"},
        {"offer_code": "tax-negotiated-company"},
        {"offer_code": "tax-monthly-cpf"},
        {"offer_code": "tax-monthly-institution"},
        {"offer_code": "missing-company"},
        {"offer_code": "Tax-monthly-company"},
        {"offer_code": " tax-monthly-company"},
        {"offer_code": "tax--monthly-company"},
        {"offer_code": "tax-empty-capabilities-company"},
        {"offer_code": "tax-invalid-capabilities-company"},
    )
    for numero, caso in enumerate(negativos):
        antes = _contagens(Session, models)
        instancias_antes = len(_SessionRastreada.instancias)
        with pytest.raises(composition.CheckoutOfferOrderCompositionError) as erro:
            _iniciar(composer, idempotency_key=f"negative-{numero}", **caso)
        _assert_erro_sanitizado(erro.value, composition)
        assert _contagens(Session, models) == antes
        _assert_sessoes_fechadas(_sessoes_desde(instancias_antes))

    for extra in (
        {"preco": Decimal("0.01")}, {"moeda": "USD"}, {"vertical": "document"},
        {"commercial_model": "one_time"}, {"contract_version": 999},
        {"capabilities": ("browser.injected",)}, {"plano_id": 7},
        {"user_id": 41}, {"estado": "published"},
    ):
        with pytest.raises(TypeError):
            composer.iniciar_checkout_empresa(
                authenticated_user_id=41, empresa_id=301,
                offer_code="document-one-time-company",
                idempotency_key="browser-commercial-field", **extra,
            )
    assert _contagens(Session, models) == (2, 4, 0, 0)

    segredo = "SELECT ordens_checkout token=ultrassecreto payload={'preco':'0.01'}"
    def sessao_falha():
        raise RuntimeError(segredo)
    falho = composition.CheckoutOfferOrderComposer(session_factory=sessao_falha)
    with pytest.raises(composition.CheckoutOfferOrderCompositionError) as erro:
        _iniciar(falho, offer_code="document-one-time-company",
                 idempotency_key="internal-failure")
    _assert_erro_sanitizado(erro.value, composition, segredo, "ultrassecreto", "0.01")
    assert _contagens(Session, models) == (2, 4, 0, 0)

    # Uma falha interna depois de a escrita SQL comecar nao pode deixar linhas.
    engine_falha, SessionFalha = _ambiente(models)
    escrita_iniciada = []

    def falhar_depois_da_escrita(_c, _u, statement, _p, _x, _m):
        if "insert" in statement.lower() and "ordens_checkout" in statement.lower():
            escrita_iniciada.append(statement)
            raise RuntimeError(segredo)

    event.listen(engine_falha, "after_cursor_execute", falhar_depois_da_escrita)
    composer_falha = composition.CheckoutOfferOrderComposer(
        session_factory=SessionFalha
    )
    instancias_antes = len(_SessionRastreada.instancias)
    with pytest.raises(composition.CheckoutOfferOrderCompositionError) as erro:
        _iniciar(
            composer_falha,
            offer_code="document-one-time-company",
            idempotency_key="failure-after-write-started",
        )
    _assert_erro_sanitizado(erro.value, composition, segredo, "ultrassecreto", "0.01")
    assert escrita_iniciada
    assert _contagens(SessionFalha, models) == (0, 0, 0, 0)
    _assert_sessoes_fechadas(_sessoes_desde(instancias_antes))

    with Session() as db:
        user = db.get(models.User, 41)
        assert user.plano_id is None
        assert user.consulta_paga is False
        assert db.scalar(select(func.count()).select_from(models.RelatorioAnalise).where(
            models.RelatorioAnalise.pago.is_(True)
        )) == 0
