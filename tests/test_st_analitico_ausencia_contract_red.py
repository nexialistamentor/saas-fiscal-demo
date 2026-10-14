"""AUD3.1: ausência não é zero observado; contratos de saída, sem filtro global.

Consultas ORM/SQL são controladas, mas os quatro consumidores reais executam.
O resolver fornece norma sintética autorizada; simulação/decisão permanecem reais.
UNKNOWN com números exige silêncio ou qualificação explícita: ORIGIN_POLICY_REQUIRED.
Não fixa implementação nem um campo/status futuro para dados insuficientes.
"""
from datetime import date
from numbers import Real
from types import SimpleNamespace
from unittest.mock import Mock
import unicodedata

import pytest

from app.services import insights_engine
from app.services.benchmark_fiscal_service import gerar_benchmark_empresas


def _db(*grupos):
    db = Mock()
    consultas = []
    for rows in grupos:
        query = Mock()
        for method in ("join", "filter", "group_by", "order_by"):
            getattr(query, method).return_value = query
        query.all.return_value = rows
        consultas.append(query)
    db.query.side_effect = consultas
    if grupos:
        db.execute.return_value.fetchall.return_value = grupos[0]
    return db


def _norma(monkeypatch):
    monkeypatch.setattr(insights_engine, "resolver_aliquota_e_mva", lambda *a, **kw: {
        "fonte": "tabela", "mva": 0.40, "aliquota": 0.18,
        "confianca": "oficial", "calculo_autorizado": True,
        "calculo_parcial": False, "mva_autorizada": True,
    })


def _item(origem, base=None, st=None):
    return SimpleNamespace(
        ncm="10019010", valor_produto=100, base_st=base, valor_st=st,
        st_observado_xml=origem,
        documento=SimpleNamespace(uf_dest="PA", uf_emit="PA", data_emissao=date(2026, 1, 15)),
    )


def _anomalia(base, origem):
    venda = SimpleNamespace(ncm="10019010", preco_medio=100)
    entrada = SimpleNamespace(ncm="10019010", base_media=base, st_observado_xml=origem)
    db = _db([venda], [entrada])
    return insights_engine.InsightEngine(db)._analisar_anomalia_mva(21)


def _divergencia(origem, base=None):
    return insights_engine.InsightEngine(_db([_item(origem, base)]))._analisar_mva_oficial_divergente(21, {})


def _decisao(origem, st=None):
    return insights_engine.InsightEngine(_db([_item(origem, st=st)]))._analisar_decisao_st(21)


def _benchmark(origem, total=None):
    row = SimpleNamespace(empresa_id=21, total_st=total, volume_operacoes=2,
                          st_observado_xml=origem)
    return gerar_benchmark_empresas(_db([row]), [21])


def _folhas(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from _folhas(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _folhas(child)
    else:
        yield value


def _qualificado_ou_silencioso(value):
    if value is None or value == [] or value == {}:
        return True
    texto = " ".join(str(v) for v in _folhas(value)).lower()
    texto = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    # Aceita cenários separados, origem desconhecida ou insuficiência explícita.
    return any(marker in texto for marker in (
        "unknown", "desconhecid", "nao comprov", "insuficien", "indisponivel",
        "estimativa", "estimado", "cenario", "simulacao",
    ))


@pytest.mark.parametrize("origem", [False, None], ids=["novo-false", "origem-null"])
def test_anomalia_mva_sem_base_st_nao_pode_lancar_excecao(origem):
    assert _anomalia(None, origem) == []


@pytest.mark.parametrize("origem", [False, None], ids=["novo-false", "origem-null"])
def test_mva_oficial_divergente_sem_base_st_nao_inventa_mva_aplicada(monkeypatch, origem):
    _norma(monkeypatch)
    assert _divergencia(origem) == []


@pytest.mark.parametrize("origem", [False, None], ids=["novo-false", "origem-null"])
def test_decisao_st_sem_st_observado_nao_afirma_recolhimento_insuficiente(monkeypatch, origem):
    _norma(monkeypatch)
    result = _decisao(origem)
    assert _qualificado_ou_silencioso(result), "Ausência virou comparação com recolhimento factual"
    textos = " ".join(str(v).lower() for v in _folhas(result))
    assert "st recolhida abaixo do valor correto" not in textos


@pytest.mark.parametrize("origem", [False, None], ids=["novo-false", "origem-null"])
def test_benchmark_sem_st_nao_divide_null(origem):
    result = _benchmark(origem)
    # Vazio, None ou insuficiência explícita são possíveis; eficiência numérica não.
    assert _qualificado_ou_silencioso(result)
    rows = result if isinstance(result, list) else [result]
    for row in rows:
        if isinstance(row, dict):
            assert not isinstance(row.get("eficiencia_tributaria"), Real)


def test_anomalia_com_base_observada_preserva_analise():
    result = _anomalia(300, True)
    assert any(i["tipo"] == "ANOMALIA_MVA" and i["valor_estimado"] == 200 for i in result)


def test_divergencia_com_base_observada_preserva_analise(monkeypatch):
    _norma(monkeypatch)
    assert any(i["tipo"] == "MVA_OFICIAL_DIVERGENTE" for i in _divergencia(True, 180))


def test_decisao_com_st_observado_preserva_analise(monkeypatch):
    _norma(monkeypatch)
    result = _decisao(True, 10)
    assert any(i["tipo"] == "RISCO_FISCAL" and i["valor_estimado"] == pytest.approx(-15.20) for i in result)


def test_benchmark_com_st_observado_preserva_calculo():
    assert _benchmark(True, 20)[0]["eficiencia_tributaria"] == 10


def test_zero_observado_nao_e_ausencia_na_decisao(monkeypatch):
    _norma(monkeypatch)
    assert any(i["tipo"] == "RISCO_FISCAL" and i["valor_estimado"] == pytest.approx(-25.20)
               for i in _decisao(True, 0))


def test_zero_observado_nao_e_ausencia_no_benchmark():
    assert _benchmark(True, 0)[0]["eficiencia_tributaria"] == 0


@pytest.mark.parametrize("consumidor", ["anomalia", "divergencia", "decisao", "benchmark"])
def test_historico_numerico_unknown_nao_e_fato_observado_silencioso(monkeypatch, consumidor):
    _norma(monkeypatch)
    result = {
        "anomalia": lambda: _anomalia(300, None),
        "divergencia": lambda: _divergencia(None, 180),
        "decisao": lambda: _decisao(None, 10),
        "benchmark": lambda: _benchmark(None, 20),
    }[consumidor]()
    assert _qualificado_ou_silencioso(result), "ORIGIN_POLICY_REQUIRED: histórico sem qualificação"
