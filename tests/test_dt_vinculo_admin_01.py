"""
DT-VINCULO-ADMIN-01 — Criação administrada de vínculo contador↔empresa
=======================================================================
Princípio: vínculo não nasce do contador. Nasce de acto administrativo auditável.

Cobertura:
  VA01-P1  admin cria vínculo → 201
  VA01-P2  ContadorEmpresaVinculo com origem=admin, status=activo, auditoria
  VA01-P3  validade futura persiste em resposta e BD
  VA01-P4  mesmo contador+empresa com escopo diferente → ambos 201
  VA01-P5  vínculo revogado existente permite novo activo igual → 201

  VA01-N1  role=user → 403
  VA01-N2  contador inexistente → 404
  VA01-N3  contador não aprovado (pendente) → 422
  VA01-N4  empresa inexistente → 404
  VA01-N5  escopo fora da lista V1 → 422
  VA01-N6  duplicado activo (INV-VINCULO-03) → 409
  VA01-N7  validade no passado → 422
  VA01-N8  sem Authorization → 401
  VA01-N9  role=contador tenta criar vínculo → 403
  VA01-N10 escopos malformados/uppercase/vazios → 422
  VA01-N11 validade ISO inválida → 400
  VA01-N12 vínculo suspenso existente bloqueia novo activo igual → 409
"""

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
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
    last_response = None
    for _ in range(10):
        email = f"va01_{uuid.uuid4().hex[:8]}@example.com"
        password = f"p{uuid.uuid4().hex}"
        documento = _cpf_unico_valido()
        res = client.post(
            "/auth/register",
            json={"email": email, "password": password,
                  "tipo_usuario": "cpf", "documento": documento},
        )
        if res.status_code in (200, 201):
            return {"email": email, "password": password}
        last_response = res
    assert False, f"Registo falhou ap?s 10 tentativas: {last_response.text}"


def _login_headers(client: TestClient, credentials: dict) -> dict:
    res = client.post(
        "/auth/login",
        data={"username": credentials["email"], "password": credentials["password"]},
    )
    assert res.status_code == 200, f"Login falhou: {res.text}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _criar_vinculo(client, headers, contador_user_id, empresa_id,
                   escopo_chave="homologacao_documental", **kwargs):
    payload = {
        "contador_user_id": contador_user_id,
        "empresa_id": empresa_id,
        "escopo_chave": escopo_chave,
        **kwargs,
    }
    return client.post("/admin/contadores/vinculos", json=payload, headers=headers)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
def _contador_headers(client):
    """role=contador — para provar que contador não pode auto-vincular."""
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        user.role = "contador"
        perfil = PerfilContador(
            user_id=user.id,
            crc=f"CRC-N9-{uuid.uuid4().hex[:6].upper()}",
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
            razao_social="Empresa VA01",
            regime_tributario="simples_nacional",
            cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
        return empresa.id


@pytest.fixture
def _contador_aprovado_user_id(client):
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        user.role = "contador"
        perfil = PerfilContador(
            user_id=user.id,
            crc=f"CRC-VA01-{uuid.uuid4().hex[:6].upper()}",
            uf_crc="PA",
            status="aprovado",
        )
        db.add(perfil)
        db.commit()
        return user.id


@pytest.fixture
def _contador_pendente_user_id(client):
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        user.role = "contador"
        perfil = PerfilContador(
            user_id=user.id,
            crc=f"CRC-PEND-{uuid.uuid4().hex[:6].upper()}",
            uf_crc="PA",
            status="pendente",
        )
        db.add(perfil)
        db.commit()
        return user.id


# ---------------------------------------------------------------------------
# VA01-P1 a P5 — fluxo positivo
# ---------------------------------------------------------------------------

class TestDtVinculoAdmin01Positivo:

    def test_va01_p1_admin_cria_vinculo_retorna_201(
        self, client, _admin_headers, _contador_aprovado_user_id, _empresa_id
    ):
        """Admin cria vínculo → 201."""
        res = _criar_vinculo(client, _admin_headers,
                             _contador_aprovado_user_id, _empresa_id)
        assert res.status_code == 201, f"{res.status_code}: {res.text}"

    def test_va01_p2_vinculo_criado_com_campos_correctos(
        self, client, _admin_headers, _contador_aprovado_user_id, _empresa_id
    ):
        """ContadorEmpresaVinculo com origem=admin, status=activo e auditoria."""
        res = _criar_vinculo(client, _admin_headers,
                             _contador_aprovado_user_id, _empresa_id)
        assert res.status_code == 201, res.text

        data = res.json()
        assert data["origem"] == "admin"
        assert data["status_vinculo"] == "activo"
        assert data["escopo_chave"] == "homologacao_documental"
        assert data["empresa_id"] == _empresa_id
        assert data["criado_por_email"] is not None
        assert data["vinculo_id"] is not None

        with _db_session() as db:
            vinculo = db.query(ContadorEmpresaVinculo).filter(
                ContadorEmpresaVinculo.id == data["vinculo_id"]
            ).first()
        assert vinculo is not None
        assert vinculo.origem == "admin"
        assert vinculo.status == "activo"
        assert vinculo.criado_por_user_id is not None

    def test_va01_p3_validade_futura_persiste(
        self, client, _admin_headers, _contador_aprovado_user_id, _empresa_id
    ):
        """Validade futura → 201, campo validade não nulo na resposta e na BD."""
        futuro = (datetime.utcnow() + timedelta(days=90)).isoformat()
        res = _criar_vinculo(client, _admin_headers,
                             _contador_aprovado_user_id, _empresa_id,
                             validade=futuro)
        assert res.status_code == 201, f"{res.status_code}: {res.text}"

        data = res.json()
        assert data["validade"] is not None, "validade deve estar na resposta"

        with _db_session() as db:
            vinculo = db.query(ContadorEmpresaVinculo).filter(
                ContadorEmpresaVinculo.id == data["vinculo_id"]
            ).first()
        assert vinculo.validade is not None

    def test_va01_p4_escopo_diferente_permite_segundo_vinculo(
        self, client, _admin_headers, _contador_aprovado_user_id, _empresa_id
    ):
        """Mesmo contador+empresa com escopos diferentes → ambos 201."""
        res1 = _criar_vinculo(client, _admin_headers,
                              _contador_aprovado_user_id, _empresa_id,
                              escopo_chave="homologacao_documental")
        assert res1.status_code == 201, res1.text

        res2 = _criar_vinculo(client, _admin_headers,
                              _contador_aprovado_user_id, _empresa_id,
                              escopo_chave="parecer_tecnico")
        assert res2.status_code == 201, (
            f"Escopo diferente devia permitir 201, obtido {res2.status_code}: {res2.text}"
        )

    def test_va01_p5_vinculo_revogado_permite_novo_activo(
        self, client, _admin_headers, _contador_aprovado_user_id, _empresa_id
    ):
        """Vínculo revogado existente → novo activo igual deve ser 201."""
        with _db_session() as db:
            # Obter perfil_id a partir do user_id
            perfil = db.query(PerfilContador).filter(
                PerfilContador.user_id == _contador_aprovado_user_id
            ).first()
            assert perfil is not None

            # Criar vínculo revogado directamente na BD
            admin_user = db.query(User).filter(User.role == "admin").first()
            vinculo_revogado = ContadorEmpresaVinculo(
                contador_id=perfil.id,
                empresa_id=_empresa_id,
                escopo_chave="homologacao_documental",
                origem="admin",
                origem_cliente="plataforma_directa",
                status="revogado",  # encerrado — não bloqueia novo
                criado_por_user_id=admin_user.id if admin_user else perfil.user_id,
                criado_por_email="admin@test.com",
                criado_em=datetime.utcnow(),
                revogado_em=datetime.utcnow(),
            )
            db.add(vinculo_revogado)
            db.commit()

        res = _criar_vinculo(client, _admin_headers,
                             _contador_aprovado_user_id, _empresa_id)
        assert res.status_code == 201, (
            f"Vínculo revogado devia permitir novo activo (201), "
            f"obtido {res.status_code}: {res.text}"
        )


# ---------------------------------------------------------------------------
# VA01-N1 a N12 — casos negativos
# ---------------------------------------------------------------------------

class TestDtVinculoAdmin01Negativo:

    def test_va01_n1_role_user_bloqueado(
        self, client, _user_headers, _contador_aprovado_user_id, _empresa_id
    ):
        """role=user → 403."""
        res = _criar_vinculo(client, _user_headers,
                             _contador_aprovado_user_id, _empresa_id)
        assert res.status_code == 403, f"{res.status_code}: {res.text}"

    def test_va01_n2_contador_inexistente_retorna_404(
        self, client, _admin_headers, _empresa_id
    ):
        """Contador user_id inexistente → 404."""
        res = _criar_vinculo(client, _admin_headers, 9999999, _empresa_id)
        assert res.status_code == 404, f"{res.status_code}: {res.text}"

    def test_va01_n3_contador_pendente_retorna_422(
        self, client, _admin_headers, _contador_pendente_user_id, _empresa_id
    ):
        """Contador com status=pendente → 422."""
        res = _criar_vinculo(client, _admin_headers,
                             _contador_pendente_user_id, _empresa_id)
        assert res.status_code == 422, f"{res.status_code}: {res.text}"

    def test_va01_n4_empresa_inexistente_retorna_404(
        self, client, _admin_headers, _contador_aprovado_user_id
    ):
        """Empresa inexistente → 404."""
        res = _criar_vinculo(client, _admin_headers,
                             _contador_aprovado_user_id, 9999999)
        assert res.status_code == 404, f"{res.status_code}: {res.text}"

    def test_va01_n5_escopo_fora_lista_v1_retorna_422(
        self, client, _admin_headers, _contador_aprovado_user_id, _empresa_id
    ):
        """Escopo fora da lista V1 → 422."""
        res = _criar_vinculo(client, _admin_headers,
                             _contador_aprovado_user_id, _empresa_id,
                             escopo_chave="escopo_invalido_v99")
        assert res.status_code == 422, f"{res.status_code}: {res.text}"

    def test_va01_n6_duplicado_activo_retorna_409(
        self, client, _admin_headers, _contador_aprovado_user_id, _empresa_id
    ):
        """INV-VINCULO-03: duplicado activo → 409."""
        res1 = _criar_vinculo(client, _admin_headers,
                              _contador_aprovado_user_id, _empresa_id)
        assert res1.status_code == 201, res1.text

        res2 = _criar_vinculo(client, _admin_headers,
                              _contador_aprovado_user_id, _empresa_id)
        assert res2.status_code == 409, (
            f"Duplicado devia devolver 409, obtido {res2.status_code}: {res2.text}"
        )

    def test_va01_n7_validade_no_passado_retorna_422(
        self, client, _admin_headers, _contador_aprovado_user_id, _empresa_id
    ):
        """Validade no passado → 422."""
        passado = (datetime.utcnow() - timedelta(days=1)).isoformat()
        res = _criar_vinculo(client, _admin_headers,
                             _contador_aprovado_user_id, _empresa_id,
                             validade=passado)
        assert res.status_code == 422, f"{res.status_code}: {res.text}"

    def test_va01_n8_sem_token_retorna_401(
        self, client, _contador_aprovado_user_id, _empresa_id
    ):
        """Sem Authorization → 401."""
        res = _criar_vinculo(client, {},
                             _contador_aprovado_user_id, _empresa_id)
        assert res.status_code == 401, f"{res.status_code}: {res.text}"

    def test_va01_n9_role_contador_bloqueado(
        self, client, _contador_headers, _contador_aprovado_user_id, _empresa_id
    ):
        """Contador não pode criar o próprio vínculo → 403."""
        res = _criar_vinculo(client, _contador_headers,
                             _contador_aprovado_user_id, _empresa_id)
        assert res.status_code == 403, (
            f"Contador não devia criar vínculo (403), obtido {res.status_code}: {res.text}"
        )

    @pytest.mark.parametrize("escopo", [
        "HOMOLOGACAO_DOCUMENTAL",
        "Homologacao_Documental",
        "homologacao documental",
        "homologacao/documental",
        "",
        "   ",
    ])
    def test_va01_n10_escopo_malformado_retorna_422(
        self, client, _admin_headers, _contador_aprovado_user_id, _empresa_id, escopo
    ):
        """Escopos uppercase/espaços/vazios → 422."""
        res = _criar_vinculo(client, _admin_headers,
                             _contador_aprovado_user_id, _empresa_id,
                             escopo_chave=escopo)
        assert res.status_code == 422, (
            f"Escopo '{escopo}' devia devolver 422, obtido {res.status_code}: {res.text}"
        )

    @pytest.mark.parametrize("validade_invalida", [
        "amanha",
        "2027/01/01",
        "01-01-2027",
        "não-é-data",
    ])
    def test_va01_n11_validade_iso_invalida_retorna_400(
        self, client, _admin_headers, _contador_aprovado_user_id, _empresa_id,
        validade_invalida
    ):
        """Validade com formato ISO inválido → 400."""
        res = _criar_vinculo(client, _admin_headers,
                             _contador_aprovado_user_id, _empresa_id,
                             validade=validade_invalida)
        assert res.status_code == 400, (
            f"Validade '{validade_invalida}' devia devolver 400, "
            f"obtido {res.status_code}: {res.text}"
        )

    def test_va01_n12_vinculo_suspenso_bloqueia_novo_activo(
        self, client, _admin_headers, _contador_aprovado_user_id, _empresa_id
    ):
        """INV-VINCULO-03: vínculo suspenso existente bloqueia novo activo igual → 409."""
        with _db_session() as db:
            perfil = db.query(PerfilContador).filter(
                PerfilContador.user_id == _contador_aprovado_user_id
            ).first()
            assert perfil is not None

            admin_user = db.query(User).filter(User.role == "admin").first()
            vinculo_suspenso = ContadorEmpresaVinculo(
                contador_id=perfil.id,
                empresa_id=_empresa_id,
                escopo_chave="homologacao_documental",
                origem="admin",
                origem_cliente="plataforma_directa",
                status="suspenso",  # suspenso = ainda institucionalmente pendente
                criado_por_user_id=admin_user.id if admin_user else perfil.user_id,
                criado_por_email="admin@test.com",
                criado_em=datetime.utcnow(),
            )
            db.add(vinculo_suspenso)
            db.commit()

        res = _criar_vinculo(client, _admin_headers,
                             _contador_aprovado_user_id, _empresa_id)
        assert res.status_code == 409, (
            f"Vínculo suspenso devia bloquear novo activo (409), "
            f"obtido {res.status_code}: {res.text}"
        )
