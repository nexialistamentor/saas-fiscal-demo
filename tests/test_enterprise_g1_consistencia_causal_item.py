"""Contrato G1: XML sintético, nunca real; sem banco, SEFAZ ou rede."""
import importlib.util
import os
from pathlib import Path
import unittest

module_path = Path(os.environ.get('SOLVERIS_G1_ENGINE_PATH', str(Path(__file__).resolve().parents[1]/'app/services/tax_consistency/tax_consistency_engine.py')))
spec = importlib.util.spec_from_file_location('_g1_engine', module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
E = module.TaxConsistencyEngine

K = '1'*44

def xml(*, count=1, st=True):
    return {'chave_nfe':K, 'itens':[
        {'ncm':'10019010', 'cfop':'1102', 'base_st':'140.00', 'valor_st':'7.20', 'st_observado_xml':st}
        for _ in range(count)]}

def motor(*, count=1, st='7.20', base='140.00'):
    return {'chave_nfe':K, 'itens_calculados':[
        {'indice_item':i, 'ncm':'10019010', 'cfop':'1102', 'base_st_calculada':base, 'valor_st_calculado':st}
        for i in range(1,count+1)]}

class TestG1(unittest.TestCase):
    def setUp(self): self.e = E()
    def test_01_empty_doesnt_claim_consistency(self):
        self.assertIsNone(self.e.verificar_consistencia({}, {})['consistente'])
    def test_02_real_motor_mirrors_xml_not_independent(self):
        r=self.e.verificar_consistencia(xml(), {'chave_nfe':K,'icms_st':'7.20','base_st':'140.00'})
        self.assertEqual(r['estado'],'NAO_AVALIADO'); self.assertIsNone(r['consistente'])
    def test_03_motor_error(self):
        self.assertEqual(self.e.verificar_consistencia(xml(),{'erro':'falso'})['estado'],'NAO_AVALIADO')
    def test_04_equal_pairs_arithmetic_not_fiscal(self):
        r=self.e.verificar_consistencia(xml(),motor())
        self.assertEqual(r['comparacoes_realizadas'],2)
        self.assertIs(r['coincidencia_numerica'],True)
        self.assertIsNone(r['consistente'])
        self.assertFalse(r['checkout_autorizado']);self.assertFalse(r['credito_confirmado'])
    def test_05_difference_number_not_credit(self):
        r=self.e.verificar_consistencia(xml(),motor(st='5.00'))
        self.assertEqual(r['divergencias'][0]['tipo'],'ICMS_ST')
        self.assertFalse(r['credito_confirmado']); self.assertIsNone(r['consistente'])
    def test_06_no_xml_st_not_evaluable(self):
        self.assertEqual(self.e.verificar_consistencia(xml(st=False),motor())['estado'],'NAO_AVALIADO')
    def test_07_different_document(self):
        m=motor();m['chave_nfe']='2'*44
        self.assertEqual(self.e.verificar_consistencia(xml(),m)['estado'],'NAO_AVALIADO')
    def test_08_extra_item_stop(self):
        self.assertEqual(self.e.verificar_consistencia(xml(),motor(count=2))['estado'],'NAO_AVALIADO')
    def test_09_duplicated_index_stop(self):
        m=motor(count=2);m['itens_calculados'][1]['indice_item']=1
        self.assertEqual(self.e.verificar_consistencia(xml(count=2),m)['estado'],'NAO_AVALIADO')
    def test_10_item_swap_stop(self):
        m=motor(count=2);m['itens_calculados'][0]['indice_item']=2;m['itens_calculados'][1]['indice_item']=1;m['itens_calculados'][0]['ncm']='99999999'
        self.assertEqual(self.e.verificar_consistencia(xml(count=2),m)['estado'],'NAO_AVALIADO')
    def test_11_invalid_numeric_nan(self):
        self.assertEqual(self.e.verificar_consistencia(xml(),motor(st='NaN'))['estado'],'PARCIAL_SEM_AUTORIDADE')
    def test_12_bool_rejected(self):
        self.assertEqual(self.e.verificar_consistencia(xml(),motor(st=True))['estado'],'PARCIAL_SEM_AUTORIDADE')
    def test_13_negative_rejected(self):
        self.assertEqual(self.e.verificar_consistencia(xml(),motor(st='-1'))['estado'],'PARCIAL_SEM_AUTORIDADE')
    def test_14_no_rounding(self):
        self.assertEqual(self.e.verificar_consistencia(xml(),motor(st='7.2009'))['estado'],'PARCIAL_SEM_AUTORIDADE')
    def test_15_ncm_mismatch_stop(self):
        m=motor();m['itens_calculados'][0]['ncm']='00000000'
        self.assertEqual(self.e.verificar_consistencia(xml(),m)['estado'],'NAO_AVALIADO')
    def test_16_two_items_complete(self):
        r=self.e.verificar_consistencia(xml(count=2),motor(count=2))
        self.assertEqual(r['comparacoes_realizadas'],4);self.assertEqual(r['itens_comparados'],2)
    def test_17_direct_fields_fail_closed(self):
        for method in ('verificar_icms_st','verificar_mva','verificar_base_st'):
            self.assertIsNone(getattr(self.e,method)({'valor_st':10},{'icms_st':10})['consistente'])
    def test_18_forged_authority_cannot_promote(self):
        m=motor();m['autoridade_fiscal']=True;m['credito_confirmado']=True;m['checkout_autorizado']=True
        r=self.e.verificar_consistencia(xml(),m)
        self.assertIs(r['autoridade_fiscal'],False);self.assertIs(r['checkout_autorizado'],False)
    def test_19_partial_two_items(self):
        x=xml(count=2); x['itens'][1]['st_observado_xml']=False
        r=self.e.verificar_consistencia(x,motor(count=2))
        self.assertEqual(r['estado'],'PARCIAL_SEM_AUTORIDADE');self.assertIsNone(r['coincidencia_numerica'])
    def test_20_ones_cent_tolerance(self):
        r=self.e.verificar_consistencia(xml(),motor(st='7.21'))
        self.assertEqual(r['divergencias'],[])
    def test_21_gt_cent_difference(self):
        r=self.e.verificar_consistencia(xml(),motor(st='7.22'))
        self.assertEqual(len(r['divergencias']),1)
    def test_22_no_implicit_mva(self):
        r=self.e.verificar_consistencia({'mva_xml':40,'valor_st':10},{'mva_utilizada':40,'icms_st':10})
        self.assertEqual(r['estado'],'NAO_AVALIADO')

if __name__=='__main__': unittest.main()
