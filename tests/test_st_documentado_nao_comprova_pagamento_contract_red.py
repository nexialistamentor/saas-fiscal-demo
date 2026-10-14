"""AUD3.5: presença documental não comprova recolhimento nem direito material.

Não fixa redação final, renomeia contexto ou muda contratos comerciais.
Executa produtores reais; consultas/norma sintéticas representam somente XML.
"""
from datetime import date
import re
from types import SimpleNamespace
from unittest.mock import Mock
import unicodedata

import pytest

from app.services import insights_engine
from app.services.motor_decisao_tributaria import decidir_acao_st
from app.services.tax_engines.tax_recovery_engine import TaxRecoveryEngine


def _textos(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from _textos(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _textos(child)
    elif isinstance(value, str):
        yield value


def _normalizar(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", texto.lower())
                   if not unicodedata.combining(c))


def _sem_prova_de_pagamento(output):
    for texto in _textos(output):
        normal = _normalizar(texto)
        # Não congela uma frase nova; veda afirmações factuais de pagamento.
        if re.search(r"\b(?:paga|pago|recolhida|recolhido)\b", normal):
            assert re.search(r"\bnao\s+(?:comprova|prova|demonstra|atesta)\b", normal), (
                "ST documental foi apresentada como pagamento/recolhimento: " + texto
            )


def _recuperacao_qualificada(output):
    texto = _normalizar(" ".join(_textos(output)))
    assert any(marker in texto for marker in (
        "estimad", "estimativa", "oportunidade", "indicio", "cenario",
        "simulacao", "potencial", "nao comprova", "nao constitui",
    )), "Diferença documental não comprova direito material recuperável"


def _queries(*rows):
    db = Mock()
    queries = []
    for group in rows:
        query = Mock()
        for method in ("join", "filter", "group_by", "order_by"):
            getattr(query, method).return_value = query
        query.all.return_value = group
        queries.append(query)
    db.query.side_effect = queries
    return db


def _estoque():
    entrada = SimpleNamespace(ncm="10019010", st_entrada=200, st_observado_xml=True)
    saida = SimpleNamespace(ncm="10019010", st_saida=0, st_observado_xml=True)
    return insights_engine.InsightEngine(_queries([entrada], [saida]))._analisar_st_sem_saida_por_ncm(21)


def _contexto_documental(monkeypatch):
    # Agregados documentais, sem comprovante financeiro ou evidência material.
    db = Mock()
    queries = []
    for scalar in (1000, 600, 200, 50):
        query = Mock()
        query.join.return_value = query
        query.filter.return_value = query
        query.scalar.return_value = scalar
        queries.append(query)
    empresa = Mock()
    empresa.filter.return_value = empresa
    empresa.first.return_value = SimpleNamespace(regime_tributario="real")
    tempo = Mock()
    tempo.filter.return_value = tempo
    tempo.scalar.return_value = date(2026, 1, 15)
    db.query.side_effect = [*queries, empresa, tempo]
    monkeypatch.setattr(insights_engine, "inferir_flags_contexto_empresa", lambda **kw: {})
    return insights_engine.InsightEngine(db)._montar_contexto_engines(21)


@pytest.mark.parametrize("st", [10, 50, 25.20], ids=["abaixo", "acima", "igual"])
def test_decisao_documental_nao_afirma_recolhimento_efetivo(st):
    output = decidir_acao_st(100, st, 0.40, 0.18)
    assert output["decisao"] and "valor_estimado" in output
    _sem_prova_de_pagamento(output)


@pytest.mark.parametrize("st", [10, 50], ids=["abaixo", "acima"])
def test_insight_com_origem_observada_nao_comprova_recolhimento(monkeypatch, st):
    item = SimpleNamespace(ncm="10019010", valor_produto=100, valor_st=st,
        st_observado_xml=True, documento=SimpleNamespace(
            uf_dest="PA", uf_emit="PA", data_emissao=date(2026, 1, 15)))
    monkeypatch.setattr(insights_engine, "resolver_aliquota_e_mva", lambda *a, **kw: {
        "mva": 0.40, "aliquota": 0.18, "calculo_autorizado": True, "calculo_parcial": False,
    })
    output = insights_engine.InsightEngine(_queries([item]))._analisar_decisao_st(21)
    assert len(output) == 1
    _sem_prova_de_pagamento(output)


def test_estoque_documental_nao_afirma_st_paga_na_entrada():
    output = _estoque()
    assert len(output) == 1 and output[0]["tipo"] == "ESTOQUE_FANTASMA_NCM"
    _sem_prova_de_pagamento(output)


def test_icms_recuperavel_documental_exige_qualificacao():
    output = TaxRecoveryEngine().execute({"icms_pago": 200, "icms_devido": 50, "ano_referencia": 2026})
    assert output["total_creditos"] == 150
    assert output["creditos_identificados"]
    _recuperacao_qualificada(output)


def test_contexto_documental_nao_cria_direito_material_na_engine(monkeypatch):
    context = _contexto_documental(monkeypatch)
    output = TaxRecoveryEngine().execute(context)
    assert output["total_creditos"] == 150
    assert output["creditos_identificados"]
    _recuperacao_qualificada(output)


@pytest.mark.parametrize("st,valor", [(10, -15.20), (50, 24.80), (25.20, 0)])
def test_comparacao_analitica_continua_calculando(st, valor):
    assert decidir_acao_st(100, st, 0.40, 0.18)["valor_estimado"] == pytest.approx(valor)


def test_estoque_continua_sendo_sinal_analitico():
    assert _estoque()[0]["valor_estimado"] == 200


def test_tax_recovery_preserva_diferenca_analitica():
    output = TaxRecoveryEngine().execute({"icms_pago": 200, "icms_devido": 50, "ano_referencia": 2026})
    assert output["creditos_identificados"][0]["valor"] == 150
    assert output["total_creditos"] == 150


def test_nomes_internos_nao_exigem_rename_neste_bloco(monkeypatch):
    context = _contexto_documental(monkeypatch)
    assert context["icms_pago"] == 200 and context["icms_devido"] == 50
    assert "creditos_detectados" not in context


@pytest.mark.parametrize("texto", [
    "Valor de ST documentado no XML diverge do cenário normativo estimado.",
    "Indício de oportunidade: a diferença documental não comprova pagamento efetivo.",
])
def test_linguagem_documental_qualificada_e_permitida(texto):
    _sem_prova_de_pagamento({"descricao": texto})
    _recuperacao_qualificada({"descricao": texto})


@pytest.mark.parametrize("texto", [
    "ST recolhida acima do valor correto.",
    "ST recolhida abaixo do valor correto.",
    "ST de R$ 200 paga na entrada sem saída correspondente.",
])
def test_controle_da_fronteira_rejeita_afirmacao_factual(texto):
    with pytest.raises(AssertionError):
        _sem_prova_de_pagamento({"descricao": texto})
