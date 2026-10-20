"""C7 synthetic dossier tests. Not a customer document, SEFAZ call or real ADR-020 binding."""
from __future__ import annotations
from copy import deepcopy
import unittest

from tools.enterprise_g113_c7_diagnostic_dossier import (
    preparar_dossie_investigativo_g113_c7, G113C7GateError, SCHEMA,
)

SHA='a'*64
XML='b'*64
EXCERPT='c'*64
DENIED={k:False for k in ('autoridade_fiscal','credito_confirmado','checkout_autorizado','usavel_comercialmente')}

def fixture():
    c3=dict(schema_version='SOLVERIS_ENTERPRISE_G113_C3_TEMPORAL_MVA_EVIDENCE_V1',
        estado='CANDIDATO_TEMPORAL_OBSERVADO_SEM_AUTORIDADE',indice_item=1,
        verificacao_pdf_pagina_excerto=True,pdf_sha256=SHA,excerto_sha256=EXCERPT,
        uf='PR',ncm='12119090',cest='2000100',data_operacao_declarada='2026-04-01',
        versao_selecionada='new',mva_original_percentual_observada='46.78',**DENIED)
    pairbase=dict(valor_xml='145.00',valor_motor_g12='146.78',
        diferenca_motor_menos_xml='1.78',divergencia_numerica=True,prova_normativa=False)
    pairst=dict(valor_xml='8.00',valor_motor_g12='8.42',
        diferenca_motor_menos_xml='0.42',divergencia_numerica=True,prova_normativa=False)
    c4=dict(schema_version='SOLVERIS_ENTERPRISE_G113_C4_FISCAL_ITEM_BRIDGE_V1',
        estado='CONFRONTO_NUMERICO_E_MVA_CANDIDATA_SEM_PONTE_CAUSAL',indice_item=1,
        documento_id=6,empresa_id=8,relatorio_id=7,xml_sha256=XML,chave_nfe='1'*44,
        data_operacao='2026-04-01',uf='PR',ncm='12119090',cest='2000100',
        versao_c3='new',mva_observada_c3='46.78',pdf_sha256=SHA,excerto_sha256=EXCERPT,
        comparacao_g1={'BASE_ST':pairbase,'ICMS_ST':pairst},**DENIED)
    c5=dict(schema_version='SOLVERIS_ENTERPRISE_G113_C5_PARAMETER_TRACE_V1',
        estado='MVA_USADA_COINCIDE_COM_CANDIDATO_DOCUMENTAL_SEM_AUTORIDADE',
        indice_item=1,documento_id=6,xml_sha256=XML,chave_nfe='1'*44,
        versao_documental_c3='new',mva_c3_percentual_observada='46.78',
        parametros_motor_cotejados=True,mva_motor_percentual='46.7800',
        diferencial_mva_pontos_percentuais='0.0000',aliquota_motor_percentual='18.00',
        base_st_motor='146.78',icms_st_motor='8.42',**DENIED)
    c6=dict(schema_version='SOLVERIS_ENTERPRISE_G113_C6_L2_RECORD_PROVENANCE_V1',
        estado='REGISTO_L2_IDENTIFICADO_SEM_UNICIDADE_OU_ADR020',
        indice_item=1,documento_id=6,xml_sha256=XML,uf='PR',ncm='12119090',cest='2000100',
        identificador_registo_l2_observado=92,unicidade_registos_vigentes_comprovada=False,
        vinculo_adr020_comprovado=False,correspondencia_cest_l2_comprovada=False,
        mva_motor_percentual='46.7800',aliquota_motor_percentual='18.00',**DENIED)
    return dict(c3_result=c3,c4_result=c4,c5_result=c5,c6_result=c6,indice_item=1)

def c1():
    return dict(schema_version='SOLVERIS_ENTERPRISE_G113_EXACT_PAGE_RULE_ITEM_V1',
        estado='EXCERTO_LOCALIZADO_REGRA_E_ITEM_COTEJADOS_SEM_AUTORIDADE',
        indice_item=1,documento_id=6,xml_sha256=XML,pdf_sha256=SHA,
        excerto_sha256=EXCERPT,mva_percentual_declarada='46.78',
        aliquota_percentual_declarada='18.00',rule_id='rule1',rule_version=1,
        rule_hash='d'*64,prova_de_relacao_semantica_entre_excerto_e_parametros=False,**DENIED)

class TestC7(unittest.TestCase):
    def setUp(self): self.a=fixture()
    def r(self):return preparar_dossie_investigativo_g113_c7(**self.a)
    def stop(self,s):
        with self.assertRaises(G113C7GateError) as cm:self.r()
        self.assertIn(s,str(cm.exception))
    def test_01_internal_report_and_two_numeric_pairs(self):
        r=self.r();self.assertEqual(r['schema_version'],SCHEMA)
        self.assertEqual(r['estado'],'DOSSIER_INTERNO_NAO_PUBLICAVEL')
        self.assertEqual(r['id_registo_l2_observado'],92)
        self.assertEqual(r['comparacoes_monetarias_condicionais']['ICMS_ST']['diferenca_motor_menos_xml'],'0.42')
        self.assertEqual(r['alerta_investigativo'],'DIVERGENCIA_NUMERICA_A_REVER')
    def test_02_never_claim_credit(self):
        r=self.r()
        for k in (*DENIED,'credito_recuperavel_demonstrado','aplicabilidade_juridica_comprovada','recolhimento_verificado'):
            self.assertIs(r[k],False)
        self.assertTrue(r['resultado_nao_comprova_pagamento_indevido'])
    def test_03_no_c1_explicitly_pending(self):
        r=self.r();self.assertIsNone(r['adr020_c1']);self.assertIn('C1_SEM_CADEIA_DE_EXCERTO_REGRA_EM_EXECUCAO',r['pendencias_para_decisao_fiscal'])
    def test_04_matching_c1_does_not_prove_l2_relation(self):
        self.a['c1_result']=c1();r=self.r();self.assertFalse(r['adr020_c1']['vinculo_entre_registo_l2_e_adr020_comprovado'])
    def test_05_c1_wrong_pdf_stops(self):
        self.a['c1_result']=c1();self.a['c1_result']['pdf_sha256']='f'*64;self.stop('C1_EXCERTO')
    def test_06_c1_wrong_excerpt_stops(self):
        self.a['c1_result']=c1();self.a['c1_result']['excerto_sha256']='f'*64;self.stop('C1_EXCERTO')
    def test_07_c1_invented_aliquota_stops(self):
        self.a['c1_result']=c1();self.a['c1_result']['aliquota_percentual_declarada']='17.00';self.stop('C1_EXCERTO')
    def test_08_c1_fake_semantics_stops(self):
        self.a['c1_result']=c1();self.a['c1_result']['prova_de_relacao_semantica_entre_excerto_e_parametros']=True;self.stop('C1_EXCERTO')
    def test_09_c3_wrong_pdf_stops(self):
        self.a['c3_result']['pdf_sha256']='f'*64;self.stop('PDF_OU_EXCERTO')
    def test_10_c3_wrong_date_stops(self):
        self.a['c3_result']['data_operacao_declarada']='2026-04-02';self.stop('DATA_OPERACAO')
    def test_11_c3_no_window_stops(self):
        self.a['c3_result']['estado']='ABSTENCAO_TEMPORAL';self.stop('SEM_PONTE')
    def test_12_c6_missing_id_stops(self):
        self.a['c6_result']['identificador_registo_l2_observado']=None;self.stop('L2_REGISTO')
    def test_13_c6_cest_authority_forged_stops(self):
        self.a['c6_result']['correspondencia_cest_l2_comprovada']=True;self.stop('L2_REGISTO')
    def test_14_c6_adr020_forged_stops(self):
        self.a['c6_result']['vinculo_adr020_comprovado']=True;self.stop('L2_REGISTO')
    def test_15_c5_mva_mismatch_stops(self):
        self.a['c5_result']['mva_motor_percentual']='46.79';self.stop('MVA_EXECUTADA')
    def test_16_source_classification_mismatch_stops(self):
        self.a['c6_result']['cest']='2000200';self.stop('CLASSIFICACAO')
    def test_17_wrong_xml_hash_stops(self):
        self.a['c6_result']['xml_sha256']='f'*64;self.stop('DOCUMENTO')
    def test_18_wrong_motor_base_amount_stops(self):
        self.a['c4_result']['comparacao_g1']['BASE_ST']['valor_motor_g12']='147.00';self.stop('C5_MONTANTES')
    def test_19_wrong_boolean_divergence_stops(self):
        self.a['c4_result']['comparacao_g1']['ICMS_ST']['divergencia_numerica']=False;self.stop('PAR_G1')
    def test_20_forged_upstream_credit_stops(self):
        self.a['c5_result']['credito_confirmado']=True;self.stop('C5_CONTRATO')
    def test_21_no_mutation(self):
        previous=deepcopy(self.a);self.r();self.assertEqual(self.a,previous)
    def test_22_zero_numeric_difference_not_conformity(self):
        for p in self.a['c4_result']['comparacao_g1'].values():
            p['valor_xml']=p['valor_motor_g12'];p['diferenca_motor_menos_xml']='0.00';p['divergencia_numerica']=False
        r=self.r();self.assertEqual(r['alerta_investigativo'],'COINCIDENCIA_NUMERICA_NAO_PROVA_CONFORMIDADE')
    def test_23_mva_difference_alert_without_credit(self):
        self.a['c5_result']['estado']='DIVERGENCIA_MVA_USADA_VS_CANDIDATA_SEM_DECISAO_FISCAL'
        self.a['c5_result']['mva_motor_percentual']='41.4200'
        self.a['c5_result']['diferencial_mva_pontos_percentuais']='-5.3600'
        self.a['c6_result']['mva_motor_percentual']='41.4200'
        self.assertEqual(self.r()['mva_divergencia_pontos_percentuais'],'-5.3600')
    def test_24_c5_monetary_trace_mismatch_stops(self):
        self.a['c5_result']['base_st_motor']='140.00';self.stop('C5_MONTANTES')
    def test_25_no_calls_to_network_or_db(self):
        import inspect
        from tools import enterprise_g113_c7_diagnostic_dossier as service
        src=inspect.getsource(service)
        for forbidden in ('requests.', 'urllib.request','db.query(', 'session.commit(', 'subprocess.', 'open('):
            self.assertNotIn(forbidden,src)

if __name__=='__main__':unittest.main(verbosity=2)
