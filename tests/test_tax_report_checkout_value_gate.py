"""F0: só crédito positivo da secção canónica permite intenção empresarial.

Usa composição, selagem, verificação e persistência reais em SQLite efémero.
Não executa checkout, gateway, aquisição ou PDF. Não define mínimo comercial.
"""
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app import models
from app.services import tax_report_checkout_intent as service
from app.services.resultado_empresarial_service import compor_resultado_empresarial
from app.services.resultado_provenance_service import (
    ResultadoProvenanceError,
    fingerprint_resultado_json,
    selar_resultado_nao_mei,
)

OFFER = "tax-report-one-time-company"
PRODUCER = "app.services.resultado_empresarial_service.compor_resultado_empresarial"


def _credito(valor):
    return {"tipo": "CREDITO_ST_ESTIMADO", "valor_estimado": valor}


@pytest.fixture
def fluxo(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    models.Base.metadata.create_all(engine, tables=(
        models.RelatorioAnalise.__table__, models.TaxReportCheckoutIntent.__table__,
    ))
    with Session(engine) as db:
        def preparar(creditos, *, xml=None, rico=None):
            documental = {
                "dados_fiscais": {"icms_st": 0},
                "insights": [],
                "previsao_recuperacao": {"potencial_recuperacao_nota": None},
                "context_flags": {},
                "decomposicao_impacto": {"valor_recuperavel_real": None, "valor_estimado": None},
            }
            if xml:
                documental.update(xml)
            empresarial = {"empresa_id": 21, "creditos_detectados": creditos}
            if rico:
                empresarial.update(rico)
            payload = compor_resultado_empresarial(21, documental, empresarial)
            sealed = selar_resultado_nao_mei(payload, producer_id=PRODUCER)
            rel = models.RelatorioAnalise(
                id=501, user_id=11, empresa_id=21, analysis_type="empresa_tax",
                status="ok", resultado_json=sealed,
                fingerprint=fingerprint_resultado_json(sealed), pago=False,
            )
            db.add(rel)
            db.commit()
            events = []
            real_verify = service.verificar_resultado_persistido

            def verificar(report):
                events.append("verificar")
                return real_verify(report)

            verify = Mock(side_effect=verificar)
            real_add = db.add

            def adicionar(item):
                events.append("adicionar")
                return real_add(item)

            add = Mock(side_effect=adicionar)
            commit = Mock(wraps=db.commit)
            monkeypatch.setattr(service, "verificar_resultado_persistido", verify)
            monkeypatch.setattr(db, "add", add)
            monkeypatch.setattr(db, "commit", commit)

            def persistir(**changes):
                kwargs = dict(user_id=11, empresa_id=21, relatorio_id=501,
                              offer_code=OFFER, checkout_idempotency_key="f0-intent",
                              request_fingerprint=rel.fingerprint)
                kwargs.update(changes)
                return service.TaxReportCheckoutIntent(db).persist(**kwargs)

            return db, rel, persistir, verify, add, commit, events
        yield preparar
    engine.dispose()


def _bloqueado(preparar, creditos, causa, **changes):
    db, _, persistir, verify, add, commit, _ = preparar(creditos, **changes)
    error = None
    try:
        persistir()
    except service.TaxReportCheckoutIntentError as exc:
        error = exc
    verify.assert_called_once()
    assert not add.called, f"INTENT_PERSISTED_BEFORE_GATE: {causa}"
    commit.assert_not_called()
    assert db.scalar(select(func.count()).select_from(models.TaxReportCheckoutIntent)) == 0
    assert error is not None, causa
    # Erro público opaco: não divulga regras, motores ou detalhes do snapshot.
    assert all(word not in str(error).lower() for word in (
        "ncm", "motor", "regra", "creditos_detectados", "valor_estimado", "fonte_legal",
    ))


@pytest.mark.parametrize("creditos", [None, [], [_credito(0)], [_credito(-250)]],
                         ids=["indisponivel", "vazio", "zero", "negativo"])
def test_sem_valor_financeiro_autorizado_bloqueia_antes_de_persistir(fluxo, creditos):
    _bloqueado(fluxo, creditos, "NO_AUTHORIZED_FINANCIAL_VALUE")


@pytest.mark.parametrize("valor", [None, "250", True, False, float("nan"),
    float("inf"), float("-inf"), {}, [], {"valor": 250}],
    ids=["none", "string", "bool_true", "bool_false", "nan", "inf", "minus_inf",
         "objeto", "lista", "objeto_com_valor"])
def test_valor_invalido_falha_fechado(fluxo, valor):
    _bloqueado(fluxo, [_credito(valor)], "INVALID_FINANCIAL_VALUE")


@pytest.mark.parametrize("creditos", [250, "250", True, {}, _credito(250),
    [None], [250], [[]], [{}], [{"tipo": "CREDITO_ST_ESTIMADO"}],
    [{"valor_estimado": 250}], [{"tipo": "OPORTUNIDADE", "valor_estimado": 250}]],
    ids=["numero", "string", "bool", "dict_vazio", "dict_credito", "item_none",
         "item_numero", "item_lista", "item_dict_vazio", "sem_valor", "sem_tipo", "tipo_invalido"])
def test_estrutura_inesperada_nao_adquire_elegibilidade(fluxo, creditos):
    _bloqueado(fluxo, creditos, "INVALID_FINANCIAL_VALUE")


def test_oportunidade_estimada_nao_substitui_credito(fluxo):
    _bloqueado(fluxo, [], "ESTIMATE_ONLY_NOT_ELIGIBLE",
               rico={"oportunidades": [{"valor_estimado": 100000}]})


def test_icms_st_documental_nao_substitui_credito(fluxo):
    _bloqueado(fluxo, [], "DOCUMENTAL_ST_NOT_ELIGIBLE",
               xml={"dados_fiscais": {"icms_st": 50000}})


def test_risco_score_e_estimativa_generica_nao_substituem_credito(fluxo):
    _bloqueado(fluxo, [], "ESTIMATE_ONLY_NOT_ELIGIBLE", rico={
        "risco_tributario": {"nivel_risco": "alto", "score": 100},
        "decomposicao_impacto": {"valor_estimado": 100000},
    })


@pytest.mark.parametrize("creditos", [[_credito(250)], [_credito(0.01)],
    [_credito(0), _credito(-1000), _credito(250)]],
    ids=["positivo", "sem_limiar_comercial", "multiplos_sem_soma"])
def test_credito_positivo_valido_passa_este_gate(fluxo, creditos):
    db, rel, persistir, verify, add, commit, events = fluxo(creditos)
    result = persistir()
    verify.assert_called_once_with(rel)
    assert events == ["verificar", "adicionar"]
    add.assert_called_once()
    commit.assert_not_called()
    assert result.offer_code == OFFER
    assert result.request_fingerprint == rel.fingerprint
    assert db.scalar(select(func.count()).select_from(models.TaxReportCheckoutIntent)) == 1


@pytest.mark.parametrize("modo", ["adulterado", "fingerprint", "pedido_divergente"],
                         ids=["adulterado", "fingerprint_invalido", "pedido_divergente"])
def test_integridade_e_fingerprint_precedem_elegibilidade(fluxo, modo):
    db, rel, persistir, verify, add, commit, _ = fluxo([])
    changes = {}
    if modo == "adulterado":
        rel.resultado_json["creditos_detectados"] = [_credito(250)]
    elif modo == "fingerprint":
        rel.fingerprint = "0" * 64
    else:
        changes["request_fingerprint"] = "f" * 64
    with pytest.raises(service.TaxReportCheckoutIntentError) as captured:
        persistir(**changes)
    verify.assert_called_once()
    if modo != "pedido_divergente":
        assert isinstance(captured.value.__cause__, ResultadoProvenanceError)
        assert str(captured.value) == "resultado persistido invalido"
    else:
        assert str(captured.value) == "fingerprint solicitado divergente"
    add.assert_not_called()
    commit.assert_not_called()
    assert db.scalar(select(func.count()).select_from(models.TaxReportCheckoutIntent)) == 0


@pytest.mark.parametrize("offer", ["mei-other-offer", "tax.report", "outra-oferta"])
def test_outras_ofertas_preservam_rejeicao_existente_sem_verificar_snapshot(fluxo, offer):
    _, _, persistir, verify, add, commit, _ = fluxo([_credito(250)])
    with pytest.raises(service.TaxReportCheckoutIntentError, match="^offer_code invalido$"):
        persistir(offer_code=offer)
    verify.assert_not_called()
    add.assert_not_called()
    commit.assert_not_called()
