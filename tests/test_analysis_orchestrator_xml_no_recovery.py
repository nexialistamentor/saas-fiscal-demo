"""C1: preservar factos do XML, sem monetizar direito não comprovado."""
from pathlib import Path
from unittest.mock import patch

import pytest
from app.services import analysis_orchestrator


def _assert_sem_recuperacao(res):
    assert res["previsao_recuperacao"]["potencial_recuperacao_nota"] is None
    assert res["previsao_recuperacao"]["metodo"] == "indisponivel_sem_validacao_normativa"
    assert res["decomposicao_impacto"]["valor_recuperavel_real"] is None
    assert res["decomposicao_impacto"]["valor_estimado"] is None
    assert res["decomposicao_impacto"]["normalizacoes_aplicadas"] == 0


def test_xml_real_preserva_st_identificado_sem_credito_presumido():
    xml = Path("app/xmls_testes/xml_icms10_st_sintetico.xml").read_bytes()
    res = analysis_orchestrator.executar_analise_xml(xml)
    _assert_sem_recuperacao(res)
    assert res["dados_fiscais"]["icms_st"] == "18.00"
    assert res["previsao_recuperacao"]["icms_st_nota"] == 18.0
    identificado = next(i for i in res["insights"] if i["tipo"] == "ICMS_ST_IDENTIFICADO")
    assert identificado["impacto"] == "informativo"
    assert identificado["valor_estimado"] == 18.0
    assert "elegibilidade" in identificado["recomendacao"]


@pytest.mark.parametrize("dados,st", [({}, None), ({"icms_st": None}, None), ({"icms_st": 0}, 0.0)])
def test_st_ausente_e_zero_documental_nao_viram_zero_de_recuperacao(dados, st):
    with patch.object(analysis_orchestrator, "analisar_xml", return_value=dados):
        res = analysis_orchestrator.executar_analise_xml(b"<NFe/>")
    _assert_sem_recuperacao(res)
    assert res["previsao_recuperacao"]["icms_st_nota"] == st
    assert not any(i["tipo"] == "ICMS_ST_IDENTIFICADO" for i in res["insights"])
