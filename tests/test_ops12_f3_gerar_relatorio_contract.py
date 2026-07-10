"""F3 — contrato HTTP para POST /relatorio/gerar."""

import io
from unittest.mock import MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routes.relatorio_router as relatorio_router
from app.database import get_db
from app.main import app
from app.models import User
from app.security import get_usuario_atual


class _DBFake:
    pass


_db_state = None


def _override_db():
    global _db_state
    _db_state = _DBFake()
    yield _db_state


def _mock_user():
    u = MagicMock(spec=User)
    u.id = 1
    return u


_PDF_FAKE = b"%PDF-1.4 fake content"
_PAYLOAD = {"perfil_id": 7}


# ---------------------------------------------------------------------------
# F3.1 — 200 pago → StreamingResponse PDF
# ---------------------------------------------------------------------------

def test_f3_gerar_relatorio_retorna_pdf_200(monkeypatch):
    global _db_state
    _db_state = None
    pagamento_calls = []
    pdf_calls = []

    def fake_pagamento(usuario, perfil_id, db):
        pagamento_calls.append((usuario, perfil_id, db))
        return True

    def fake_pdf(perfil_id, db):
        pdf_calls.append((perfil_id, db))
        buf = io.BytesIO(_PDF_FAKE)
        return buf

    monkeypatch.setattr(relatorio_router, "_pagamento_confirmado", fake_pagamento)
    monkeypatch.setattr(relatorio_router, "_gerar_pdf_relatorio_completo", fake_pdf)
    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.post("/relatorio/gerar", json=_PAYLOAD)
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"] == "attachment; filename=relatorio-fiscal.pdf"
    assert res.content == _PDF_FAKE
    assert len(pagamento_calls) == 1
    assert pagamento_calls[0][0].id == 1
    assert pagamento_calls[0][1] == 7
    assert pagamento_calls[0][2] is _db_state
    assert len(pdf_calls) == 1
    assert pdf_calls[0][0] == 7
    assert pdf_calls[0][1] is _db_state


# ---------------------------------------------------------------------------
# F3.2 — 402 pagamento não confirmado
# ---------------------------------------------------------------------------

def test_f3_gerar_relatorio_sem_pagamento_retorna_402(monkeypatch):
    global _db_state
    _db_state = None
    pagamento_calls = []

    def fake_pagamento(usuario, perfil_id, db):
        pagamento_calls.append((usuario, perfil_id, db))
        return False

    def fail_pdf(*_a, **_k):
        raise AssertionError("_gerar_pdf_relatorio_completo não deve ser chamado sem pagamento")

    monkeypatch.setattr(relatorio_router, "_pagamento_confirmado", fake_pagamento)
    monkeypatch.setattr(relatorio_router, "_gerar_pdf_relatorio_completo", fail_pdf)
    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.post("/relatorio/gerar", json=_PAYLOAD)
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 402
    assert res.json() == {"detail": "Pagamento necessário"}
    assert len(pagamento_calls) == 1
    assert pagamento_calls[0][0].id == 1
    assert pagamento_calls[0][1] == 7
    assert pagamento_calls[0][2] is _db_state


# ---------------------------------------------------------------------------
# F3.3 — 401 sem autenticação
# ---------------------------------------------------------------------------

def test_f3_gerar_relatorio_sem_auth_retorna_401(monkeypatch):
    def fail_pagamento(*_a, **_k):
        raise AssertionError("_pagamento_confirmado não deve ser chamado sem auth")

    def fail_pdf(*_a, **_k):
        raise AssertionError("_gerar_pdf_relatorio_completo não deve ser chamado sem auth")

    monkeypatch.setattr(relatorio_router, "_pagamento_confirmado", fail_pagamento)
    monkeypatch.setattr(relatorio_router, "_gerar_pdf_relatorio_completo", fail_pdf)

    def _user_401():
        raise HTTPException(status_code=401, detail="Não autenticado")

    app.dependency_overrides[get_usuario_atual] = _user_401
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.post("/relatorio/gerar", json=_PAYLOAD)
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 401
    assert res.json() == {"detail": "Não autenticado"}
