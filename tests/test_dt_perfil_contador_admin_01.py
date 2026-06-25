"""
tests/test_dt_perfil_contador_admin_01.py

B10-ADMIN-CONT-01 — Ciclo admin soberano de PerfilContador
Cobertura:
  P1  admin cria perfil pendente → 201
  P2  criação promove role=contador
  P3  admin lista pendentes → inclui perfil criado
  P4  admin aprova → status=aprovado + aprovado_em + aprovado_por persistidos
  P5  contador aprovado passa guard /contador/homologacoes/pendentes
  N1  role=user → 403 em criar
  N2  role=user → 403 em listar
  N3  role=user → 403 em aprovar
  N4  utilizador inexistente → 404
  N5  perfil duplicado (mesmo user) → 409
  N6  CRC duplicado (user diferente) → 409
  N7  aprovar já aprovado → 422
  N8  aprovar inexistente → 404
  N9  status de filtro inválido → 422
  N10 uf_crc inválido → 422
"""

import uuid
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import PerfilContador, User

# ---------------------------------------------------------------------------
# Helpers locais (padrão VA01)
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
    email = f"pca_{uuid.uuid4().hex[:8]}@example.com"
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


@pytest.fixture
def _user_email_para_perfil(client):
    """User sem perfil, role=user — alvo das operações de criação."""
    credentials = _registar_user(client)
    return credentials["email"]


# ---------------------------------------------------------------------------
# Testes positivos
# ---------------------------------------------------------------------------


def test_p1_admin_cria_perfil_pendente(client, _admin_headers, _user_email_para_perfil):
    """P1 — admin cria perfil pendente → 201."""
    res = client.post(
        "/admin/contadores/perfis",
        json={
            "email": _user_email_para_perfil,
            "crc": _crc_unico(),
            "uf_crc": "PA",
        },
        headers=_admin_headers,
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["perfil_status"] == "pendente"
    assert data["perfil_id"] is not None
    assert data["uf_crc"] == "PA"


def test_p2_criacao_promove_role_contador(client, _admin_headers, _user_email_para_perfil):
    """P2 — após criação, User.role = 'contador'."""
    res = client.post(
        "/admin/contadores/perfis",
        json={
            "email": _user_email_para_perfil,
            "crc": _crc_unico(),
            "uf_crc": "PA",
        },
        headers=_admin_headers,
    )
    assert res.status_code == 201, res.text

    with _db_session() as db:
        user = db.query(User).filter(User.email == _user_email_para_perfil).first()
        assert user.role == "contador"


def test_p3_admin_lista_pendentes(client, _admin_headers, _user_email_para_perfil):
    """P3 — admin lista pendentes → inclui perfil criado."""
    crc = _crc_unico()
    res_criar = client.post(
        "/admin/contadores/perfis",
        json={"email": _user_email_para_perfil, "crc": crc, "uf_crc": "PA"},
        headers=_admin_headers,
    )
    assert res_criar.status_code == 201, res_criar.text

    res = client.get(
        "/admin/contadores/perfis?status=pendente",
        headers=_admin_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    emails = [p["email"] for p in data["perfis"]]
    assert _user_email_para_perfil in emails


def test_p4_admin_aprova_perfil(client, _admin_headers, _user_email_para_perfil):
    """P4 — admin aprova → status=aprovado + aprovado_em + aprovado_por persistidos."""
    crc = _crc_unico()
    res_criar = client.post(
        "/admin/contadores/perfis",
        json={"email": _user_email_para_perfil, "crc": crc, "uf_crc": "PA"},
        headers=_admin_headers,
    )
    assert res_criar.status_code == 201, res_criar.text
    perfil_id = res_criar.json()["perfil_id"]

    res = client.post(
        f"/admin/contadores/perfis/{perfil_id}/aprovar",
        headers=_admin_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["perfil_status"] == "aprovado"
    assert data["aprovado_em"] is not None
    assert data["aprovado_por"] is not None

    # Confirmar persistência na BD
    with _db_session() as db:
        perfil = db.query(PerfilContador).filter(PerfilContador.id == perfil_id).first()
        assert perfil.status == "aprovado"
        assert perfil.aprovado_em is not None
        assert perfil.aprovado_por is not None


def test_p5_contador_aprovado_passa_guard(client, _admin_headers):
    """P5 — contador aprovado acede /contador/homologacoes/pendentes (integração MT-05b)."""
    credentials_contador = _registar_user(client)
    email_contador = credentials_contador["email"]

    res_criar = client.post(
        "/admin/contadores/perfis",
        json={"email": email_contador, "crc": _crc_unico(), "uf_crc": "PA"},
        headers=_admin_headers,
    )
    assert res_criar.status_code == 201, res_criar.text
    perfil_id = res_criar.json()["perfil_id"]

    res_aprovar = client.post(
        f"/admin/contadores/perfis/{perfil_id}/aprovar",
        headers=_admin_headers,
    )
    assert res_aprovar.status_code == 200, res_aprovar.text

    headers_contador = _login_headers(client, credentials_contador)
    res = client.get("/contador/homologacoes/pendentes", headers=headers_contador)
    assert res.status_code == 200, res.text


# ---------------------------------------------------------------------------
# Testes negativos
# ---------------------------------------------------------------------------


def test_n1_user_nao_pode_criar(client, _user_headers, _user_email_para_perfil):
    """N1 — role=user → 403 em criar."""
    res = client.post(
        "/admin/contadores/perfis",
        json={"email": _user_email_para_perfil, "crc": _crc_unico(), "uf_crc": "PA"},
        headers=_user_headers,
    )
    assert res.status_code == 403, res.text


def test_n2_user_nao_pode_listar(client, _user_headers):
    """N2 — role=user → 403 em listar."""
    res = client.get("/admin/contadores/perfis", headers=_user_headers)
    assert res.status_code == 403, res.text


def test_n3_user_nao_pode_aprovar(client, _user_headers):
    """N3 — role=user → 403 em aprovar."""
    res = client.post("/admin/contadores/perfis/999/aprovar", headers=_user_headers)
    assert res.status_code == 403, res.text


def test_n4_user_inexistente(client, _admin_headers):
    """N4 — email inexistente → 404."""
    res = client.post(
        "/admin/contadores/perfis",
        json={
            "email": "naoexiste_xyz_abc@example.com",
            "crc": _crc_unico(),
            "uf_crc": "PA",
        },
        headers=_admin_headers,
    )
    assert res.status_code == 404, res.text


def test_n5_perfil_duplicado(client, _admin_headers, _user_email_para_perfil):
    """N5 — perfil duplicado para mesmo user → 409."""
    res1 = client.post(
        "/admin/contadores/perfis",
        json={"email": _user_email_para_perfil, "crc": _crc_unico(), "uf_crc": "PA"},
        headers=_admin_headers,
    )
    assert res1.status_code == 201, res1.text

    res2 = client.post(
        "/admin/contadores/perfis",
        json={"email": _user_email_para_perfil, "crc": _crc_unico(), "uf_crc": "PA"},
        headers=_admin_headers,
    )
    assert res2.status_code == 409, res2.text


def test_n6_crc_duplicado(client, _admin_headers):
    """N6 — CRC duplicado para user diferente → 409."""
    crc_fixo = _crc_unico()

    email1 = _registar_user(client)["email"]
    email2 = _registar_user(client)["email"]

    res1 = client.post(
        "/admin/contadores/perfis",
        json={"email": email1, "crc": crc_fixo, "uf_crc": "PA"},
        headers=_admin_headers,
    )
    assert res1.status_code == 201, res1.text

    res2 = client.post(
        "/admin/contadores/perfis",
        json={"email": email2, "crc": crc_fixo, "uf_crc": "SP"},
        headers=_admin_headers,
    )
    assert res2.status_code == 409, res2.text


def test_n7_aprovar_ja_aprovado(client, _admin_headers, _user_email_para_perfil):
    """N7 — aprovar perfil já aprovado → 422."""
    res_criar = client.post(
        "/admin/contadores/perfis",
        json={"email": _user_email_para_perfil, "crc": _crc_unico(), "uf_crc": "PA"},
        headers=_admin_headers,
    )
    assert res_criar.status_code == 201, res_criar.text
    perfil_id = res_criar.json()["perfil_id"]

    res1 = client.post(
        f"/admin/contadores/perfis/{perfil_id}/aprovar",
        headers=_admin_headers,
    )
    assert res1.status_code == 200, res1.text

    res2 = client.post(
        f"/admin/contadores/perfis/{perfil_id}/aprovar",
        headers=_admin_headers,
    )
    assert res2.status_code == 422, res2.text


def test_n8_aprovar_inexistente(client, _admin_headers):
    """N8 — perfil inexistente → 404."""
    res = client.post(
        "/admin/contadores/perfis/999999/aprovar",
        headers=_admin_headers,
    )
    assert res.status_code == 404, res.text


def test_n9_status_filtro_invalido(client, _admin_headers):
    """N9 — status de filtro inválido → 422."""
    res = client.get(
        "/admin/contadores/perfis?status=invalido",
        headers=_admin_headers,
    )
    assert res.status_code == 422, res.text


def test_n10_uf_crc_invalido(client, _admin_headers, _user_email_para_perfil):
    """N10 — uf_crc com mais de 2 caracteres → 422."""
    res = client.post(
        "/admin/contadores/perfis",
        json={
            "email": _user_email_para_perfil,
            "crc": _crc_unico(),
            "uf_crc": "PARA",
        },
        headers=_admin_headers,
    )
    assert res.status_code == 422, res.text
