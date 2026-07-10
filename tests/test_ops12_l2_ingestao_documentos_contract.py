"""L2 — contrato HTTP para POST /ingestao/documentos."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routers.ingestion_router as ingestion_router
from app.database import get_db
from app.main import app
from app.models import DocumentoIngerido, Empresa, User
from app.security import get_usuario_atual
from app.services.document_ingestion.classifier import TipoDocumento

_PDF_BYTES = b"%PDF-1.4 fake"
_HASH = "abc123hash"
_DECISAO = "aprovado"
_SCORE = 0.95


def _mock_user(user_id=1):
    u = MagicMock(spec=User)
    u.id = user_id
    return u


def _pdf_file(content=_PDF_BYTES, content_type="application/pdf"):
    return ("file", ("doc.pdf", content, content_type))


# ---------------------------------------------------------------------------
# _DBFake: suporta query de DocumentoIngerido e Empresa
# ---------------------------------------------------------------------------

class _QueryFake:
    def __init__(self, rows):
        self._rows = rows if isinstance(rows, list) else [rows] if rows else []
        self.filter_called = False
        self.first_called = False

    def filter(self, *_a, **_k):
        self.filter_called = True
        return self

    def first(self):
        self.first_called = True
        return self._rows[0] if self._rows else None


class _DBFake:
    def __init__(self, duplicado=None, empresa=None):
        self._duplicado = duplicado
        self._empresa = empresa
        self.query_calls = []
        self.query_instances = []
        self.added = []
        self.committed = False
        self.refreshed = []

    def query(self, model):
        self.query_calls.append(model)
        if model is DocumentoIngerido:
            q = _QueryFake(self._duplicado)
        else:
            q = _QueryFake(self._empresa)
        self.query_instances.append(q)
        return q

    def add(self, obj):
        self.added.append(obj)
        obj.id = 99

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed.append(obj)
        obj.id = 99
        obj.conteudo_sha256 = _HASH
        obj.decisao = _DECISAO
        obj.score_confianca = _SCORE


_db_state = None


def _override_db(duplicado=None, empresa=None):
    def _inner():
        global _db_state
        _db_state = _DBFake(duplicado=duplicado, empresa=empresa)
        yield _db_state
    return _inner


# ---------------------------------------------------------------------------
# Fakes reutilizáveis de pipeline
# ---------------------------------------------------------------------------

def _fake_cls(tipo=None):
    t = tipo or TipoDocumento.DANFE
    return SimpleNamespace(tipo=t, motivo_rejeicao=None)


def _fake_ext():
    return SimpleNamespace(texto="texto extraido", requer_ocr=False, erro=None)


def _fake_conf():
    return SimpleNamespace(score=_SCORE, decisao=SimpleNamespace(value=_DECISAO), motivos=[])


def _fake_norm():
    return SimpleNamespace(campos={})


def _fake_evidencia():
    return SimpleNamespace(
        documento_hash=_HASH,
        timestamp=datetime(2026, 1, 1),
        versao_pipeline="v1",
        tipo_documento=TipoDocumento.DANFE,
        score_confianca=_SCORE,
        decisao=SimpleNamespace(value=_DECISAO),
        requereu_ocr=False,
        campos_extraidos={},
        campos_nao_extraidos=[],
        motivos=[],
        validado_humano=False,
        validado_por=None,
        validado_em=None,
        nome_ficheiro="doc.pdf",
        tamanho_bytes=len(_PDF_BYTES),
    )


def _patch_pipeline(monkeypatch, tipo=None):
    monkeypatch.setattr(ingestion_router, "classificar", lambda *_a, **_k: _fake_cls(tipo))
    monkeypatch.setattr(ingestion_router, "extrair", lambda *_a, **_k: _fake_ext())
    monkeypatch.setattr(ingestion_router, "calcular", lambda *_a, **_k: _fake_conf())
    monkeypatch.setattr(ingestion_router, "normalizar", lambda *_a, **_k: _fake_norm())
    monkeypatch.setattr(ingestion_router, "criar_evidencia", lambda **_k: _fake_evidencia())
    monkeypatch.setattr(ingestion_router, "serializar_campos_estruturados", lambda *_a: {})


# ---------------------------------------------------------------------------
# L2.1 — 200 sucesso sem empresa_id
# ---------------------------------------------------------------------------

def test_l2_ingerir_documento_sem_empresa_retorna_200(monkeypatch):
    global _db_state
    _db_state = None
    _patch_pipeline(monkeypatch)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db(duplicado=None, empresa=None)

    try:
        with TestClient(app) as c:
            res = c.post("/ingestao/documentos", files=[_pdf_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "id": 99,
        "documento_hash": _HASH,
        "decisao": _DECISAO,
        "score_confianca": _SCORE,
    }
    assert _db_state.committed is True
    assert len(_db_state.added) == 1
    assert isinstance(_db_state.added[0], DocumentoIngerido)
    assert _db_state.added[0].user_id == 1
    assert _db_state.added[0].empresa_id is None
    assert len(_db_state.refreshed) == 1
    # AJUSTE 2b: provar query exacta (so DocumentoIngerido - sem empresa_id)
    assert _db_state.query_calls == [DocumentoIngerido]
    assert _db_state.query_instances[0].filter_called is True
    assert _db_state.query_instances[0].first_called is True


# ---------------------------------------------------------------------------
# L2.2 — 200 sucesso com empresa_id=10
# ---------------------------------------------------------------------------

def test_l2_ingerir_documento_com_empresa_retorna_200(monkeypatch):
    global _db_state
    _db_state = None
    _patch_pipeline(monkeypatch)
    emp = SimpleNamespace(id=10, user_id=1)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db(duplicado=None, empresa=emp)

    try:
        with TestClient(app) as c:
            res = c.post("/ingestao/documentos?empresa_id=10", files=[_pdf_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "id": 99,
        "documento_hash": _HASH,
        "decisao": _DECISAO,
        "score_confianca": _SCORE,
    }
    assert _db_state.committed is True
    assert len(_db_state.added) == 1
    assert _db_state.added[0].empresa_id == 10
    assert _db_state.added[0].user_id == 1
    # AJUSTE 2a: provar ordem das queries e estado das instancias
    assert _db_state.query_calls == [DocumentoIngerido, Empresa]
    assert _db_state.query_instances[0].filter_called is True
    assert _db_state.query_instances[0].first_called is True
    assert _db_state.query_instances[1].filter_called is True
    assert _db_state.query_instances[1].first_called is True
    assert len(_db_state.refreshed) == 1


# ---------------------------------------------------------------------------
# L2.3 — 409 documento duplicado
# ---------------------------------------------------------------------------

def test_l2_ingerir_documento_duplicado_retorna_409(monkeypatch):
    global _db_state
    _db_state = None
    _patch_pipeline(monkeypatch)
    duplicado = SimpleNamespace(
        id=7, conteudo_sha256=_HASH,
        evidencia_em=datetime(2025, 12, 1, 10, 0, 0)
    )
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db(duplicado=duplicado)

    try:
        with TestClient(app) as c:
            res = c.post("/ingestao/documentos", files=[_pdf_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 409
    # AJUSTE 1: body exacto completo
    assert res.json() == {
        "detail": {
            "erro": "Documento já ingerido anteriormente.",
            "id": 7,
            "documento_hash": _HASH,
            "evidencia_em": "2025-12-01T10:00:00",
        }
    }
    assert _db_state.committed is False
    assert _db_state.added == []
    assert _db_state.refreshed == []


# ---------------------------------------------------------------------------
# L2.4 — 404 empresa não encontrada
# ---------------------------------------------------------------------------

def test_l2_ingerir_documento_empresa_nao_encontrada_retorna_404(monkeypatch):
    global _db_state
    _db_state = None
    _patch_pipeline(monkeypatch)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db(duplicado=None, empresa=None)

    try:
        with TestClient(app) as c:
            res = c.post("/ingestao/documentos?empresa_id=99", files=[_pdf_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 404
    assert res.json() == {"detail": "Empresa não encontrada."}
    # AJUSTE 3: provar fluxo exacto de queries e ausencia de efeitos
    assert _db_state.query_calls == [DocumentoIngerido, Empresa]
    assert _db_state.query_instances[0].filter_called is True
    assert _db_state.query_instances[0].first_called is True
    assert _db_state.query_instances[1].filter_called is True
    assert _db_state.query_instances[1].first_called is True
    assert _db_state.committed is False
    assert _db_state.added == []
    assert _db_state.refreshed == []


# ---------------------------------------------------------------------------
# L2.5 — 415 MIME não aceite
# ---------------------------------------------------------------------------

def test_l2_ingerir_documento_mime_invalido_retorna_415(monkeypatch):
    def fail_cls(*_a, **_k):
        raise AssertionError("classificar nao deve ser chamado com MIME invalido")
    monkeypatch.setattr(ingestion_router, "classificar", fail_cls)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db()

    try:
        with TestClient(app) as c:
            res = c.post("/ingestao/documentos", files=[_pdf_file(content_type="text/plain")])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 415
    assert "Tipo não suportado" in res.json()["detail"]


# ---------------------------------------------------------------------------
# L2.6 — 400 ficheiro vazio
# ---------------------------------------------------------------------------

def test_l2_ingerir_documento_vazio_retorna_400(monkeypatch):
    def fail_cls(*_a, **_k):
        raise AssertionError("classificar nao deve ser chamado com ficheiro vazio")
    monkeypatch.setattr(ingestion_router, "classificar", fail_cls)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db()

    try:
        with TestClient(app) as c:
            res = c.post("/ingestao/documentos", files=[_pdf_file(content=b"")])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 400
    assert res.json() == {"detail": "Ficheiro vazio."}


# ---------------------------------------------------------------------------
# L2.7 — 422 classificação UNKNOWN
# ---------------------------------------------------------------------------

def test_l2_ingerir_documento_unknown_retorna_422(monkeypatch):
    monkeypatch.setattr(ingestion_router, "classificar",
                        lambda *_a, **_k: SimpleNamespace(
                            tipo=TipoDocumento.UNKNOWN,
                            motivo_rejeicao="Formato não reconhecido"
                        ))

    def fail_ext(*_a, **_k):
        raise AssertionError("extrair nao deve ser chamado apos UNKNOWN")

    # AJUSTE 4: fail mocks para todos os passos seguintes
    def fail_calcular(*_a, **_k):
        raise AssertionError("calcular nao deve ser chamado apos UNKNOWN")

    def fail_normalizar(*_a, **_k):
        raise AssertionError("normalizar nao deve ser chamado apos UNKNOWN")

    def fail_evidencia(*_a, **_k):
        raise AssertionError("criar_evidencia nao deve ser chamado apos UNKNOWN")

    def fail_serializar(*_a, **_k):
        raise AssertionError("serializar_campos_estruturados nao deve ser chamado apos UNKNOWN")

    monkeypatch.setattr(ingestion_router, "extrair", fail_ext)
    monkeypatch.setattr(ingestion_router, "calcular", fail_calcular)
    monkeypatch.setattr(ingestion_router, "normalizar", fail_normalizar)
    monkeypatch.setattr(ingestion_router, "criar_evidencia", fail_evidencia)
    monkeypatch.setattr(ingestion_router, "serializar_campos_estruturados", fail_serializar)

    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db()

    try:
        with TestClient(app) as c:
            res = c.post("/ingestao/documentos", files=[_pdf_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json() == {"detail": "Formato não reconhecido"}
    # AJUSTE 4b: provar ausencia de efeitos no DB
    assert _db_state.query_calls == []
    assert _db_state.added == []
    assert _db_state.committed is False


# ---------------------------------------------------------------------------
# L2.8 — 401 sem autenticação
# ---------------------------------------------------------------------------

def test_l2_ingerir_documento_sem_auth_retorna_401(monkeypatch):
    def fail_cls(*_a, **_k):
        raise AssertionError("classificar nao deve ser chamado sem auth")
    monkeypatch.setattr(ingestion_router, "classificar", fail_cls)

    def _user_401():
        raise HTTPException(status_code=401, detail="Não autenticado")

    app.dependency_overrides[get_usuario_atual] = _user_401
    app.dependency_overrides[get_db] = _override_db()

    try:
        with TestClient(app) as c:
            res = c.post("/ingestao/documentos", files=[_pdf_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 401
    assert res.json() == {"detail": "Não autenticado"}
