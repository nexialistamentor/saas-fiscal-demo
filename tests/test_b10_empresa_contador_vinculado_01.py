"""
tests/test_b10_empresa_contador_vinculado_01.py

B10-EMPRESA-01 — GET /empresas/{empresa_id}/contador-vinculado
Cobertura:
  P1  titular com vínculo activo → 200 + campos exactos + crc correcto
  P2  titular sem vínculo → 200 + vinculos=[]
  P3  titular vê vínculo suspenso → 200 + status=suspenso
  N1  outro utilizador → 403
  N2  contador (não titular) → 403
  N3  admin (não titular) → 403
"""

import uuid
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import ContadorEmpresaVinculo, Empresa, PerfilContador, User

CAMPOS_VINCULO = {"vinculo_id", "escopo_chave", "status", "criado_em", "contador"}
CAMPOS_CONTADOR = {"crc", "uf_crc", "status_regulatorio"}
CAMPOS_RESPOSTA = {"empresa_id", "vinculos"}


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
    email = f"empresa_b10_{uuid.uuid4().hex[:8]}@example.com"
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
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    terms = client.post("/auth/accept-terms", headers=headers)
    assert terms.status_code == 200, f"accept-terms falhou: {terms.text}"
    return headers


def _crc_unico() -> str:
    return f"CRC-B10-{uuid.uuid4().hex[:6].upper()}"


def _criar_empresa_para_user(credentials: dict) -> int:
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        empresa = Empresa(
            user_id=user.id,
            razao_social="Empresa B10",
            regime_tributario="simples_nacional",
            cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
        return empresa.id


def _criar_contador_aprovado() -> tuple[int, str]:
    """Devolve (perfil_id, crc)."""
    crc = _crc_unico()
    with _db_session() as db:
        user = User(
            email=f"cont_b10_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="x",
            role="contador",
        )
        db.add(user)
        db.flush()
        perfil = PerfilContador(
            user_id=user.id,
            crc=crc,
            uf_crc="PA",
            status="aprovado",
        )
        db.add(perfil)
        db.commit()
        db.refresh(perfil)
        return perfil.id, crc


def _criar_vinculo(
    *,
    contador_id: int,
    empresa_id: int,
    admin_user_id: int,
    admin_email: str,
    status: str = "activo",
) -> int:
    with _db_session() as db:
        vinculo = ContadorEmpresaVinculo(
            contador_id=contador_id,
            empresa_id=empresa_id,
            escopo_chave="homologacao_documental",
            origem="admin",
            origem_cliente="plataforma_directa",
            status=status,
            criado_por_user_id=admin_user_id,
            criado_por_email=admin_email,
        )
        db.add(vinculo)
        db.commit()
        db.refresh(vinculo)
        return vinculo.id


@pytest.fixture
def client():
    from app.rate_limit import limiter

    limiter.enabled = False
    with TestClient(app) as c:
        yield c
    limiter.enabled = True


@pytest.fixture
def _admin_user_id(client):
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        user.role = "admin"
        db.commit()
        return user.id, credentials["email"]


@pytest.fixture
def _titular_ctx(client):
    credentials = _registar_user(client)
    empresa_id = _criar_empresa_para_user(credentials)
    headers = _login_headers(client, credentials)
    return {"headers": headers, "empresa_id": empresa_id, "credentials": credentials}


@pytest.fixture
def _outro_titular_headers(client):
    credentials = _registar_user(client)
    _criar_empresa_para_user(credentials)
    return _login_headers(client, credentials)


@pytest.fixture
def _contador_headers(client):
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        user.role = "contador"
        perfil = PerfilContador(
            user_id=user.id,
            crc=_crc_unico(),
            uf_crc="PA",
            status="aprovado",
        )
        db.add(perfil)
        db.commit()
    return _login_headers(client, credentials)


@pytest.fixture
def _admin_headers(client):
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        user.role = "admin"
        db.commit()
    return _login_headers(client, credentials)


def test_p1_titular_com_vinculo_activo(client, _titular_ctx, _admin_user_id):
    """P1 — titular consulta vínculo activo: 200, campos exactos, crc correcto."""
    admin_id, admin_email = _admin_user_id
    contador_id, crc = _criar_contador_aprovado()
    vinculo_id = _criar_vinculo(
        contador_id=contador_id,
        empresa_id=_titular_ctx["empresa_id"],
        admin_user_id=admin_id,
        admin_email=admin_email,
    )

    res = client.get(
        f"/empresas/{_titular_ctx['empresa_id']}/contador-vinculado",
        headers=_titular_ctx["headers"],
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert set(data.keys()) == CAMPOS_RESPOSTA
    assert data["empresa_id"] == _titular_ctx["empresa_id"]
    assert len(data["vinculos"]) == 1
    v = data["vinculos"][0]
    assert set(v.keys()) == CAMPOS_VINCULO
    assert v["vinculo_id"] == vinculo_id
    assert v["escopo_chave"] == "homologacao_documental"
    assert v["status"] == "activo"
    assert v["criado_em"] is not None
    assert set(v["contador"].keys()) == CAMPOS_CONTADOR
    assert v["contador"]["crc"] == crc
    assert v["contador"]["uf_crc"] == "PA"
    assert v["contador"]["status_regulatorio"] == "aprovado"


def test_p2_titular_sem_vinculo(client, _titular_ctx):
    """P2 — titular sem vínculo: 200 + lista vazia."""
    res = client.get(
        f"/empresas/{_titular_ctx['empresa_id']}/contador-vinculado",
        headers=_titular_ctx["headers"],
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert set(data.keys()) == CAMPOS_RESPOSTA
    assert data["empresa_id"] == _titular_ctx["empresa_id"]
    assert data["vinculos"] == []


def test_p3_titular_ve_vinculo_suspenso(client, _titular_ctx, _admin_user_id):
    """P3 — titular vê vínculo suspenso com status correcto."""
    admin_id, admin_email = _admin_user_id
    contador_id, crc = _criar_contador_aprovado()
    _criar_vinculo(
        contador_id=contador_id,
        empresa_id=_titular_ctx["empresa_id"],
        admin_user_id=admin_id,
        admin_email=admin_email,
        status="suspenso",
    )

    res = client.get(
        f"/empresas/{_titular_ctx['empresa_id']}/contador-vinculado",
        headers=_titular_ctx["headers"],
    )
    assert res.status_code == 200, res.text
    v = res.json()["vinculos"][0]
    assert v["status"] == "suspenso"
    assert v["contador"]["crc"] == crc


def test_n1_outro_utilizador_bloqueado(client, _titular_ctx, _outro_titular_headers):
    """N1 — outro utilizador não acede à empresa alheia → 403."""
    res = client.get(
        f"/empresas/{_titular_ctx['empresa_id']}/contador-vinculado",
        headers=_outro_titular_headers,
    )
    assert res.status_code == 403, res.text


def test_n2_contador_nao_titular_bloqueado(client, _titular_ctx, _contador_headers):
    """N2 — contador sem titularidade → 403."""
    res = client.get(
        f"/empresas/{_titular_ctx['empresa_id']}/contador-vinculado",
        headers=_contador_headers,
    )
    assert res.status_code == 403, res.text


def test_n3_admin_nao_titular_bloqueado(client, _titular_ctx, _admin_headers):
    """N3 — admin sem titularidade → 403 (opera por /admin/*)."""
    res = client.get(
        f"/empresas/{_titular_ctx['empresa_id']}/contador-vinculado",
        headers=_admin_headers,
    )
    assert res.status_code == 403, res.text
