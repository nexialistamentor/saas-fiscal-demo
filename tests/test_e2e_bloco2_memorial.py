"""
tests/test_e2e_bloco2_memorial.py
E2E Bloco 2 — Upload XML → relatorio_id → memorial PDF

Cobre:
  E2E-B2-P1  /upload-xml → 200 + relatorio_id + empresa_id correcto
  E2E-B2-P2  RelatorioAnalise persistido com score e alertas
  E2E-B2-N1  GET /relatorio/memorial/{id}/pdf sem pago=True → 402
  E2E-B2-P3  GET /relatorio/memorial/{id}/pdf com pago=True → 200
  E2E-B2-P4  PDF contém header %PDF válido
"""

from contextlib import contextmanager

from app.database import SessionLocal, get_db
from app.models import RelatorioAnalise

from tests.helpers.seed_pipeline import (
    XML_FIXTURE,
    cleanup_icms10_st,
    seed_user_empresa,
)


# ---------------------------------------------------------------------------
# Infra
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


def _login_headers(client, email: str, password: str = "testpass") -> dict:
    res = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert res.status_code == 200, f"Login falhou: {res.text}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@contextmanager
def _pipeline_user_empresa(client):
    """
    Context manager: cria 1 user/empresa, faz login + accept-terms,
    garante cleanup no finally independentemente do resultado.
    """
    db = SessionLocal()
    user, empresa = seed_user_empresa(db)
    user_id = user.id
    empresa_id = empresa.id
    email = user.email
    db.close()

    headers = _login_headers(client, email)
    res_terms = client.post("/auth/accept-terms", headers=headers)
    assert res_terms.status_code in (200, 204), (
        f"accept-terms falhou: {res_terms.status_code} {res_terms.text}"
    )

    try:
        yield user_id, empresa_id, email, headers
    finally:
        with _db_session() as db_cleanup:
            cleanup_icms10_st(db_cleanup, user_id, empresa_id)


# ---------------------------------------------------------------------------
# E2E-B2-P1 e P2 — upload XML
# ---------------------------------------------------------------------------

class TestE2EBloco2Upload:

    def test_e2e_b2_p1_upload_xml_retorna_relatorio_id(self, client):
        """POST /upload-xml → 200 + relatorio_id + empresa_id do tenant correcto."""
        with _pipeline_user_empresa(client) as (user_id, empresa_id, email, headers):
            assert XML_FIXTURE.exists(), f"Fixture XML não encontrada: {XML_FIXTURE}"
            with open(XML_FIXTURE, "rb") as f:
                res = client.post(
                    "/upload-xml",
                    headers=headers,
                    files={"file": ("nfe.xml", f, "application/xml")},
                )
            assert res.status_code == 200, f"{res.status_code}: {res.text}"
            data = res.json()
            assert "relatorio_id" in data, f"relatorio_id ausente: {data}"
            assert data["relatorio_id"] is not None
            # Provar que /upload-xml resolveu a empresa do tenant correcto
            assert data["empresa_id"] == empresa_id, (
                f"empresa_id errado: esperado {empresa_id}, obtido {data['empresa_id']}"
            )

    def test_e2e_b2_p2_relatorio_persiste_score_e_alertas(self, client):
        """RelatorioAnalise tem score e alertas — pipeline canónico completo."""
        with _pipeline_user_empresa(client) as (user_id, empresa_id, email, headers):
            with open(XML_FIXTURE, "rb") as f:
                res = client.post(
                    "/upload-xml",
                    headers=headers,
                    files={"file": ("nfe.xml", f, "application/xml")},
                )
            assert res.status_code == 200, res.text
            relatorio_id = res.json()["relatorio_id"]

            with _db_session() as db_check:
                rel = db_check.query(RelatorioAnalise).filter(
                    RelatorioAnalise.id == relatorio_id
                ).first()
            assert rel is not None, "RelatorioAnalise não encontrado na BD"
            assert rel.status != "erro", f"Pipeline retornou erro: {rel.status}"
            assert rel.score_resultante is not None, "score_resultante não calculado"
            assert rel.total_alertas is not None, "total_alertas não calculado"


# ---------------------------------------------------------------------------
# E2E-B2-N1, P3, P4 — memorial PDF
# ---------------------------------------------------------------------------

class TestE2EBloco2MemorialPDF:

    def test_e2e_b2_n1_memorial_sem_pagamento_retorna_402(self, client):
        """GET /relatorio/memorial/{id}/pdf sem pago=True → 402."""
        with _pipeline_user_empresa(client) as (user_id, empresa_id, email, headers):
            with open(XML_FIXTURE, "rb") as f:
                res = client.post(
                    "/upload-xml",
                    headers=headers,
                    files={"file": ("nfe.xml", f, "application/xml")},
                )
            assert res.status_code == 200, res.text
            relatorio_id = res.json()["relatorio_id"]

            res_pdf = client.get(
                f"/relatorio/memorial/{relatorio_id}/pdf",
                headers=headers,
            )
            assert res_pdf.status_code == 402, (
                f"Esperado 402 sem pagamento, obtido {res_pdf.status_code}: {res_pdf.text}"
            )

    def test_e2e_b2_p3_memorial_com_pagamento_retorna_200(self, client):
        """GET /relatorio/memorial/{id}/pdf com pago=True → 200."""
        with _pipeline_user_empresa(client) as (user_id, empresa_id, email, headers):
            with open(XML_FIXTURE, "rb") as f:
                res = client.post(
                    "/upload-xml",
                    headers=headers,
                    files={"file": ("nfe.xml", f, "application/xml")},
                )
            assert res.status_code == 200, res.text
            relatorio_id = res.json()["relatorio_id"]

            with _db_session() as db:
                rel = db.query(RelatorioAnalise).filter(
                    RelatorioAnalise.id == relatorio_id
                ).first()
                assert rel is not None
                rel.pago = True
                db.commit()

            res_pdf = client.get(
                f"/relatorio/memorial/{relatorio_id}/pdf",
                headers=headers,
            )
            assert res_pdf.status_code == 200, (
                f"Esperado 200 com pago=True, obtido {res_pdf.status_code}: {res_pdf.text}"
            )

    def test_e2e_b2_p4_memorial_pdf_bytes_validos(self, client):
        """PDF gerado contém header %PDF válido."""
        with _pipeline_user_empresa(client) as (user_id, empresa_id, email, headers):
            with open(XML_FIXTURE, "rb") as f:
                res = client.post(
                    "/upload-xml",
                    headers=headers,
                    files={"file": ("nfe.xml", f, "application/xml")},
                )
            assert res.status_code == 200, res.text
            relatorio_id = res.json()["relatorio_id"]

            with _db_session() as db:
                rel = db.query(RelatorioAnalise).filter(
                    RelatorioAnalise.id == relatorio_id
                ).first()
                rel.pago = True
                db.commit()

            res_pdf = client.get(
                f"/relatorio/memorial/{relatorio_id}/pdf",
                headers=headers,
            )
            assert res_pdf.status_code == 200, res_pdf.text
            assert res_pdf.content[:4] == b"%PDF", (
                f"Não é PDF válido: {res_pdf.content[:20]}"
            )
