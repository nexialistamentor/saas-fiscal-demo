"""P1-02C: regressao defensiva da fronteira Enterprise sem acesso a BD.

Os XMLs sao sinteticos. Nao validam autorizacao SEFAZ nem direito fiscal.
Nao concedem compra/pagamento, nao relaxam P1-02A nem alteram snapshots.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

import pytest

from app.services.enterprise_diagnostic_amount_binding import (
    normalizar_valor_nfe_para_politica as normalizar,
)
from app.services.enterprise_diagnostic_coverage import avaliar_cobertura_nfe_documental
from app.services.enterprise_paid_diagnostic_eligibility import (
    avaliar_elegibilidade_diagnostico_empresarial as elegivel,
)


def _xml(*, st=False, tax=True, two_items=False, raiz="nfeProc"):
    grupo = (
        '<imposto><ICMS><ICMS10><orig>0</orig><CST>10</CST>'
        '<vBC>1499.00</vBC><vICMS>269.82</vICMS><vBCST>1499.00</vBCST>'
        '<vICMSST>12.00</vICMSST></ICMS10></ICMS></imposto>'
    ) if st else (
        '<imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST>'
        '<vBC>1499.00</vBC><vICMS>269.82</vICMS></ICMS00></ICMS></imposto>'
    )
    if not tax:
        grupo = ''
    det = ('<det nItem="1"><prod><NCM>22030000</NCM><CFOP>5102</CFOP>'
           '<qCom>1</qCom><vProd>1499.00</vProd></prod>' + grupo + '</det>')
    if two_items:
        det += ('<det nItem="2"><prod><NCM>10019010</NCM><CFOP>5102</CFOP>'
                '<qCom>1</qCom><vProd>0.00</vProd></prod>' + grupo + '</det>')
    nfe = ('<NFe><infNFe Id="NFe' + ('1' * 44) + '" versao="4.00">'
           '<ide><tpNF>1</tpNF></ide>'
           '<emit><CNPJ>11111111000111</CNPJ><enderEmit><UF>PA</UF></enderEmit></emit>'
           '<dest><CNPJ>22222222000122</CNPJ><enderDest><UF>PA</UF></enderDest></dest>'
           + det + '<total><ICMSTot><vNF>1499.00</vNF></ICMSTot></total>'
           '</infNFe></NFe>')
    if raiz == 'NFe':
        return nfe.replace('<NFe>', '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">', 1).encode()
    return ('<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">'
            + nfe + '</nfeProc>').encode()


def _resultado(valor='1499.00'):
    return {
        'empresa_id': 21,
        'dados_fiscais': {
            'chave_nfe': '1' * 44, 'valor_total_nota': valor,
            'uf_emit': 'PA', 'uf_dest': 'PA', 'cnpj_emitente': '11111111000111',
            'icms_st': None,
        },
        'insights': {'documental': [], 'empresarial': None},
        'oportunidades': [], 'creditos_detectados': [],
        'previsao_recuperacao': {'potencial_recuperacao_nota': None},
        'context_flags': {
            'documental': {'dados_incompletos': True},
            'empresarial': {'dados_incompletos': True},
        },
    }


@pytest.mark.parametrize('st,two_items,expected_st', [
    (False, False, True), (True, False, False),
    (False, True, True), (True, True, False),
])
def test_cobertura_preserva_observacao_nao_afirma_credito(st, two_items, expected_st):
    xml = _xml(st=st, two_items=two_items)
    original = _resultado()
    backup = deepcopy(original)
    assert avaliar_cobertura_nfe_documental(xml, original, empresa_id=21) == {
        'documental_suficiente': True,
        'empresarial_completo': False,
        'st_nao_destacado_observado': expected_st,
    }
    assert original == backup
    assert elegivel(original, empresa_id=21) == {'eligible': False}


def test_raiz_nfe_unica_aceite_sem_diferenciar_regime():
    assert avaliar_cobertura_nfe_documental(_xml(raiz='NFe'), _resultado(), empresa_id=21)['documental_suficiente'] is True


@pytest.mark.parametrize('modificar', [
    lambda r: r.update(empresa_id=22),
    lambda r: r['dados_fiscais'].update(chave_nfe='2' * 44),
    lambda r: r['dados_fiscais'].update(uf_emit='SP'),
    lambda r: r['dados_fiscais'].update(uf_dest='SP'),
    lambda r: r['dados_fiscais'].update(cnpj_emitente='22222222000122'),
    lambda r: r['dados_fiscais'].update(valor_total_nota='1499.01'),
    lambda r: r['dados_fiscais'].update(valor_total_nota=None),
    lambda r: r['dados_fiscais'].update(erro='Falha do parser'),
    lambda r: r.update(insights=None),
    lambda r: r['insights'].update(documental=None),
    lambda r: r.update(previsao_recuperacao=None),
])
def test_cobertura_fechada_para_divergencias(modificar):
    r = _resultado()
    modificar(r)
    assert avaliar_cobertura_nfe_documental(_xml(), r, empresa_id=21) == {
        'documental_suficiente': False,
        'empresarial_completo': False,
        'st_nao_destacado_observado': False,
    }


@pytest.mark.parametrize('xml', [
    b'<NFe>', b'', b'<root/>',
    b'<!DOCTYPE nfeProc [<!ENTITY x "x">]><nfeProc>&x;</nfeProc>',
    _xml(tax=False),
    _xml().replace(b'<total>', b'<totali>', 1),
    _xml().replace(b'<CNPJ>11111111000111</CNPJ>', b'<CNPJ>11111</CNPJ>', 1),
    _xml().replace(b'<NFe>', b'<other>', 1),
])
def test_xml_malformado_ou_incompleto_nao_tem_cobertura(xml):
    assert avaliar_cobertura_nfe_documental(xml, _resultado(), empresa_id=21)['documental_suficiente'] is False


@pytest.mark.parametrize('value', ['1499.00', '0.00', '12.3', '5', 1499, 1499.0, 0])
def test_montante_exato_normaliza_copia_de_politica(value):
    original = _resultado(value)
    original['context_flags']['documental']['dados_incompletos'] = False
    original['context_flags']['empresarial']['dados_incompletos'] = False
    backup = deepcopy(original)
    normalizado = normalizar(original)
    assert normalizado is not original
    assert original == backup
    assert type(normalizado['dados_fiscais']['valor_total_nota']) is float
    assert normalizado['dados_fiscais']['valor_total_nota'] == float(value)
    assert elegivel(normalizado, empresa_id=21) == {'eligible': True}
    normalizado['context_flags']['documental']['dados_incompletos'] = True
    assert original == backup


@pytest.mark.parametrize('valor', [
    True, False, None, [], {}, Decimal('1.00'),
    '-0.01', '-1', '', ' ', ' 1.00', '1.00 ', '1e3',
    '1,00', '1.000,00', '1_000', '+1.00', 'NaN', 'Infinity',
    '100.001', '100.000', 0.001, float('nan'), float('inf'), -2,
    '999999999999999999999999.99', '10000000000000.00',
])
def test_valores_ambiguos_ou_excessivos_nao_convertidos(valor):
    original = _resultado(valor)
    backup = deepcopy(original)
    assert normalizar(original) is None
    assert original == backup


def test_normalizador_nao_ignora_dados_incompletos_nem_empresa_divergente():
    original = _resultado()
    convertido = normalizar(original)
    assert convertido['context_flags'] == original['context_flags']
    assert elegivel(convertido, empresa_id=21) == {'eligible': False}
    convertido['context_flags']['documental']['dados_incompletos'] = False
    convertido['context_flags']['empresarial']['dados_incompletos'] = False
    assert elegivel(convertido, empresa_id=22) == {'eligible': False}
    assert original['context_flags']['documental']['dados_incompletos'] is True


@pytest.mark.parametrize('obj', [None, [], '1499.00', {'dados_fiscais': None}, {}])
def test_payload_sem_forma_documental_falha_fechado(obj):
    assert normalizar(obj) is None
