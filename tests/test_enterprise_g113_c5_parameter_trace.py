"""G1.13-C5: pure bridge tests + isolated *actual G12* instrumentation smoke.
No DB connection, official source, client XML, checkout, production or deployment.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
import hashlib
import importlib.util
import sys
import types
import unittest
from unittest.mock import patch

from tools.enterprise_g113_c5_parameter_trace import (
    cotejar_rastro_parametros_g113_c5, G113C5EvidenceError, SCHEMA,
)

SHA = 'a'*64
XML_HASH = 'b'*64
URL = 'https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/101202501245.pdf'
SOURCE = 'RESOLUCAO SINTETICA DE TESTE'

def sample():
    trace = dict(
        versao=1,mva_fracao_utilizada='0.4678',aliquota_fracao_utilizada='0.18',
        fonte_legal_consultada=SOURCE,url_fonte_consultada=URL,
        nivel_confianca_registro='oficial',vprod_xml='100.00',icms_proprio_xml='18.00',
        base_st_motor='146.78',icms_st_motor='8.42',metodo_base='iva_st',
        identidade_registo_normativo_comprovada=False,regra_adr020_comprovada=False,
        autoridade_fiscal=False,credito_confirmado=False)
    g12 = dict(schema_version='SOLVERIS_ENTERPRISE_G12_ST_ITEM_READONLY_V1',
        xml_sha256=XML_HASH,itens_total=1,
        itens=[dict(indice_item=1,estado='SIMULACAO_CONDICIONAL_MVA',metodo_base='iva_st',
                    comparacao_condicional=True,fonte_original_autenticada=False,
                    ncm='12119090',rastro_parametros_g12_v1=trace)],
        autoridade_fiscal=False,credito_confirmado=False,
        checkout_autorizado=False,usavel_comercialmente=False)
    g13 = dict(empresa_id=8,relatorio_id=7,documento_id=6,xml_sha256=XML_HASH,
        confronto_condicional_g12=g12,autoridade_fiscal=False,credito_confirmado=False,
        checkout_autorizado=False,usavel_comercialmente=False)
    c3 = dict(schema_version='SOLVERIS_ENTERPRISE_G113_C3_TEMPORAL_MVA_EVIDENCE_V1',
        estado='CANDIDATO_TEMPORAL_OBSERVADO_SEM_AUTORIDADE',indice_item=1,
        verificacao_pdf_pagina_excerto=True,pdf_sha256=SHA,excerto_sha256='c'*64,
        uf='PR',ncm='12119090',cest='2000100',data_operacao_declarada='2026-04-01',
        versao_selecionada='nova',mva_original_percentual_observada='46.78',
        autoridade_fiscal=False,credito_confirmado=False,
        checkout_autorizado=False,usavel_comercialmente=False)
    c4 = dict(schema_version='SOLVERIS_ENTERPRISE_G113_C4_FISCAL_ITEM_BRIDGE_V1',
        estado='CONFRONTO_NUMERICO_E_MVA_CANDIDATA_SEM_PONTE_CAUSAL',
        indice_item=1,documento_id=6,empresa_id=8,relatorio_id=7,xml_sha256=XML_HASH,
        chave_nfe='1'*44,data_operacao='2026-04-01',uf='PR',ncm='12119090',cest='2000100',
        mva_observada_c3='46.78',versao_c3='nova',pdf_sha256=SHA,excerto_sha256='c'*64,
        fonte_mva_motor_g12_demonstrada=False,
        comparacao_g1={'BASE_ST':{'valor_motor_g12':'146.78'},
                       'ICMS_ST':{'valor_motor_g12':'8.42'}},
        autoridade_fiscal=False,credito_confirmado=False,
        checkout_autorizado=False,usavel_comercialmente=False)
    g14 = dict(indice_item=1,estado='COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST',
        sha256_texto_normativo_declarado=SHA,uf_operacao='PR',
        ncm='12119090',cest_observado='2000100',fonte_legal_candidata=SOURCE)
    return dict(c4_result=c4,c3_result=c3,g13_result=g13,g14_item=g14,indice_item=1)

class C5BridgeTests(unittest.TestCase):
    def setUp(self):self.a = sample()
    def run_bridge(self):return cotejar_rastro_parametros_g113_c5(**self.a)
    def reject(self, code=None):
        with self.assertRaises(G113C5EvidenceError) as caught:self.run_bridge()
        if code:self.assertIn(code,str(caught.exception))
    def test_01_matching_actual_parameter_values_remain_non_authoritative(self):
        x=self.run_bridge()
        self.assertEqual(x['schema_version'], SCHEMA)
        self.assertEqual(x['estado'],'MVA_USADA_COINCIDE_COM_CANDIDATO_DOCUMENTAL_SEM_AUTORIDADE')
        self.assertEqual(x['mva_motor_percentual'],'46.7800')
        self.assertTrue(x['parametros_motor_cotejados'])
        self.assertFalse(x['autoridade_fiscal'])
        self.assertFalse(x['credito_confirmado'])
    def test_02_legacy_g12_trace_missing_abstains(self):
        self.a['g13_result']['confronto_condicional_g12']['itens'][0].pop('rastro_parametros_g12_v1')
        x=self.run_bridge()
        self.assertEqual(x['estado'],'ABSTENCAO_G12_SEM_RASTRO_DE_EXECUCAO')
        self.assertFalse(x['parametros_motor_cotejados'])
    def test_03_difference_detected_not_tax_credit(self):
        t=self.a['g13_result']['confronto_condicional_g12']['itens'][0]['rastro_parametros_g12_v1']
        t['mva_fracao_utilizada']='0.4142';t['base_st_motor']='141.42';t['icms_st_motor']='7.46'
        self.a['c4_result']['comparacao_g1']['BASE_ST']['valor_motor_g12']='141.42'
        self.a['c4_result']['comparacao_g1']['ICMS_ST']['valor_motor_g12']='7.46'
        x=self.run_bridge()
        self.assertEqual(x['estado'],'DIVERGENCIA_MVA_USADA_VS_CANDIDATA_SEM_DECISAO_FISCAL')
        self.assertEqual(x['diferencial_mva_pontos_percentuais'],'-5.3600')
        self.assertFalse(x['credito_recuperavel_demonstrado'])
    def test_04_xml_mismatch(self):self.a['g13_result']['xml_sha256']='0'*64;self.reject('G13_IDENTIDADE')
    def test_05_c4_forced_authority(self):self.a['c4_result']['credito_confirmado']=True;self.reject('C4_INVALIDO')
    def test_06_g13_forced_checkout(self):self.a['g13_result']['checkout_autorizado']=True;self.reject('G13_IDENTIDADE')
    def test_07_c3_changed_pdf_hash(self):self.a['c3_result']['pdf_sha256']='f'*64;self.reject('C3_CANDIDATO')
    def test_08_c3_changed_excerpt_hash(self):self.a['c3_result']['excerto_sha256']='f'*64;self.reject('C3_CANDIDATO')
    def test_09_c3_changed_day(self):self.a['c3_result']['data_operacao_declarada']='2026-04-02';self.reject('C3_CANDIDATO')
    def test_10_c3_wrong_uf(self):self.a['c3_result']['uf']='PA';self.reject('C3_CANDIDATO')
    def test_11_c3_wrong_ncm(self):self.a['c3_result']['ncm']='99999999';self.reject('C3_CANDIDATO')
    def test_12_c3_wrong_cest(self):self.a['c3_result']['cest']='9999999';self.reject('C3_CANDIDATO')
    def test_13_g14_pdf_different(self):self.a['g14_item']['sha256_texto_normativo_declarado']='f'*64;self.reject('G14_IDENTIDADE')
    def test_14_missing_comparison(self):self.a['c4_result']['comparacao_g1']=None;self.reject('C4_PARES')
    def test_15_partial_item(self):self.a['c4_result']['estado']='ABSTENCAO_G1_SEM_PARES_NUMERICOS';self.reject('C4_SEM_COMPARACAO')
    def test_16_unexpected_trace_field(self):
        self.a['g13_result']['confronto_condicional_g12']['itens'][0]['rastro_parametros_g12_v1']['elevated']=True;self.reject('RASTRO_FORMA')
    def test_17_trace_claims_authority(self):
        self.a['g13_result']['confronto_condicional_g12']['itens'][0]['rastro_parametros_g12_v1']['autoridade_fiscal']=True;self.reject('RASTRO_AUTORIDADE')
    def test_18_trace_claims_adr020_id(self):
        self.a['g13_result']['confronto_condicional_g12']['itens'][0]['rastro_parametros_g12_v1']['regra_adr020_comprovada']=True;self.reject('RASTRO_AUTORIDADE')
    def test_19_invalid_rule_source(self):
        self.a['g14_item']['fonte_legal_candidata']='OTHER';self.reject('RASTRO_FONTE')
    def test_20_wrong_mva_format(self):
        self.a['g13_result']['confronto_condicional_g12']['itens'][0]['rastro_parametros_g12_v1']['mva_fracao_utilizada']='1e500';self.reject('NUMERO_NAO_CANONICO')
    def test_21_wrong_aliquota(self):
        self.a['g13_result']['confronto_condicional_g12']['itens'][0]['rastro_parametros_g12_v1']['aliquota_fracao_utilizada']='1.5';self.reject('RASTRO_PARAMETROS')
    def test_22_base_mismatch(self):
        self.a['g13_result']['confronto_condicional_g12']['itens'][0]['rastro_parametros_g12_v1']['base_st_motor']='100.00';self.reject('RASTRO_MONTANTES')
    def test_23_arithmetic_mismatch(self):
        self.a['g13_result']['confronto_condicional_g12']['itens'][0]['rastro_parametros_g12_v1']['vprod_xml']='200.00';self.reject('RASTRO_ARITMETICA')
    def test_24_icms_st_mismatch(self):
        self.a['g13_result']['confronto_condicional_g12']['itens'][0]['rastro_parametros_g12_v1']['icms_st_motor']='9.00';self.reject('RASTRO_MONTANTES')
    def test_25_disallowed_http_source(self):
        self.a['g13_result']['confronto_condicional_g12']['itens'][0]['rastro_parametros_g12_v1']['url_fonte_consultada']='http://example.com';self.reject('RASTRO_URL')
    def test_26_no_g12_mutation(self):
        original=deepcopy(self.a)
        self.run_bridge()
        self.assertEqual(self.a,original)

class C5RealG12InstrumentationTests(unittest.TestCase):
    """Actual checked-out G12 implementation loaded against isolated stubs."""
    @staticmethod
    def engine(authorized=True):
        # No real app imports; all external engine calls are faked.
        repo=Path(__file__).resolve().parents[1]
        original=(repo/'app/services/enterprise_g12_st_item_reconciliation.py').read_text(encoding='utf-8-sig')
        if "info['rastro_parametros_g12_v1']" not in original:
            raise AssertionError('G12_TRACE_NOT_INSTALLED')
        names=['app','app.services','app.motor_fiscal','app.services.fiscal_utils',
            'app.services.tabela_normativa_service','app.services.tax_consistency',
            'app.services.tax_consistency.tax_consistency_engine','app.xml_service']
        stub={n:types.ModuleType(n) for n in names}
        for n in ('app','app.services','app.services.tax_consistency'):
            stub[n].__path__=[]
        class MotorFiscal:
            @staticmethod
            def calcular_base_st(x,m):return round(x*(1+m/100),2)
            @staticmethod
            def calcular_icms_st(base,ali,icms):return max(0,round(base*ali/100-icms,2))
        stub['app.motor_fiscal'].MotorFiscal=MotorFiscal
        stub['app.services.fiscal_utils'].resolver_aliquota_e_mva=lambda *a,**kw: dict(
            calculo_autorizado=authorized,calculo_parcial=False,mva_autorizada=True,
            aliquota_autorizada=True,confianca='oficial',aliquota=0.18,mva=46.78)
        source=SOURCE
        stub['app.services.tabela_normativa_service'].buscar_mva=lambda *a,**kw: dict(
            mva=46.78,aliquota_interna=0.18,vigencia_inicio=date(2026,4,1),
            vigencia_fim=None,fonte_legal=source,nivel_confianca_fonte='oficial',url_fonte=URL)
        stub['app.services.tabela_normativa_service'].resolver_base_calculo_st=lambda *a,**kw: dict(
            base_calculo=146.78,metodo='iva_st',confianca='oficial',fonte_legal=source,aliquota_interna=0.18)
        class TaxConsistencyEngine:
            def verificar_consistencia(self,*args,**kwargs):return dict(consistente=None,autoridade_fiscal=False,credito_confirmado=False,checkout_autorizado=False)
        stub['app.services.tax_consistency.tax_consistency_engine'].TaxConsistencyEngine=TaxConsistencyEngine
        stub['app.xml_service'].ler_xml_unico=lambda *a,**kw: dict(
            chave_nfe='1'*44,uf_emit='PR',uf_dest='PR',itens=[dict(
                ncm='12119090',cfop='5102',st_observado_xml=True,base_st='146.78',valor_st='8.42')])
        with patch.dict(sys.modules, stub):
            spec=importlib.util.spec_from_file_location('_g113c5_isolated_g12',repo/'app/services/enterprise_g12_st_item_reconciliation.py')
            mod=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        return mod
    @staticmethod
    def xml():
        key='1'*44
        return (f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
        f'<infNFe Id="NFe{key}"><ide><mod>55</mod><tpNF>1</tpNF><finNFe>1</finNFe>'
        f'<idDest>1</idDest><dhEmi>2026-04-01T10:00:00-03:00</dhEmi></ide>'
        f'<emit><enderEmit><UF>PR</UF></enderEmit></emit>'
        f'<dest><enderDest><UF>PR</UF></enderDest></dest>'
        f'<det nItem="1"><prod><NCM>12119090</NCM><CEST>2000100</CEST>'
        f'<CFOP>5102</CFOP><vProd>100.00</vProd></prod>'
        f'<imposto><ICMS><ICMS10><CST>10</CST><modBCST>4</modBCST>'
        f'<vICMS>18.00</vICMS><vBC>100.00</vBC><pICMS>18.00</pICMS>'
        f'<vBCST>146.78</vBCST><vICMSST>8.42</vICMSST>'
        f'</ICMS10></ICMS></imposto></det></infNFe></NFe>').encode()
    def test_27_actual_g12_synthetic_trace_fields(self):
        m=self.engine();r=m.confrontar_st_por_item_g12(db=object(),xml_bytes=self.xml())
        self.assertEqual(r['itens_simulados'],1)
        tr=r['itens'][0]['rastro_parametros_g12_v1']
        self.assertEqual(tr['mva_fracao_utilizada'],'0.4678')
        self.assertEqual(tr['base_st_motor'],'146.78')
        self.assertEqual(tr['icms_st_motor'],'8.42')
        self.assertEqual(tr['aliquota_fracao_utilizada'],'0.18')
        self.assertEqual(tr['fonte_legal_consultada'],SOURCE)
        self.assertFalse(tr['autoridade_fiscal'])
    def test_28_actual_g12_disabled_rule_no_trace(self):
        m=self.engine(authorized=False);r=m.confrontar_st_por_item_g12(db=object(),xml_bytes=self.xml())
        self.assertEqual(r['itens_simulados'],0)
        self.assertNotIn('rastro_parametros_g12_v1',r['itens'][0])
    def test_29_actual_g12_xml_digest_preserved(self):
        m=self.engine();raw=self.xml();r=m.confrontar_st_por_item_g12(db=object(),xml_bytes=raw)
        self.assertEqual(r['xml_sha256'],hashlib.sha256(raw).hexdigest())
    def test_30_actual_g12_flags_not_escalated(self):
        m=self.engine();r=m.confrontar_st_por_item_g12(db=object(),xml_bytes=self.xml())
        for key in ('autoridade_fiscal','credito_confirmado','checkout_autorizado','usavel_comercialmente'):
            self.assertIs(r[key],False)
    def test_31_trace_never_claims_persisted_normative_id(self):
        tr=self.engine().confrontar_st_por_item_g12(db=object(),xml_bytes=self.xml())['itens'][0]['rastro_parametros_g12_v1']
        self.assertFalse(tr['identidade_registo_normativo_comprovada'])
        self.assertFalse(tr['regra_adr020_comprovada'])
    def test_32_trace_source_audit_marker_once(self):
        repo=Path(__file__).resolve().parents[1]
        src=(repo/'app/services/enterprise_g12_st_item_reconciliation.py').read_text(encoding='utf-8-sig')
        self.assertEqual(src.count("info['rastro_parametros_g12_v1'] = {"),1)
        self.assertLess(src.index("info['rastro_parametros_g12_v1'] = {"),src.index("info['estado'] = 'SIMULACAO_CONDICIONAL_MVA'"))

if __name__ == '__main__':unittest.main(verbosity=2)
