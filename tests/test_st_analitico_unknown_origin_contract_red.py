"""AUD3.3: política local dos quatro outputs atuais, sem provenance de saída.

Somente OBSERVED participa desses consumidores. UNKNOWN continua armazenado.
Não exige SQL/filtro específico nem generaliza a política a outros motores.
SQLite efémero executa agregações reais, incluindo OBSERVED + UNKNOWN.
"""
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models
from app.services import insights_engine
from app.services.benchmark_fiscal_service import gerar_benchmark_empresas

CONSUMIDORES = ("anomalia", "divergencia", "decisao", "benchmark")


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    models.DocumentoFiscal.__table__.create(engine)
    models.ItemFiscal.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def norma(monkeypatch):
    monkeypatch.setattr(insights_engine, "resolver_aliquota_e_mva", lambda *a, **kw: {
        "fonte": "tabela", "mva": 0.40, "aliquota": 0.18,
        "confianca": "oficial", "calculo_autorizado": True,
        "calculo_parcial": False, "mva_autorizada": True,
    })


def _item(db, origem, *, base=140, st=10, tipo="entrada"):
    documento = models.DocumentoFiscal(
        empresa_id=21, usuario_id=11, tipo=tipo,
        data_emissao=date(2026, 1, 15), uf_emit="PA", uf_dest="PA",
    )
    db.add(documento)
    db.flush()
    item = models.ItemFiscal(
        documento_id=documento.id, ncm="10019010", cfop="1102",
        quantidade=1, valor_produto=50, base_st=base, valor_st=st,
        st_observado_xml=origem,
    )
    db.add(item)
    db.commit()
    return item.id


def _venda_para_anomalia(db, consumidor):
    if consumidor == "anomalia":
        _item(db, True, base=0, st=0, tipo="saida")


def _estado(db):
    db.flush()
    return list(db.execute(select(
        models.ItemFiscal.id, models.ItemFiscal.base_st,
        models.ItemFiscal.valor_st, models.ItemFiscal.st_observado_xml,
    ).order_by(models.ItemFiscal.id)).all())


def _executar(db, consumidor):
    engine = insights_engine.InsightEngine(db)
    if consumidor == "anomalia":
        return engine._analisar_anomalia_mva(21)
    if consumidor == "divergencia":
        return engine._analisar_mva_oficial_divergente(21, {})
    if consumidor == "decisao":
        return engine._analisar_decisao_st(21)
    return gerar_benchmark_empresas(db, [21])


def _resultado_observado(consumidor, result):
    assert len(result) == 1
    row = result[0]
    if consumidor == "anomalia":
        assert row["tipo"] == "ANOMALIA_MVA"
        assert row["valor_estimado"] == 90
    elif consumidor == "divergencia":
        assert row["tipo"] == "MVA_OFICIAL_DIVERGENTE"
    elif consumidor == "decisao":
        assert row["tipo"] == "RISCO_FISCAL"
        assert row["valor_estimado"] == pytest.approx(-2.60)
    else:
        assert row["eficiencia_tributaria"] == 10
        assert row["volume_operacoes"] == 1


def test_anomalia_mva_historico_unknown_nao_emite_sem_qualificacao(db, norma):
    _item(db, None)
    _venda_para_anomalia(db, "anomalia")
    assert _executar(db, "anomalia") == []


def test_mva_divergente_historico_unknown_nao_afirma_mva_aplicada(db, norma):
    _item(db, None)
    assert _executar(db, "divergencia") == []


def test_decisao_st_historico_unknown_nao_afirma_recolhimento(db, norma):
    _item(db, None, st=7.20)
    assert _executar(db, "decisao") == []


def test_benchmark_historico_unknown_nao_compoe_metrica_factual(db, norma):
    _item(db, None, st=7.20)
    assert _executar(db, "benchmark") == []


@pytest.mark.parametrize("consumidor", CONSUMIDORES)
def test_mistura_observed_unknown_so_observed_participa(db, norma, consumidor):
    _item(db, True, st=10)
    _item(db, None, base=700, st=90)
    _venda_para_anomalia(db, consumidor)
    antes = _estado(db)
    result = _executar(db, consumidor)
    assert _estado(db) == antes, "Uso analítico não pode atualizar/apagar/reclassificar histórico"
    _resultado_observado(consumidor, result)


@pytest.mark.parametrize("consumidor", CONSUMIDORES)
def test_observed_preserva_analise(db, norma, consumidor):
    _item(db, True)
    _venda_para_anomalia(db, consumidor)
    _resultado_observado(consumidor, _executar(db, consumidor))


@pytest.mark.parametrize("consumidor", CONSUMIDORES)
def test_zero_observado_permanece_valido(db, norma, consumidor):
    _item(db, True, base=0, st=0)
    _venda_para_anomalia(db, consumidor)
    antes = _estado(db)
    result = _executar(db, consumidor)
    assert _estado(db) == antes
    if consumidor == "anomalia":
        assert result == []  # zero conhecido não indica esta anomalia
    elif consumidor == "divergencia":
        assert len(result) == 1 and result[0]["tipo"] == "MVA_OFICIAL_DIVERGENTE"
    elif consumidor == "decisao":
        assert len(result) == 1 and result[0]["valor_estimado"] == pytest.approx(-12.60)
    else:
        assert result[0]["eficiencia_tributaria"] == 0


@pytest.mark.parametrize("consumidor", CONSUMIDORES)
def test_false_com_campos_ausentes_permanece_seguro(db, norma, consumidor):
    _item(db, False, base=None, st=None)
    _venda_para_anomalia(db, consumidor)
    assert _executar(db, consumidor) == []
