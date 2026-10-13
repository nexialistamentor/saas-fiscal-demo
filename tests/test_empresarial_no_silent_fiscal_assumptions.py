"""C0 TEST-ONLY: contexto ausente não cria autoridade financeira.

Observa respostas públicas de XML e engines. A montagem do contexto empresarial
é exercitada na sua fronteira de leitura, sem executar persistência/relatórios.
Fixtures não ratificam fontes fiscais e não substituem fórmulas de produção.
"""
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services import analysis_orchestrator, insights_engine
from app.services.tax_engines.lucro_presumido_engine import LucroPresumidoEngine
from app.services.tax_engines.pis_cofins_engine import PISCOFINSEngine
from app.services.tax_engines.tax_planning_engine import TaxPlanningEngine

REF = date(2026, 1, 1)
AUSENTE = object()


def _assert_indisponivel_ou_sem_autoridade(resposta, *caminho):
    """Zero numérico não é N/D; rótulo genérico 'estimativa' não nega autoridade."""
    atual = resposta
    envelopes = [resposta]
    for chave in caminho:
        if not isinstance(atual, dict) or chave not in atual:
            return  # Campo financeiro não exposto.
        atual = atual[chave]
        if isinstance(atual, dict):
            envelopes.append(atual)
    if atual is None or (isinstance(atual, str) and atual in ("N/D", "indisponivel")):
        return
    for envelope in envelopes:
        if (envelope.get("calculo_autorizado") is False
                or envelope.get("success") is False
                or envelope.get("estado_l3") == "bloqueado"):
            return
    pytest.fail(f"Valor financeiro exposto sem negação explícita de autoridade: {'.'.join(caminho)}={atual!r}")


def _xml_resultado(icms_st=1000.0):
    xml = b'<NFe><infNFe><total><ICMSTot><vST>1000.00</vST></ICMSTot></total></infNFe></NFe>'
    dados = {"icms_st": icms_st, "valor_total_nota": 10000.0, "chave_nfe": "1" * 44}
    # Só parsing é simulado; previsão, decomposição e flags são de produção.
    with patch.object(analysis_orchestrator, "analisar_xml", return_value=dados):
        return analysis_orchestrator.executar_analise_xml(xml)


def _contexto_empresa(regime):
    db = MagicMock()
    query = db.query.return_value
    query.join.return_value = query
    query.filter.return_value = query
    query.scalar.side_effect = [10000.0, 2000.0, 0.0, 0.0, REF]
    query.first.return_value = SimpleNamespace(regime_tributario=regime, cnae_principal=None, cnae_secundarios=None)
    return insights_engine.InsightEngine(db)._montar_contexto_engines(1)


def _engines(contexto, *nomes):
    reais = {"pis_cofins": PISCOFINSEngine, "lucro_presumido": LucroPresumidoEngine, "tax_planning": TaxPlanningEngine}
    # Executa apenas os caminhos fiscais do contrato; nenhuma engine é falsificada.
    with patch.object(insights_engine, "ENGINES", {n: reais[n] for n in nomes}):
        return insights_engine.executar_engines(dict(contexto))


def _dados(atividade=AUSENTE, faturamento=10000.0):
    dados = {"faturamento": faturamento, "lucro": 2000.0, "regime": "presumido", "data_referencia": REF}
    if atividade is not AUSENTE:
        dados["atividade"] = atividade
    return dados


@pytest.mark.parametrize("icms_st", [1000.0, 250.0])
def test_HEURISTICA_15_nao_expoe_recuperacao_autorizada_sem_fundamento(icms_st):
    res = _xml_resultado(icms_st)
    _assert_indisponivel_ou_sem_autoridade(res, "previsao_recuperacao", "potencial_recuperacao_nota")
    _assert_indisponivel_ou_sem_autoridade(res, "decomposicao_impacto", "valor_estimado")


@pytest.mark.parametrize("icms_st", [1000.0, 250.0])
def test_ICMS_ST_COMO_RECUPERAVEL_nao_converte_imposto_em_direito(icms_st):
    res = _xml_resultado(icms_st)
    _assert_indisponivel_ou_sem_autoridade(res, "decomposicao_impacto", "valor_recuperavel_real")


@pytest.mark.parametrize("regime", [None, ""])
def test_REGIME_DEFAULT_PRESUMIDO_contexto_nao_inventa_regime(regime):
    contexto = _contexto_empresa(regime)
    assert contexto.get("regime") not in ("presumido", "lucro_presumido"), "Regime ausente virou Lucro Presumido"


@pytest.mark.parametrize("regime", [None, ""])
def test_REGIME_DEFAULT_PRESUMIDO_sem_carga_financeira_no_fluxo_empresa(regime):
    resultado = _engines(_contexto_empresa(regime), "pis_cofins")["pis_cofins"]
    for tributo in ("pis", "cofins"):
        _assert_indisponivel_ou_sem_autoridade(resultado, "tributos", tributo)


@pytest.mark.parametrize("regime", [None, "", "presumido"])
def test_ATIVIDADE_DEFAULT_COMERCIO_contexto_nao_injeta_atividade(regime):
    contexto = _contexto_empresa(regime)
    assert contexto.get("atividade") in (None, ""), "Sem prova de atividade, contexto injectou comércio"


def test_ATIVIDADE_DEFAULT_COMERCIO_empresa_sem_atividade_nao_expoe_comparacao():
    resultado = _engines(_contexto_empresa("presumido"), "tax_planning")["tax_planning"]
    for regime in ("lucro_presumido", "lucro_real"):
        _assert_indisponivel_ou_sem_autoridade(resultado, "comparacao", regime)
    _assert_indisponivel_ou_sem_autoridade(resultado, "economia_estimada")


@pytest.mark.parametrize("atividade", [AUSENTE, None, ""], ids=["campo_ausente", "None", "vazio"])
def test_ATIVIDADE_DEFAULT_COMERCIO_engine_sem_atividade_nao_presume_bases(atividade):
    res = LucroPresumidoEngine().execute(_dados(atividade))
    for base in ("base_irpj", "base_csll"):
        _assert_indisponivel_ou_sem_autoridade(res, "data", "bases_calculo", base)
    for tributo in ("irpj", "csll"):
        _assert_indisponivel_ou_sem_autoridade(res, "data", "tributos", tributo)


def test_ATIVIDADE_DESCONHECIDA_FALLBACK_engine_nao_aplica_8_e_12_por_cento():
    res = LucroPresumidoEngine().execute(_dados("atividade_desconhecida"))
    for base in ("base_irpj", "base_csll"):
        _assert_indisponivel_ou_sem_autoridade(res, "data", "bases_calculo", base)
    for tributo in ("irpj", "csll"):
        _assert_indisponivel_ou_sem_autoridade(res, "data", "tributos", tributo)


def test_ATIVIDADE_DESCONHECIDA_FALLBACK_comparacao_nao_expoe_economia():
    res = _engines(_dados("atividade_desconhecida"), "tax_planning")["tax_planning"]
    for regime in ("lucro_presumido", "lucro_real"):
        _assert_indisponivel_ou_sem_autoridade(res, "comparacao", regime)
    _assert_indisponivel_ou_sem_autoridade(res, "economia_estimada")


@pytest.mark.parametrize("atividade,base_irpj,base_csll,irpj,csll", [
    ("comercio", 800.0, 1200.0, 120.0, 108.0),
    ("servicos", 3200.0, 3200.0, 480.0, 288.0),
])
def test_CONTROLE_POSITIVO_atividade_explicita_preserva_formulas(atividade, base_irpj, base_csll, irpj, csll):
    res = LucroPresumidoEngine().execute(_dados(atividade))
    assert res["success"] is True
    assert res["data"]["regime"] == "lucro_presumido"
    assert res["data"]["bases_calculo"]["base_irpj"] == pytest.approx(base_irpj)
    assert res["data"]["bases_calculo"]["base_csll"] == pytest.approx(base_csll)
    assert res["data"]["tributos"]["irpj"] == pytest.approx(irpj)
    assert res["data"]["tributos"]["csll"] == pytest.approx(csll)


def test_CONTROLE_POSITIVO_regime_presumido_explicito_preserva_pis_cofins():
    res = _engines(_dados("comercio"), "pis_cofins")["pis_cofins"]
    assert res["tributos"]["pis"] == pytest.approx(65.0)
    assert res["tributos"]["cofins"] == pytest.approx(300.0)


@pytest.mark.parametrize("atividade", ["comercio", "servicos"])
def test_CONTROLE_POSITIVO_comparacao_com_inputs_conhecidos(atividade):
    res = _engines(_dados(atividade), "tax_planning")["tax_planning"]
    assert res["comparacao"]["lucro_presumido"] == pytest.approx(593.0 if atividade == "comercio" else 1133.0)
    assert res["comparacao"]["lucro_real"] >= 0
    assert res["economia_estimada"] >= 0


def test_CONTROLE_POSITIVO_zero_comprovado_nao_e_indisponibilidade():
    res = LucroPresumidoEngine().execute(_dados("comercio", faturamento=0.0))
    assert res["success"] is True
    assert res["data"]["bases_calculo"]["base_irpj"] == 0
    assert res["data"]["bases_calculo"]["base_csll"] == 0
    assert all(valor == 0 for valor in res["data"]["tributos"].values())
