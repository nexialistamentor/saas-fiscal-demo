import base64
import json
import uuid
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.database import get_db
from app.main import app
from app import models
from app.models import Empresa, User
from app.services.mei_competencia_authority import tem_autoridade_economica_mei_competencia
from app.services.mei_competencia_authority_writer import MeiCompetenciaAuthorityWriter
from app.services.mei_competencia_checkout_intent import MeiCompetenciaCheckoutIntent
from app.rate_limit import limiter


VALID_BODY = {"periodo_apuracao": "202607", "formato": "pdf"}
PDF_BASE64 = base64.b64encode(b"%PDF-1.7\ntenant binding contract\n%%EOF").decode("ascii")


@contextmanager
def _db_session():
    generator = get_db()
    db = next(generator)
    try:
        yield db
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


def _cpf_unico_valido() -> str:
    base = f"{uuid.uuid4().int % 10**9:09d}"
    total = sum(int(digit) * (10 - index) for index, digit in enumerate(base))
    remainder = total % 11
    first = 0 if remainder < 2 else 11 - remainder
    total = sum(int(base[index]) * (11 - index) for index in range(9)) + first * 2
    remainder = total % 11
    second = 0 if remainder < 2 else 11 - remainder
    return base + f"{first}{second}"


def _register_login_and_accept_terms(client, label: str) -> tuple[str, dict]:
    email = f"pgmei_tenant_{label}_{uuid.uuid4().hex}@example.com"
    password = f"p{uuid.uuid4().hex}"
    registered = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "tipo_usuario": "cpf",
            "documento": _cpf_unico_valido(),
        },
    )
    assert registered.status_code in (200, 201), registered.text

    logged_in = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert logged_in.status_code == 200, logged_in.text
    headers = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}

    accepted = client.post("/auth/accept-terms", headers=headers)
    assert accepted.status_code == 200, accepted.text
    return email, headers


def _create_active_mei(email: str, label: str) -> int:
    with _db_session() as db:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        empresa = Empresa(
            user_id=user.id,
            razao_social=f"MEI tenant binding {label}",
            regime_tributario="mei",
            cnpj=f"{uuid.uuid4().int % 10**14:014d}",
            porte="mei",
            status_empresa="ativa",
            optante_mei=True,
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
        return empresa.id


def _prepare_paid_competence(empresa_id: int, competencia: str) -> None:
    """Synthetic local purchase, materialized through the canonical writers."""
    with _db_session() as db:
        empresa = db.query(Empresa).filter(Empresa.id == empresa_id).one()
        key = "tenant-test-" + uuid.uuid4().hex
        offer = models.CheckoutOffer(
            codigo="mei-das-tenant-test-" + uuid.uuid4().hex,
            nome_publico="Synthetic MEI DAS test",
            vertical="tax", commercial_model="one_time",
            subject_type="company", estado="published", moeda="BRL",
            preco=Decimal("39.90"), billing_period=None,
            usage_unit="competence", usage_limit=1, contract_version=1,
        )
        offer.capabilities = [models.CheckoutOfferCapability(codigo="mei.das")]
        db.add(offer)
        db.flush()
        MeiCompetenciaCheckoutIntent(db).persist(
            user_id=empresa.user_id, empresa_id=empresa_id,
            competencia=competencia, offer_code=offer.codigo,
            checkout_idempotency_key=key,
        )
        order = models.OrdemCheckout(
            user_id=empresa.user_id, empresa_id=empresa_id, plano_id=None,
            offer_id=offer.id, offer_code=offer.codigo, contract_version=1,
            vertical="tax", commercial_model="one_time",
            subject_type="company", subject_id=empresa_id,
            valor=Decimal("39.90"), moeda="BRL", billing_period=None,
            usage_unit="competence", usage_limit=1,
            idempotency_key=key, estado="paid", payment_id="synthetic-" + key,
        )
        order.capabilities = [models.OrdemCheckoutCapability(codigo="mei.das")]
        db.add(order)
        db.flush()
        db.add(models.Pagamento(
            ordem_checkout_id=order.id, user_id=empresa.user_id, plano_id=None,
            idempotency_key="notification-" + key, valor=Decimal("39.90"),
            mp_payment_id=order.payment_id, status="approved",
            confirmado_em=datetime.utcnow(),
        ))
        db.flush()
        binding = MeiCompetenciaAuthorityWriter(db).materialize(order.id)
        assert binding.empresa_id == empresa_id
        assert binding.competencia == competencia
        assert tem_autoridade_economica_mei_competencia(
            db, empresa_id=empresa_id, competencia=competencia, capability="mei.das"
        )
        assert not tem_autoridade_economica_mei_competencia(
            db, empresa_id=empresa_id, competencia="202608", capability="mei.das"
        )
        db.commit()


class OfflineTransport:
    def __init__(self, effects):
        self.effects = effects

    def send(self, service, contribuinte, periodo_apuracao):
        self.effects.append(("transport", service, contribuinte, periodo_apuracao))
        detail = {
            "periodoApuracao": periodo_apuracao,
            "numeroDocumento": "12345678901234567",
            "dataVencimento": "20260820",
            "dataLimiteAcolhimento": "20260820",
            "valores": {"total": 86.05},
        }
        data = json.dumps(
            [{"pdf": PDF_BASE64, "cnpjCompleto": contribuinte, "detalhamento": detail}],
            separators=(",", ":"),
        )
        return SimpleNamespace(data=data, messages=[])


class OfflineClient:
    def __init__(self, effects, transport):
        self.effects = effects
        self.transport = transport

    def request(self, service, contribuinte, periodo_apuracao):
        self.effects.append(("client", service, contribuinte, periodo_apuracao))
        return self.transport.send(service, contribuinte, periodo_apuracao)


@pytest.fixture(autouse=True)
def _isolated_pgmei_boundary(monkeypatch):
    import app.routes.imposto_router as imposto_router

    effects = []
    transport = OfflineTransport(effects)
    offline_client = OfflineClient(effects, transport)

    def compose():
        effects.append(("compose",))
        return offline_client

    app.dependency_overrides.clear()
    limiter.enabled = False
    monkeypatch.setattr(imposto_router, "compose_serpro_pgmei", compose)
    imposto_router._get_serpro_pgmei_client.cache_clear()
    yield effects
    app.dependency_overrides.clear()
    imposto_router._get_serpro_pgmei_client.cache_clear()
    limiter.reset()
    limiter.enabled = True


def test_cross_tenant_denial_precedes_serpro_composition(client, _isolated_pgmei_boundary):
    _, headers_a = _register_login_and_accept_terms(client, "a")
    email_b, _ = _register_login_and_accept_terms(client, "b")
    empresa_b_id = _create_active_mei(email_b, "b")

    response = client.post(
        f"/imposto/mei/{empresa_b_id}/das",
        headers=headers_a,
        json=VALID_BODY,
    )

    assert response.status_code == 403, response.text
    assert _isolated_pgmei_boundary == []


def test_owner_crosses_real_tenant_guard_and_publishes_path_identity(
    client, _isolated_pgmei_boundary, monkeypatch
):
    email, headers = _register_login_and_accept_terms(client, "owner")
    empresa_id = _create_active_mei(email, "owner")
    with _db_session() as db:
        empresa = db.query(Empresa).filter(Empresa.id == empresa_id).one()
        cnpj = empresa.cnpj

    monkeypatch.setenv("SERPRO_PGMEI_CANARY_CNPJ", cnpj)
    _prepare_paid_competence(empresa_id, VALID_BODY["periodo_apuracao"])

    response = client.post(
        f"/imposto/mei/{empresa_id}/das",
        headers=headers,
        json=VALID_BODY,
    )

    assert response.status_code == 200, response.text
    assert response.json()["empresa_id"] == empresa_id
    assert [effect[0] for effect in _isolated_pgmei_boundary] == [
        "compose",
        "client",
        "transport",
    ]


def test_non_integer_empresa_id_is_rejected_before_serpro_composition(
    client, _isolated_pgmei_boundary
):
    _, headers = _register_login_and_accept_terms(client, "invalid_path")

    response = client.post(
        "/imposto/mei/not-an-integer/das",
        headers=headers,
        json=VALID_BODY,
    )

    assert response.status_code == 422, response.text
    assert _isolated_pgmei_boundary == []


def test_owner_without_paid_competence_still_blocks_before_provider(
    client, _isolated_pgmei_boundary, monkeypatch
):
    email, headers = _register_login_and_accept_terms(client, "unpaid-owner")
    empresa_id = _create_active_mei(email, "unpaid-owner")
    with _db_session() as db:
        empresa = db.query(Empresa).filter(Empresa.id == empresa_id).one()
        cnpj = empresa.cnpj
    monkeypatch.setenv("SERPRO_PGMEI_CANARY_CNPJ", cnpj)
    response = client.post(
        f"/imposto/mei/{empresa_id}/das", headers=headers, json=VALID_BODY
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["tipo_bloqueio"] == "AUTORIDADE_ECONOMICA_MEI_COMPETENCIA_AUSENTE"
    assert _isolated_pgmei_boundary == []
