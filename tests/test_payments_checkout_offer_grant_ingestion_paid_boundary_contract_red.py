"""MP-8D.3 RED: boundary pago de ingestao documental por checkout offer."""

import ast
import inspect
from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.routers.ingestion_router as ingestion_router
from app.database import get_db
from app.main import app
from app.models import DocumentoIngerido, Empresa
from app.security import get_usuario_atual
from app.services.checkout_offer_grant_usage import (
    CheckoutOfferGrantUsage,
    CheckoutOfferGrantUsageError,
)
from app.services.document_ingestion.classifier import TipoDocumento


_PAID_PATH = "/ingestao/documentos/checkout-offer"
_LEGACY_PATH = "/ingestao/documentos"
_CAPABILITY = "document.extract"
_DOCUMENT_HASH = "a" * 64
_USER_ID = 7
_EMPRESA_ID = 23
_IDEMPOTENCY_KEY = (
    f"document.extract:v1:{_USER_ID}:{_EMPRESA_ID}:{_DOCUMENT_HASH}"
)
_REQUEST_FINGERPRINT = f"document.extract:v1:sha256:{_DOCUMENT_HASH}"
_GENERIC_GRANT_REJECTION = {"detail": "Operacao de checkout indisponivel."}
_PDF_BYTES = b"%PDF-1.4 paid boundary"


class _QueryFake:
    def __init__(self, db, model):
        self._db = db
        self._model = model
        self._criteria = ()

    def filter(self, *criteria):
        self._criteria = criteria
        self._db.events.append(f"filter:{self._model.__name__}")
        return self

    @staticmethod
    def _bound_values(criteria):
        values = {}
        pending = list(criteria)
        while pending:
            expression = pending.pop()
            left = getattr(expression, "left", None)
            right = getattr(expression, "right", None)
            key = getattr(left, "key", None)
            if key is not None and hasattr(right, "value"):
                values[key] = right.value
            get_children = getattr(expression, "get_children", None)
            if callable(get_children):
                pending.extend(get_children())
        return values

    def first(self):
        self._db.events.append(f"first:{self._model.__name__}")
        if self._model is DocumentoIngerido:
            return self._db.duplicate
        if self._model is Empresa:
            empresa = self._db.empresa
            if empresa is None:
                return None
            requested = self._bound_values(self._criteria)
            if requested.get("id") != empresa.id:
                return None
            if requested.get("user_id") != empresa.user_id:
                return None
            return empresa
        raise AssertionError(f"query inesperada: {self._model!r}")


class _DBFake:
    def __init__(self, *, duplicate=None, empresa=None, fail_document_add=False):
        self.duplicate = duplicate
        self.empresa = empresa
        self.fail_document_add = fail_document_add
        self.events = []
        self.added = []
        self.pending = []
        self.persisted = []
        self.commit_count = 0
        self.refreshed = []
        self.closed = False

    def query(self, model):
        self.events.append(f"query:{model.__name__}")
        return _QueryFake(self, model)

    def add(self, obj):
        model_name = type(obj).__name__
        self.events.append(f"add:{model_name}")
        self.added.append(obj)
        if self.fail_document_add and isinstance(obj, DocumentoIngerido):
            raise RuntimeError("falha antes do commit final")
        self.pending.append(obj)

    def commit(self):
        self.events.append("commit")
        self.commit_count += 1
        self.persisted.extend(self.pending)
        self.pending.clear()

    def refresh(self, obj):
        self.events.append(f"refresh:{type(obj).__name__}")
        self.refreshed.append(obj)
        obj.id = 101

    def rollback(self):
        self.events.append("rollback")
        self.pending.clear()

    def close(self):
        self.events.append("close")
        self.pending.clear()
        self.closed = True


class _PendingGrantConsumption:
    pass


def _response_payload():
    return {
        "id": 101,
        "documento_hash": _DOCUMENT_HASH,
        "decisao": "aprovado",
        "score_confianca": 0.95,
    }


def _event_index(events, name):
    try:
        return events.index(name)
    except ValueError as exc:
        raise AssertionError(f"evento obrigatorio ausente: {name}; eventos={events}") from exc


def test_mp8d3_paid_ingestion_boundary_contract_red(monkeypatch):
    paid_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == _PAID_PATH
        and "POST" in getattr(route, "methods", set())
    ]
    assert len(paid_routes) == 1, (
        "MP-8D.3 RED: boundary/wiring pago ausente; esperado "
        "POST /ingestao/documentos/checkout-offer"
    )

    paid_route = paid_routes[0]
    legacy_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == _LEGACY_PATH
        and "POST" in getattr(route, "methods", set())
    ]
    assert len(legacy_routes) == 1

    assert {parameter.alias for parameter in paid_route.dependant.query_params} == {
        "empresa_id"
    }
    assert {parameter.alias for parameter in paid_route.dependant.body_params} == {
        "file"
    }

    def _walk_dependants(dependant):
        yield dependant
        for child in dependant.dependencies:
            yield from _walk_dependants(child)

    all_dependants = list(_walk_dependants(paid_route.dependant))
    assert get_usuario_atual in {
        dependant.call for dependant in all_dependants
    }
    header_aliases = {
        parameter.alias.lower()
        for dependant in all_dependants
        for parameter in dependant.header_params
    }
    assert "idempotency-key" not in header_aliases

    service_tree = ast.parse(inspect.getsource(CheckoutOfferGrantUsage))
    service_commits = [
        node
        for node in ast.walk(service_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "commit"
    ]
    assert service_commits == [], "CheckoutOfferGrantUsage nao pode fazer commit"
    CheckoutOfferGrantUsage._validar_entrada(
        user_id=_USER_ID,
        empresa_id=_EMPRESA_ID,
        capability=_CAPABILITY,
        idempotency_key="document.extract:v1:opaque-operation",
        request_fingerprint="document.extract:v2:pqc:opaque-fingerprint",
    )

    holder = {
        "db": None,
        "timestamp": datetime(2026, 9, 2, 12, 0, 0),
        "usage_mode": "accept",
        "usage_calls": [],
        "usage_sessions": [],
    }

    def _current_db():
        db = holder["db"]
        assert db is not None
        return db

    def _classificar(*_args, **_kwargs):
        _current_db().events.append("classificar")
        return SimpleNamespace(tipo=TipoDocumento.DANFE, motivo_rejeicao=None)

    def _extrair(*_args, **_kwargs):
        _current_db().events.append("extrair")
        return SimpleNamespace(texto="texto extraido", requer_ocr=False, erro=None)

    def _calcular(*_args, **_kwargs):
        _current_db().events.append("calcular")
        return SimpleNamespace(
            score=0.95,
            decisao=SimpleNamespace(value="aprovado"),
            motivos=[],
        )

    def _normalizar(*_args, **_kwargs):
        _current_db().events.append("normalizar")
        return SimpleNamespace(campos={})

    def _criar_evidencia(**kwargs):
        _current_db().events.append("criar_evidencia")
        return SimpleNamespace(
            documento_hash=_DOCUMENT_HASH,
            timestamp=holder["timestamp"],
            versao_pipeline="v1",
            tipo_documento=TipoDocumento.DANFE,
            score_confianca=0.95,
            decisao=SimpleNamespace(value="aprovado"),
            requereu_ocr=False,
            campos_extraidos={},
            campos_nao_extraidos=[],
            motivos=[],
            validado_humano=False,
            validado_por=None,
            validado_em=None,
            nome_ficheiro=kwargs.get("nome_ficheiro"),
            tamanho_bytes=len(_PDF_BYTES),
        )

    def _serializar(*_args, **_kwargs):
        _current_db().events.append("serializar")
        return {}

    monkeypatch.setattr(ingestion_router, "classificar", _classificar)
    monkeypatch.setattr(ingestion_router, "extrair", _extrair)
    monkeypatch.setattr(ingestion_router, "calcular", _calcular)
    monkeypatch.setattr(ingestion_router, "normalizar", _normalizar)
    monkeypatch.setattr(ingestion_router, "criar_evidencia", _criar_evidencia)
    monkeypatch.setattr(
        ingestion_router,
        "serializar_campos_estruturados",
        _serializar,
    )

    def _usage_init(self, db):
        self._db = db
        db.events.append("usage:init")
        holder["usage_sessions"].append(db)

    def _usage_consume(self, **kwargs):
        self._db.events.append("usage:consumir")
        holder["usage_calls"].append(dict(kwargs))
        if holder["usage_mode"] == "reject":
            raise CheckoutOfferGrantUsageError(
                "grant_id=991 sem saldo durante locking interno"
            )
        consumption = _PendingGrantConsumption()
        self._db.add(consumption)
        return consumption

    monkeypatch.setattr(CheckoutOfferGrantUsage, "__init__", _usage_init)
    monkeypatch.setattr(CheckoutOfferGrantUsage, "consumir", _usage_consume)

    def _db_override():
        db = _current_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_usuario_atual] = lambda: SimpleNamespace(id=_USER_ID)

    def _post(client, path, *, filename="doc.pdf", content=_PDF_BYTES, mime="application/pdf"):
        return client.post(path, files={"file": (filename, content, mime)})

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            holder["db"] = _DBFake()
            usage_before = len(holder["usage_calls"])
            response = _post(client, _PAID_PATH)
            assert response.status_code == 422
            assert len(holder["usage_calls"]) == usage_before

            holder["db"] = _DBFake()
            response = _post(client, f"{_PAID_PATH}?empresa_id=0")
            assert response.status_code == 422
            assert holder["db"].commit_count == 0

            holder["db"] = _DBFake()
            response = _post(
                client,
                f"{_PAID_PATH}?empresa_id={_EMPRESA_ID}",
                mime="text/plain",
            )
            assert response.status_code == 415
            assert "classificar" not in holder["db"].events
            assert holder["db"].commit_count == 0

            holder["db"] = _DBFake()
            response = _post(
                client,
                f"{_PAID_PATH}?empresa_id={_EMPRESA_ID}",
                content=b"",
            )
            assert response.status_code == 400
            assert "classificar" not in holder["db"].events
            assert holder["db"].commit_count == 0

            legacy_db = _DBFake()
            holder["db"] = legacy_db
            usage_before = len(holder["usage_calls"])
            response = _post(client, _LEGACY_PATH)
            assert response.status_code == 200
            assert response.json() == _response_payload()
            assert len(holder["usage_calls"]) == usage_before
            assert legacy_db.commit_count == 1
            legacy_documents = [
                obj for obj in legacy_db.added if isinstance(obj, DocumentoIngerido)
            ]
            assert len(legacy_documents) == 1
            assert legacy_documents[0].empresa_id is None
            assert "query:Empresa" not in legacy_db.events

            success_db = _DBFake(
                empresa=SimpleNamespace(id=_EMPRESA_ID, user_id=_USER_ID)
            )
            holder["db"] = success_db
            success_call_start = len(holder["usage_calls"])
            response = _post(
                client,
                f"{_PAID_PATH}?empresa_id={_EMPRESA_ID}"
                "&user_id=999&capability=forged&grant_id=991",
                filename="mutable-name-a.pdf",
            )
            assert response.status_code == 200
            assert response.json() == _response_payload()
            assert len(holder["usage_calls"]) == success_call_start + 1
            call = holder["usage_calls"][-1]
            assert call == {
                "user_id": _USER_ID,
                "empresa_id": _EMPRESA_ID,
                "capability": _CAPABILITY,
                "idempotency_key": _IDEMPOTENCY_KEY,
                "request_fingerprint": _REQUEST_FINGERPRINT,
            }
            assert len(call["idempotency_key"]) <= 255
            assert len(call["request_fingerprint"]) <= 255
            assert holder["usage_sessions"][-1] is success_db
            assert success_db.commit_count == 1
            assert len(success_db.refreshed) == 1
            assert isinstance(success_db.refreshed[0], DocumentoIngerido)
            assert len(success_db.persisted) == 2
            assert isinstance(success_db.persisted[0], _PendingGrantConsumption)
            assert isinstance(success_db.persisted[1], DocumentoIngerido)

            ordered_events = [
                "classificar",
                "extrair",
                "calcular",
                "normalizar",
                "criar_evidencia",
                "query:DocumentoIngerido",
                "first:DocumentoIngerido",
                "query:Empresa",
                "first:Empresa",
                "usage:init",
                "usage:consumir",
                "add:_PendingGrantConsumption",
                "add:DocumentoIngerido",
                "commit",
                "refresh:DocumentoIngerido",
            ]
            positions = [_event_index(success_db.events, event) for event in ordered_events]
            assert positions == sorted(positions)
            assert success_db.events.count("usage:consumir") == 1
            assert success_db.events.count("commit") == 1

            repeat_db = _DBFake(
                empresa=SimpleNamespace(id=_EMPRESA_ID, user_id=_USER_ID)
            )
            holder["db"] = repeat_db
            holder["timestamp"] = datetime(2026, 9, 2, 12, 45, 30)
            response = _post(
                client,
                f"{_PAID_PATH}?empresa_id={_EMPRESA_ID}",
                filename="mutable-name-b.pdf",
            )
            assert response.status_code == 200
            assert holder["usage_calls"][-1]["idempotency_key"] == _IDEMPOTENCY_KEY
            assert (
                holder["usage_calls"][-1]["request_fingerprint"]
                == _REQUEST_FINGERPRINT
            )

            duplicate = SimpleNamespace(
                id=55,
                conteudo_sha256=_DOCUMENT_HASH,
                evidencia_em=datetime(2026, 9, 1, 8, 0, 0),
            )
            duplicate_db = _DBFake(duplicate=duplicate)
            holder["db"] = duplicate_db
            usage_before = len(holder["usage_calls"])
            response = _post(
                client,
                f"{_PAID_PATH}?empresa_id={_EMPRESA_ID}",
            )
            assert response.status_code == 409
            assert len(holder["usage_calls"]) == usage_before
            assert "query:Empresa" not in duplicate_db.events
            assert duplicate_db.added == []
            assert duplicate_db.commit_count == 0

            missing_empresa_db = _DBFake(empresa=None)
            holder["db"] = missing_empresa_db
            usage_before = len(holder["usage_calls"])
            response = _post(
                client,
                f"{_PAID_PATH}?empresa_id={_EMPRESA_ID}",
            )
            assert response.status_code == 404
            assert len(holder["usage_calls"]) == usage_before
            assert missing_empresa_db.added == []
            assert missing_empresa_db.commit_count == 0

            foreign_empresa_db = _DBFake(
                empresa=SimpleNamespace(id=_EMPRESA_ID, user_id=999)
            )
            holder["db"] = foreign_empresa_db
            usage_before = len(holder["usage_calls"])
            response = _post(
                client,
                f"{_PAID_PATH}?empresa_id={_EMPRESA_ID}",
            )
            assert response.status_code == 404
            assert len(holder["usage_calls"]) == usage_before
            assert foreign_empresa_db.added == []
            assert foreign_empresa_db.commit_count == 0

            rejected_db = _DBFake(
                empresa=SimpleNamespace(id=_EMPRESA_ID, user_id=_USER_ID)
            )
            holder["db"] = rejected_db
            holder["usage_mode"] = "reject"
            response = _post(
                client,
                f"{_PAID_PATH}?empresa_id={_EMPRESA_ID}",
            )
            assert response.status_code == 409
            assert response.json() == _GENERIC_GRANT_REJECTION
            assert rejected_db.added == []
            assert rejected_db.commit_count == 0
            assert rejected_db.persisted == []

            failed_composition_db = _DBFake(
                empresa=SimpleNamespace(id=_EMPRESA_ID, user_id=_USER_ID),
                fail_document_add=True,
            )
            holder["db"] = failed_composition_db
            holder["usage_mode"] = "accept"
            response = _post(
                client,
                f"{_PAID_PATH}?empresa_id={_EMPRESA_ID}",
            )
            assert response.status_code == 500
            assert failed_composition_db.commit_count == 0
            assert failed_composition_db.persisted == []
            assert failed_composition_db.pending == []
            assert failed_composition_db.closed is True
            assert any(
                isinstance(obj, _PendingGrantConsumption)
                for obj in failed_composition_db.added
            )
            assert any(
                isinstance(obj, DocumentoIngerido)
                for obj in failed_composition_db.added
            )
    finally:
        app.dependency_overrides.clear()
