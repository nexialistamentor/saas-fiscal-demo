"""Contrato HTTP read-only da fronteira soberana do memorial."""

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routes.relatorio_router as relatorio_router
import app.services.memorial_service as memorial_service
from app.database import get_db
from app.main import app
from app.models import Empresa, RelatorioAnalise, User
from app.security import get_usuario_atual


class _QueryEmpresaFake:
    def __init__(self, db):
        self.db = db

    def filter(self, *_args):
        return self

    def first(self):
        if self.db.empresa_ok:
            return SimpleNamespace(id=20, user_id=self.db.actor_id)
        return None


class _DBFake:
    def __init__(self, events, *, actor_id=1, empresa_ok=False):
        self.events = events
        self.actor_id = actor_id
        self.empresa_ok = empresa_ok

    def query(self, *entities):
        assert entities == (Empresa,)
        self.events.append("E")
        return _QueryEmpresaFake(self)

    def commit(self):
        raise AssertionError("K: commit proibido em GET")

    def flush(self):
        raise AssertionError("F: flush proibido em GET")

    def rollback(self):
        raise AssertionError("R: rollback proibido em GET")


def _mock_user(user_id=1):
    user = MagicMock(spec=User)
    user.id = user_id
    return user


def _contexto_fake(*, user_id=1, empresa_id=None, pago=True):
    return {
        "relatorio": {
            "id": 1,
            "user_id": user_id,
            "empresa_id": empresa_id,
            "pago": pago,
            "memorial_gerado": False,
        },
        "engines": [],
        "alertas": [],
        "insights": [],
        "referencias_legais": [],
    }


def _request(
    monkeypatch,
    *,
    endpoint,
    preflight,
    actor_id=1,
    empresa_ok=False,
    contexto=None,
    collector_disappears=False,
    generator_fails=False,
    authenticated=True,
):
    events = []
    db = _DBFake(events, actor_id=actor_id, empresa_ok=empresa_ok)

    def override_db():
        yield db

    def fake_preflight(actual_db, relatorio_id):
        assert actual_db is db
        assert relatorio_id == 1
        events.append("P")
        return preflight

    def fake_collector(actual_db, relatorio_id):
        assert actual_db is db
        assert relatorio_id == 1
        events.append("C")
        return None if collector_disappears else contexto

    def fake_generator(actual_context):
        assert actual_context is contexto
        events.append("G_falha" if generator_fails else "G")
        if generator_fails:
            raise RuntimeError("falha controlada do gerador")
        return BytesIO(b"%PDF-1.4\ncontract")

    def fail_mark(*_args, **_kwargs):
        raise AssertionError("M: marcar_memorial_gerado proibido em GET")

    monkeypatch.setattr(
        relatorio_router, "obter_preflight_memorial", fake_preflight, raising=False
    )
    monkeypatch.setattr(relatorio_router, "coletar_contexto_memorial", fake_collector)
    monkeypatch.setattr(relatorio_router, "gerar_pdf_memorial", fake_generator)
    monkeypatch.setattr(
        relatorio_router, "marcar_memorial_gerado", fail_mark, raising=False
    )
    app.dependency_overrides[get_db] = override_db
    if authenticated:
        app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(actor_id)
    else:
        def unauthenticated():
            raise HTTPException(status_code=401, detail="Não autenticado")

        app.dependency_overrides[get_usuario_atual] = unauthenticated

    client = TestClient(app, raise_server_exceptions=not generator_fails)
    try:
        response = client.get(f"/relatorio/memorial/1{endpoint}")
    finally:
        app.dependency_overrides.clear()
    events.append(response.status_code)
    return response, events


@pytest.mark.parametrize("endpoint", ["", "/pdf"])
def test_memorial_401_sem_qualquer_operacao(monkeypatch, endpoint):
    response, events = _request(
        monkeypatch, endpoint=endpoint, preflight=None, authenticated=False
    )
    assert response.status_code == 401
    assert events == [401]


@pytest.mark.parametrize("endpoint", ["", "/pdf"])
def test_memorial_404_executa_apenas_preflight(monkeypatch, endpoint):
    response, events = _request(monkeypatch, endpoint=endpoint, preflight=None)
    assert response.status_code == 404
    assert response.json() == {"detail": "Relatório não encontrado."}
    assert events == ["P", 404]


@pytest.mark.parametrize("endpoint", ["", "/pdf"])
def test_memorial_403_sem_empresa(monkeypatch, endpoint):
    preflight = SimpleNamespace(id=1, user_id=99, empresa_id=None, pago=True)
    response, events = _request(
        monkeypatch, endpoint=endpoint, preflight=preflight
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Acesso negado."}
    assert events == ["P", 403]


@pytest.mark.parametrize("endpoint", ["", "/pdf"])
def test_memorial_403_empresa_alheia(monkeypatch, endpoint):
    preflight = SimpleNamespace(id=1, user_id=99, empresa_id=20, pago=True)
    response, events = _request(
        monkeypatch, endpoint=endpoint, preflight=preflight, empresa_ok=False
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Acesso negado."}
    assert events == ["P", "E", 403]


@pytest.mark.parametrize("endpoint", ["", "/pdf"])
@pytest.mark.parametrize(
    ("preflight", "empresa_ok", "expected"),
    [
        (SimpleNamespace(id=1, user_id=1, empresa_id=None, pago=False), False, ["P", 402]),
        (SimpleNamespace(id=1, user_id=99, empresa_id=20, pago=False), True, ["P", "E", 402]),
    ],
    ids=["user_id", "empresa"],
)
def test_memorial_402_antes_do_colector(
    monkeypatch, endpoint, preflight, empresa_ok, expected
):
    response, events = _request(
        monkeypatch,
        endpoint=endpoint,
        preflight=preflight,
        empresa_ok=empresa_ok,
    )
    assert response.status_code == 402
    assert response.json() == {
        "detail": "Pagamento necessário para aceder ao memorial."
    }
    assert events == expected


@pytest.mark.parametrize(
    ("preflight", "empresa_ok", "expected"),
    [
        (SimpleNamespace(id=1, user_id=1, empresa_id=None, pago=True), False, ["P", "C", 200]),
        (SimpleNamespace(id=1, user_id=99, empresa_id=20, pago=True), True, ["P", "E", "C", 200]),
    ],
    ids=["user_id", "empresa"],
)
def test_memorial_json_200_read_only(monkeypatch, preflight, empresa_ok, expected):
    contexto = _contexto_fake(
        user_id=preflight.user_id, empresa_id=preflight.empresa_id
    )
    response, events = _request(
        monkeypatch,
        endpoint="",
        preflight=preflight,
        empresa_ok=empresa_ok,
        contexto=contexto,
    )
    assert response.status_code == 200
    assert response.json() == contexto
    assert events == expected
    assert contexto["relatorio"]["memorial_gerado"] is False


@pytest.mark.parametrize(
    ("preflight", "empresa_ok", "expected"),
    [
        (SimpleNamespace(id=1, user_id=1, empresa_id=None, pago=True), False, ["P", "C", "G", 200]),
        (SimpleNamespace(id=1, user_id=99, empresa_id=20, pago=True), True, ["P", "E", "C", "G", 200]),
    ],
    ids=["user_id", "empresa"],
)
def test_memorial_pdf_200_read_only(monkeypatch, preflight, empresa_ok, expected):
    contexto = _contexto_fake(
        user_id=preflight.user_id, empresa_id=preflight.empresa_id
    )
    response, events = _request(
        monkeypatch,
        endpoint="/pdf",
        preflight=preflight,
        empresa_ok=empresa_ok,
        contexto=contexto,
    )
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["content-disposition"] == (
        "attachment; filename=memorial-1.pdf"
    )
    assert events == expected
    assert contexto["relatorio"]["memorial_gerado"] is False


@pytest.mark.parametrize("endpoint", ["", "/pdf"])
def test_memorial_desaparecimento_concorrente_retorna_404(monkeypatch, endpoint):
    preflight = SimpleNamespace(id=1, user_id=1, empresa_id=None, pago=True)
    response, events = _request(
        monkeypatch,
        endpoint=endpoint,
        preflight=preflight,
        collector_disappears=True,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Relatório não encontrado."}
    assert events == ["P", "C", 404]


def test_memorial_pdf_falha_do_gerador_sem_mutacao(monkeypatch):
    preflight = SimpleNamespace(id=1, user_id=1, empresa_id=None, pago=True)
    contexto = _contexto_fake()
    response, events = _request(
        monkeypatch,
        endpoint="/pdf",
        preflight=preflight,
        contexto=contexto,
        generator_fails=True,
    )
    assert response.status_code == 500
    assert events == ["P", "C", "G_falha", 500]
    assert contexto["relatorio"]["memorial_gerado"] is False


class _PreflightQueryFake:
    def __init__(self, row):
        self.row = row

    def filter(self, criterion):
        assert criterion.left.key == "id"
        assert criterion.right.value == 7
        return self

    def first(self):
        return self.row


class _PreflightSessionFake:
    def __init__(self, row):
        self.row = row
        self.entities = None

    def query(self, *entities):
        self.entities = entities
        return _PreflightQueryFake(self.row)


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (None, None),
        (SimpleNamespace(id=7, user_id=11, empresa_id=None, pago=False), (7, 11, None, False)),
        (SimpleNamespace(id=7, user_id=11, empresa_id=23, pago=True), (7, 11, 23, True)),
    ],
)
def test_preflight_selecciona_quatro_colunas_exactas(row, expected):
    db = _PreflightSessionFake(row)
    result = memorial_service.obter_preflight_memorial(db, 7)
    assert db.entities == (
        RelatorioAnalise.id,
        RelatorioAnalise.user_id,
        RelatorioAnalise.empresa_id,
        RelatorioAnalise.pago,
    )
    if expected is None:
        assert result is None
    else:
        assert isinstance(result, tuple)
        assert tuple(result) == expected
        with pytest.raises(AttributeError):
            result.pago = True


def test_fronteira_produtiva_nao_integra_l3():
    root = Path(__file__).resolve().parents[1]
    source = "\n".join(
        (root / relative).read_text(encoding="utf-8")
        for relative in (
            "app/routes/relatorio_router.py",
            "app/services/memorial_service.py",
        )
    )
    forbidden = (
        "MemorialValidatorAgent",
        "MemorialValidatorContext",
        "run_mission",
        "registry",
        "scheduler",
    )
    assert all(token not in source for token in forbidden)
