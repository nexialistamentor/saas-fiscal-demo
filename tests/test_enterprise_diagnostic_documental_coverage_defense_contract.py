"""P1-02B — testes defensivos de cobertura documental pura, sem checkout.

A NF-e artificial destes testes nao prova autenticidade ou direito fiscal.
"""
from copy import deepcopy

import pytest

from app.motor_fiscal import analisar_xml
from app.services.context_flags_service import inferir_flags_xml
from app.services.enterprise_diagnostic_coverage import avaliar_cobertura_nfe_documental
from app.services.enterprise_paid_diagnostic_eligibility import avaliar_elegibilidade_diagnostico_empresarial
from app.services.resultado_empresarial_service import compor_resultado_empresarial


def _xml(*, st=False, tax=True):
    if tax:
        icms = ('<imposto><ICMS><ICMS10><orig>0</orig><CST>10</CST>'
                '<vBC>1499.00</vBC><vICMS>269.82</vICMS><vBCST>1499.00</vBCST>'
                '<vICMSST>12.00</vICMSST></ICMS10></ICMS></imposto>') if st else (
                '<imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST>'
                '<vBC>1499.00</vBC><vICMS>269.82</vICMS></ICMS00></ICMS></imposto>')
    else:
        icms = ''
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">'
        '<NFe><infNFe Id="NFe' + ('1' * 44) + '" versao="4.00">'
        '<ide><tpNF>1</tpNF></ide>'
        '<emit><CNPJ>11111111000111</CNPJ><enderEmit><UF>PA</UF></enderEmit></emit>'
        '<dest><CNPJ>22222222000122</CNPJ><enderDest><UF>PA</UF></enderDest></dest>'
        '<det nItem="1"><prod><NCM>22030000</NCM><CFOP>5102</CFOP>'
        '<qCom>1</qCom><vProd>1499.00</vProd></prod>' + icms + '</det>'
        '<total><ICMSTot><vNF>1499.00</vNF></ICMSTot></total>'
        '</infNFe></NFe></nfeProc>'
    ).encode('utf-8')


def _resultado(xml):
    dados = analisar_xml(xml)
    assert 'erro' not in dados
    doc = {'dados_fiscais': dados, 'insights': [],
           'previsao_recuperacao': {'potencial_recuperacao_nota': None},
           'context_flags': inferir_flags_xml(dados, {})}
    return compor_resultado_empresarial(
        21, doc,
        {'empresa_id': 21, 'oportunidades': [], 'creditos_detectados': [],
         'context_flags': {'dados_incompletos': True}},
    )


def test_scoped_no_st_nao_altera_payload_ou_p102a():
    xml = _xml()
    res = _resultado(xml)
    original = deepcopy(res)
    assert avaliar_cobertura_nfe_documental(xml, res, empresa_id=21) == {
        'documental_suficiente': True,
        'empresarial_completo': False,
        'st_nao_destacado_observado': True,
    }
    assert res == original
    assert avaliar_elegibilidade_diagnostico_empresarial(res, empresa_id=21) == {'eligible': False}


def test_st_encontrada_nao_se_transforma_em_credito():
    xml = _xml(st=True)
    res = _resultado(xml)
    assert res['creditos_detectados'] == []
    assert avaliar_cobertura_nfe_documental(xml, res, empresa_id=21) == {
        'documental_suficiente': True,
        'empresarial_completo': False,
        'st_nao_destacado_observado': False,
    }


@pytest.mark.parametrize('mudanca', [
    lambda r: r.update(empresa_id=22),
    lambda r: r['dados_fiscais'].update(chave_nfe='2' * 44),
    lambda r: r['dados_fiscais'].update(valor_total_nota='1499.01'),
    lambda r: r['dados_fiscais'].update(uf_dest='SP'),
    lambda r: r['dados_fiscais'].update(cnpj_emitente='33333333000133'),
    lambda r: r.update(insights=None),
    lambda r: r['insights'].update(documental=None),
    lambda r: r.update(previsao_recuperacao=None),
    lambda r: r['dados_fiscais'].update(erro='Falha parser'),
])
def test_fiscal_ou_empresa_divergentes_fecham_cobertura(mudanca):
    xml = _xml()
    res = _resultado(xml)
    mudanca(res)
    assert avaliar_cobertura_nfe_documental(xml, res, empresa_id=21) == {
        'documental_suficiente': False,
        'empresarial_completo': False,
        'st_nao_destacado_observado': False,
    }


@pytest.mark.parametrize('xml', [
    b'<xml-malformado', b'', b'<root/>', _xml(tax=False),
    b'<!DOCTYPE nfeProc [<!ENTITY x "payload">]>'
    b'<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">&x;</nfeProc>',
])
def test_documento_malformado_ou_sem_prova_icms_nao_e_suficiente(xml):
    res = _resultado(_xml())
    assert avaliar_cobertura_nfe_documental(xml, res, empresa_id=21) == {
        'documental_suficiente': False,
        'empresarial_completo': False,
        'st_nao_destacado_observado': False,
    }


def test_flags_empresariais_otimistas_nao_provam_auditoria_integral():
    xml = _xml()
    res = _resultado(xml)
    res['context_flags']['empresarial']['dados_incompletos'] = False
    assert avaliar_cobertura_nfe_documental(xml, res, empresa_id=21)['empresarial_completo'] is False
