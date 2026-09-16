"""Contrato RED do handoff do fingerprint persistido no preview fiscal."""

from __future__ import annotations

import inspect
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile

import app.routes.relatorio_router as relatorio_router


_FINGERPRINT = "a" * 64
_MENSAGEM = (
    "Análise concluída. Desbloqueie o relatório completo para visualizar os detalhes."
)
_DETAIL_INDISPONIVEL = "Relatório indisponível para aquisição."


def _endpoint_gerar_relatorio():
    matches = [
        route.endpoint
        for route in relatorio_router.router.routes
        if route.path == "/gerar-relatorio" and "POST" in route.methods
    ]
    assert len(matches) == 1
    return matches[0]


class _QueryFake:
    def __init__(self, empresa):
        self._empresa = empresa

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._empresa


class _DBFake:
    def __init__(self):
        self.empresa = SimpleNamespace(id=21, user_id=11)

    def query(self, _model):
        return _QueryFake(self.empresa)


def _relatorio_obj(*, status="ok", fingerprint=_FINGERPRINT):
    return SimpleNamespace(
        id=501,
        empresa_id=21,
        user_id=11,
        status=status,
        fingerprint=fingerprint,
        resultado_json={"resultado": "persistido"},
    )


async def _executar_endpoint(monkeypatch, relatorio_obj, *, analise=None):
    endpoint = _endpoint_gerar_relatorio()
    analise = analise or {"fingerprint": "b" * 64, "origem": "transitória"}
    verificacoes = []

    async def fake_validar_upload_xml(_file):
        return b"<xml/>"

    def fake_verificar_empresa(empresa_id, usuario, _db):
        assert empresa_id == 21
        assert usuario.id == 11

    def fake_executar(_db, xml_bytes, user_id, empresa_id, limite_analises=100):
        assert xml_bytes == b"<xml/>"
        assert (user_id, empresa_id, limite_analises) == (11, 21, 100)
        return relatorio_obj, analise

    def fake_montar(recebida, empresa_id, _db):
        assert recebida is analise
        assert empresa_id == 21
        return {"relatorio_id": 999, "request_fingerprint": "c" * 64}

    def fake_verificar_resultado_persistido(recebido):
        verificacoes.append(recebido)
        if recebido.status != "ok" or recebido.fingerprint != _FINGERPRINT:
            raise relatorio_router.ResultadoProvenanceError("detalhe interno secreto")
        return {"resultado": "persistido"}

    monkeypatch.setattr(relatorio_router, "validar_upload_xml", fake_validar_upload_xml)
    monkeypatch.setattr(
        relatorio_router, "verificar_empresa_do_usuario", fake_verificar_empresa
    )
    monkeypatch.setattr(
        relatorio_router, "executar_e_registrar_analise_xml", fake_executar
    )
    monkeypatch.setattr(relatorio_router, "_montar_relatorio", fake_montar)
    monkeypatch.setattr(
        relatorio_router,
        "verificar_resultado_persistido",
        fake_verificar_resultado_persistido,
    )

    resposta = await endpoint(
        file=UploadFile(filename="nota.xml", file=BytesIO(b"<xml/>")),
        empresa_id=21,
        db=_DBFake(),
        usuario_atual=SimpleNamespace(id=11, plano=None),
    )
    return resposta, verificacoes


@pytest.mark.asyncio
async def test_preview_entrega_exatamente_fingerprint_do_resultado_persistido(monkeypatch):
    relatorio_obj = _relatorio_obj()

    resposta, verificacoes = await _executar_endpoint(monkeypatch, relatorio_obj)

    assert resposta == {
        "status": "processado",
        "mensagem": _MENSAGEM,
        "relatorio_id": 501,
        "request_fingerprint": _FINGERPRINT,
    }
    assert resposta["request_fingerprint"] == relatorio_obj.fingerprint
    assert verificacoes == [relatorio_obj]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "relatorio_obj",
    [
        pytest.param(_relatorio_obj(status="erro"), id="status-nao-ok"),
        pytest.param(_relatorio_obj(fingerprint="fingerprint-invalido"), id="fingerprint-invalido"),
    ],
)
async def test_preview_falha_fechado_sem_expor_detalhes(monkeypatch, relatorio_obj):
    with pytest.raises(HTTPException) as exc_info:
        await _executar_endpoint(monkeypatch, relatorio_obj)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == _DETAIL_INDISPONIVEL
    resposta_publica = str(exc_info.value.detail)
    for segredo in (
        relatorio_obj.fingerprint,
        "provenance",
        "producer",
        "hash esperado",
        "resultado_json",
        "detalhe interno secreto",
    ):
        assert segredo not in resposta_publica


def test_endpoint_preview_mantem_isolamento_da_autorizacao_de_pagamento():
    source = inspect.getsource(_endpoint_gerar_relatorio())

    assert "relatorio_obj.fingerprint" in source
    assert "verificar_resultado_persistido" in source
    for autoridade_proibida in (
        "TaxReportAcquisition",
        "CheckoutOfferGrant",
        "CheckoutOfferGrantConsumption",
        "OrdemCheckout",
        "consulta_paga",
        "_pagamento_confirmado",
    ):
        assert autoridade_proibida not in source
