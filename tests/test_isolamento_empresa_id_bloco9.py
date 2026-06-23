"""
Bloco 9.2 — Segundo lote: isolamento empresa_id fora de /empresas/
===================================================================
Princípio: caracterização antes de correcção.

Guards confirmadas por evidência directa:
  tenant_empresa           → security.py L174-179 (wrapper FastAPI)
  verificar_empresa_do_usuario → security.py L159-171 (núcleo)
  Ambas fazem: Empresa.user_id == usuario.id → 403 se falhar

Resposta esperada em acesso cruzado: 403
Detalhe esperado: "Acesso negado: empresa não pertence ao usuário"

Cobertura:
  MT-09   GET /dashboard/resumo/{empresa_id}        — tenant_empresa
  MT-10   GET /dashboard/analises/{empresa_id}      — tenant_empresa
  MT-11   GET /analise-st/{empresa_id}              — tenant_empresa
            prefixo confirmado em st_router.py L11 (main.py L580 inclui sem prefixo extra)
  MT-12   GET /relatorio/empresas/{empresa_id}/engines — verificar_empresa_do_usuario manual
  MT-13   Sem token em rota com empresa_id → 401 (guard de auth antes de ownership)
  Em MT-09 a MT-12: proprietário legítimo acede própria empresa → 200
    (embutido em cada teste — prova que guard não bloqueia tudo)

Notas:
  - Rotas dashboard/st/relatorio não passam por TermosMiddleware — sem _aceitar_termos.
  - Se algum teste devolver 200 com dados de B: parar e trazer output antes de corrigir.
  - Este lote não fecha o Bloco 9.2 para insights/inteligencia (cobertura futura).
"""

import uuid
from contextlib import contextmanager

import pytest

from app.database import get_db
from app.models import Empresa, User


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


def _registar_user(client) -> dict:
    email = f"bloco9b_{uuid.uuid4().hex[:8]}@example.com"
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


def _login_headers(client, credentials: dict) -> dict:
    res = client.post(
        "/auth/login",
        data={"username": credentials["email"], "password": credentials["password"]},
    )
    assert res.status_code == 200, f"Login falhou ({res.status_code}): {res.text}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _aceitar_termos(client, headers: dict) -> None:
    """
    POST /auth/accept-terms — sem body, só Bearer token.
    ROTAS_FISCAIS em main.py inclui /dashboard, /analise-st e /relatorio:
    TermosMiddleware devolve 403 sem aceite, antes de tenant_empresa.
    Confirmado em auth_router.py L140-164.
    """
    res = client.post("/auth/accept-terms", headers=headers)
    assert res.status_code == 200, f"accept-terms falhou ({res.status_code}): {res.text}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def _user_a_headers(client):
    headers = _login_headers(client, _registar_user(client))
    _aceitar_termos(client, headers)
    return headers


@pytest.fixture
def _user_b_com_empresa(client):
    """Regista utilizador B e cria empresa explícita. Devolve (headers_b, empresa_id)."""
    credentials = _registar_user(client)
    headers = _login_headers(client, credentials)
    _aceitar_termos(client, headers)
    with _db_session() as db:
        user_b = db.query(User).filter(User.email == credentials["email"]).first()
        assert user_b is not None
        empresa = Empresa(
            user_id=user_b.id,
            razao_social="Empresa B Lote 2",
            regime_tributario="simples_nacional",
            cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
        empresa_id = empresa.id
    return headers, empresa_id


# ---------------------------------------------------------------------------
# MT-09 a MT-12 — acesso cruzado em rotas com {empresa_id}
# Padrão: A tenta aceder empresa de B → 403
#         B acede própria empresa → 200 (prova que guard não bloqueia tudo)
# ---------------------------------------------------------------------------

class TestIsolamentoEmpresaId:

    def test_mt09_dashboard_resumo_acesso_cruzado(
        self, client, _user_a_headers, _user_b_com_empresa
    ):
        """
        GET /dashboard/resumo/{empresa_id} — Depends(tenant_empresa).
        A com empresa_id de B → 403.
        B com empresa própria → 200.
        """
        headers_b, empresa_id = _user_b_com_empresa

        # A não deve ver resumo de B
        res_a = client.get(f"/dashboard/resumo/{empresa_id}", headers=_user_a_headers)
        assert res_a.status_code == 403, (
            f"VAZAMENTO: A obteve {res_a.status_code} em /dashboard/resumo/{empresa_id}. "
            f"Resposta: {res_a.text}"
        )

        # B vê a própria empresa (guard não bloqueia tudo)
        res_b = client.get(f"/dashboard/resumo/{empresa_id}", headers=headers_b)
        assert res_b.status_code == 200, (
            f"B não conseguiu aceder própria empresa: {res_b.status_code} {res_b.text}"
        )

    def test_mt10_dashboard_analises_acesso_cruzado(
        self, client, _user_a_headers, _user_b_com_empresa
    ):
        """GET /dashboard/analises/{empresa_id} — Depends(tenant_empresa)."""
        headers_b, empresa_id = _user_b_com_empresa

        res_a = client.get(f"/dashboard/analises/{empresa_id}", headers=_user_a_headers)
        assert res_a.status_code == 403, (
            f"VAZAMENTO: A obteve {res_a.status_code} em /dashboard/analises/{empresa_id}. "
            f"Resposta: {res_a.text}"
        )

        res_b = client.get(f"/dashboard/analises/{empresa_id}", headers=headers_b)
        assert res_b.status_code == 200, (
            f"B não conseguiu aceder próprias analises: {res_b.status_code} {res_b.text}"
        )

    def test_mt11_analise_st_acesso_cruzado(
        self, client, _user_a_headers, _user_b_com_empresa
    ):
        """
        GET /analise-st/{empresa_id} — Depends(tenant_empresa).
        Prefixo confirmado: st_router.py L11 router = APIRouter(prefix="/analise-st").
        main.py L580 inclui sem prefixo adicional.
        """
        headers_b, empresa_id = _user_b_com_empresa

        res_a = client.get(f"/analise-st/{empresa_id}", headers=_user_a_headers)
        assert res_a.status_code == 403, (
            f"VAZAMENTO: A obteve {res_a.status_code} em /analise-st/{empresa_id}. "
            f"Resposta: {res_a.text}"
        )

        res_b = client.get(f"/analise-st/{empresa_id}", headers=headers_b)
        assert res_b.status_code == 200, (
            f"B não conseguiu aceder próprio analise-st: {res_b.status_code} {res_b.text}"
        )

    def test_mt12_relatorio_engines_acesso_cruzado(
        self, client, _user_a_headers, _user_b_com_empresa
    ):
        """
        GET /relatorio/empresas/{empresa_id}/engines
        Usa verificar_empresa_do_usuario manual (relatorio_router.py L49-57).
        Mesmo mecanismo que tenant_empresa, resultado idêntico.
        """
        headers_b, empresa_id = _user_b_com_empresa

        res_a = client.get(
            f"/relatorio/empresas/{empresa_id}/engines",
            headers=_user_a_headers,
        )
        assert res_a.status_code == 403, (
            f"VAZAMENTO: A obteve {res_a.status_code} em engines de empresa {empresa_id}. "
            f"Resposta: {res_a.text}"
        )

        res_b = client.get(
            f"/relatorio/empresas/{empresa_id}/engines",
            headers=headers_b,
        )
        assert res_b.status_code == 200, (
            f"B não conseguiu aceder próprios engines: {res_b.status_code} {res_b.text}"
        )


# ---------------------------------------------------------------------------
# MT-13 — sem token: 401 antes de chegar ao guard de ownership
# ---------------------------------------------------------------------------

class TestSemTokenEmpresaId:

    @pytest.mark.parametrize("path", [
        "/dashboard/resumo/1",
        "/dashboard/analises/1",
        "/analise-st/1",
        "/relatorio/empresas/1/engines",
    ])
    def test_mt13_sem_token_retorna_401(self, client, path):
        """Sem token → 401 em todas as rotas com empresa_id."""
        res = client.get(path)
        assert res.status_code == 401, (
            f"Esperado 401 sem token em {path}, obtido {res.status_code}: {res.text}"
        )
