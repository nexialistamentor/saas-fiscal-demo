"""E0: snapshot canónico inteiro, selo e fingerprint reais, sem DB externo."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from app.models import Empresa, RelatorioAnalise
from app.services import registro_analise_service as registro
from app.services.resultado_empresarial_service import compor_resultado_empresarial
from app.services.resultado_provenance_service import (
    PROVENANCE_KEY, selar_resultado_nao_mei, fingerprint_resultado_json,
    verificar_resultado_persistido,
)

PRODUTOR = 'app.services.resultado_empresarial_service.compor_resultado_empresarial'
XML_PRODUTOR = 'app.services.analysis_orchestrator.executar_analise_xml'


def _xml():
    return {'dados_fiscais':{'icms_st':1000,'chave_nfe':'chave'},
            'insights':[{'tipo':'ICMS_ST_IDENTIFICADO','impacto':'informativo'}],
            'previsao_recuperacao':{'icms_st_nota':1000,'potencial_recuperacao_nota':None},
            'context_flags':{'dados_incompletos':True},
            'decomposicao_impacto':{'valor_recuperavel_real':None,'valor_estimado':None}}


def _rico():
    return {'empresa_id':7,'oportunidades':[{'tipo':'ESTIMATIVA','valor_estimado':25}],
            'creditos_detectados':[], 'risco_tributario':{'nivel_risco':'baixo'},
            'resultados_engines':{'lucro_presumido':{'estado_l3':'bloqueado','calculo_autorizado':False}},
            'comparativo_regime':{},'context_flags':{'dados_incompletos':True},
            'decomposicao_impacto':{'valor_recuperavel_real':None,'valor_estimado':None}}


def _fluxo(estado='rico', empresa_id=7):
    xml=_xml(); rico=_rico() if estado=='rico' else None
    rel=SimpleNamespace(id=9,analysis_type='xml_analise',resultado_json=None,fingerprint=None)
    db=MagicMock()
    def query(model):
        q=MagicMock(); q.filter.return_value=q
        q.first.return_value=SimpleNamespace(user_id=1) if model is Empresa else rel
        q.order_by.return_value.first.return_value=None
        return q
    db.query.side_effect=query
    eventos=[]; capturas={}
    def compor(*args,**kwargs):
        eventos.append('compor'); return compor_resultado_empresarial(*args,**kwargs)
    def selar(payload,**kwargs):
        eventos.append('selar'); capturas['pre_selo']=deepcopy(payload)
        capturas['producer_id']=kwargs['producer_id']
        capturas['selado']=selar_resultado_nao_mei(payload,**kwargs)
        return capturas['selado']
    def fingerprint(payload):
        eventos.append('fingerprint')
        assert payload is capturas['selado']
        return fingerprint_resultado_json(payload)
    with patch.object(registro,'verificar_limite_analises'), \
         patch.object(registro,'executar_analise_xml',return_value=xml), \
         patch.object(registro,'processar_e_persistir_xml'), \
         patch.object(registro,'criar_registro_analise',return_value=rel), \
         patch('app.services.insights_engine.InsightEngine') as engine, \
         patch.object(registro,'calcular_score_global_tributario',return_value={}), \
         patch.object(registro,'contar_alertas_empresa',return_value=0), \
         patch.object(registro,'compor_resultado_empresarial',side_effect=compor), \
         patch.object(registro,'selar_resultado_nao_mei',side_effect=selar) as selo, \
         patch.object(registro,'fingerprint_resultado_json',side_effect=fingerprint), \
         patch.object(registro,'finalizar_registro_analise',wraps=registro.finalizar_registro_analise) as finalizar, \
         patch.object(registro,'incrementar_uso_analise'):
        if estado=='falha':
            engine.return_value.gerar_insights_empresa.side_effect=RuntimeError('Falha simulada de insights')
        else:
            engine.return_value.gerar_insights_empresa.return_value=rico
        _,retorno=registro.executar_e_registrar_analise_xml(db,b'xml',1,empresa_id=empresa_id)
    capturas.update(rel=rel,retorno=retorno,xml=xml,rico=rico,eventos=eventos,
                    selo_chamadas=selo.call_count,final_payload=finalizar.call_args.kwargs['resultado_json'])
    return capturas


@pytest.mark.parametrize('estado',['rico','ausente','falha'])
def test_CANONICAL_NOT_SEALED_composicao_precede_selagem_unica(estado):
    c=_fluxo(estado)
    assert c['pre_selo']==compor_resultado_empresarial(7,c['xml'],c['rico']), 'CANONICAL_NOT_SEALED'
    assert c['eventos']==['compor','selar','fingerprint'], 'CANONICAL_NOT_SEALED: ordem'
    assert c['selo_chamadas']==1
    assert c['pre_selo']['insights']['empresarial'] is None
    for origem in ['documental','empresarial']:
        assert origem in c['pre_selo']['context_flags']
        assert origem in c['pre_selo']['decomposicao_impacto']


@pytest.mark.parametrize('estado',['rico','ausente','falha'])
def test_LEGACY_XML_STILL_PERSISTED_finalizador_recebe_snapshot_canonico_selado(estado):
    c=_fluxo(estado)
    esperado=selar_resultado_nao_mei(compor_resultado_empresarial(7,c['xml'],c['rico']),producer_id=PRODUTOR)
    assert c['final_payload']==esperado, 'LEGACY_XML_STILL_PERSISTED'
    assert c['final_payload'] is c['selado']
    assert c['rel'].resultado_json is c['selado']
    assert c['rel'].fingerprint==fingerprint_resultado_json(c['rel'].resultado_json)
    if estado!='rico':
        for sec in ['oportunidades','creditos_detectados','risco_tributario','resultados_engines','comparativo_regime']:
            assert c['rel'].resultado_json[sec] is None


@pytest.mark.parametrize('estado',['rico','ausente','falha'])
def test_WRONG_PRODUCER_ID_snapshot_empresarial_identifica_compositor(estado):
    c=_fluxo(estado)
    assert c['producer_id']==PRODUTOR, 'WRONG_PRODUCER_ID'
    assert c['rel'].resultado_json[PROVENANCE_KEY]['producer_id']==PRODUTOR


@pytest.mark.parametrize('estado',['rico','ausente','falha'])
def test_RETURN_PERSISTENCE_MISMATCH_retorno_equivale_a_negocio_verificado(estado):
    c=_fluxo(estado)
    assert c['retorno']==verificar_resultado_persistido(c['rel']), 'RETURN_PERSISTENCE_MISMATCH'
    assert PROVENANCE_KEY not in c['retorno']
    assert c['retorno']['previsao_recuperacao']['potencial_recuperacao_nota'] is None
    assert c['retorno']['decomposicao_impacto']['documental']['valor_recuperavel_real'] is None


def test_sem_empresa_preserva_xml_selo_produtor_e_fingerprint_anteriores():
    c=_fluxo(empresa_id=None)
    assert c['retorno']==c['xml']
    assert c['pre_selo']==c['xml']
    assert c['producer_id']==XML_PRODUTOR
    assert verificar_resultado_persistido(c['rel'])==c['xml']
    assert c['rel'].fingerprint==fingerprint_resultado_json(c['rel'].resultado_json)
    assert c['eventos']==['selar','fingerprint']


def test_finalizador_real_fingerprinta_exactamente_payload_canonico_selado():
    payload=selar_resultado_nao_mei(compor_resultado_empresarial(7,_xml(),_rico()),producer_id=PRODUTOR)
    rel=SimpleNamespace(resultado_json=None,fingerprint=None)
    db=MagicMock(); db.query.return_value.filter.return_value.first.return_value=rel
    registro.finalizar_registro_analise(db,9,resultado_json=payload)
    assert rel.resultado_json is payload
    assert rel.fingerprint==fingerprint_resultado_json(payload)
    assert rel.fingerprint!=fingerprint_resultado_json(_xml())
    assert rel.fingerprint!=fingerprint_resultado_json(compor_resultado_empresarial(7,_xml(),_rico()))
    assert verificar_resultado_persistido(SimpleNamespace(resultado_json=payload,fingerprint=rel.fingerprint,analysis_type='xml_analise'))==compor_resultado_empresarial(7,_xml(),_rico())


@pytest.mark.parametrize('secao',['oportunidades','creditos_detectados','risco_tributario','resultados_engines','comparativo_regime','context_flags','decomposicao_impacto'])
def test_fingerprint_cobre_cada_secao_enriquecida(secao):
    anterior=compor_resultado_empresarial(7,_xml(),_rico())
    alterado=deepcopy(anterior)
    if secao in ('context_flags','decomposicao_impacto'):
        alterado[secao]['empresarial']={'alteracao_provada':True}
    else:
        alterado[secao]={'alteracao_provada':True}
    a=selar_resultado_nao_mei(anterior,producer_id=PRODUTOR)
    b=selar_resultado_nao_mei(alterado,producer_id=PRODUTOR)
    assert a['dados_fiscais']==b['dados_fiscais']
    assert a[PROVENANCE_KEY]==b[PROVENANCE_KEY]
    assert fingerprint_resultado_json(a)!=fingerprint_resultado_json(b)
