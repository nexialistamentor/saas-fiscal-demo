"""Contrato E2E: pagamento MEI autoriza somente a competência paga antes do SERPRO."""

from decimal import Decimal
import subprocess
import time
from types import SimpleNamespace
import uuid

import psycopg2

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import models
from app.main import app
from app.rate_limit import limiter
from app.security import tenant_empresa
from app.services.checkout_offer_one_time_confirmation import (
    CheckoutOfferOneTimeConfirmer,
)
from app.services.checkout_offer_one_time_dispatch import (
    CheckoutOfferOneTimeDispatcher,
)
from app.services.checkout_offer_order_composition import (
    CheckoutOfferOrderComposer,
)
from app.services.mei_competencia_authority import (
    tem_autoridade_economica_mei_competencia,
)
from app.services.mei_competencia_checkout_intent import (
    MeiCompetenciaCheckoutIntent,
)


EMPRESA_ID = 301
USER_ID = 41
COMPETENCIA = "202609"
OUTRA_COMPETENCIA = "202610"
OFFER_CODE = "mei-das-one-time-company"
IDEMPOTENCY_KEY = "mei-das-e2e-301-202609-v1"
CNPJ = "12345678000190"
VALOR = Decimal("39.90")


class _GatewayIsolado:
    def __init__(self):
        self.calls = []
        self.compensations = []

    def criar_cobranca(self, **data):
        self.calls.append(dict(data))
        return {
            "provider_order_id": "mp-pref-mei-das-e2e-202609",
            "checkout_url": "https://checkout.example.invalid/mei-das-e2e-202609",
        }

    def cancelar_cobranca(self, **data):
        self.compensations.append(dict(data))


class _SerproIsolado:
    def __init__(self):
        self.calls = []

    def request(self, servico, cnpj, competencia):
        self.calls.append((servico, cnpj, competencia))
        return SimpleNamespace(
            data="",
            messages=[
                {
                    "codigo": "[Aviso-PGMEI-MSG_23018]",
                    "texto": "isolated-test-provider-message",
                }
            ],
        )


def _run(*args):
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


def _published_port(container):
    published = _run("docker", "port", container, "5432/tcp")
    assert published.returncode == 0, published.stderr
    mappings = [
        line.strip()
        for line in published.stdout.splitlines()
        if line.strip()
    ]
    assert len(mappings) == 1, mappings
    host, separator, raw_port = mappings[0].rpartition(":")
    assert separator == ":", mappings[0]
    assert host == "127.0.0.1", host
    assert raw_port.isascii() and raw_port.isdigit(), raw_port
    port = int(raw_port)
    assert 1 <= port <= 65535, port
    return port


def _wait_for_postgresql(port, database, password):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        connection = None
        try:
            connection = psycopg2.connect(
                host="127.0.0.1",
                port=port,
                dbname=database,
                user="postgres",
                password=password,
                connect_timeout=1,
            )
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                probe = cursor.fetchone()
            assert probe == (1,), probe
            return
        except psycopg2.Error:
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(0.25, remaining))
        finally:
            if connection is not None:
                connection.close()

    raise AssertionError(
        "PostgreSQL 17.10 nao ficou pronto em "
        f"127.0.0.1:{port}"
    )


class _PgEnvironmentHandle:
    def __init__(self, engine, container):
        self._engine = engine
        self._container = container
        self._disposed = False

    def dispose(self):
        if self._disposed:
            return
        self._disposed = True
        self._engine.dispose()
        _run("docker", "rm", "--force", self._container)


def _ambiente():
    container = f"mei-das-economic-e2e-{uuid.uuid4().hex[:12]}"
    database = "mei_das_economic_authority_e2e"
    password = uuid.uuid4().hex
    engine = None
    container_started = False

    try:
        started = _run(
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            container,
            "-e",
            f"POSTGRES_PASSWORD={password}",
            "-e",
            f"POSTGRES_DB={database}",
            "-p",
            "127.0.0.1::5432",
            "postgres:17.10-trixie",
        )
        assert started.returncode == 0, started.stderr
        container_started = True

        port = _published_port(container)
        _wait_for_postgresql(port, database, password)

        engine = create_engine(
            f"postgresql+psycopg2://postgres:{password}"
            f"@127.0.0.1:{port}/{database}",
            connect_args={
                "connect_timeout": 5,
                "options": (
                    "-c timezone=UTC -c lock_timeout=5000 "
                    "-c statement_timeout=10000"
                ),
            },
            pool_pre_ping=True,
        )

        with engine.connect() as connection:
            assert (
                connection.execute(text("SHOW TIME ZONE")).scalar_one()
                == "UTC"
            )
            assert connection.dialect.server_version_info[:2] == (17, 10)

        required_table_names = (
            "planos",
            "usuarios",
            "empresas",
            "checkout_offers",
            "checkout_offer_capabilities",
            "checkout_offer_campaigns",
            "ordens_checkout",
            "ordem_checkout_capabilities",
            "checkout_offer_campaign_reservations",
            "tax_report_checkout_intents",
            "mei_competencia_checkout_intents",
            "mercado_pago_payment_observations",
            "eventos_pagamento",
            "relatorios_analise",
            "pagamentos",
            "checkout_offer_grants",
            "checkout_offer_grant_capabilities",
            "mei_competencia_authority_bindings",
        )
        models.Base.metadata.create_all(
            engine,
            tables=[
                models.Base.metadata.tables[name]
                for name in required_table_names
            ],
        )
        Session = sessionmaker(bind=engine, expire_on_commit=False)

        with Session() as db:
            plano = models.Plano(
                id=1,
                nome="controle legado",
                limite_cnpjs=1,
                limite_analises=1,
                preco=Decimal("29.90"),
                billing_type="monthly",
                ativo=True,
                tipo_acesso="relatorio",
            )
            db.add(plano)
            db.flush()

            owner = models.User(
                id=USER_ID,
                email="mei-das-e2e@example.invalid",
                hashed_password="hash",
                plano_id=1,
            )
            db.add(owner)
            db.flush()

            empresa = models.Empresa(
                id=EMPRESA_ID,
                user_id=USER_ID,
                cnpj=CNPJ,
                regime_tributario="mei",
                porte="mei",
                status_empresa="ativa",
            )
            db.add(empresa)
            db.flush()

            oferta = models.CheckoutOffer(
                id=7,
                codigo=OFFER_CODE,
                nome_publico="MEI DAS",
                vertical="tax",
                commercial_model="one_time",
                subject_type="company",
                estado="published",
                moeda="BRL",
                preco=VALOR,
                billing_period=None,
                usage_unit="competence",
                usage_limit=1,
                contract_version=1,
            )
            oferta.capabilities = [
                models.CheckoutOfferCapability(codigo="mei.das")
            ]
            db.add(oferta)
            db.commit()

        return _PgEnvironmentHandle(engine, container), Session

    except Exception:
        if engine is not None:
            engine.dispose()
        if container_started:
            _run("docker", "rm", "--force", container)
        raise


def test_mei_competencia_pagamento_autoriza_rota_exata_sem_bypass(
    monkeypatch,
):
    import app.routes.imposto_router as imposto_router

    engine, Session = _ambiente()
    gateway = _GatewayIsolado()
    serpro = _SerproIsolado()
    compositions = []

    def compose_serpro_isolado():
        compositions.append(True)
        return serpro

    previous_limiter_state = limiter.enabled
    previous_tenant_override = app.dependency_overrides.get(tenant_empresa)
    had_tenant_override = tenant_empresa in app.dependency_overrides

    try:
        with Session() as db:
            intent = MeiCompetenciaCheckoutIntent(db).persist(
                user_id=USER_ID,
                empresa_id=EMPRESA_ID,
                competencia=COMPETENCIA,
                offer_code=OFFER_CODE,
                checkout_idempotency_key=IDEMPOTENCY_KEY,
            )
            db.commit()

        assert intent.competencia == COMPETENCIA
        assert intent.capability == "mei.das"

        ordem = CheckoutOfferOrderComposer(
            Session
        ).iniciar_checkout_empresa(
            authenticated_user_id=USER_ID,
            empresa_id=EMPRESA_ID,
            offer_code=OFFER_CODE,
            idempotency_key=IDEMPOTENCY_KEY,
        )

        despacho = CheckoutOfferOneTimeDispatcher(
            Session,
            gateway,
        ).despachar(
            authenticated_user_id=USER_ID,
            empresa_id=EMPRESA_ID,
            ordem_id=ordem.id,
        )

        assert despacho.provider_order_id == "mp-pref-mei-das-e2e-202609"
        assert len(gateway.calls) == 1

        with Session() as db:
            assert (
                tem_autoridade_economica_mei_competencia(
                    db,
                    empresa_id=EMPRESA_ID,
                    competencia=COMPETENCIA,
                    capability="mei.das",
                )
                is False
            )

        monkeypatch.setattr(imposto_router, "SessionLocal", Session)
        monkeypatch.setenv("SERPRO_PGMEI_CANARY_CNPJ", CNPJ)
        monkeypatch.setattr(
            imposto_router,
            "_get_serpro_pgmei_client",
            compose_serpro_isolado,
        )

        app.dependency_overrides[tenant_empresa] = lambda: SimpleNamespace(
            id=EMPRESA_ID,
            cnpj=CNPJ,
            regime_tributario="mei",
            status_empresa="ativa",
        )
        limiter.enabled = False

        with TestClient(app) as client:
            antes = client.post(
                f"/imposto/mei/{EMPRESA_ID}/das",
                json={
                    "periodo_apuracao": COMPETENCIA,
                    "formato": "pdf",
                },
            )

            assert antes.status_code == 403
            assert antes.json()["detail"]["tipo_bloqueio"] == (
                "AUTORIDADE_ECONOMICA_MEI_COMPETENCIA_AUSENTE"
            )
            assert compositions == []
            assert serpro.calls == []

            confirmado = CheckoutOfferOneTimeConfirmer(
                Session
            ).confirmar_pagamento_autorizado(
                ordem.id,
                "812820260924",
                "471920260924",
                VALOR,
                "BRL",
            )

            assert confirmado.estado == "paid"

            with Session() as db:
                bindings = (
                    db.query(models.MeiCompetenciaAuthorityBinding)
                    .filter(
                        models.MeiCompetenciaAuthorityBinding.ordem_id
                        == ordem.id
                    )
                    .all()
                )
                assert len(bindings) == 1
                assert bindings[0].empresa_id == EMPRESA_ID
                assert bindings[0].competencia == COMPETENCIA
                assert bindings[0].capability == "mei.das"

                assert (
                    tem_autoridade_economica_mei_competencia(
                        db,
                        empresa_id=EMPRESA_ID,
                        competencia=COMPETENCIA,
                        capability="mei.das",
                    )
                    is True
                )
                assert (
                    tem_autoridade_economica_mei_competencia(
                        db,
                        empresa_id=EMPRESA_ID,
                        competencia=OUTRA_COMPETENCIA,
                        capability="mei.das",
                    )
                    is False
                )

            autorizada = client.post(
                f"/imposto/mei/{EMPRESA_ID}/das",
                json={
                    "periodo_apuracao": COMPETENCIA,
                    "formato": "pdf",
                },
            )

            assert autorizada.status_code == 200
            assert autorizada.json()["estado_oficial"] == "nao_emitido"
            assert compositions == [True]
            assert serpro.calls == [
                ("GERARDASPDF21", CNPJ, COMPETENCIA)
            ]

            outra = client.post(
                f"/imposto/mei/{EMPRESA_ID}/das",
                json={
                    "periodo_apuracao": OUTRA_COMPETENCIA,
                    "formato": "pdf",
                },
            )

            assert outra.status_code == 403
            assert outra.json()["detail"]["tipo_bloqueio"] == (
                "AUTORIDADE_ECONOMICA_MEI_COMPETENCIA_AUSENTE"
            )
            assert compositions == [True]
            assert serpro.calls == [
                ("GERARDASPDF21", CNPJ, COMPETENCIA)
            ]

    finally:
        if had_tenant_override:
            app.dependency_overrides[tenant_empresa] = previous_tenant_override
        else:
            app.dependency_overrides.pop(tenant_empresa, None)
        limiter.reset()
        limiter.enabled = previous_limiter_state
        engine.dispose()
