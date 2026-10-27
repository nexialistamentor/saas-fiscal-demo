"""B02 synthetic-only, actual adapter and ORM model identities; DB fake GET only.

No network, production DB, client XML, fiscal law certification, writes or payment.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import date
from types import SimpleNamespace as S
import unittest

from app.models import TabelaMVA, RuleVersion, ExtractionResult
from app.services.enterprise_b02_normative_binding import (
    SCHEMA, EnterpriseB02GateError, cotejar_vinculo_normativo_b02 as run,
)

HEX=lambda v:v*64
DENIED={k:False for k in ("autoridade_fiscal","credito_confirmado","checkout_autorizado","usavel_comercialmente")}
DOC_HASH=HEX('a');EXCERPT=HEX('b');XML_HASH=HEX('c');RULE_HASH=HEX('d');RECORD_HASH=HEX('e')
DATE="2026-04-01";ROW_ID=781;IDENT="12119090";CEST="2000100";URL="https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/101201900571.pdf";SRC="SEFA PR DOCUMENTO SINTETICO DE TESTE"

class ReadOnlyDB:
    def __init__(self, rows):
        self.rows=rows
        self.calls=[]
        self.concurrent=[]
    def get(self, typ, pk):
        self.calls.append((typ.__name__,pk))
        return self.rows.get((typ.__name__,pk))
    def add(self,*args):raise AssertionError('WRITE_PROIBIDO')
    def commit(self,*args):raise AssertionError('COMMIT_PROIBIDO')
    def execute(self,*args):raise AssertionError('SQL_PROIBIDO')
    def query(self, typ):
        if typ is not TabelaMVA:raise AssertionError('QUERY_FORA_DE_ESCOPO')
        self.calls.append(('query_bounded',typ.__name__))
        return self
    def filter(self,*args):return self
    def limit(self,n):
        if n!=2:raise AssertionError('QUERY_SEM_LIMIT_2')
        return self
    def all(self):
        if self.concurrent:return self.concurrent
        return [row for (name,_),row in self.rows.items() if name=='TabelaMVA']


def fixture():
    g14=dict(indice_item=1,estado='COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST',
             uf_operacao='PR',ncm=IDENT,cest_observado=CEST,cfop='5102',
             cst_observado='10',regime_empresa='real',competencia_declarada='2026-04',
             url_fonte_candidata=URL,fonte_legal_candidata=SRC,sha256_texto_normativo_declarado=DOC_HASH)
    c4=dict(schema_version='SOLVERIS_ENTERPRISE_G113_C4_FISCAL_ITEM_BRIDGE_V1',
            indice_item=1,documento_id=12,xml_sha256=XML_HASH,data_operacao=DATE,
            uf='PR',ncm=IDENT,cest=CEST,**DENIED)
    c5=dict(schema_version='SOLVERIS_ENTERPRISE_G113_C5_PARAMETER_TRACE_V1',
            indice_item=1,documento_id=12,xml_sha256=XML_HASH,
            mva_motor_percentual='46.78',aliquota_motor_percentual='18.00',**DENIED)
    c6=dict(schema_version='SOLVERIS_ENTERPRISE_G113_C6_L2_RECORD_PROVENANCE_V1',
            indice_item=1,documento_id=12,xml_sha256=XML_HASH,uf='PR',ncm=IDENT,cest=CEST,
            estado='REGISTO_L2_IDENTIFICADO_SEM_UNICIDADE_OU_ADR020',
            identificador_registo_l2_observado=ROW_ID,vinculo_adr020_comprovado=False,
            fonte_legal_declarada=SRC,url_fonte_declarada=URL,
            mva_motor_percentual='46.78',aliquota_motor_percentual='18.00',
            vigencia_inicio_registo='2026-04-01',vigencia_fim_registo=None,**DENIED)
    c3=dict(schema_version='SOLVERIS_ENTERPRISE_G113_C3_TEMPORAL_MVA_EVIDENCE_V1',
            indice_item=1,uf='PR',ncm=IDENT,cest=CEST,estado='CANDIDATO_TEMPORAL_OBSERVADO_SEM_AUTORIDADE',
            verificacao_pdf_pagina_excerto=True,pdf_sha256=DOC_HASH,excerto_sha256=EXCERPT,
            data_operacao_declarada=DATE,mva_original_percentual_observada='46.78',**DENIED)
    c1=dict(schema_version='SOLVERIS_ENTERPRISE_G113_EXACT_PAGE_RULE_ITEM_V1',
            indice_item=1,documento_id=12,xml_sha256=XML_HASH,
            pdf_sha256=DOC_HASH,excerto_sha256=EXCERPT,
            rule_id='r1',rule_version=2,rule_hash=RULE_HASH,
            extraction_result_id='ex1',normative_artifact_id='art1',
            mva_percentual_declarada='46.78',aliquota_percentual_declarada='18.00',
            prova_de_relacao_semantica_entre_excerto_e_parametros=False,
            fonte_primaria_autenticada=False,vigencia_juridica_comprovada=False,**DENIED)
    g16=dict(schema_version='SOLVERIS_ENTERPRISE_G16_TEMPORAL_RULE_CHECKPOINT_V1',
             documento_id=12,xml_sha256=XML_HASH,data_operacao_observada=DATE,itens_total=1,
             itens=[dict(indice_item=1,estado='CADEIA_TEMPORAL_INTERNA_SEM_AUTORIDADE',
                         regra_interna_cotejada=True,rule_id='r1',rule_version=2,rule_hash=RULE_HASH,
                         relacoes_declaradas=[],fonte_oficial_autenticada=False,
                         vigencia_juridica_comprovada=False,cobertura_publicacoes_completa=False,
                         ausencia_revogacao_comprovada=False,excecoes_aplicadas=False)],**DENIED)
    g18=dict(schema_version='SOLVERIS_ENTERPRISE_G18_EXTERNAL_PUBLICATION_HASH_LINK_V1',
             documento_id=12,xml_sha256=XML_HASH,itens_total=1,
             itens=[dict(indice_item=1,vinculo_hash_adr020=True,
                         pdf_bytes_recalculados=True,sha256_publicacao_observado=DOC_HASH,
                         fonte_primaria_autenticada=False,revogacao_historica_comprovada=False,
                         cadeia_icp_brasil_verificada_neste_servico=False,
                         tempo_assinatura_confiavel=False)],**DENIED)
    params=dict(uf='PR',ncm=IDENT,cest=CEST,cfop='5102',cst='10',regime='real',
                operacao='saida_interna',metodo_base='iva_st',vigencia_inicio=DATE,
                vigencia_fim=None,mva_percentual='46.78',aliquota_percentual='18.00')
    row=S(id=ROW_ID,estado='PR',ncm=IDENT,fonte_legal=SRC,url_fonte=URL,
          nivel_confianca_fonte='oficial',vigencia_inicio=date(2026,4,1),vigencia_fim=None,
          mva=46.78,aliquota_interna=.18)
    rule=S(rule_version_record_id='ver2',rule_id='r1',rule_version=2,rule_hash=RULE_HASH,
           record_hash=RECORD_HASH,extraction_result_id='ex1',
           extraction_result_record_hash=HEX('f'),structured_content={'g113_v1':deepcopy(params)})
    extraction=S(extraction_result_id='ex1',record_hash=HEX('f'),artifact_hash=DOC_HASH,
                 normative_artifact_id='art1',outcome='conclusivo',
                 structured_content={'g113_v1':deepcopy(params)})
    db=ReadOnlyDB({('TabelaMVA',ROW_ID):row,('RuleVersion','ver2'):rule,('ExtractionResult','ex1'):extraction})
    return dict(db=db,indice_item=1,rule_version_record_id='ver2',c4_result=c4,c5_result=c5,
                c6_result=c6,c3_result=c3,c1_result=c1,g14_item=g14,g16_result=g16,g18_result=g18)

class TestB02NormativeBinding(unittest.TestCase):
    def setUp(self):self.f=fixture()
    def check_denied(self,out):
        self.assertEqual(out['schema_version'],SCHEMA)
        for key in DENIED:
            self.assertIs(out[key],False,key)
        for k in ('vinculo_l2_ruleversion_canonico_comprovado',
                  'autenticidade_institucional_independente_comprovada',
                  'cobertura_alteracoes_revogacoes_exaustiva',
                  'aplicabilidade_juridica_comprovada','decisao_fiscal_autorizada'):
            self.assertIs(out[k],False,k)
    def result(self):return run(**self.f)
    def assert_stop(self,txt):
        with self.assertRaisesRegex(EnterpriseB02GateError,txt):self.result()
    def test_01_exacto_interno_nao_promove_norma(self):
        r=self.result()
        self.assertEqual(r['estado'],'CANDIDATO_DOCUMENTAL_COTEJADO')
        self.assertTrue(r['parametros_e_registo_l2_cotejados'])
        self.assertTrue(r['identidade_documental_cotejada'])
        self.assertEqual(r['registro_mva_id_observado'],ROW_ID)
        self.check_denied(r)
        self.assertEqual(self.f['db'].calls,[('TabelaMVA',ROW_ID),('query_bounded','TabelaMVA'),('RuleVersion','ver2'),('ExtractionResult','ex1')])
    def test_02_ausencia_l2_abstencao(self):
        self.f['db'].rows.pop(('TabelaMVA',ROW_ID));r=self.result();self.assertEqual(r['estado'],'ABSTENCAO');self.check_denied(r)
    def test_03_sem_id_l2_abstencao(self):
        self.f['c6_result']['estado']='ABSTENCAO_SEM_IDENTIDADE_REGISTO_L2'
        r=self.result();self.assertEqual(r['estado'],'ABSTENCAO');self.assertEqual(self.f['db'].calls,[])
    def test_04_id_l2_trocado_stop(self):
        self.f['db'].rows[('TabelaMVA',ROW_ID)].id=782;self.assert_stop('ID_DIVERGENTE')
    def test_05_l2_uf_divergente(self):
        self.f['db'].rows[('TabelaMVA',ROW_ID)].estado='PA';r=self.result();self.assertEqual(r['estado'],'CONTRADICAO');self.check_denied(r)
    def test_06_l2_ncm_divergente(self):
        self.f['db'].rows[('TabelaMVA',ROW_ID)].ncm='00000000';self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_07_l2_fonte_diferente(self):
        self.f['db'].rows[('TabelaMVA',ROW_ID)].fonte_legal='FONTE OUTRA';self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_08_l2_rotulo_nao_autoriza(self):
        self.f['db'].rows[('TabelaMVA',ROW_ID)].nivel_confianca_fonte='oficial'
        self.check_denied(self.result())
    def test_09_l2_nao_oficial_nao_prova(self):
        self.f['db'].rows[('TabelaMVA',ROW_ID)].nivel_confianca_fonte='estimativa';self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_10_l2_data_depois_nao_vigente(self):
        self.f['db'].rows[('TabelaMVA',ROW_ID)].vigencia_inicio=date(2026,4,2);self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_11_l2_registo_fim_antes(self):
        self.f['db'].rows[('TabelaMVA',ROW_ID)].vigencia_fim=date(2026,3,31);self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_12_l2_mva_motor_diverge(self):
        self.f['db'].rows[('TabelaMVA',ROW_ID)].mva=44.12;self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_13_l2_aliquota_motor_diverge(self):
        self.f['db'].rows[('TabelaMVA',ROW_ID)].aliquota_interna=.17;self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_14_c3_sem_janela_abstencao(self):
        self.f['c3_result']['estado']='ABSTENCAO_TEMPORAL';self.assertEqual(self.result()['estado'],'ABSTENCAO')
    def test_15_c1_ausente_abstencao(self):
        self.f['c1_result']=None;self.assertEqual(self.result()['estado'],'ABSTENCAO')
    def test_16_id_rule_nao_fornecido(self):
        self.f['rule_version_record_id']=None;self.assertEqual(self.result()['estado'],'ABSTENCAO')
    def test_17_rule_ausente_abstencao(self):
        self.f['db'].rows.pop(('RuleVersion','ver2'));self.assertEqual(self.result()['estado'],'ABSTENCAO')
    def test_18_extraction_ausente_abstencao(self):
        self.f['db'].rows.pop(('ExtractionResult','ex1'));self.assertEqual(self.result()['estado'],'ABSTENCAO')
    def test_19_rule_hash_inconsistente(self):
        self.f['db'].rows[('RuleVersion','ver2')].rule_hash=HEX('9');self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_20_extraction_hash_inconsistente(self):
        self.f['db'].rows[('ExtractionResult','ex1')].artifact_hash=HEX('9');self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_21_fonte_pdf_hash_divergente(self):
        self.f['c1_result']['pdf_sha256']=HEX('9');self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_22_excerto_pdf_hash_divergente(self):
        self.f['c1_result']['excerto_sha256']=HEX('9');self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_23_rule_cest_inaplicavel(self):
        self.f['db'].rows[('RuleVersion','ver2')].structured_content['g113_v1']['cest']='9999999'
        self.f['db'].rows[('ExtractionResult','ex1')].structured_content['g113_v1']['cest']='9999999'
        self.assertEqual(self.result()['estado'],'NAO_APLICAVEL_AO_ESCOPO_DECLARADO')
    def test_24_rule_cfop_inaplicavel(self):
        for cls,ident in [('RuleVersion','ver2'),('ExtractionResult','ex1')]:
            self.f['db'].rows[(cls,ident)].structured_content['g113_v1']['cfop']='6102'
        self.assertEqual(self.result()['estado'],'NAO_APLICAVEL_AO_ESCOPO_DECLARADO')
    def test_25_rule_regime_inaplicavel(self):
        for cls,ident in [('RuleVersion','ver2'),('ExtractionResult','ex1')]:
            self.f['db'].rows[(cls,ident)].structured_content['g113_v1']['regime']='presumido'
        self.assertEqual(self.result()['estado'],'NAO_APLICAVEL_AO_ESCOPO_DECLARADO')
    def test_26_rule_operacao_inaplicavel(self):
        for cls,ident in [('RuleVersion','ver2'),('ExtractionResult','ex1')]:
            self.f['db'].rows[(cls,ident)].structured_content['g113_v1']['operacao']='entrada'
        self.assertEqual(self.result()['estado'],'NAO_APLICAVEL_AO_ESCOPO_DECLARADO')
    def test_27_rule_tempo_inaplicavel(self):
        for cls,ident in [('RuleVersion','ver2'),('ExtractionResult','ex1')]:
            self.f['db'].rows[(cls,ident)].structured_content['g113_v1']['vigencia_inicio']='2026-04-02'
        self.assertEqual(self.result()['estado'],'NAO_APLICAVEL_AO_ESCOPO_DECLARADO')
    def test_28_mva_da_regra_diferente_motor(self):
        for cls,ident in [('RuleVersion','ver2'),('ExtractionResult','ex1')]:
            self.f['db'].rows[(cls,ident)].structured_content['g113_v1']['mva_percentual']='41.42'
        self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_29_aliquota_sem_prova(self):
        for cls,ident in [('RuleVersion','ver2'),('ExtractionResult','ex1')]:
            self.f['db'].rows[(cls,ident)].structured_content['g113_v1']['aliquota_percentual']='17.00'
        self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_30_fonte_trust_falso_promovido_stop(self):
        self.f['g18_result']['fonte_primaria_autenticada']=True;self.assert_stop('AUTORIDADE')
    def test_31_c1_prova_semantica_forjada_stop(self):
        self.f['c1_result']['prova_de_relacao_semantica_entre_excerto_e_parametros']=True;self.assert_stop('AUTORIDADE')
    def test_32_c6_fk_forjada_stop(self):
        self.f['c6_result']['vinculo_adr020_comprovado']=True;self.assert_stop('AUTORIDADE_OU_CONTRATO_INVALIDO_C6')
    def test_33_rels_declaradas_abstencao(self):
        self.f['g16_result']['itens'][0]['relacoes_declaradas']=['altera'];self.assertEqual(self.result()['estado'],'ABSTENCAO')
    def test_34_c3_periodo_alterado_stop(self):
        self.f['c3_result']['data_operacao_declarada']='2026-04-02';self.assert_stop('DATA_OPERACAO')
    def test_35_c4_ncm_c6_divergente_stop(self):
        self.f['c4_result']['ncm']='01234567';self.assert_stop('CLASSIFICACAO')
    def test_36_xml_hash_divergente_stop(self):
        self.f['g16_result']['xml_sha256']=HEX('0');self.assert_stop('DOCUMENTO_OU_XML')
    def test_37_nao_executa_query_ou_escrita(self):
        self.result();self.assertEqual(len(self.f['db'].calls),4)
    def test_38_extraction_params_divergem(self):
        self.f['db'].rows[('ExtractionResult','ex1')].structured_content['g113_v1']['mva_percentual']='40.00'
        self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_39_c5_nao_faz_decisao_para_outros_valores(self):
        self.f['c5_result']['mva_motor_percentual']='41.42'
        self.assertEqual(self.result()['estado'],'CONTRADICAO')
    def test_41_duplicado_l2_abstencao(self):
        self.f['db'].concurrent=[self.f['db'].rows[('TabelaMVA',ROW_ID)],
                                  S(id=782,estado='PR',ncm=IDENT)]
        r=self.result()
        self.assertEqual(r['estado'],'ABSTENCAO')
        self.assertEqual(r['motivo'],'L2_DUPLICIDADE_OU_SELECAO_CONCORRENTE')
        self.check_denied(r)
    def test_42_sem_auditoria_de_unicidade_abstencao(self):
        self.f['db'].query=lambda typ: (_ for _ in ()).throw(RuntimeError('isolamento nao disponivel'))
        r=self.result();self.assertEqual(r['estado'],'ABSTENCAO')
    def test_40_nao_considera_ausencia_de_fim_vigencia_infinita(self):
        self.f['c4_result']['data_operacao']='2026-04-02'
        self.f['c3_result']['data_operacao_declarada']='2026-04-02'
        self.f['g16_result']['data_operacao_observada']='2026-04-02'
        self.f['c3_result']['estado']='ABSTENCAO_TEMPORAL'
        self.assertEqual(self.result()['estado'],'ABSTENCAO')

if __name__=='__main__':unittest.main(verbosity=2)
