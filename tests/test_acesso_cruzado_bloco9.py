"""
Bloco 9.2 — Testes de acesso cruzado multi-tenant e autorização contador
=========================================================================
Princípio: caracterização antes de correcção.

Campos confirmados por evidência directa (models.py):
  Empresa:           user_id (NOT NULL), razao_social, regime_tributario, cnpj
  DocumentoIngerido: conteudo_sha256 (NOT NULL), versao_pipeline (NOT NULL),
                     tipo_documento (NOT NULL), score_confianca (NOT NULL),
                     decisao (NOT NULL) = "fila_homologacao" para MT-08
                     (confidence.py L24-27, contador_router.py L111-114)

Termos: POST /auth/accept-terms exige Bearer token, sem body.
        TermosMiddleware bloqueia /empresas/ com 403 se não aceite.
        MT-01 aceita termos para A e B antes de chamar /empresas/.

Cobertura (primeiro lote — Bloco 9.2 não está fechado):
  MT-01  utilizador A não vê empresa explícita de utilizador B
  MT-02  sem token → 401
  MT-03  role=user bloqueado em /contador/homologacoes/pendentes → 403
  MT-04  role=contador sem PerfilContador → 403
  MT-05  role=contador com PerfilContador status=pendente → 403
  MT-05b contador aprovado lista pendentes → 200
  MT-06  role=admin passa guard de /admin/set-role
  MT-07  role=user bloqueado em /admin/set-role → 403
  MT-08  pool aberto ADR-003: 201→xfail, 403→pass, 404/422→fail

Ainda faltam para fechar Bloco 9.2:
  - Isolamento em rotas com empresa_id fora de /empresas/
    (dashboard, relatorio, inteligencia, engines)
"""

import uuid
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.models import (
    DocumentoIngerido,
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
    email = f"bloco9_{uuid.uuid4().hex[:8]}@example.com"
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
    assert res.status_code in (200, 201), f"Registo falhou ({res.status_code}): {res.text}"
    return {"email": email, "password": password}


def _login_headers(client: TestClient, credentials: dict) -> dict:
    res = client.post(
        "/auth/login",
        data={"username": credentials["email"], "password": credentials["password"]},
    )
    assert res.status_code == 200, f"Login falhou ({res.status_code}): {res.text}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _aceitar_termos(client: TestClient, headers: dict) -> None:
    """
    POST /auth/accept-terms — sem body, só Bearer token.
    TermosMiddleware bloqueia /empresas/ com 403 se não aceite.
    Confirmar assinatura em auth_router.py L140-164.
    """
    res = client.post("/auth/accept-terms", headers=headers)
    assert res.status_code == 200, f"accept-terms falhou ({res.status_code}): {res.text}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def _outro_user(client):
    return _registar_user(client)


@pytest.fixture
def _auth_headers_b(client, _outro_user):
    return _login_headers(client, _outro_user)


@pytest.fixture
def _empresa_user_b(client, _outro_user) -> int:
    """
    Empresa criada explicitamente para utilizador B.
    Campos obrigatórios confirmados: user_id (NOT NULL), razao_social, cnpj.
    Devolve empresa_id para asserções directas em MT-01.
    """
    with _db_session() as db:
        user_b = db.query(User).filter(User.email == _outro_user["email"]).first()
        assert user_b is not None, "Utilizador B não encontrado na BD"
        empresa = Empresa(
            user_id=user_b.id,
            razao_social="Empresa Exclusiva B",
            regime_tributario="simples_nacional",
            cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
        return empresa.id


@pytest.fixture
def _admin_headers(client):
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        assert user is not None
        user.role = "admin"
        db.commit()
    return _login_headers(client, credentials)


@pytest.fixture
def _contador_sem_perfil_headers(client):
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        assert user is not None
        user.role = "contador"
        db.commit()
    return _login_headers(client, credentials)


@pytest.fixture
def _contador_pendente_headers(client):
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        assert user is not None
        user.role = "contador"
        perfil = PerfilContador(
            user_id=user.id,
            crc=f"CRC-PEND-{uuid.uuid4().hex[:6].upper()}",
            uf_crc="PA",
            status="pendente",
        )
        db.add(perfil)
        db.commit()
    return _login_headers(client, credentials)


@pytest.fixture
def _contador_aprovado(client):
    """Devolve (headers, perfil_id)."""
    credentials = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == credentials["email"]).first()
        assert user is not None
        user.role = "contador"
        perfil = PerfilContador(
            user_id=user.id,
            crc=f"CRC-APROV-{uuid.uuid4().hex[:6].upper()}",
            uf_crc="PA",
            status="aprovado",
        )
        db.add(perfil)
        db.commit()
        db.refresh(perfil)
        perfil_id = perfil.id
    headers = _login_headers(client, credentials)
    return headers, perfil_id


@pytest.fixture
def _documento_em_fila_user_b(client, _outro_user) -> int:
    """
    DocumentoIngerido com decisao="fila_homologacao" pertencente ao utilizador B.

    Campos NOT NULL confirmados (models.py L587-616):
      conteudo_sha256, versao_pipeline, tipo_documento, score_confianca, decisao

    "fila_homologacao" confirmado em:
      confidence.py L24-27  (DecisaoProcessamento.FILA_HOMOLOGACAO)
      contador_router.py L111-114 (guard do /assumir)

    Se este fixture devolver documento com decisao errada, MT-08 devolve 422
    e a vulnerabilidade fica mascarada — não caracterizada.
    """
    with _db_session() as db:
        user_b = db.query(User).filter(User.email == _outro_user["email"]).first()
        assert user_b is not None, "Utilizador B não encontrado"

        empresa = Empresa(
            user_id=user_b.id,
            razao_social="Empresa B para MT-08",
            regime_tributario="simples_nacional",
            cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        )
        db.add(empresa)
        db.flush()

        doc = DocumentoIngerido(
            user_id=user_b.id,
            empresa_id=empresa.id,
            conteudo_sha256=uuid.uuid4().hex + uuid.uuid4().hex[:32],  # 64 chars
            versao_pipeline="test-v1",
            tipo_documento="nfe",
            score_confianca=0.82,
            decisao="fila_homologacao",  # valor canónico — não alterar
            nome_ficheiro="nfe_fila.xml",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc.id


# ---------------------------------------------------------------------------
# MT-01 e MT-02 — isolamento multi-tenant /empresas/
# ---------------------------------------------------------------------------

class TestMultiTenantEmpresas:

    def test_mt01_user_a_nao_ve_empresa_de_user_b(
        self,
        client,
        auth_headers,
        _auth_headers_b,
        _empresa_user_b,
    ):
        """
        Prova isolamento multi-tenant com empresa criada explicitamente.
        Termos aceites antes de chamar /empresas/ — TermosMiddleware devolve
        403 sem aceite (não é falha de ownership).

        Duas asserções obrigatórias:
          (1) B vê a própria empresa — fixture não está vazia
          (2) A não vê a empresa de B — isolamento real
        Sem (1), (2) seria trivialmente verdadeiro com listas vazias.
        """
        # Aceitar termos para A e B antes de chamar /empresas/
        _aceitar_termos(client, auth_headers)
        _aceitar_termos(client, _auth_headers_b)

        res_a = client.get("/empresas/", headers=auth_headers)
        res_b = client.get("/empresas/", headers=_auth_headers_b)

        assert res_a.status_code == 200, f"A: {res_a.status_code} {res_a.text}"
        assert res_b.status_code == 200, f"B: {res_b.status_code} {res_b.text}"

        ids_a = {e["id"] for e in res_a.json()}
        ids_b = {e["id"] for e in res_b.json()}

        # (1) B vê a própria empresa
        assert _empresa_user_b in ids_b, (
            f"Empresa {_empresa_user_b} não aparece para B — "
            "fixture de criação falhou ou /empresas/ não filtra por user_id."
        )

        # (2) A não vê a empresa de B
        assert _empresa_user_b not in ids_a, (
            f"VAZAMENTO MULTI-TENANT: empresa {_empresa_user_b} de B "
            "visível para A."
        )

    def test_mt02_sem_token_retorna_401(self, client):
        res = client.get("/empresas/")
        assert res.status_code == 401, (
            f"Esperado 401 sem token, obtido {res.status_code}: {res.text}"
        )


# ---------------------------------------------------------------------------
# MT-03 a MT-05b — guard _get_perfil_contador
# ---------------------------------------------------------------------------

class TestAutorizacaoContador:

    def test_mt03_role_user_bloqueado(self, client, auth_headers):
        res = client.get("/contador/homologacoes/pendentes", headers=auth_headers)
        assert res.status_code == 403

    def test_mt04_contador_sem_perfil_bloqueado(self, client, _contador_sem_perfil_headers):
        res = client.get("/contador/homologacoes/pendentes", headers=_contador_sem_perfil_headers)
        assert res.status_code == 403

    def test_mt05_contador_pendente_bloqueado(self, client, _contador_pendente_headers):
        res = client.get("/contador/homologacoes/pendentes", headers=_contador_pendente_headers)
        assert res.status_code == 403

    def test_mt05b_contador_aprovado_lista_pendentes(self, client, _contador_aprovado):
        headers, _ = _contador_aprovado
        res = client.get("/contador/homologacoes/pendentes", headers=headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)


# ---------------------------------------------------------------------------
# MT-06 e MT-07 — guard /admin/set-role
# ---------------------------------------------------------------------------

class TestAdminSetRole:

    def test_mt07_role_user_bloqueado(self, client, auth_headers):
        res = client.post(
            "/admin/set-role",
            json={"email": "qualquer@example.com", "role": "user"},
            headers=auth_headers,
        )
        assert res.status_code == 403

    def test_mt06_admin_passa_guard(self, client, _admin_headers):
        """Pode devolver 404 (user não existe) — o que importa é não ser 401/403."""
        res = client.post(
            "/admin/set-role",
            json={"email": "naoexiste@example.com", "role": "user"},
            headers=_admin_headers,
        )
        assert res.status_code not in (401, 403), (
            f"Guard admin falhou: {res.status_code} {res.text}"
        )


# ---------------------------------------------------------------------------
# MT-08 — pool aberto: caracterização ADR-003 / DT-CONTADOR-01
# ---------------------------------------------------------------------------

class TestPoolAbertoCaracterizacao:

    def test_mt08_contador_aprovado_nao_deve_assumir_documento_alheio(
        self,
        client,
        _contador_aprovado,
        _documento_em_fila_user_b,
    ):
        """
        Caracterização do pool aberto V1 (ADR-003 / DT-CONTADOR-01).
        O contador não tem vínculo com a empresa do documento.

          201 → pytest.xfail() — vulnerabilidade activa, piloto BLOQUEADO
          403 → PASS — sistema protegido (DT-CONTADOR-01 implementado)
          404 → FAIL — fixture incorrecta (decisao != "fila_homologacao"?)
          422 → FAIL — payload inválido ou guard inesperada
        """
        headers, _ = _contador_aprovado
        documento_id = _documento_em_fila_user_b

        res = client.post(
            f"/contador/homologacoes/{documento_id}/assumir",
            json={"tipo_decisao": "homologacao_documental"},
            headers=headers,
        )

        if res.status_code == 201:
            pytest.xfail(
                "ADR-003/DT-CONTADOR-01 — VULNERABILIDADE ACTIVA: "
                f"contador assumiu documento {documento_id} de empresa alheia sem vínculo. "
                "Piloto BLOQUEADO até DT-CONTADOR-01."
            )

        if res.status_code == 404:
            pytest.fail(
                f"404 em /contador/homologacoes/{documento_id}/assumir — "
                "fixture possivelmente incorrecta. "
                "Verificar: DocumentoIngerido.decisao deve ser 'fila_homologacao' "
                "(confidence.py L24-27). "
                f"Resposta: {res.text}"
            )

        if res.status_code == 422:
            pytest.fail(
                f"422 em /contador/homologacoes/{documento_id}/assumir — "
                f"payload inválido ou guard inesperada. Resposta: {res.text}"
            )

        assert res.status_code == 403, (
            f"Código inesperado: {res.status_code}. Resposta: {res.text}"
        )
