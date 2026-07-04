"""
Testes de contrato HTTP — H4, L2, M4/decidir (OPS-11).
"""

import uuid

from contextlib import contextmanager

from datetime import date, datetime

import pytest

from fastapi.testclient import TestClient

from app.database import get_db

from app.models import (
    ContadorEmpresaVinculo,
    DocumentoFiscal,
    DocumentoIngerido,
    Empresa,
    ItemFiscal,
    PerfilContador,
    TabelaMVA,
    User,
)


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
    email = f"ops11_{uuid.uuid4().hex[:8]}@example.com"
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


def _aceitar_termos(client: TestClient, headers: dict) -> None:
    res = client.post("/auth/accept-terms", headers=headers)
    assert res.status_code == 200, f"accept-terms falhou: {res.text}"


# ---------------------------------------------------------------------------
# H4 — GET /analise-st/periodo/{empresa_id}
# ---------------------------------------------------------------------------


@pytest.fixture
def _empresa_do_usuario(client):
    creds = _registar_user(client)
    headers = _login_headers(client, creds)
    _aceitar_termos(client, headers)
    with _db_session() as db:
        user = db.query(User).filter(User.email == creds["email"]).first()
        empresa = Empresa(
            user_id=user.id,
            razao_social="Empresa Teste",
            regime_tributario="simples_nacional",
            cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
        empresa_id = empresa.id
    return headers, empresa_id


def test_h4_analise_st_periodo_com_datas_validas_retorna_200(client, _empresa_do_usuario):
    headers, empresa_id = _empresa_do_usuario
    res = client.get(
        f"/analise-st/periodo/{empresa_id}",
        params={"data_inicio": "2026-01-01", "data_fim": "2026-06-30"},
        headers=headers,
    )
    assert res.status_code == 200


def test_h4_analise_st_periodo_sem_datas_retorna_422(client, _empresa_do_usuario):
    headers, empresa_id = _empresa_do_usuario
    res = client.get(f"/analise-st/periodo/{empresa_id}", headers=headers)
    assert res.status_code == 422


def test_h4_analise_st_periodo_empresa_de_outro_usuario_bloqueia(client, _empresa_do_usuario):
    _, empresa_id = _empresa_do_usuario
    outro_creds = _registar_user(client)
    outro_headers = _login_headers(client, outro_creds)
    _aceitar_termos(client, outro_headers)
    res = client.get(
        f"/analise-st/periodo/{empresa_id}",
        params={"data_inicio": "2026-01-01", "data_fim": "2026-06-30"},
        headers=outro_headers,
    )
    assert res.status_code in (403, 404)


def test_h4_analise_st_periodo_valida_body_e_ignora_fora_do_periodo(client, _empresa_do_usuario):
    headers, empresa_id = _empresa_do_usuario
    ncm = "22021000"

    with _db_session() as db:
        doc_ids = [
            row[0]
            for row in db.query(DocumentoFiscal.id)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .all()
        ]
        if doc_ids:
            db.query(ItemFiscal).filter(ItemFiscal.documento_id.in_(doc_ids)).delete(
                synchronize_session=False
            )
            db.query(DocumentoFiscal).filter(DocumentoFiscal.id.in_(doc_ids)).delete(
                synchronize_session=False
            )

        db.query(TabelaMVA).filter(
            TabelaMVA.estado == "PA",
            TabelaMVA.ncm == ncm,
        ).delete(synchronize_session=False)

        db.add(
            TabelaMVA(
                estado="PA",
                ncm=ncm,
                mva=0.45,
                aliquota_interna=0.19,
                vigencia_inicio=date(2024, 1, 1),
                vigencia_fim=None,
                fonte_legal="Teste H4.1",
                nivel_confianca_fonte="oficial",
            )
        )

        entrada_dentro = DocumentoFiscal(
            empresa_id=empresa_id,
            tipo="entrada",
            data_emissao=date(2024, 6, 1),
            uf_dest="PA",
        )
        db.add(entrada_dentro)
        db.flush()
        db.add(
            ItemFiscal(
                documento_id=entrada_dentro.id,
                ncm=ncm,
                valor_produto=100.0,
                valor_st=50.0,
            )
        )

        entrada_fora = DocumentoFiscal(
            empresa_id=empresa_id,
            tipo="entrada",
            data_emissao=date(2024, 7, 1),
            uf_dest="PA",
        )
        db.add(entrada_fora)
        db.flush()
        db.add(
            ItemFiscal(
                documento_id=entrada_fora.id,
                ncm=ncm,
                valor_produto=100.0,
                valor_st=999.0,
            )
        )

        saida_dentro = DocumentoFiscal(
            empresa_id=empresa_id,
            tipo="saida",
            data_emissao=date(2024, 6, 15),
            uf_dest="PA",
        )
        db.add(saida_dentro)
        db.flush()
        db.add(
            ItemFiscal(
                documento_id=saida_dentro.id,
                ncm=ncm,
                valor_produto=80.0,
                valor_st=0.0,
            )
        )

        saida_fora = DocumentoFiscal(
            empresa_id=empresa_id,
            tipo="saida",
            data_emissao=date(2024, 7, 15),
            uf_dest="PA",
        )
        db.add(saida_fora)
        db.flush()
        db.add(
            ItemFiscal(
                documento_id=saida_fora.id,
                ncm=ncm,
                valor_produto=1000.0,
                valor_st=0.0,
            )
        )

        db.commit()

    res = client.get(
        f"/analise-st/periodo/{empresa_id}",
        params={"data_inicio": "2024-06-01", "data_fim": "2024-06-30"},
        headers=headers,
    )

    assert res.status_code == 200
    body = res.json()

    assert set(body.keys()) == {"st_pago", "st_devido", "restituicao"}

    assert body["st_pago"] == 50.0

    # Saída dentro do período:
    # valor_produto = 80
    # MVA = 45% → base ST = 116
    # alíquota = 19%
    # ICMS próprio = 80 * 19% = 15.20
    # ICMS ST = 116 * 19% - 15.20 = 6.84
    assert body["st_devido"] == 6.84
    assert body["restituicao"] == 43.16


# ---------------------------------------------------------------------------
# L2 — POST /ingestao/documentos
# ---------------------------------------------------------------------------


@pytest.fixture
def _usuario_autenticado(client):
    creds = _registar_user(client)
    headers = _login_headers(client, creds)
    _aceitar_termos(client, headers)
    return headers


def test_l2_ingerir_documento_pdf_rejeitado_por_classificador_retorna_422(client, _usuario_autenticado):
    conteudo_pdf = b"%PDF-1.4\n%mock pdf content for test\n%%EOF"
    res = client.post(
        "/ingestao/documentos",
        files={"file": ("teste.pdf", conteudo_pdf, "application/pdf")},
        headers=_usuario_autenticado,
    )
    assert res.status_code == 422
    assert "detail" in res.json()


def test_l2_ingerir_documento_mime_invalido_retorna_415(client, _usuario_autenticado):
    res = client.post(
        "/ingestao/documentos",
        files={"file": ("teste.txt", b"conteudo qualquer", "text/plain")},
        headers=_usuario_autenticado,
    )
    assert res.status_code == 415


def test_l2_ingerir_documento_vazio_retorna_400(client, _usuario_autenticado):
    res = client.post(
        "/ingestao/documentos",
        files={"file": ("vazio.pdf", b"", "application/pdf")},
        headers=_usuario_autenticado,
    )
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# M4 — POST /contador/homologacoes/{id}/decidir
# ---------------------------------------------------------------------------


@pytest.fixture
def _empresa_com_documento(client):
    creds = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == creds["email"]).first()
        empresa = Empresa(
            user_id=user.id,
            razao_social="Empresa OPS11",
            regime_tributario="simples_nacional",
            cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        )
        db.add(empresa)
        db.flush()
        documento = DocumentoIngerido(
            user_id=user.id,
            empresa_id=empresa.id,
            conteudo_sha256=uuid.uuid4().hex + uuid.uuid4().hex[:32],
            versao_pipeline="v1",
            tipo_documento="pdf",
            score_confianca=80,
            decisao="fila_homologacao",
        )
        db.add(documento)
        db.commit()
        db.refresh(empresa)
        db.refresh(documento)
        return empresa.id, documento.id


@pytest.fixture
def _contador_com_vinculo(client, _empresa_com_documento):
    empresa_id, documento_id = _empresa_com_documento
    creds = _registar_user(client)
    with _db_session() as db:
        user = db.query(User).filter(User.email == creds["email"]).first()
        user.role = "contador"
        perfil = PerfilContador(
            user_id=user.id,
            crc=f"CRC-{uuid.uuid4().hex[:8].upper()}",
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


@pytest.fixture
def _homologacao_assumida(client, _contador_com_vinculo):
    headers, perfil_id, empresa_id, documento_id = _contador_com_vinculo
    res = client.post(
        f"/contador/homologacoes/{documento_id}/assumir",
        json={"tipo_decisao": "homologacao_documental"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    homologacao_id = res.json()["id"]
    return headers, perfil_id, empresa_id, documento_id, homologacao_id


def test_m4_decidir_aprovado_retorna_contrato(client, _homologacao_assumida):
    headers, *_rest, homologacao_id = _homologacao_assumida
    res = client.post(
        f"/contador/homologacoes/{homologacao_id}/decidir",
        json={"status_decisao": "aprovado", "parecer_texto": "Documento válido."},
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "aprovado"
    assert body["parecer_texto"] == "Documento válido."
    assert body["assinatura_logica"] is not None
    assert body["decidido_em"] is not None


def test_m4_decidir_rejeitado_retorna_contrato(client, _homologacao_assumida):
    headers, *_rest, homologacao_id = _homologacao_assumida
    res = client.post(
        f"/contador/homologacoes/{homologacao_id}/decidir",
        json={"status_decisao": "rejeitado", "parecer_texto": "Documento inválido."},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "rejeitado"


def test_m4_decidir_parecer_vazio_retorna_422(client, _homologacao_assumida):
    headers, *_rest, homologacao_id = _homologacao_assumida
    res = client.post(
        f"/contador/homologacoes/{homologacao_id}/decidir",
        json={"status_decisao": "aprovado", "parecer_texto": "   "},
        headers=headers,
    )
    assert res.status_code == 422
