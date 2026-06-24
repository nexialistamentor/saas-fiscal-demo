"""
DT-CONTADOR-01 — Testes positivos do fluxo soberano de homologação
===================================================================
Prova o lado autorizado: com vínculo activo, /assumir cria
HomologacaoAtribuicao (aceite) + HomologacaoDocumental (pendente).

Complementa MT-08 (que prova o bloqueio sem vínculo).

Cobertura:
  DT01-P1  com vínculo activo → POST /assumir devolve 201
  DT01-P2  HomologacaoAtribuicao criada com campos correctos
  DT01-P3  HomologacaoDocumental criada com status=pendente
  DT01-N1  vínculo suspenso → 403
  DT01-N2  vínculo para empresa errada → 403
"""

import uuid
from contextlib import contextmanager
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.models import (
    ContadorEmpresaVinculo,
    DocumentoIngerido,
    Empresa,
    HomologacaoAtribuicao,
    HomologacaoDocumental,
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
    email = f"dt01_{uuid.uuid4().hex[:8]}@example.com"
    password = f"p{uuid.uuid4().hex}"
    res = client.post(
        "/auth/register",
        json={"email": email, "password": password,
              "tipo_usuario": "cpf", "documento": _cpf_unico_valido()},
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


def _aceitar_termos(client: TestClient, headers: dict) -> None:
    res = client.post("/auth/accept-terms", headers=headers)
    assert res.status_code == 200, f"accept-terms falhou: {res.text}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def _empresa_com_documento(client):
    """
    Cria utilizador dono, empresa e documento em fila_homologacao.
    Devolve (empresa_id, documento_id).
    """
    creds = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == creds["email"]).first()
        empresa = Empresa(
            user_id=user.id,
            razao_social="Empresa DT-CONTADOR-01",
            regime_tributario="simples_nacional",
            cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        )
        db.add(empresa)
        db.flush()
        doc = DocumentoIngerido(
            user_id=user.id,
            empresa_id=empresa.id,
            conteudo_sha256=uuid.uuid4().hex + uuid.uuid4().hex[:32],
            versao_pipeline="test-v1",
            tipo_documento="nfe",
            score_confianca=0.82,
            decisao="fila_homologacao",
        )
        db.add(doc)
        db.commit()
        db.refresh(empresa)
        db.refresh(doc)
        return empresa.id, doc.id


@pytest.fixture
def _contador_com_vinculo(client, _empresa_com_documento):
    """
    Cria contador aprovado + vínculo activo para a empresa do documento.
    Devolve (headers_contador, perfil_id, empresa_id, documento_id).
    """
    empresa_id, documento_id = _empresa_com_documento
    creds = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == creds["email"]).first()
        user.role = "contador"
        perfil = PerfilContador(
            user_id=user.id,
            crc=f"CRC-DT01-{uuid.uuid4().hex[:6].upper()}",
            uf_crc="PA",
            status="aprovado",
        )
        db.add(perfil)
        db.flush()

        # Admin que cria o vínculo (pode ser o próprio user para o teste)
        vinculo = ContadorEmpresaVinculo(
            contador_id=perfil.id,
            empresa_id=empresa_id,
            escopo_chave="homologacao_documental",
            origem="admin",
            origem_cliente="plataforma_directa",
            status="activo",
            criado_por_user_id=user.id,
            criado_por_email=user.email,
            criado_em=datetime.utcnow(),
        )
        db.add(vinculo)
        db.commit()
        db.refresh(perfil)

    headers = _login_headers(client, creds)
    _aceitar_termos(client, headers)
    return headers, perfil.id, empresa_id, documento_id


# ---------------------------------------------------------------------------
# DT01-P1, P2, P3 — fluxo positivo completo
# ---------------------------------------------------------------------------

class TestDtContador01Positivo:

    def test_dt01_p1_com_vinculo_activo_assumir_retorna_201(
        self, client, _contador_com_vinculo
    ):
        """Com vínculo activo → POST /assumir devolve 201."""
        headers, _, _, documento_id = _contador_com_vinculo
        res = client.post(
            f"/contador/homologacoes/{documento_id}/assumir",
            json={"tipo_decisao": "homologacao_documental"},
            headers=headers,
        )
        assert res.status_code == 201, (
            f"Esperado 201 com vínculo activo, obtido {res.status_code}: {res.text}"
        )

    def test_dt01_p2_atribuicao_criada_com_campos_correctos(
        self, client, _contador_com_vinculo
    ):
        """HomologacaoAtribuicao criada com status=aceite e campos correctos."""
        headers, perfil_id, empresa_id, documento_id = _contador_com_vinculo

        res = client.post(
            f"/contador/homologacoes/{documento_id}/assumir",
            json={"tipo_decisao": "homologacao_documental"},
            headers=headers,
        )
        assert res.status_code == 201, res.text

        with _db_session() as db:
            atribuicao = db.query(HomologacaoAtribuicao).filter(
                HomologacaoAtribuicao.documento_ingerido_id == documento_id,
                HomologacaoAtribuicao.escopo_chave == "homologacao_documental",
            ).first()

        assert atribuicao is not None, "HomologacaoAtribuicao não foi criada"
        assert atribuicao.status == "aceite", (
            f"status esperado 'aceite', obtido '{atribuicao.status}'"
        )
        assert atribuicao.contador_id == perfil_id
        assert atribuicao.empresa_id == empresa_id
        assert atribuicao.escopo_chave == "homologacao_documental"
        assert atribuicao.aceite_em is not None
        assert atribuicao.vinculo_id is not None

    def test_dt01_p3_homologacao_documental_criada_pendente(
        self, client, _contador_com_vinculo
    ):
        """HomologacaoDocumental criada com status=pendente após /assumir."""
        headers, perfil_id, _, documento_id = _contador_com_vinculo

        res = client.post(
            f"/contador/homologacoes/{documento_id}/assumir",
            json={"tipo_decisao": "homologacao_documental"},
            headers=headers,
        )
        assert res.status_code == 201, res.text

        with _db_session() as db:
            homologacao = db.query(HomologacaoDocumental).filter(
                HomologacaoDocumental.documento_ingerido_id == documento_id,
                HomologacaoDocumental.contador_id == perfil_id,
            ).first()

        assert homologacao is not None, "HomologacaoDocumental não foi criada"
        assert homologacao.status == "pendente", (
            f"status esperado 'pendente', obtido '{homologacao.status}'"
        )
        assert homologacao.tipo_decisao == "homologacao_documental"


# ---------------------------------------------------------------------------
# DT01-N1, N2 — casos negativos com vínculo inválido
# ---------------------------------------------------------------------------

class TestDtContador01Negativo:

    def test_dt01_n1_vinculo_suspenso_bloqueado(
        self, client, _empresa_com_documento
    ):
        """Vínculo suspenso → 403."""
        empresa_id, documento_id = _empresa_com_documento
        creds = _registar_user(client)
        with _db_session() as db:
            user = db.query(User).filter(User.email == creds["email"]).first()
            user.role = "contador"
            perfil = PerfilContador(
                user_id=user.id,
                crc=f"CRC-SUSP-{uuid.uuid4().hex[:6].upper()}",
                uf_crc="PA",
                status="aprovado",
            )
            db.add(perfil)
            db.flush()
            vinculo = ContadorEmpresaVinculo(
                contador_id=perfil.id,
                empresa_id=empresa_id,
                escopo_chave="homologacao_documental",
                origem="admin",
                origem_cliente="plataforma_directa",
                status="suspenso",  # não activo
                criado_por_user_id=user.id,
                criado_por_email=user.email,
                criado_em=datetime.utcnow(),
            )
            db.add(vinculo)
            db.commit()

        headers = _login_headers(client, creds)
        _aceitar_termos(client, headers)
        res = client.post(
            f"/contador/homologacoes/{documento_id}/assumir",
            json={"tipo_decisao": "homologacao_documental"},
            headers=headers,
        )
        assert res.status_code == 403, (
            f"Vínculo suspenso devia devolver 403, obtido {res.status_code}: {res.text}"
        )

    def test_dt01_n2_vinculo_para_empresa_errada_bloqueado(
        self, client, _empresa_com_documento
    ):
        """Vínculo activo mas para empresa diferente → 403."""
        empresa_id, documento_id = _empresa_com_documento
        creds = _registar_user(client)
        with _db_session() as db:
            user = db.query(User).filter(User.email == creds["email"]).first()
            user.role = "contador"
            perfil = PerfilContador(
                user_id=user.id,
                crc=f"CRC-ERRAD-{uuid.uuid4().hex[:5].upper()}",
                uf_crc="PA",
                status="aprovado",
            )
            db.add(perfil)
            db.flush()

            # Empresa diferente — vínculo não cobre o documento
            outra_empresa = Empresa(
                user_id=user.id,
                razao_social="Outra Empresa",
                regime_tributario="simples_nacional",
                cnpj=f"{uuid.uuid4().int % 10**14:014d}",
            )
            db.add(outra_empresa)
            db.flush()

            vinculo = ContadorEmpresaVinculo(
                contador_id=perfil.id,
                empresa_id=outra_empresa.id,  # empresa errada
                escopo_chave="homologacao_documental",
                origem="admin",
                origem_cliente="plataforma_directa",
                status="activo",
                criado_por_user_id=user.id,
                criado_por_email=user.email,
                criado_em=datetime.utcnow(),
            )
            db.add(vinculo)
            db.commit()

        headers = _login_headers(client, creds)
        _aceitar_termos(client, headers)
        res = client.post(
            f"/contador/homologacoes/{documento_id}/assumir",
            json={"tipo_decisao": "homologacao_documental"},
            headers=headers,
        )
        assert res.status_code == 403, (
            f"Vínculo para empresa errada devia devolver 403, "
            f"obtido {res.status_code}: {res.text}"
        )
