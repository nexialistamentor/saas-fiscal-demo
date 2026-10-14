"""UX2.1 TEST-ONLY: autoridade semântica única, projeção informativa e transporte.

API futura preferida (não criada neste bloco):
app.services.tax_report_eligibility.resultado_tem_credito_tax_report_elegivel
app.services.tax_report_eligibility.projetar_tax_report_eligibility
Nomes públicos equivalentes são descobertos por AST; nunca se usa o método
privado de F1 como autoridade compartilhada. Imports futuros são lazy para que
as ausências sejam assertion failures, não erros de collection.
SQLite efémero somente para observar o enforcement real de persist().
"""
from __future__ import annotations

import ast
import copy
import importlib
import inspect
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app import models
from app.jobs import analysis_job
from app.routes import fiscal_router
from app.services import tax_report_checkout_intent as checkout
from app.services.resultado_provenance_service import (
    ResultadoProvenanceError,
    fingerprint_resultado_json,
    selar_resultado_nao_mei,
    verificar_resultado_persistido,
)
from app.database import get_db
from app.security import get_usuario_atual

ROOT = Path(__file__).resolve().parents[1]
OFFER = "tax-report-one-time-company"
PRODUCER = "app.services.resultado_empresarial_service.compor_resultado_empresarial"


def _credito(valor):
    return {"tipo": "CREDITO_ST_ESTIMADO", "valor_estimado": valor}


# Valores esperados explícitos: não replica o algoritmo de F1.
CASES = [
    ("ausente", {}, False),
    ("none", {"creditos_detectados": None}, False),
    ("dict", {"creditos_detectados": {}}, False),
    ("colecao-string", {"creditos_detectados": "100"}, False),
    ("colecao-bool", {"creditos_detectados": True}, False),
    ("colecao-tuple", {"creditos_detectados": (_credito(100),)}, False),
    ("vazia", {"creditos_detectados": []}, False),
    ("item-string", {"creditos_detectados": ["100"]}, False),
    ("item-none", {"creditos_detectados": [None]}, False),
    ("item-lista", {"creditos_detectados": [[]]}, False),
    ("tipo-errado", {"creditos_detectados": [{"tipo": "OUTRO", "valor_estimado": 100}]}, False),
    ("tipo-ausente", {"creditos_detectados": [{"valor_estimado": 100}]}, False),
    ("valor-ausente", {"creditos_detectados": [{"tipo": "CREDITO_ST_ESTIMADO"}]}, False),
    ("valor-none", {"creditos_detectados": [_credito(None)]}, False),
    ("valor-true", {"creditos_detectados": [_credito(True)]}, False),
    ("valor-false", {"creditos_detectados": [_credito(False)]}, False),
    ("valor-string", {"creditos_detectados": [_credito("100")]}, False),
    ("valor-dict", {"creditos_detectados": [_credito({})]}, False),
    ("valor-lista", {"creditos_detectados": [_credito([])]}, False),
    ("nan", {"creditos_detectados": [_credito(float("nan"))]}, False),
    ("inf", {"creditos_detectados": [_credito(float("inf"))]}, False),
    ("minus-inf", {"creditos_detectados": [_credito(float("-inf"))]}, False),
    ("zero", {"creditos_detectados": [_credito(0)]}, False),
    ("negativo", {"creditos_detectados": [_credito(-100)]}, False),
    ("todos-nao-positivos", {"creditos_detectados": [_credito(0), _credito(-100)]}, False),
    ("zero-positivo", {"creditos_detectados": [_credito(0), _credito(100)]}, True),
    ("positivo", {"creditos_detectados": [_credito(100)]}, True),
    ("sem-threshold", {"creditos_detectados": [_credito(0.000001)]}, True),
    ("sem-soma-minima", {"creditos_detectados": [_credito(-1000), _credito(1)]}, True),
    ("inteiro-grande", {"creditos_detectados": [_credito(10**400)]}, True),
    ("positivo-malformado", {"creditos_detectados": [_credito(100), {}]}, False),
    ("malformado-positivo", {"creditos_detectados": [{}, _credito(100)]}, False),
    ("positivo-tipo-errado", {"creditos_detectados": [_credito(100), {"tipo": "OUTRO", "valor_estimado": 1}]}, False),
    ("positivo-nan", {"creditos_detectados": [_credito(100), _credito(float("nan"))]}, False),
    ("agregado-nao-autoriza", {"valor_estimado": 100000, "tem_resultado": True}, False),
]
MATRIX = pytest.mark.parametrize("name,resultado,expected", CASES, ids=[c[0] for c in CASES])


def _public_function(kind):
    preferred = (
        "resultado_tem_credito_tax_report_elegivel" if kind == "authority"
        else "projetar_tax_report_eligibility"
    )
    matches = []
    for path in sorted((ROOT / "app/services").glob("*tax_report*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            name = node.name.lower()
            semantic = "eligib" in name or "elegib" in name
            projection = "projet" in name or "project" in name
            if node.name == preferred or (semantic and projection == (kind == "projector")):
                matches.append((path, node.name))
    assert len(matches) == 1, (
        "SHARED_AUTHORITY_MISSING_OR_AMBIGUOUS" if kind == "authority"
        else "DOMAIN_PROJECTION_MISSING_OR_AMBIGUOUS"
    )
    path, name = matches[0]
    module = importlib.import_module("app.services." + path.stem)
    function = getattr(module, name)
    assert inspect.isfunction(function) and "." not in function.__qualname__, "PUBLIC_PURE_FUNCTION_REQUIRED"
    return module, function


def _projection(value, expected):
    assert type(value) is dict, "DOMAIN_PROJECTION_REQUIRED"
    assert set(value) == {"eligible"}, "BOOLEAN_ONLY_NO_NEW_FINANCIAL_VALUE"
    assert type(value["eligible"]) is bool, "REAL_BOOLEAN_REQUIRED"
    assert value["eligible"] is expected


def _sealed_report(resultado):
    sealed = selar_resultado_nao_mei(copy.deepcopy(resultado), producer_id=PRODUCER)
    return SimpleNamespace(id=501, user_id=11, empresa_id=21, status="ok",
                           resultado_json=sealed, fingerprint=fingerprint_resultado_json(sealed))


def _enforce(resultado, *, expected_persisted=None):
    """Decisão real de persist(), com provenance real; não chama o método privado."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    models.Base.metadata.create_all(engine, tables=(
        models.RelatorioAnalise.__table__, models.TaxReportCheckoutIntent.__table__,
    ))
    try:
        with Session(engine) as db:
            snapshot = _sealed_report(resultado)
            rel = models.RelatorioAnalise(
                id=501, user_id=11, empresa_id=21, status="ok", analysis_type="empresa_tax",
                resultado_json=snapshot.resultado_json, fingerprint=snapshot.fingerprint, pago=False,
            )
            db.add(rel)
            db.commit()
            if expected_persisted is not None:
                # Compara com a coluna recarregada, não com o objeto pré-JSON.
                db.refresh(rel)
                persisted = verificar_resultado_persistido(rel)
                assert type(persisted["creditos_detectados"]) is list
                assert persisted == expected_persisted
            try:
                result = checkout.TaxReportCheckoutIntent(db).persist(
                    user_id=11, empresa_id=21, relatorio_id=501, offer_code=OFFER,
                    checkout_idempotency_key="ux21-test", request_fingerprint=rel.fingerprint,
                )
            except checkout.TaxReportCheckoutIntentError as error:
                assert str(error) == "relatorio inexistente ou inelegivel", "UNRELATED_ENFORCEMENT_FAILURE"
                assert db.scalar(select(func.count()).select_from(models.TaxReportCheckoutIntent)) == 0
                return False
            assert result.offer_code == OFFER
            assert db.scalar(select(func.count()).select_from(models.TaxReportCheckoutIntent)) == 1
            assert rel.pago is False
            return True
    finally:
        engine.dispose()


@MATRIX
def test_f1_semantica_existente_permanece_green(name, resultado, expected):
    if name == "colecao-tuple":
        _, authority = _public_function("authority")
        _, projector = _public_function("projector")
        assert type(resultado["creditos_detectados"]) is tuple
        assert authority(resultado) is expected is False
        _projection(projector(resultado), False)
        persisted = json.loads(json.dumps(resultado))
        assert type(persisted["creditos_detectados"]) is list
        assert authority(persisted) is True
        assert _enforce(resultado, expected_persisted=persisted) is True
        return
    assert _enforce(resultado) is expected, name


@MATRIX
def test_autoridade_compartilhada_projecao_e_enforcement_mesma_decisao(name, resultado, expected):
    _, authority = _public_function("authority")
    _, projector = _public_function("projector")
    original = copy.deepcopy(resultado)
    decision = authority(resultado)
    assert type(decision) is bool
    assert decision is expected, name
    _projection(projector(resultado), decision)
    if name == "colecao-tuple":
        # Paridade é exigida no mesmo domínio: JSON persistido é uma lista.
        assert decision is False and type(resultado["creditos_detectados"]) is tuple
        persisted = json.loads(json.dumps(resultado))
        assert type(persisted["creditos_detectados"]) is list
        persisted_decision = authority(persisted)
        assert persisted_decision is True
        _projection(projector(persisted), persisted_decision)
        assert _enforce(resultado, expected_persisted=persisted) is persisted_decision
    else:
        assert _enforce(resultado) is decision, name
    # JSON/fingerprint preserva inclusive NaN sem comparação NaN == NaN.
    assert fingerprint_resultado_json(resultado) == fingerprint_resultado_json(original)


def _replace_references(monkeypatch, original, replacement, modules):
    for module in modules:
        for name, value in list(vars(module).items()):
            if value is original:
                monkeypatch.setattr(module, name, replacement)


@pytest.mark.parametrize("decision", [False, True])
def test_f1_e_projetor_delegam_realmente_sem_copy_paste(monkeypatch, decision):
    module, authority = _public_function("authority")
    project_module, projector = _public_function("projector")
    spy = Mock(return_value=decision)
    _replace_references(monkeypatch, authority, spy, (module, project_module, checkout))
    # Força decisão oposta à semântica normal: uma cópia independente falharia.
    resultado = {"creditos_detectados": [] if decision else [_credito(100)]}
    _projection(projector(resultado), decision)
    spy.assert_called_once_with(resultado)
    spy.reset_mock()
    assert _enforce(resultado) is decision, "F1_MUST_USE_SHARED_AUTHORITY"
    spy.assert_called_once()
    assert spy.call_args.args[0]["creditos_detectados"] == resultado["creditos_detectados"]


def test_checkout_nao_conserva_segunda_implementacao_da_regra():
    tree = ast.parse(inspect.getsource(checkout.TaxReportCheckoutIntent))
    literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "creditos_detectados" not in literals and "CREDITO_ST_ESTIMADO" not in literals, "F1_PRIVATE_RULE_STILL_PRESENT"
    # Delegação é comprovada por spy comportamental no teste anterior.


@pytest.mark.parametrize("resultado", [None, [], "browser-object", {}, {"tem_resultado": True}])
def test_dominio_falha_fechado_sem_resultado_suficiente(resultado):
    _, authority = _public_function("authority")
    _, projector = _public_function("projector")
    assert authority(resultado) is False
    _projection(projector(resultado), False)


class _PipelineDB:
    def __init__(self):
        self.closed = False
        self.add = Mock(side_effect=AssertionError("UX_PROJECTION_MUST_NOT_PERSIST_INTENT_OR_PAYMENT"))
        self.flush = Mock(side_effect=AssertionError("UX_PROJECTION_MUST_NOT_FLUSH_COMMERCIAL_STATE"))
        self.commit = Mock(side_effect=AssertionError("UX_PROJECTION_MUST_NOT_COMMIT_COMMERCIAL_STATE"))

    def query(self, model):
        assert model is models.Empresa
        return self

    def filter(self, *_args):
        return self

    def first(self):
        return SimpleNamespace(id=21, user_id=11)

    def close(self):
        self.closed = True


def _pipeline(monkeypatch, expected, *, invalid_provenance=False):
    db = _PipelineDB()
    result = {"creditos_detectados": [_credito(100)] if expected else []}
    rel = _sealed_report(result)
    # Resultados transitório e persistido têm decisões opostas.
    transient = {"creditos_detectados": [] if expected else [_credito(100)]}
    execute = Mock(return_value=(rel, transient))
    verify = Mock(wraps=verificar_resultado_persistido)
    if invalid_provenance:
        rel.fingerprint = "0" * 64
    monkeypatch.setattr(analysis_job, "SessionLocal", lambda: db)
    monkeypatch.setattr(analysis_job, "executar_e_registrar_analise_xml", execute)
    monkeypatch.setattr(analysis_job, "verificar_resultado_persistido", verify)
    return db, rel, execute, verify


@pytest.mark.parametrize("expected", [False, True])
def test_job_projeta_resultado_persistido_verificado_sem_autoridade_comercial(monkeypatch, expected):
    db, rel, execute, verify = _pipeline(monkeypatch, expected)
    response = analysis_job.processar_xml_job(b"<xml/>", 21)
    verify.assert_called_once_with(rel)
    execute.assert_called_once_with(db=db, xml_bytes=b"<xml/>", user_id=11, empresa_id=21)
    assert response["relatorio_id"] == 501
    assert response["request_fingerprint"] == rel.fingerprint
    assert response["tem_resultado"] is True
    assert "tax_report_eligibility" in response, "JOB_PROJECTION_MISSING"
    _projection(response["tax_report_eligibility"], expected)
    assert db.closed is True
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_job_provenance_falha_antes_de_projetar(monkeypatch):
    module, projector = _public_function("projector")
    spy = Mock(side_effect=AssertionError("PROJECTION_BEFORE_PROVENANCE"))
    _replace_references(monkeypatch, projector, spy, (module, analysis_job))
    db, _, _, verify = _pipeline(monkeypatch, True, invalid_provenance=True)
    with pytest.raises(ResultadoProvenanceError):
        analysis_job.processar_xml_job(b"<xml/>", 21)
    verify.assert_called_once()
    spy.assert_not_called()
    assert db.closed is True


def test_job_delega_projetor_com_payload_verificado(monkeypatch):
    module, projector = _public_function("projector")
    projection = {"eligible": False}
    spy = Mock(return_value=projection)
    _replace_references(monkeypatch, projector, spy, (module, analysis_job))
    db, rel, _, verify = _pipeline(monkeypatch, True)
    events = []
    verified = verificar_resultado_persistido(rel)
    verify.side_effect = lambda report: (events.append("verified"), verified)[1]
    spy.side_effect = lambda result: (events.append("projected"), projection)[1]
    response = analysis_job.processar_xml_job(b"<xml/>", 21)
    assert events == ["verified", "projected"]
    spy.assert_called_once_with(verified)
    assert spy.call_args.args[0] is verified
    _projection(response["tax_report_eligibility"], False)
    assert db.closed is True


def _http(monkeypatch, db=None):
    app = FastAPI()
    app.include_router(fiscal_router.router, prefix="/fiscal")
    app.dependency_overrides[get_usuario_atual] = lambda: SimpleNamespace(id=11, role="user")
    app.dependency_overrides[get_db] = lambda: db or _PipelineDB()
    queue = types.ModuleType("app.queue.redis_queue")
    queue.redis_conn = Mock()
    queue.analysis_queue = Mock()
    monkeypatch.setitem(sys.modules, "app.queue.redis_queue", queue)
    return TestClient(app), queue


@pytest.mark.parametrize("mode", ["inline", "fallback"])
@pytest.mark.parametrize("expected", [False, True])
def test_http_sync_pipeline_preserva_projecao(monkeypatch, mode, expected):
    db, rel, _, verify = _pipeline(monkeypatch, expected)
    monkeypatch.setattr(fiscal_router, "processar_xml_job", analysis_job.processar_xml_job)
    monkeypatch.setenv("ANALISE_XML_INLINE", "true" if mode == "inline" else "false")
    async def upload(file):
        return await file.read()
    monkeypatch.setattr(fiscal_router, "validar_upload_xml", upload)
    monkeypatch.setattr(fiscal_router, "verificar_empresa_do_usuario", lambda *_args: None)
    client, queue = _http(monkeypatch, db)
    if mode == "fallback":
        queue.redis_conn.ping.side_effect = RuntimeError("Redis indisponivel no teste")
    with client:
        response = client.post("/fiscal/analisar-xml?empresa_id=21", files={"file": ("nota.xml", b"<xml/>", "application/xml")})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "finished"
    assert body["result"]["relatorio_id"] == 501
    assert body["result"]["request_fingerprint"] == rel.fingerprint
    assert body["result"]["tem_resultado"] is True
    assert "tax_report_eligibility" in body["result"], "SYNC_PROJECTION_MISSING"
    _projection(body["result"]["tax_report_eligibility"], expected)
    verify.assert_called_once_with(rel)


@pytest.mark.parametrize("expected", [False, True])
def test_http_polling_preserva_projecao_recebida_do_job(monkeypatch, expected):
    db, _, _, _ = _pipeline(monkeypatch, expected)
    result = analysis_job.processar_xml_job(b"<xml/>", 21)
    # Entrada do transporte explícita permite isolar RED polling do RED job.
    result["tax_report_eligibility"] = {"eligible": expected}
    client, _ = _http(monkeypatch)
    job = SimpleNamespace(id="ux21-job", meta={"owner_id": 11}, result=result, get_status=lambda: "finished")
    monkeypatch.setattr(fiscal_router.Job, "fetch", Mock(return_value=job))
    with client:
        response = client.get("/fiscal/analise/status/ux21-job")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "finished"
    assert body["result"]["relatorio_id"] == 501
    assert body["result"]["request_fingerprint"] == result["request_fingerprint"]
    assert body["result"]["tem_resultado"] is True
    assert "tax_report_eligibility" in body["result"], "POLLING_PROJECTION_MISSING"
    _projection(body["result"]["tax_report_eligibility"], expected)


@pytest.mark.parametrize("path", ["sync", "polling"])
@pytest.mark.parametrize("unsafe", [None, {}, {"eligible": 1}, {"eligible": "true"}, {"eligible": None}, True])
def test_transporte_sem_projecao_segura_falha_fechado(monkeypatch, path, unsafe):
    result = {"relatorio_id": 501, "request_fingerprint": "a" * 64, "tem_resultado": True}
    if unsafe is not None:
        result["tax_report_eligibility"] = unsafe
    if path == "sync":
        monkeypatch.setenv("ANALISE_XML_INLINE", "true")
        monkeypatch.setattr(fiscal_router, "processar_xml_job", Mock(return_value=result))
        response = fiscal_router._enqueue_or_run_sync(b"<xml/>", 21, 11)
    else:
        client, _ = _http(monkeypatch)
        job = SimpleNamespace(id="ux21-unsafe", meta={"owner_id": 11}, result=result, get_status=lambda: "finished")
        monkeypatch.setattr(fiscal_router.Job, "fetch", Mock(return_value=job))
        with client:
            response = client.get("/fiscal/analise/status/ux21-unsafe").json()
    assert response["status"] == "finished"
    assert "tax_report_eligibility" in response["result"], "FAIL_CLOSED_PROJECTION_MISSING"
    _projection(response["result"]["tax_report_eligibility"], False)


def test_router_apenas_propaga_sem_recalcular_e_sem_endpoint_browser():
    tree = ast.parse(inspect.getsource(fiscal_router))
    forbidden = {"creditos_detectados", "CREDITO_ST_ESTIMADO", "valor_estimado"}
    assert not forbidden.intersection(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str))
    for route in fiscal_router.router.routes:
        assert "eligib" not in route.path.lower() and "elegib" not in route.path.lower(), "BROWSER_ELIGIBILITY_ENDPOINT_FORBIDDEN"
    assert set(inspect.signature(fiscal_router.analisar_xml_fiscal).parameters) == {"file", "empresa_id", "db", "usuario_atual"}
    assert set(inspect.signature(fiscal_router.status_job).parameters) == {"job_id", "usuario_atual"}


def test_projecao_pura_nao_invoca_autoridades_comerciais():
    _, authority = _public_function("authority")
    _, projector = _public_function("projector")
    sources = "\n".join((inspect.getsource(authority), inspect.getsource(projector),
                           inspect.getsource(analysis_job.processar_xml_job),
                           inspect.getsource(fiscal_router._enqueue_or_run_sync),
                           inspect.getsource(fiscal_router.status_job)))
    for forbidden in ("TaxReportCheckoutIntent", "OrdemCheckout", "CheckoutOfferGrant", "TaxReportAcquisition",
                      "MercadoPago", "mercado_pago", "consulta_paga", "relatorio.pago", "capability"):
        assert forbidden not in sources, "UX_INFORMATION_MUST_NOT_GRANT_AUTHORITY: " + forbidden
    pure = ast.parse(inspect.getsource(authority) + "\n" + inspect.getsource(projector))
    for node in ast.walk(pure):
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func).lower()
            assert not any(word in name for word in ("sum", "max", "min", "commit", "flush", "persist", "payment", "acquire", "requests", "session", "open")), "PURE_BOOLEAN_PROJECTION_REQUIRED"


def test_f1_revalida_provenance_mesmo_com_projecao_true(monkeypatch):
    # Campo UX adulterado não substitui o snapshot nem a verificação de F1.
    resultado = {"creditos_detectados": [], "tax_report_eligibility": {"eligible": True}}
    assert _enforce(resultado) is False
    verify = Mock(side_effect=ResultadoProvenanceError("snapshot adulterado"))
    monkeypatch.setattr(checkout, "verificar_resultado_persistido", verify)
    db = Mock()
    db.scalar.return_value = None
    db.get.return_value = _sealed_report({"creditos_detectados": [_credito(100)], "tax_report_eligibility": {"eligible": True}})
    with pytest.raises(checkout.TaxReportCheckoutIntentError, match="resultado persistido invalido"):
        checkout.TaxReportCheckoutIntent(db).persist(user_id=11, empresa_id=21, relatorio_id=501,
            offer_code=OFFER, checkout_idempotency_key="ux21-forged", request_fingerprint=db.get.return_value.fingerprint)
    verify.assert_called_once()
    db.add.assert_not_called()
    db.flush.assert_not_called()


@pytest.mark.parametrize("path", ["sync", "polling"])
@pytest.mark.parametrize("expected", [False, True])
def test_router_nao_chama_autoridade_nem_projetor_para_projecao_pronta(monkeypatch, path, expected):
    module, authority = _public_function("authority")
    project_module, projector = _public_function("projector")
    deny = Mock(side_effect=AssertionError("ROUTER_MUST_ONLY_PROPAGATE"))
    _replace_references(monkeypatch, authority, deny, (module, project_module, fiscal_router))
    _replace_references(monkeypatch, projector, deny, (project_module, fiscal_router))
    result = {"relatorio_id": 501, "request_fingerprint": "a" * 64,
              "tem_resultado": True, "tax_report_eligibility": {"eligible": expected}}
    if path == "sync":
        monkeypatch.setenv("ANALISE_XML_INLINE", "true")
        monkeypatch.setattr(fiscal_router, "processar_xml_job", Mock(return_value=result))
        response = fiscal_router._enqueue_or_run_sync(b"<xml/>", 21, 11)
    else:
        client, _ = _http(monkeypatch)
        job = SimpleNamespace(id="ux21-propagate", meta={"owner_id": 11}, result=result, get_status=lambda: "finished")
        monkeypatch.setattr(fiscal_router.Job, "fetch", Mock(return_value=job))
        with client:
            response = client.get("/fiscal/analise/status/ux21-propagate").json()
    _projection(response["result"]["tax_report_eligibility"], expected)
    deny.assert_not_called()
