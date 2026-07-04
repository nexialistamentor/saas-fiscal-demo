"""
Bloco 9.2 — Lote final: isolamento /inteligencia e /insights
=============================================================
Princípio: caracterização representativa, não exaustiva.
Uma rota de cada domínio é suficiente — todas usam tenant_empresa.

Guards confirmadas:
  tenant_empresa → security.py L174-179
  Ambos em ROTAS_FISCAIS (main.py L475-490) → TermosMiddleware activo

Rotas escolhidas (estáveis, sem dependência de dados fiscais):
  /inteligencia/score-tributario/{empresa_id}  — GET, tenant_empresa
  /insights/{empresa_id}                       — POST, tenant_empresa

Cobertura:
  MT-14  GET /inteligencia/score-tributario/{empresa_id}
         A → 403 (ownership); B → 200; sem token → 401
  MT-15  POST /insights/{empresa_id}
         A → 403 (ownership); B → 200 ou 422 (sem dados fiscais); sem token → 401

Nota MT-15: insights pode devolver 422 para B se InsightEngine não encontrar
dados fiscais para a empresa recém-criada. Isso é aceitável — o que importa
é que A receba 403, não 200.
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
    email = f"bloco9c_{uuid.uuid4().hex[:8]}@example.com"
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
    /inteligencia e /insights estão em ROTAS_FISCAIS (main.py L475-490).
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
    """Regista B, cria empresa explícita, aceita termos. Devolve (headers_b, empresa_id)."""
    credentials = _registar_user(client)
    headers = _login_headers(client, credentials)
    _aceitar_termos(client, headers)
    with _db_session() as db:
        user_b = db.query(User).filter(User.email == credentials["email"]).first()
        assert user_b is not None
        empresa = Empresa(
            user_id=user_b.id,
            razao_social="Empresa B Lote Final",
            regime_tributario="simples_nacional",
            cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
        empresa_id = empresa.id
    return headers, empresa_id


# ---------------------------------------------------------------------------
# MT-14 — /inteligencia/score-tributario/{empresa_id}
# ---------------------------------------------------------------------------

class TestIsolamentoInteligencia:

    def test_mt14_score_tributario_acesso_cruzado(
        self, client, _user_a_headers, _user_b_com_empresa
    ):
        """
        GET /inteligencia/score-tributario/{empresa_id} — tenant_empresa.
        A → 403 (ownership); B → 200.
        """
        headers_b, empresa_id = _user_b_com_empresa

        res_a = client.get(
            f"/inteligencia/score-tributario/{empresa_id}",
            headers=_user_a_headers,
        )
        assert res_a.status_code == 403, (
            f"VAZAMENTO: A obteve {res_a.status_code} em "
            f"/inteligencia/score-tributario/{empresa_id}. Resposta: {res_a.text}"
        )

        res_b = client.get(
            f"/inteligencia/score-tributario/{empresa_id}",
            headers=headers_b,
        )
        assert res_b.status_code == 200, (
            f"B não acedeu próprio score: {res_b.status_code} {res_b.text}"
        )

    def test_mt14b_sem_token_inteligencia_retorna_401(self, client):
        res = client.get("/inteligencia/score-tributario/1")
        assert res.status_code == 401, (
            f"Esperado 401 sem token, obtido {res.status_code}: {res.text}"
        )


# ---------------------------------------------------------------------------
# MT-15 — POST /insights/{empresa_id}
# ---------------------------------------------------------------------------

class TestIsolamentoInsights:

    def test_mt15_insights_acesso_cruzado(
        self, client, _user_a_headers, _user_b_com_empresa
    ):
        """
        POST /insights/{empresa_id} — tenant_empresa.
        A → 403 (ownership).
        B → 200 ou 422 (sem dados fiscais na empresa recém-criada — aceitável).
        O que não pode acontecer: A receber 200 com dados de B.
        """
        headers_b, empresa_id = _user_b_com_empresa

        res_a = client.post(
            f"/insights/{empresa_id}",
            headers=_user_a_headers,
        )
        assert res_a.status_code == 403, (
            f"VAZAMENTO: A obteve {res_a.status_code} em "
            f"/insights/{empresa_id}. Resposta: {res_a.text}"
        )

        res_b = client.post(
            f"/insights/{empresa_id}",
            headers=headers_b,
        )
        assert res_b.status_code == 200, (
            f"B não acedeu aos próprios insights: {res_b.status_code} {res_b.text}"
        )
        body = res_b.json()
        assert body["empresa_id"] == empresa_id
        campos_obrigatorios = {
            "empresa_id",
            "oportunidades",
            "creditos_detectados",
            "risco_tributario",
            "resultados_engines",
            "comparativo_regime",
            "context_flags",
            "decomposicao_impacto",
        }
        assert campos_obrigatorios.issubset(body.keys())

    def test_mt15b_sem_token_insights_retorna_401(self, client):
        res = client.post("/insights/1")
        assert res.status_code == 401, (
            f"Esperado 401 sem token, obtido {res.status_code}: {res.text}"
        )
