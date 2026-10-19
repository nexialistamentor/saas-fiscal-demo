"""G16 isolated gates: synthetic-only, no DB/network; modules in fake registry."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import importlib.util
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace as S
from unittest.mock import patch
import sys
import unittest

MODULE=Path(os.environ.get('SOLVERIS_G16_MODULE_PATH',str(Path(__file__).resolve().parents[1]/'app/services/enterprise_g16_temporal_rule_chain.py')))
app=ModuleType('app');app.__path__=[]
service=ModuleType('app.services');service.__path__=[]
models=ModuleType('app.models');g15mod=ModuleType('app.services.enterprise_g15_adr020_primary_artifact_link')
class ExtractionResult:pass
class ExtractionRun:pass
class RuleVersion:pass
class RuleReviewRecord:pass
class NormativeActivation:pass
class NormativeRelationVersion:pass
for C in (ExtractionResult,ExtractionRun,RuleVersion,RuleReviewRecord,NormativeActivation,NormativeRelationVersion):setattr(models,C.__name__,C)
g15mod.cotejar_artefacto_primario_g15=lambda **kwargs:None
with patch.dict(sys.modules,{'app':app,'app.services':service,'app.models':models,
    'app.services.enterprise_g15_adr020_primary_artifact_link':g15mod}):
    spec=importlib.util.spec_from_file_location('_g16_test',MODULE)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

XML=b'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe><ide><dhEmi>2026-09-12T10:00:00-03:00</dhEmi></ide></infNFe></NFe>'
SHA=hashlib.sha256(XML).hexdigest()
AH='a'*64

def g15(n=1):
    return {'schema_version':m._G15_SCHEMA,'empresa_id':1,'relatorio_id':2,'documento_id':3,
        'xml_sha256':SHA,'posse_e_proveniencia_interna_g14':True,'itens_total':n,
        'itens_com_cadeia_interna':n,'versao_oficial_verificada':False,
        'texto_normativo_interpretado_e_aplicado':False,
        'itens':[{'indice_item':i,'normative_artifact_id':'art-1','artefacto_sha256':AH,
             'cadeia_interna_adr020_verificada':True,'fonte_primaria_autenticada':False,
             'versao_ato_verificada':False,'aplicabilidade_juridica_comprovada':False} for i in range(1,n+1)],
        **{k:False for k in m._NEGATIVE}}

def refs(idx=1,relations=None):
    return {'indice_item':idx,'extraction_result_id':'result-1',
       'rule_version_record_id':'rule-record-1','rule_review_record_id':'review-1',
       'normative_activation_id':'activation-1',
       'relation_version_record_ids':[] if relations is None else relations}

def records():
    extraction=S(extraction_result_id='result-1',normative_artifact_id='art-1',artifact_hash=AH,
        outcome='conclusivo',run_event='conclusao',run_state='concluida',record_hash='b'*64,
        extraction_run_record_id='run-1')
    run=S(extraction_run_record_id='run-1',normative_artifact_id='art-1',artifact_hash=AH,
          run_event='conclusao',projected_state='concluida',record_hash='c'*64)
    rule=S(rule_version_record_id='rule-record-1',rule_id='rule-1',rule_version=1,
           rule_hash='d'*64,extraction_result_id='result-1',
           extraction_result_record_hash=extraction.record_hash,record_hash='e'*64)
    review=S(rule_review_record_id='review-1',subject_id=rule.rule_id,
        subject_version=1,subject_hash=rule.rule_hash,review_event='revisao_concluida',
        outcome='validada',record_hash='f'*64)
    activation=S(normative_activation_id='activation-1',subject_type='rule_version',
        subject_id=rule.rule_id,subject_version=1,subject_hash=rule.rule_hash,
        review_record_id=review.rule_review_record_id,review_record_hash=review.record_hash,
        state='active',record_hash='1'*64)
    relation=S(normative_relation_version_record_id='relation-1',relation_type='revoga',
        record_hash='2'*64,normative_relation_hash='3'*64,
        source_subject_type='rule_version',source_subject_id='rule-2',
        source_subject_version=1,source_subject_hash='4'*64,
        target_subject_type='rule_version',target_subject_id=rule.rule_id,
        target_subject_version=1,target_subject_hash=rule.rule_hash)
    return {(ExtractionResult,'result-1'):extraction,(ExtractionRun,'run-1'):run,
      (RuleVersion,'rule-record-1'):rule,(RuleReviewRecord,'review-1'):review,
      (NormativeActivation,'activation-1'):activation,(NormativeRelationVersion,'relation-1'):relation}

class FakeDB:
    def __init__(self):self.rows=records();self.reads=0;self.writes=0
    def get(self,cls,key):self.reads+=1;return self.rows.get((cls,key))
    def add(self,*a):self.writes+=1;raise AssertionError('WRITE_FORBIDDEN')
    def commit(self,*a):self.writes+=1;raise AssertionError('WRITE_FORBIDDEN')
    def query(self,*a):self.writes+=1;raise AssertionError('UNBOUNDED_QUERY_FORBIDDEN')

class G16(unittest.TestCase):
    def setUp(self):
        self.db=FakeDB();self.projection=g15()
        p=patch.object(m,'cotejar_artefacto_primario_g15',side_effect=lambda **kwargs:self.projection)
        p.start();self.addCleanup(p.stop)
    def call(self,**kw):
        inp={'db':self.db,'authenticated_user_id':9,'empresa_id':1,'relatorio_id':2,
             'xml_bytes':XML,'candidatos_normativos':[],'referencias_adr020':[],
             'referencias_temporais':[refs()]};inp.update(kw)
        return m.cotejar_ciclo_normativo_g16(**inp)
    def noauthority(self,r):
        for k in ('fonte_primaria_autenticada','versao_oficial_verificada',
            'atualizacao_e_revogacao_exaustivas','vigencia_juridica_comprovada',
            'autoridade_fiscal','credito_confirmado','checkout_autorizado','usavel_comercialmente'):
            self.assertIs(r[k],False,k)
        self.assertEqual(self.db.writes,0)
    def test_01_internal_chain_no_external_authority(self):
        r=self.call();self.assertEqual(r['itens_com_cadeia_temporal_interna'],1);self.noauthority(r)
        self.assertEqual(r['itens'][0]['motivo'],'CADEIA_INTERNA_REGRA_COTEJADA_SEM_PROVA_DE_VIGENCIA')
    def test_02_issue_date_is_from_bytes(self):self.assertEqual(self.call()['data_operacao_observada'],'2026-09-12')
    def test_03_revocation_relation_alerts(self):
        r=self.call(referencias_temporais=[refs(relations=['relation-1'])]);self.assertEqual(r['itens'][0]['estado'],'ALERTA_RELACAO_NORMATIVA_SEM_DECISAO');self.noauthority(r)
    def test_04_no_temporal_links_no_claim(self):
        r=self.call(referencias_temporais=[]);self.assertEqual(self.db.reads,0);self.assertEqual(r['itens_com_cadeia_temporal_interna'],0);self.noauthority(r)
    def test_05_failure_g15_prevents_lookups(self):
        with patch.object(m,'cotejar_artefacto_primario_g15',side_effect=ValueError('blocked')):
            with self.assertRaisesRegex(m.EnterpriseG16GateError,'G16_G15_'):self.call()
        self.assertEqual(self.db.reads,0)
    def test_06_g15_other_company(self):
        self.projection['empresa_id']=17
        with self.assertRaises(m.EnterpriseG16GateError):self.call()
    def test_07_xml_bytes_changed(self):
        with self.assertRaises(m.EnterpriseG16GateError):self.call(xml_bytes=XML+b' ')
    def test_08_g15_trust_forged(self):
        self.projection['autoridade_fiscal']=True
        with self.assertRaises(m.EnterpriseG16GateError):self.call()
    def test_09_bad_g15_item_index(self):
        self.projection['itens'][0]['indice_item']=True
        with self.assertRaises(m.EnterpriseG16GateError):self.call()
    def test_10_extra_ref_key(self):
        x=refs();x['trusted']=True
        with self.assertRaises(m.EnterpriseG16GateError):self.call(referencias_temporais=[x])
    def test_11_double_ref(self):
        with self.assertRaises(m.EnterpriseG16GateError):self.call(referencias_temporais=[refs(),refs()])
    def test_12_ref_outside_document(self):
        with self.assertRaises(m.EnterpriseG16GateError):self.call(referencias_temporais=[refs(2)])
    def test_13_boolean_ref_index(self):
        with self.assertRaises(m.EnterpriseG16GateError):self.call(referencias_temporais=[refs(True)])
    def test_14_invalid_relations_list(self):
        x=refs();x['relation_version_record_ids']='relation-1'
        with self.assertRaises(m.EnterpriseG16GateError):self.call(referencias_temporais=[x])
    def test_15_duplicate_relation_rejected(self):
        with self.assertRaises(m.EnterpriseG16GateError):self.call(referencias_temporais=[refs(relations=['relation-1','relation-1'])])
    def test_16_false_g15_chain_no_reads(self):
        self.projection['itens'][0]['cadeia_interna_adr020_verificada']=False
        r=self.call();self.assertEqual(self.db.reads,0);self.assertEqual(r['itens_com_cadeia_temporal_interna'],0)
    def test_17_bad_artifact_hash(self):
        self.db.rows[(ExtractionResult,'result-1')].artifact_hash='0'*64
        self.assertEqual(self.call()['itens_com_cadeia_temporal_interna'],0)
    def test_18_inconclusive_extraction(self):
        self.db.rows[(ExtractionResult,'result-1')].outcome='inconclusivo'
        self.assertEqual(self.call()['itens'][0]['motivo'],'EXTRACAO_NAO_VINCULADA_AO_ARTEFACTO')
    def test_19_wrong_extraction_run(self):
        self.db.rows[(ExtractionRun,'run-1')].run_event='falha'
        self.assertEqual(self.call()['itens'][0]['motivo'],'EXECUCAO_EXTRACAO_NAO_VINCULADA')
    def test_20_bad_rule_extraction_hash(self):
        self.db.rows[(RuleVersion,'rule-record-1')].extraction_result_record_hash='7'*64
        self.assertEqual(self.call()['itens'][0]['motivo'],'VERSAO_REGRA_SEM_ORIGEM_EXACTA')
    def test_21_wrong_rule_identity(self):
        self.db.rows[(RuleVersion,'rule-record-1')].rule_version=2
        self.assertEqual(self.call()['itens_com_cadeia_temporal_interna'],0)
    def test_22_rejected_review(self):
        self.db.rows[(RuleReviewRecord,'review-1')].outcome='rejeitada'
        self.assertEqual(self.call()['itens'][0]['motivo'],'REVISAO_REGRA_NAO_FAVORAVEL')
    def test_23_not_active(self):
        self.db.rows[(NormativeActivation,'activation-1')].state='revoked'
        self.assertEqual(self.call()['itens'][0]['motivo'],'ATIVACAO_INTERNA_NAO_ATIVA')
    def test_24_suspended(self):
        self.db.rows[(NormativeActivation,'activation-1')].state='suspended'
        self.assertEqual(self.call()['itens_com_cadeia_temporal_interna'],0)
    def test_25_wrong_activation_subject(self):
        self.db.rows[(NormativeActivation,'activation-1')].subject_hash='9'*64
        self.assertEqual(self.call()['itens'][0]['motivo'],'ATIVACAO_SEM_VINCULO_EXACTO')
    def test_26_relation_unrelated(self):
        self.db.rows[(NormativeRelationVersion,'relation-1')].target_subject_id='rule-999'
        self.assertEqual(self.call(referencias_temporais=[refs(relations=['relation-1'])])['itens'][0]['motivo'],'RELACAO_NAO_LIGADA_A_REGRA')
    def test_27_relation_bad_hash(self):
        self.db.rows[(NormativeRelationVersion,'relation-1')].record_hash='NOTHASH'
        self.assertEqual(self.call(referencias_temporais=[refs(relations=['relation-1'])])['itens_com_cadeia_temporal_interna'],0)
    def test_28_other_relations_not_legal_proof(self):
        self.db.rows[(NormativeRelationVersion,'relation-1')].relation_type='referencia'
        r=self.call(referencias_temporais=[refs(relations=['relation-1'])]);self.assertEqual(r['itens_com_cadeia_temporal_interna'],1);self.noauthority(r)
    def test_29_bad_nonaware_date(self):
        raw=XML.replace(b'-03:00',b'')
        self.projection['xml_sha256']=hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(m.EnterpriseG16GateError,'G16_DATA_EMISSAO_'):self.call(xml_bytes=raw)
    def test_30_multiple_items_partial(self):
        self.projection=g15(2)
        r=self.call();self.assertEqual(r['estado'],'COBERTURA_TEMPORAL_PARCIAL');self.noauthority(r)
    def test_31_no_publication_absence_claim(self):
        r=self.call();self.assertIs(r['itens'][0]['ausencia_revogacao_comprovada'],False)
        self.assertFalse(r['atualizacao_e_revogacao_exaustivas'])
    def test_32_bad_result_primary_key(self):
        self.db.rows[(ExtractionResult,'result-1')].extraction_result_id='forged'
        self.assertEqual(self.call()['itens_com_cadeia_temporal_interna'],0)
    def test_33_bad_activation_primary_key(self):
        self.db.rows[(NormativeActivation,'activation-1')].normative_activation_id='forged'
        self.assertEqual(self.call()['itens_com_cadeia_temporal_interna'],0)
    def test_34_bool_item_total(self):
        self.projection['itens_total']=True
        with self.assertRaises(m.EnterpriseG16GateError):self.call()
    def test_35_does_not_leak_xml_bytes(self):
        r=self.call();self.assertNotIn('dhEmi',str(r));self.assertNotIn('utf-8',str(r))
    def test_36_malformed_input_not_call_g15(self):
        with patch.object(m,'cotejar_artefacto_primario_g15',side_effect=AssertionError('called')):
            with self.assertRaisesRegex(m.EnterpriseG16GateError,'G16_ENTRADA_'):self.call(xml_bytes='raw')

if __name__=='__main__':unittest.main()
