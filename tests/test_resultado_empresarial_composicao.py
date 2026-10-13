"""Bloco D: composição retornada, sem mudar o payload persistido existente."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from app.services.resultado_empresarial_service import compor_resultado_empresarial
from app.services import registro_analise_service as registro


def _xml():
    return {'dados_fiscais': {'icms_st': 1000, 'chave_nfe': 'chave'},
            'insights': [{'tipo': 'ICMS_ST_IDENTIFICADO', 'impacto': 'informativo'}],
            'previsao_recuperacao': {'potencial_recuperacao_nota': None, 'icms_st_nota': 1000,
                                    'metodo': 'indisponivel_sem_validacao_normativa'},
            'context_flags': {'dados_incompletos': True},
            'decomposicao_impacto': {'valor_recuperavel_real': None, 'valor_estimado': None}}


def _rico():
    return {'empresa_id': 7, 'oportunidades': [{'tipo': 'AUTORIZADA', 'valor_estimado': 25}],
            'creditos_detectados': [{'tipo': 'CREDITO_ST_ESTIMADO', 'valor_estimado': 10}],
            'risco_tributario': {'nivel_risco': 'baixo'},
            'resultados_engines': {'lucro_presumido': {'estado_l3': 'bloqueado', 'calculo_autorizado': False}},
            'comparativo_regime': {},
            'context_flags': {'dados_incompletos': False},
            'decomposicao_impacto': {'valor_estimado': 25, 'valor_recuperavel_real': None}}


def test_composicao_preserva_factos_seccoes_ricas_e_origens_sem_colisao():
    xml, rico = _xml(), _rico()
    resultado = compor_resultado_empresarial(7, xml, rico)
    assert resultado['empresa_id'] == 7
    assert resultado['dados_fiscais'] == xml['dados_fiscais']
    assert resultado['insights']['documental'] == xml['insights']
    for campo in ('oportunidades','creditos_detectados','risco_tributario','resultados_engines'):
        assert resultado[campo] == rico[campo]
    for campo in ('context_flags','decomposicao_impacto'):
        assert resultado[campo] == {'documental': xml[campo], 'empresarial': rico[campo]}
    assert resultado['previsao_recuperacao']['potencial_recuperacao_nota'] is None
    assert resultado['decomposicao_impacto']['documental']['valor_recuperavel_real'] is None
    assert resultado['decomposicao_impacto']['documental']['valor_estimado'] is None
    assert resultado['resultados_engines']['lucro_presumido']['calculo_autorizado'] is False
    assert resultado['comparativo_regime'] == {}


@pytest.mark.parametrize('rico', [None, {}, {'empresa_id':7}])
def test_seccoes_nao_produzidas_ficam_indisponiveis_sem_zero(rico):
    res = compor_resultado_empresarial(7, _xml(), rico)
    for campo in ('oportunidades','creditos_detectados','risco_tributario','resultados_engines','comparativo_regime'):
        assert res[campo] is None
    assert res['insights']['empresarial'] is None
    assert res['context_flags']['empresarial'] is None
    assert res['decomposicao_impacto']['empresarial'] is None


def test_zero_explicito_e_estruturas_vazias_nao_sao_confundidos_com_ausencia():
    rico = {'empresa_id':7, 'oportunidades':[], 'creditos_detectados':[],
            'decomposicao_impacto':{'valor_estimado':0}}
    res = compor_resultado_empresarial(7, _xml(), rico)
    assert res['oportunidades'] == []
    assert res['creditos_detectados'] == []
    assert res['decomposicao_impacto']['empresarial']['valor_estimado'] == 0


def test_compositor_nao_muta_inputs_nem_partilha_payloads():
    xml,rico = _xml(),_rico(); anterior=deepcopy((xml,rico))
    res = compor_resultado_empresarial(7,xml,rico)
    assert (xml,rico)==anterior
    res['dados_fiscais']['icms_st']=0
    res['oportunidades'][0]['valor_estimado']=0
    assert (xml,rico)==anterior


def test_resultado_de_outra_empresa_nao_e_composto():
    with pytest.raises(ValueError,match='outra empresa'):
        compor_resultado_empresarial(7,_xml(),{'empresa_id':8})


@pytest.mark.parametrize('rico', [_rico(), None], ids=['retorno_rico','insight_indisponivel'])
def test_registro_usa_retorno_real_da_chamada(rico):
    xml=_xml(); db=MagicMock(); empresa=SimpleNamespace(user_id=1)
    db.query.return_value.filter.return_value.first.return_value=empresa
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value=None
    rel=SimpleNamespace(id=9,resultado_json={'anterior':True},fingerprint='anterior')
    with patch.object(registro,'verificar_limite_analises'), \
         patch.object(registro,'executar_analise_xml',return_value=xml), \
         patch.object(registro,'processar_e_persistir_xml'), \
         patch.object(registro,'criar_registro_analise',return_value=rel), \
         patch('app.services.insights_engine.InsightEngine') as engine, \
         patch.object(registro,'calcular_score_global_tributario',return_value={}), \
         patch.object(registro,'contar_alertas_empresa',return_value=0), \
         patch.object(registro,'selar_resultado_nao_mei',side_effect=lambda payload,**kw: {'legado':deepcopy(payload)}) as selo, \
         patch.object(registro,'finalizar_registro_analise') as finalizar, \
         patch.object(registro,'incrementar_uso_analise'):
        engine.return_value.gerar_insights_empresa.return_value=rico
        obtido_rel,resultado=registro.executar_e_registrar_analise_xml(db,b'xml',1,empresa_id=7)
    engine.return_value.gerar_insights_empresa.assert_called_once_with(empresa_id=7,relatorio_analise_id=9)
    assert obtido_rel is rel
    assert resultado == compor_resultado_empresarial(7,xml,rico)
    assert rel.resultado_json=={'anterior':True}
    assert rel.fingerprint=='anterior'


def test_shape_real_rico_sem_insights_mantem_seccao_intencionalmente_indisponivel():
    rico = _rico()
    assert set(rico) == {
        'empresa_id', 'oportunidades', 'creditos_detectados', 'risco_tributario',
        'resultados_engines', 'comparativo_regime', 'context_flags', 'decomposicao_impacto',
    }
    assert 'insights' not in rico
    resultado = compor_resultado_empresarial(7, _xml(), rico)
    assert resultado['insights']['empresarial'] is None
    assert resultado['insights']['documental'] == _xml()['insights']
    for campo in ('oportunidades', 'creditos_detectados', 'risco_tributario', 'resultados_engines'):
        assert resultado[campo] == rico[campo]
        assert resultado[campo] is not None


def test_lista_bruta_nao_auditada_nao_preenche_insights_empresariais():
    rico = _rico()
    rico['insights'] = [{'tipo': 'NAO_AUDITADO', 'valor_estimado': 999}]
    resultado = compor_resultado_empresarial(7, _xml(), rico)
    assert resultado['insights']['empresarial'] is None
    assert rico['insights'] == [{'tipo': 'NAO_AUDITADO', 'valor_estimado': 999}]
