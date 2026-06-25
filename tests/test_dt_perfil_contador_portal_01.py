"""
tests/test_dt_perfil_contador_portal_01.py

B10-PORTAL-CONT-01A — GET /contador/perfil (backend informacional)
Cobertura:
  P1  contador aprovado consulta próprio perfil → 200 + campos exactos + crc correcto
  P2  contador pendente consulta próprio perfil → 200 + campos exactos
  P3  contador suspenso consulta próprio perfil → 200 + campos exactos
  N1  role=user → 403
  N2  contador sem PerfilContador → 404 com detail esperado
  N3  role=admin → 403
  I1  contador pendente bloqueado em /homologacoes/pendentes (guard operacional intacto)
  I2  contador suspenso bloqueado em /homologacoes/pendentes (guard operacional intacto)
"""

import uuid
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import PerfilContador, User

# Campos exactos esperados na resposta — nenhum a mais, nenhum a menos
CAMPOS_ESPERADOS = {
    "perfil_id",
    "crc",
    "uf_crc",
    "status",
    "aprovado_em",
    "aprovado_por",
    "criado_em",
}

# ---------------------------------------------------------------------------
# Helpers locais (padrão VA01 / DT-PERFIL-ADMIN-01)
# ---------------------------------------------------------------------------


@contextmanager
def _db_session():
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _cpf_unico_valido() -> str:
    base = f"{uuid.uuid4().int % 10**9:09d}"
    s = sum(int(d) * (10 - i) for i, d in enumerate(base))
    r = s % 11
    d1 = 0 if r < 2 else 11 - r
    s2 = sum(int(base[i]) * (11 - i) for i in range(9)) + d1 * 2
    r2 = s2 % 11
    d2 = 0 if r2 < 2 else 11 - r2
    return base + f"{d1}{d2}"


def _registar_user(client: TestClient) -> dict:
    email = f"portal_{uuid.uuid4().hex[:8]}@example.com"
    password = f"p{uuid.uuid4().hex}"
    res = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "tipo_usuario": "cpf",
            "documento": _cpf_unico_valido(),
        },
    )
    assert res.status_code in (200, 201), f"Registo falhou: {res.text}"
    return {"email": email, "password": password}


def _login_headers(client: TestClient, credentials: dict) -> dict:
    res = client.post(
        "/auth/login",
        data={"username": credentials["email"], "password": credentials["password"]},
    )
    assert res.status_code == 200, f"Login falhou: {res.text}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _crc_unico() -> str:
    return f"CRC-PA-{uuid.uuid4().hex[:6].upper()}"


def _criar_contador_com_status(client: TestClient, status_perfil: str) -> dict:
    """
    Cria user com role=contador e PerfilContador no status pedido.
    Devolve headers, email e crc para validação exacta nos testes.
    """
    credentials = _registar_user(client)
    crc = _crc_unico()
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        user.role = "contador"
        perfil = PerfilContador(
            user_id=user.id,
            crc=crc,
            uf_crc="PA",
            status=status_perfil,
        )
        db.add(perfil)
        db.commit()
    headers = _login_headers(client, credentials)
    return {"headers": headers, "email": credentials["email"], "crc": crc}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    from app.rate_limit import limiter

    limiter.enabled = False
    with TestClient(app) as c:
        yield c
    limiter.enabled = True


@pytest.fixture
def _admin_headers(client):
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        user.role = "admin"
        db.commit()
    return _login_headers(client, credentials)


@pytest.fixture
def _user_headers(client):
    credentials = _registar_user(client)
    return _login_headers(client, credentials)


# ---------------------------------------------------------------------------
# Testes positivos
# ---------------------------------------------------------------------------


def test_p1_contador_aprovado_consulta_perfil(client):
    """P1 — contador aprovado: 200, campos exactos, crc correcto."""
    ctx = _criar_contador_com_status(client, "aprovado")
    res = client.get("/contador/perfil", headers=ctx["headers"])
    assert res.status_code == 200, res.text
    data = res.json()
    assert set(data.keys()) == CAMPOS_ESPERADOS
    assert data["status"] == "aprovado"
    assert data["perfil_id"] is not None
    assert data["crc"] == ctx["crc"]
    assert data["uf_crc"] == "PA"
    assert data["criado_em"] is not None
    assert data["aprovado_em"] is None   # não aprovado via endpoint admin
    assert data["aprovado_por"] is None


def test_p2_contador_pendente_consulta_perfil(client):
    """P2 — contador pendente: 200, campos exactos, não bloqueado."""
    ctx = _criar_contador_com_status(client, "pendente")
    res = client.get("/contador/perfil", headers=ctx["headers"])
    assert res.status_code == 200, res.text
    data = res.json()
    assert set(data.keys()) == CAMPOS_ESPERADOS
    assert data["status"] == "pendente"
    assert data["crc"] == ctx["crc"]
    assert data["aprovado_em"] is None
    assert data["aprovado_por"] is None


def test_p3_contador_suspenso_consulta_perfil(client):
    """P3 — contador suspenso: 200, campos exactos, não bloqueado."""
    ctx = _criar_contador_com_status(client, "suspenso")
    res = client.get("/contador/perfil", headers=ctx["headers"])
    assert res.status_code == 200, res.text
    data = res.json()
    assert set(data.keys()) == CAMPOS_ESPERADOS
    assert data["status"] == "suspenso"
    assert data["crc"] == ctx["crc"]


# ---------------------------------------------------------------------------
# Testes negativos
# ---------------------------------------------------------------------------


def test_n1_user_comum_nao_acede(client, _user_headers):
    """N1 — role=user → 403."""
    res = client.get("/contador/perfil", headers=_user_headers)
    assert res.status_code == 403, res.text


def test_n2_contador_sem_perfil(client):
    """N2 — role=contador mas sem PerfilContador → 404 com detail esperado."""
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        user.role = "contador"
        db.commit()
    headers = _login_headers(client, credentials)
    res = client.get("/contador/perfil", headers=headers)
    assert res.status_code == 404, res.text
    assert "PerfilContador não encontrado" in res.json()["detail"]


def test_n3_admin_nao_acede(client, _admin_headers):
    """N3 — role=admin → 403 (admin opera por /admin/*, não /contador/*)."""
    res = client.get("/contador/perfil", headers=_admin_headers)
    assert res.status_code == 403, res.text


# ---------------------------------------------------------------------------
# Invariantes — _get_perfil_contador intacto
# ---------------------------------------------------------------------------


def test_i1_pendente_bloqueado_em_operacional(client):
    """I1 — contador pendente não acede a /homologacoes/pendentes."""
    ctx = _criar_contador_com_status(client, "pendente")
    res = client.get("/contador/homologacoes/pendentes", headers=ctx["headers"])
    assert res.status_code == 403, res.text


def test_i2_suspenso_bloqueado_em_operacional(client):
    """I2 — contador suspenso não acede a /homologacoes/pendentes."""
    ctx = _criar_contador_com_status(client, "suspenso")
    res = client.get("/contador/homologacoes/pendentes", headers=ctx["headers"])
    assert res.status_code == 403, res.text
