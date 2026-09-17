"""Contrato RED da proveniencia do fingerprint no preview fiscal assincrono."""

from __future__ import annotations

import inspect
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.jobs.analysis_job as analysis_job
import app.routes.fiscal_router as fiscal_router
from app.main import app
from app.models import User
from app.security import get_usuario_atual


_FINGERPRINT = "a" * 64


class _QueryFake:
    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return SimpleNamespace(id=21, user_id=11)


class _DBFake:
    def __init__(self):
        self.closed = False

    def query(self, _model):
        return _QueryFake()

    def close(self):
        self.closed = True


def _instalar_job_fakes(monkeypatch, verificar):
    db = _DBFake()
    rel = SimpleNamespace(
        id=501,
        fingerprint=_FINGERPRINT,
        resultado_json={"fingerprint": "b" * 64, "origem": "persistida"},
    )
    analise = {"fingerprint": "c" * 64, "origem": "transitoria"}
    chamadas = []

    def fake_executar(**kwargs):
        chamadas.append(kwargs)
        return rel, analise

    monkeypatch.setattr(analysis_job, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        analysis_job, "executar_e_registrar_analise_xml", fake_executar
    )
    monkeypatch.setattr(
        analysis_job, "verificar_resultado_persistido", verificar, raising=False
    )
    return db, rel, analise, chamadas


def test_job_valida_persistido_e_expoe_exatamente_fingerprint_do_relatorio(monkeypatch):
    verificados = []

    def fake_verificar(relatorio):
        verificados.append(relatorio)
        return {"fingerprint": "d" * 64, "resultado": "validado"}

    db, rel, analise, chamadas = _instalar_job_fakes(monkeypatch, fake_verificar)

    resposta = analysis_job.processar_xml_job(b"<xml/>", 21)

    assert chamadas == [
        {
            "db": db,
            "xml_bytes": b"<xml/>",
            "user_id": 11,
            "empresa_id": 21,
        }
    ]
    assert verificados == [rel]
    assert resposta == {
        "relatorio_id": 501,
        "request_fingerprint": _FINGERPRINT,
        "tem_resultado": True,
    }
    assert resposta["request_fingerprint"] == rel.fingerprint
    assert resposta["request_fingerprint"] != analise["fingerprint"]
    assert resposta["request_fingerprint"] != rel.resultado_json["fingerprint"]
    assert db.closed is True


def test_job_nao_expoe_fingerprint_quando_validacao_persistida_falha(monkeypatch):
    def fake_verificar(_relatorio):
        raise RuntimeError("proveniencia persistida invalida")

    db, _rel, _analise, _chamadas = _instalar_job_fakes(
        monkeypatch, fake_verificar
    )

    with pytest.raises(RuntimeError, match="proveniencia persistida invalida"):
        analysis_job.processar_xml_job(b"<xml/>", 21)

    assert db.closed is True


def test_resultado_sincrono_preserva_id_e_fingerprint(monkeypatch):
    monkeypatch.setenv("ANALISE_XML_INLINE", "true")
    monkeypatch.setattr(
        fiscal_router,
        "processar_xml_job",
        lambda _conteudo, _empresa_id: {
            "relatorio_id": 501,
            "request_fingerprint": _FINGERPRINT,
            "tem_resultado": True,
        },
    )

    resposta = fiscal_router._enqueue_or_run_sync(b"<xml/>", 21, 11)

    assert resposta["status"] == "finished"
    assert resposta["result"] == {
        "relatorio_id": 501,
        "request_fingerprint": _FINGERPRINT,
        "tem_resultado": True,
    }


@pytest.fixture
def _fila_redis_fake(monkeypatch):
    modulo = types.ModuleType("app.queue.redis_queue")
    modulo.redis_conn = MagicMock()
    modulo.analysis_queue = MagicMock()
    monkeypatch.setitem(sys.modules, "app.queue.redis_queue", modulo)
    return modulo


def test_status_do_job_finalizado_preserva_id_fingerprint_e_resultado(
    _fila_redis_fake,
):
    usuario = MagicMock(spec=User)
    usuario.id = 11
    usuario.role = "user"
    job = SimpleNamespace(
        id="job-preview-501",
        meta={"owner_id": 11},
        result={
            "relatorio_id": 501,
            "request_fingerprint": _FINGERPRINT,
        },
        get_status=lambda: "finished",
    )
    app.dependency_overrides[get_usuario_atual] = lambda: usuario

    with patch("app.routes.fiscal_router.Job") as job_cls:
        job_cls.fetch.return_value = job
        try:
            with TestClient(app) as client:
                resposta = client.get("/fiscal/analise/status/job-preview-501")
        finally:
            app.dependency_overrides.clear()

    assert resposta.status_code == 200
    assert resposta.json()["result"] == {
        "relatorio_id": 501,
        "request_fingerprint": _FINGERPRINT,
        "tem_resultado": True,
    }


def test_fluxo_assincrono_permanece_isolado_de_autoridades_de_pagamento():
    source = "\n".join(
        (
            inspect.getsource(analysis_job.processar_xml_job),
            inspect.getsource(fiscal_router._enqueue_or_run_sync),
            inspect.getsource(fiscal_router.status_job),
        )
    )
    autoridades_proibidas = (
        "consulta" + "_paga",
        "relatorio" + ".pago",
        "Checkout" + "OfferGrant",
        "Ordem" + "Checkout",
        "TaxReport" + "Acquisition",
    )

    assert all(autoridade not in source for autoridade in autoridades_proibidas)
