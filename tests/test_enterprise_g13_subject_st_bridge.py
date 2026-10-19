"""Synthetic G1.3 boundary tests. No real XML, network, database, or business data."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

TARGET=Path(os.environ.get('SOLVERIS_G13_MODULE_PATH',str(Path(__file__).resolve().parents[1]/'app/services/enterprise_g13_subject_st_bridge.py')))
app=types.ModuleType('app');app.__path__=[]
services=types.ModuleType('app.services');services.__path__=[]
i2module=types.ModuleType('app.services.enterprise_i2_documentary_bridge')
g12module=types.ModuleType('app.services.enterprise_g12_st_item_reconciliation')
i2module.projetar_diagnostico_integral_i2=lambda **kw: None
g12module.confrontar_st_por_item_g12=lambda **kw: None
with patch.dict(sys.modules,{'app':app,'app.services':services,'app.services.enterprise_i2_documentary_bridge':i2module,'app.services.enterprise_g12_st_item_reconciliation':g12module}):
    spec=importlib.util.spec_from_file_location('_g13_test',TARGET)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

RAW=b'<nfe>G13 SYNTHETIC PLACEHOLDER NEVER USED AS A REAL NF-E</nfe>'
H=hashlib.sha256(RAW).hexdigest()
K='1'*44

def i2(items=1):
    return {'schema_version':'ENTERPRISE_I2_DOCUMENTARY_BRIDGE_V1',
        'uso':'INTERNO_NAO_PUBLICAVEL', 'checkout_autorizado':False,
        'diagnostico_empresarial_completo':False,'comprovacao_normativa':False,
        'documental_i2':{
            'estado':'DOCUMENTO_INTERNO_RECONCILIADO','documento_id':10,'relatorio_id':77,
            'xml_sha256':H,'chave_nfe':K,'competencia_observada':'2026-04',
            'autenticidade_sefaz_verificada':False,'escrituracao_efd_verificada':False,
            'norma_vigente_verificada':False,'recolhimento_verificado':False,
            'credibilidade_credito_fiscal':False,
            'itens_xml_observados':[{'nItem':idx,'ncm':'10019010','cfop':'5102'} for idx in range(1,items+1)]}}

def g12(items=1, simulated=None):
    simulated=items if simulated is None else simulated
    status=('G12_SIMULACAO_CONDICIONAL_SEM_AUTORIDADE' if simulated == items
            else 'G12_SIMULACAO_PARCIAL_SEM_AUTORIDADE' if simulated else 'G12_SEM_SIMULACAO')
    return {'schema_version':'SOLVERIS_ENTERPRISE_G12_ST_ITEM_READONLY_V1','estado':status,
        'xml_sha256':H,'itens_total':items,'itens_simulados':simulated,
        'autoridade_fiscal':False,'norma_juridicamente_ratificada':False,
        'icms_proprio_recalculado_por_fonte_independente':False,
        'documento_autenticado_sefaz':False,'credito_confirmado':False,
        'checkout_autorizado':False,'usavel_comercialmente':False,
        'confronto_g1':{'consistente':None,'autoridade_fiscal':False,'credito_confirmado':False,'checkout_autorizado':False},
        'itens':[{'indice_item':idx,'ncm':'10019010','cfop':'5102','competencia':'2026-04',
                  'fonte_original_autenticada':False,
                  'comparacao_condicional':idx<=simulated,
                  'estado':'SIMULACAO_CONDICIONAL_MVA' if idx<=simulated else 'NAO_AVALIADO',
                  'metodo_base':'iva_st' if idx<=simulated else None,
                  'fonte_legal_informada':'SINTETICA NAO OFICIAL' if idx<=simulated else None}
                 for idx in range(1,items+1)]}

class G13Tests(unittest.TestCase):
    def setUp(self):
        self.i=i2();self.g=g12();self.db=object()
        self.pi=patch.object(module,'projetar_diagnostico_integral_i2',side_effect=lambda **kw:copy.deepcopy(self.i))
        self.pg=patch.object(module,'confrontar_st_por_item_g12',side_effect=lambda **kw:copy.deepcopy(self.g))
        self.oi=self.pi.start();self.addCleanup(self.pi.stop)
        self.og=self.pg.start();self.addCleanup(self.pg.stop)
    def run_bridge(self,**kw):
        a=dict(db=self.db,authenticated_user_id=7,empresa_id=41,relatorio_id=77,xml_bytes=RAW)
        a.update(kw)
        return module.projetar_confronto_st_sujeito_g13(**a)
    def reject(self,code):
        with self.assertRaisesRegex(module.EnterpriseG13GateError,code):self.run_bridge()
    def test_01_complete_proof_is_internal_only(self):
        r=self.run_bridge()
        self.assertEqual(r['estado'],'SIMULACAO_CONDICIONAL_VINCULADA_NAO_AUTORIZADA')
        self.assertEqual(r['itens_simulados'],1)
        self.assertTrue(r['posse_e_proveniencia_interna_i2'])
        for k in ('credito_confirmado','autoridade_fiscal','checkout_autorizado','usavel_comercialmente','autenticidade_sefaz_verificada','norma_legal_verificada_por_fonte_primaria'):
            self.assertIs(r[k],False)
        self.assertEqual(r['xml_sha256'],H)
    def test_02_g12_not_called_before_i2_verification(self):
        self.i['documental_i2']['xml_sha256']='f'*64
        self.reject('G13_I2_IDENTIDADE_OU_AUTORIDADE_INCONSISTENTE')
        self.og.assert_not_called()
    def test_03_identity_subject_mismatch_by_i2(self):
        self.oi.side_effect=ValueError('I2_SUBJECT_REGIME_OR_OWNER_INVALID')
        self.reject('G13_I2_DOCUMENTO_OU_POSSE_NAO_COMPROVADOS')
        self.og.assert_not_called()
    def test_04_forged_i2_checkout(self):
        self.i['checkout_autorizado']=True
        self.reject('G13_I2_CONTRATO_INCOMPATIVEL')
    def test_05_wrong_i2_schema(self):
        self.i['schema_version']='FORGED';self.reject('G13_I2_CONTRATO_INCOMPATIVEL')
    def test_06_forged_i2_sefaz(self):
        self.i['documental_i2']['autenticidade_sefaz_verificada']=True
        self.reject('G13_I2_IDENTIDADE_OU_AUTORIDADE_INCONSISTENTE')
    def test_07_g12_bytes_mismatch(self):
        self.g['xml_sha256']='f'*64;self.reject('G13_G12_PROVA_OU_IDENTIDADE_INCOMPATIVEL')
    def test_08_g12_claims_credit(self):
        self.g['credito_confirmado']=True;self.reject('G13_G12_PROVA_OU_IDENTIDADE_INCOMPATIVEL')
    def test_09_g12_wrong_ncm(self):
        self.g['itens'][0]['ncm']='99999999';self.reject('G13_G12_ITEM_OU_COMPETENCIA_DIVERGENTE')
    def test_10_g12_wrong_competence(self):
        self.g['itens'][0]['competencia']='2026-05';self.reject('G13_G12_ITEM_OU_COMPETENCIA_DIVERGENTE')
    def test_11_g12_missing_source(self):
        self.g['itens'][0]['fonte_legal_informada']=None;self.reject('G13_G12_SIMULACAO_SEM_RASTRO_NORMATIVO')
    def test_12_g12_misleading_sim_count(self):
        self.g['itens_simulados']=0;self.reject('G13_G12_CONTAGEM_SIMULACAO_DIVERGENTE')
    def test_13_forged_g1_consistency(self):
        self.g['confronto_g1']['consistente']=True;self.reject('G13_G1_CONFRONTO_NAO_FALHA_FECHADO')
    def test_14_unsupported_operation_no_claim(self):
        self.g=g12(simulated=0)
        r=self.run_bridge();self.assertEqual(r['estado'],'SEM_SIMULACAO_VINCULADA');self.assertEqual(r['itens_simulados'],0)
    def test_15_partial_keeps_block(self):
        self.i=i2(items=2);self.g=g12(items=2,simulated=1)
        r=self.run_bridge();self.assertEqual(r['estado'],'COBERTURA_PARCIAL_VINCULADA_NAO_AUTORIZADA');self.assertFalse(r['credito_confirmado'])
    def test_16_duplicate_item_claim(self):
        self.i=i2(items=2);self.i['documental_i2']['itens_xml_observados'][1]['nItem']=1
        self.g=g12(items=2);self.reject('G13_I2_ITEM_OBSERVADO_INCONSISTENTE')
    def test_17_bad_entry_rejected(self):
        with self.assertRaisesRegex(module.EnterpriseG13GateError,'G13_ENTRADA_INVALIDA'):
            self.run_bridge(xml_bytes=b'')
        self.oi.assert_not_called();self.og.assert_not_called()
    def test_18_g12_error_no_fallback(self):
        self.og.side_effect=RuntimeError('simulated backend')
        self.reject('G13_G12_MOTOR_INDISPONIVEL')
    def test_19_incorrect_status_for_partial(self):
        self.i=i2(items=2);self.g=g12(items=2,simulated=1)
        self.g['estado']='G12_SIMULACAO_CONDICIONAL_SEM_AUTORIDADE'
        self.reject('G13_G12_ESTADO_INCONSISTENTE')
    def test_20_exact_same_db_and_xml_used(self):
        self.run_bridge()
        self.assertIs(self.oi.call_args.kwargs['db'],self.db)
        self.assertEqual(self.oi.call_args.kwargs['xml_bytes'],RAW)
        self.assertIs(self.og.call_args.kwargs['db'],self.db)
        self.assertEqual(self.og.call_args.kwargs['xml_bytes'],RAW)
    def test_21_reject_g12_independent_tax_claim(self):
        self.g['icms_proprio_recalculado_por_fonte_independente']=True
        self.reject('G13_G12_PROVA_OU_IDENTIDADE_INCOMPATIVEL')
    def test_22_g12_cardinality_wrong(self):
        self.g['itens']=[];self.reject('G13_G12_CARDINALIDADE_INCOMPATIVEL')
    def test_23_reject_i2_proof_legally_proven(self):
        self.i['comprovacao_normativa']=True;self.reject('G13_I2_CONTRATO_INCOMPATIVEL')
    def test_24_reject_empty_observed_items(self):
        self.i['documental_i2']['itens_xml_observados']=[];self.reject('G13_I2_ITENS_INVALIDOS')

if __name__ == '__main__':unittest.main()
