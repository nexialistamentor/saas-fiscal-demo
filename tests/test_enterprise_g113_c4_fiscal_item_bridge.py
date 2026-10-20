"""C4 synthetic scope tests. No DB, no HTTP, no SEFAZ and no commercial tax proof."""
import copy
import hashlib
import unittest
from tools.enterprise_g113_c4_fiscal_item_bridge import (
    cotejar_item_evidencia_calculo_g113_c4 as run, G113C4EvidenceError, SCHEMA,
)

KEY='1'*44
PDF='a'*64
EXCERPT='b'*64
XML=('''<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe'''+KEY+'''">
<ide><mod>55</mod><tpNF>1</tpNF><finNFe>1</finNFe><idDest>1</idDest><dhEmi>2026-04-01T10:00:00-03:00</dhEmi></ide>
<emit><enderEmit><UF>PR</UF></enderEmit></emit><dest><enderDest><UF>PR</UF></enderDest></dest>
<det nItem="1"><prod><NCM>12119090</NCM><CEST>2000100</CEST><CFOP>5102</CFOP><vProd>100.00</vProd></prod>
<imposto><ICMS><ICMS10><CST>10</CST><modBCST>4</modBCST><vBCST>146.78</vBCST><vICMSST>8.42</vICMSST></ICMS10></ICMS></imposto>
</det></infNFe></NFe>''').encode()
DIGEST=hashlib.sha256(XML).hexdigest()


def fixture():
    comp=[{'indice_item':1,'tipo':'BASE_ST','valor_xml':'146.78','valor_motor':'146.78',
           'divergencia_numerica':False,'prova_normativa':False},
          {'indice_item':1,'tipo':'ICMS_ST','valor_xml':'8.42','valor_motor':'8.50',
           'divergencia_numerica':True,'prova_normativa':False}]
    g1={'estado':'COMPARACAO_NUMERICA_SEM_AUTORIDADE','consistente':None,
        'comparacoes':comp,'autoridade_fiscal':False,'credito_confirmado':False,
        'checkout_autorizado':False,'usavel_comercialmente':False}
    g12={'schema_version':'SOLVERIS_ENTERPRISE_G12_ST_ITEM_READONLY_V1','xml_sha256':DIGEST,
         'itens_total':1,'itens':[{'indice_item':1,'ncm':'12119090','cfop':'5102',
          'competencia':'2026-04','comparacao_condicional':True,'estado':'SIMULACAO_CONDICIONAL_MVA',
          'metodo_base':'iva_st','fonte_original_autenticada':False}],
         'confronto_g1':g1,'icms_proprio_recalculado_por_fonte_independente':False,
         'autoridade_fiscal':False,'credito_confirmado':False,'checkout_autorizado':False,
         'usavel_comercialmente':False}
    g13={'schema_version':'SOLVERIS_ENTERPRISE_G13_SUBJECT_ST_ITEM_BRIDGE_V1',
         'posse_e_proveniencia_interna_i2':True,'chave_nfe':KEY,'empresa_id':8,
         'relatorio_id':7,'documento_id':6,'xml_sha256':DIGEST,'competencia_declarada':'2026-04',
         'confronto_condicional_g12':g12,'autoridade_fiscal':False,'credito_confirmado':False,
         'checkout_autorizado':False,'usavel_comercialmente':False}
    g14={'schema_version':'SOLVERIS_ENTERPRISE_G14_OPERATIONAL_NORMATIVE_SCOPE_V1',
         'empresa_id':8,'relatorio_id':7,'documento_id':6,'xml_sha256':DIGEST,
         'posse_e_proveniencia_interna_g13':True,'itens_total':1,
         'itens':[{'indice_item':1,'estado':'COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST',
                   'uf_operacao':'PR','ncm':'12119090','cest_observado':'2000100',
                   'cfop':'5102','cst_observado':'10','competencia_declarada':'2026-04',
                   'sha256_texto_normativo_declarado':PDF}],
         'autoridade_fiscal':False,'credito_confirmado':False,'checkout_autorizado':False,
         'usavel_comercialmente':False}
    c3={'schema_version':'SOLVERIS_ENTERPRISE_G113_C3_TEMPORAL_MVA_EVIDENCE_V1',
         'indice_item':1,'data_operacao_declarada':'2026-04-01',
         'uf':'PR','ncm':'12119090','cest':'2000100',
         'estado':'CANDIDATO_TEMPORAL_OBSERVADO_SEM_AUTORIDADE',
         'verificacao_pdf_pagina_excerto':True,'versao_selecionada':'PR-2026-04-01',
         'mva_original_percentual_observada':'46.78','pdf_sha256':PDF,'excerto_sha256':EXCERPT,
         'prova_nf_e_real':False,'prova_adr020_regra_persistida':False,
         'autoridade_fiscal':False,'credito_confirmado':False,'checkout_autorizado':False,
         'usavel_comercialmente':False}
    return dict(xml_bytes=XML,authenticated_user_id=9,empresa_id=8,relatorio_id=7,
                indice_item=1,g13_result=g13,g14_result=g14,c3_result=c3)


class C4Tests(unittest.TestCase):
    def setUp(self):self.a=fixture()
    def call(self):return run(**self.a)
    def deny(self,code):
        with self.assertRaisesRegex(G113C4EvidenceError,code):self.call()
    def test_01_join_is_non_authoritative(self):
        r=self.call();self.assertEqual(r['schema_version'],SCHEMA)
        self.assertEqual(r['estado'],'CONFRONTO_NUMERICO_E_MVA_CANDIDATA_SEM_PONTE_CAUSAL')
        self.assertEqual(r['mva_observada_c3'],'46.78')
        for name in ('fonte_mva_motor_g12_demonstrada','prova_semantica_regra_st',
                     'autoridade_fiscal','credito_confirmado','checkout_autorizado',
                     'credito_recuperavel_demonstrado','usavel_comercialmente'):
            self.assertIs(r[name],False)
    def test_02_g1_numeric_pair_is_merely_observed(self):
        r=self.call();self.assertEqual(r['comparacao_g1']['ICMS_ST']['diferenca_motor_menos_xml'],'0.08')
        self.assertFalse(r['comparacao_g1']['BASE_ST']['divergencia_numerica'])
    def test_03_c3_temporal_abstention(self):
        c=self.a['c3_result'];c.update(estado='ABSTENCAO_TEMPORAL',motivo='SEM_JANELA_DOCUMENTAL_COTEJADA',versao_selecionada=None,mva_original_percentual_observada=None)
        r=self.call();self.assertEqual(r['estado'],'ABSTENCAO_NORMATIVA_TEMPORAL');self.assertIsNone(r['comparacao_g1'])
    def test_04_abstention_with_selected_value_forbidden(self):
        self.a['c3_result']['estado']='ABSTENCAO_TEMPORAL';self.deny('C3_ABSTENCAO_INCOERENTE')
    def test_05_c3_wrong_date(self):
        self.a['c3_result']['data_operacao_declarada']='2026-03-31';self.deny('C3_IDENTIDADE')
    def test_06_c3_wrong_uf(self):
        self.a['c3_result']['uf']='PA';self.deny('C3_IDENTIDADE')
    def test_07_c3_wrong_ncm(self):
        self.a['c3_result']['ncm']='00000000';self.deny('C3_IDENTIDADE')
    def test_08_c3_wrong_cest(self):
        self.a['c3_result']['cest']='0000000';self.deny('C3_IDENTIDADE')
    def test_09_pdf_hash_not_equal_g14(self):
        self.a['g14_result']['itens'][0]['sha256_texto_normativo_declarado']='0'*64;self.deny('C3_CANDIDATO')
    def test_10_g13_xml_hash(self):
        self.a['g13_result']['xml_sha256']='0'*64;self.deny('G13_SUJEITO')
    def test_11_g13_foreign_document(self):
        self.a['g14_result']['documento_id']=2;self.deny('G14_IDENTIDADE')
    def test_12_g13_foreign_company(self):
        self.a['g13_result']['empresa_id']=100;self.deny('G13_SUJEITO')
    def test_13_g13_nonmatching_key(self):
        self.a['g13_result']['chave_nfe']='2'*44;self.deny('G13_SUJEITO')
    def test_14_g13_forged_authority(self):
        self.a['g13_result']['autoridade_fiscal']=True;self.deny('G13_SUJEITO')
    def test_15_g12_forged_credit(self):
        self.a['g13_result']['confronto_condicional_g12']['credito_confirmado']=True;self.deny('G12_IDENTIDADE')
    def test_16_g12_wrong_hash(self):
        self.a['g13_result']['confronto_condicional_g12']['xml_sha256']='0'*64;self.deny('G12_IDENTIDADE')
    def test_17_g12_wrong_item_ncm(self):
        self.a['g13_result']['confronto_condicional_g12']['itens'][0]['ncm']='22222222';self.deny('G12_ITEM')
    def test_18_g14_wrong_item_cest(self):
        self.a['g14_result']['itens'][0]['cest_observado']='0000000';self.deny('G14_CLASSIFICACAO')
    def test_19_g14_incomplete_candidacy(self):
        self.a['g14_result']['itens'][0]['estado']='LACUNA';self.deny('G14_CLASSIFICACAO')
    def test_20_g1_declares_consistency(self):
        self.a['g13_result']['confronto_condicional_g12']['confronto_g1']['consistente']=True
        self.assertEqual(self.call()['estado'],'ABSTENCAO_G1_SEM_PARES_NUMERICOS')
    def test_21_g1_wrong_xml_amount(self):
        self.a['g13_result']['confronto_condicional_g12']['confronto_g1']['comparacoes'][1]['valor_xml']='8.50';self.deny('CONFRONTO_G1')
    def test_22_g1_wrong_divergence_flag(self):
        self.a['g13_result']['confronto_condicional_g12']['confronto_g1']['comparacoes'][1]['divergencia_numerica']=False;self.deny('CONFRONTO_G1')
    def test_23_g1_duplicate_numeric_kind(self):
        self.a['g13_result']['confronto_condicional_g12']['confronto_g1']['comparacoes'][1]['tipo']='BASE_ST'
        self.assertEqual(self.call()['estado'],'ABSTENCAO_G1_SEM_PARES_NUMERICOS')
    def test_24_g1_missing_comparison(self):
        self.a['g13_result']['confronto_condicional_g12']['confronto_g1']['comparacoes']=[]
        self.assertEqual(self.call()['estado'],'ABSTENCAO_G1_SEM_PARES_NUMERICOS')
    def test_25_g12_not_simulated(self):
        self.a['g13_result']['confronto_condicional_g12']['itens'][0]['comparacao_condicional']=False
        self.assertEqual(self.call()['estado'],'ABSTENCAO_G12_SEM_SIMULACAO_ITEM')
    def test_26_wrong_xml_cest(self):
        self.a['xml_bytes']=XML.replace(b'<CEST>2000100</CEST>',b'<CEST>9000000</CEST>')
        self.deny('G13_SUJEITO')
    def test_27_xml_entity_forbidden(self):
        self.a['xml_bytes']=b'<!DOCTYPE x [<!ENTITY boom "BAD">]>'+XML
        self.deny('XML_NAO_SEGURO')
    def test_28_xml_wrong_protocol_operation(self):
        self.a['xml_bytes']=XML.replace(b'<idDest>1</idDest>',b'<idDest>2</idDest>')
        self.deny('OPERACAO_NAO_SUPORTADA')
    def test_29_c3_forged_invoice_proof(self):
        self.a['c3_result']['prova_nf_e_real']=True;self.deny('C3_IDENTIDADE')
    def test_30_c3_forged_mva(self):
        self.a['c3_result']['mva_original_percentual_observada']='garbage';self.deny('C3_MVA_INVALIDA')
    def test_31_missing_icms_st_xml(self):
        self.a['xml_bytes']=XML.replace(b'<vICMSST>8.42</vICMSST>',b'')
        self.deny('VALOR_MONETARIO_INVALIDO')
    def test_32_g1_forged_normative_proof(self):
        self.a['g13_result']['confronto_condicional_g12']['confronto_g1']['comparacoes'][0]['prova_normativa']=True
        self.deny('CONFRONTO_G1')

if __name__=='__main__': unittest.main(verbosity=2)
