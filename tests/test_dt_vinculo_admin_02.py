"""
DT-VINCULO-ADMIN-02 — Gestão soberana de vínculos contador↔empresa
===================================================================
Princípio: Admin cria, lista, suspende e revoga. Sem ciclo de vida, não há soberania operacional.

Cobertura:
  VA02-P1  admin lista vínculos → 200 com estrutura operacional
  VA02-P2  filtro status=activo retorna só activos
  VA02-P3  filtro contador_user_id retorna só vínculos daquele contador
  VA02-P4  filtro empresa_id retorna só vínculos daquela empresa
  VA02-P5  filtro escopo_chave retorna só escopo pedido

  VA02-P6  admin suspende vínculo activo → 200 + status=suspenso
  VA02-N1  suspender vínculo inexistente → 404
  VA02-N2  suspender vínculo revogado → 409
  VA02-N3  role=user tenta suspender → 403

  VA02-P7  admin revoga vínculo activo → 200 + revogado_em preenchido
  VA02-P8  admin revoga vínculo suspenso → 200
  VA02-N4  revogar vínculo inexistente → 404
  VA02-N5  revogar vínculo já revogado → 409
  VA02-N6  role=contador tenta revogar → 403
"""

import uuid
from contextlib import contextmanager
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.rate_limit import limiter
from app.models import (
    ContadorEmpresaVinculo,
    Empresa,
    PerfilContador,
    User,
)


# ---------------------------------------------------------------------------
# Infra BD
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _registar_user(client: TestClient) -> dict:
    limiter.reset()
    email = f"va02_{uuid.uuid4().hex}@example.com"
    password = f"p{uuid.uuid4().hex}"
    res = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "tipo_usuario": "cpf",
        },
    )
    assert res.status_code in (200, 201), (
        f"Registo falhou: {res.status_code}: {res.text}"
    )
    return {"email": email, "password": password}


def _login_headers(client: TestClient, credentials: dict) -> dict:
    res = client.post(
        "/auth/login",
        data={"username": credentials["email"], "password": credentials["password"]},
    )
    assert res.status_code == 200, f"Login falhou: {res.text}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def _admin_creds_headers(client):
    """Devolve (credentials, headers) para acesso ao email do admin."""
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        user.role = "admin"
        db.commit()
    return credentials, _login_headers(client, credentials)


@pytest.fixture
def _admin_headers(client, _admin_creds_headers):
    _, headers = _admin_creds_headers
    return headers


@pytest.fixture
def _user_headers(client):
    credentials = _registar_user(client)
    return _login_headers(client, credentials)


@pytest.fixture
def _contador_headers(client):
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        user.role = "contador"
        perfil = PerfilContador(
            user_id=user.id,
            crc=f"CRC-VA02-{uuid.uuid4().hex[:6].upper()}",
            uf_crc="PA",
            status="aprovado",
        )
        db.add(perfil)
        db.commit()
    return _login_headers(client, credentials)


@pytest.fixture
def _empresa_id(client):
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        empresa = Empresa(
            user_id=user.id,
            razao_social="Empresa VA02",
            regime_tributario="simples_nacional",
            cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
        return empresa.id


@pytest.fixture
def _contador_user_id(client):
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        user.role = "contador"
        crc = None
        for _ in range(10):
            candidato = f"CRC-VA02B-{uuid.uuid4().hex[:8].upper()}"
            if not db.query(PerfilContador).filter(PerfilContador.crc == candidato).first():
                crc = candidato
                break
        assert crc is not None, "Não foi possível gerar CRC único para o teste"
        perfil = PerfilContador(
            user_id=user.id,
            crc=crc,
            uf_crc="PA",
            status="aprovado",
        )
        db.add(perfil)
        db.commit()
        return user.id


@pytest.fixture
def _vinculo_activo(client, _admin_headers, _contador_user_id, _empresa_id):
    """Cria vínculo activo via endpoint. Devolve vinculo_id."""
    res = client.post(
        "/admin/contadores/vinculos",
        json={
            "contador_user_id": _contador_user_id,
            "empresa_id": _empresa_id,
            "escopo_chave": "homologacao_documental",
        },
        headers=_admin_headers,
    )
    assert res.status_code == 201, f"Criação de vínculo falhou: {res.text}"
    return res.json()["vinculo_id"]


@pytest.fixture
def _vinculo_suspenso(client, _admin_headers, _vinculo_activo):
    """Suspende o vínculo activo. Devolve vinculo_id."""
    res = client.post(
        f"/admin/contadores/vinculos/{_vinculo_activo}/suspender",
        headers=_admin_headers,
    )
    assert res.status_code == 200, f"Suspensão falhou: {res.text}"
    return _vinculo_activo


@pytest.fixture
def _vinculo_revogado(client, _admin_headers, _vinculo_activo):
    """Revoga o vínculo activo. Devolve vinculo_id."""
    res = client.post(
        f"/admin/contadores/vinculos/{_vinculo_activo}/revogar",
        headers=_admin_headers,
    )
    assert res.status_code == 200, f"Revogação falhou: {res.text}"
    return _vinculo_activo


# ---------------------------------------------------------------------------
# VA02-P1 a P5 — listagem e filtros
# ---------------------------------------------------------------------------

class TestDtVinculoAdmin02Listagem:

    def test_va02_p1_admin_lista_vinculos_retorna_200(
        self, client, _admin_headers, _vinculo_activo
    ):
        """Admin lista vínculos → 200 com estrutura operacional."""
        res = client.get("/admin/contadores/vinculos", headers=_admin_headers)
        assert res.status_code == 200, res.text

        data = res.json()
        assert "vinculos" in data
        assert "total" in data
        assert data["total"] >= 1

        # Verificar campos operacionais obrigatórios
        v = next((x for x in data["vinculos"] if x["vinculo_id"] == _vinculo_activo), None)
        assert v is not None, "Vínculo criado não aparece na listagem"
        assert v["contador_crc"] is not None
        assert v["contador_email"] is not None
        assert v["empresa_razao_social"] is not None
        assert v["escopo_chave"] == "homologacao_documental"
        assert v["status"] == "activo"
        assert v["origem"] == "admin"
        assert v["criado_por_email"] is not None

    def test_va02_p2_filtro_status_activo(
        self, client, _admin_headers, _vinculo_activo
    ):
        """filtro status=activo retorna só activos."""
        res = client.get(
            "/admin/contadores/vinculos?status=activo",
            headers=_admin_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert all(v["status"] == "activo" for v in data["vinculos"]), (
            "Listagem com filtro status=activo contém vínculos não activos"
        )

    def test_va02_p3_filtro_contador_user_id(
        self, client, _admin_headers, _contador_user_id, _vinculo_activo
    ):
        """filtro contador_user_id retorna só vínculos daquele contador."""
        res = client.get(
            f"/admin/contadores/vinculos?contador_user_id={_contador_user_id}",
            headers=_admin_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1
        assert all(
            v["contador_user_id"] == _contador_user_id
            for v in data["vinculos"]
        )

    def test_va02_p4_filtro_empresa_id(
        self, client, _admin_headers, _empresa_id, _vinculo_activo
    ):
        """filtro empresa_id retorna só vínculos daquela empresa."""
        res = client.get(
            f"/admin/contadores/vinculos?empresa_id={_empresa_id}",
            headers=_admin_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1
        assert all(v["empresa_id"] == _empresa_id for v in data["vinculos"])

    def test_va02_p5_filtro_escopo_chave(
        self, client, _admin_headers, _vinculo_activo
    ):
        """filtro escopo_chave retorna só escopo pedido."""
        res = client.get(
            "/admin/contadores/vinculos?escopo_chave=homologacao_documental",
            headers=_admin_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert all(
            v["escopo_chave"] == "homologacao_documental"
            for v in data["vinculos"]
        )


# ---------------------------------------------------------------------------
# VA02-P6, N1, N2, N3 — suspensão
# ---------------------------------------------------------------------------

class TestDtVinculoAdmin02Suspender:

    def test_va02_p6_admin_suspende_activo(
        self, client, _admin_headers, _vinculo_activo
    ):
        """Admin suspende vínculo activo → 200 + status=suspenso."""
        res = client.post(
            f"/admin/contadores/vinculos/{_vinculo_activo}/suspender",
            headers=_admin_headers,
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status_vinculo"] == "suspenso"

        with _db_session() as db:
            v = db.query(ContadorEmpresaVinculo).filter(
                ContadorEmpresaVinculo.id == _vinculo_activo
            ).first()
        assert v.status == "suspenso"

    def test_va02_n1_suspender_inexistente_retorna_404(
        self, client, _admin_headers
    ):
        """Suspender vínculo inexistente → 404."""
        res = client.post(
            "/admin/contadores/vinculos/9999999/suspender",
            headers=_admin_headers,
        )
        assert res.status_code == 404, f"{res.status_code}: {res.text}"

    def test_va02_n2_suspender_revogado_retorna_409(
        self, client, _admin_headers, _vinculo_revogado
    ):
        """Suspender vínculo revogado → 409."""
        res = client.post(
            f"/admin/contadores/vinculos/{_vinculo_revogado}/suspender",
            headers=_admin_headers,
        )
        assert res.status_code == 409, f"{res.status_code}: {res.text}"

    def test_va02_n3_role_user_nao_suspende(
        self, client, _user_headers, _vinculo_activo
    ):
        """role=user tenta suspender → 403."""
        res = client.post(
            f"/admin/contadores/vinculos/{_vinculo_activo}/suspender",
            headers=_user_headers,
        )
        assert res.status_code == 403, f"{res.status_code}: {res.text}"


# ---------------------------------------------------------------------------
# VA02-P7, P8, N4, N5, N6 — revogação
# ---------------------------------------------------------------------------

class TestDtVinculoAdmin02Revogar:

    def test_va02_p7_admin_revoga_activo(
        self, client, _admin_headers, _vinculo_activo
    ):
        """Admin revoga vínculo activo → 200 + revogado_em preenchido."""
        res = client.post(
            f"/admin/contadores/vinculos/{_vinculo_activo}/revogar",
            headers=_admin_headers,
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status_vinculo"] == "revogado"
        assert data["revogado_em"] is not None
        assert data["revogado_por_user_id"] is not None

    def test_va02_p8_admin_revoga_suspenso(
        self, client, _admin_headers, _vinculo_suspenso
    ):
        """Admin revoga vínculo suspenso → 200."""
        res = client.post(
            f"/admin/contadores/vinculos/{_vinculo_suspenso}/revogar",
            headers=_admin_headers,
        )
        assert res.status_code == 200, res.text
        assert res.json()["status_vinculo"] == "revogado"

    def test_va02_n4_revogar_inexistente_retorna_404(
        self, client, _admin_headers
    ):
        """Revogar vínculo inexistente → 404."""
        res = client.post(
            "/admin/contadores/vinculos/9999999/revogar",
            headers=_admin_headers,
        )
        assert res.status_code == 404, f"{res.status_code}: {res.text}"

    def test_va02_n5_revogar_ja_revogado_retorna_409(
        self, client, _admin_headers, _vinculo_revogado
    ):
        """Revogar vínculo já revogado → 409."""
        res = client.post(
            f"/admin/contadores/vinculos/{_vinculo_revogado}/revogar",
            headers=_admin_headers,
        )
        assert res.status_code == 409, f"{res.status_code}: {res.text}"

    def test_va02_n6_role_contador_nao_revoga(
        self, client, _contador_headers, _vinculo_activo
    ):
        """role=contador tenta revogar → 403."""
        res = client.post(
            f"/admin/contadores/vinculos/{_vinculo_activo}/revogar",
            headers=_contador_headers,
        )
        assert res.status_code == 403, f"{res.status_code}: {res.text}"


# ---------------------------------------------------------------------------
# VA02-N7, N8, N9 — filtros inválidos e leitura indevida
# ---------------------------------------------------------------------------

class TestDtVinculoAdmin02FiltrosERole:

    def test_va02_n7_status_invalido_retorna_422(
        self, client, _admin_headers
    ):
        """GET com status inválido → 422 (não lista vazia silenciosa)."""
        res = client.get(
            "/admin/contadores/vinculos?status=ativo",  # "ativo" ≠ "activo"
            headers=_admin_headers,
        )
        assert res.status_code == 422, (
            f"Status inválido devia devolver 422, obtido {res.status_code}: {res.text}"
        )

    @pytest.mark.parametrize("escopo_invalido", [
        "HOMOLOGACAO_DOCUMENTAL",
        "homologacao documental",
        "escopo_fora_da_lista_v1",
    ])
    def test_va02_n8_escopo_invalido_no_get_retorna_422(
        self, client, _admin_headers, escopo_invalido
    ):
        """GET com escopo inválido/uppercase → 422."""
        res = client.get(
            f"/admin/contadores/vinculos?escopo_chave={escopo_invalido}",
            headers=_admin_headers,
        )
        assert res.status_code == 422, (
            f"Escopo '{escopo_invalido}' devia devolver 422, "
            f"obtido {res.status_code}: {res.text}"
        )

    def test_va02_n9_role_user_nao_lista(
        self, client, _user_headers
    ):
        """role=user tenta listar vínculos → 403."""
        res = client.get(
            "/admin/contadores/vinculos",
            headers=_user_headers,
        )
        assert res.status_code == 403, (
            f"role=user devia ser bloqueado (403), obtido {res.status_code}: {res.text}"
        )
