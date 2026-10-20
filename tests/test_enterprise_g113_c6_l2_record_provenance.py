"""G1.13-C6 synthetic-only tests. No database/network/client NF-e."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import importlib.util
from pathlib import Path
import unittest

from tools.enterprise_g113_c6_l2_record_provenance import (
    SCHEMA, G113C6EvidenceError, cotejar_registo_l2_g113_c6)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'isolated_c5_fixture', ROOT / 'tests/test_enterprise_g113_c5_parameter_trace.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def inputs(with_id=True):
    s = fixture.sample()
    from tools.enterprise_g113_c5_parameter_trace import cotejar_rastro_parametros_g113_c5
    c5 = cotejar_rastro_parametros_g113_c5(**s)
    row = dict(
        versao=1, registro_mva_id=781, uf='PR', ncm='12119090',
        data_referencia='2026-04-01', vigencia_inicio='2026-04-01',
        vigencia_fim=None, fonte_legal=fixture.SOURCE,
        url_fonte=fixture.URL, importado_por_declarado='IMPORTADOR SINTETICO',
        mva_fracao_registo='0.4678', aliquota_fracao_registo='0.18',
        unicidade_registos_vigentes_comprovada=False,
        vinculo_adr020_comprovado=False,
        autenticidade_fonte_externa_comprovada=False,
        autoridade_fiscal=False,
    )
    if with_id:
        s['g13_result']['confronto_condicional_g12']['itens'][0]['proveniencia_l2_g12_v1'] = row
    return dict(c4_result=s['c4_result'], c5_result=c5,
                g13_result=s['g13_result'], indice_item=1)


class C6ReconciliationTests(unittest.TestCase):
    def setUp(self):self.a=inputs()
    def check(self):return cotejar_registo_l2_g113_c6(**self.a)
    def deny(self,code):
        with self.assertRaises(G113C6EvidenceError) as cm:self.check()
        self.assertIn(code,str(cm.exception))
    def row(self):return self.a['g13_result']['confronto_condicional_g12']['itens'][0]['proveniencia_l2_g12_v1']
    def test_01_id_observed_not_legal_authority(self):
        x=self.check()
        self.assertEqual(x['schema_version'],SCHEMA)
        self.assertEqual(x['identificador_registo_l2_observado'],781)
        self.assertEqual(x['estado'],'REGISTO_L2_IDENTIFICADO_SEM_UNICIDADE_OU_ADR020')
        for f in ('unicidade_registos_vigentes_comprovada','correspondencia_cest_l2_comprovada',
                  'vinculo_adr020_comprovado','fonte_primaria_autenticada',
                  'autoridade_fiscal','credito_confirmado','checkout_autorizado','usavel_comercialmente'):
            self.assertIs(x[f],False)
    def test_02_no_row_id_abstains(self):
        self.a=inputs(False)
        self.assertEqual(self.check()['estado'],'ABSTENCAO_SEM_IDENTIDADE_REGISTO_L2')
    def test_03_no_side_effect(self):
        original=deepcopy(self.a);self.check();self.assertEqual(self.a,original)
    def test_04_bool_as_identifier_rejected(self):self.row()['registro_mva_id']=True;self.deny('PROVENIENCIA_ID')
    def test_05_negative_identifier_rejected(self):self.row()['registro_mva_id']=-8;self.deny('PROVENIENCIA_ID')
    def test_06_unknown_field_rejected(self):self.row()['proof']=True;self.deny('PROVENIENCIA_FORMA')
    def test_07_trust_escalation_rejected(self):self.row()['vinculo_adr020_comprovado']=True;self.deny('PROVENIENCIA_ID')
    def test_08_cest_is_not_in_l2_selection(self):self.assertFalse(self.check()['correspondencia_cest_l2_comprovada'])
    def test_09_wrong_uf_rejected(self):self.row()['uf']='PA';self.deny('REGISTO_IDENTIDADE')
    def test_10_wrong_ncm_rejected(self):self.row()['ncm']='11111111';self.deny('REGISTO_IDENTIDADE')
    def test_11_wrong_source_rejected(self):self.row()['fonte_legal']='ANOTHER';self.deny('REGISTO_IDENTIDADE')
    def test_12_wrong_date_rejected(self):self.row()['data_referencia']='2026-04-02';self.deny('VIGENCIA_REGISTO')
    def test_13_expired_record_rejected(self):self.row()['vigencia_fim']='2026-03-31';self.deny('VIGENCIA_REGISTO')
    def test_14_future_record_rejected(self):self.row()['vigencia_inicio']='2026-04-02';self.deny('VIGENCIA_REGISTO')
    def test_15_mva_mismatch_rejected(self):self.row()['mva_fracao_registo']='0.4142';self.deny('PARAMETROS_L2')
    def test_16_aliquota_mismatch_rejected(self):self.row()['aliquota_fracao_registo']='0.17';self.deny('PARAMETROS_L2')
    def test_17_forged_c5_authority_rejected(self):self.a['c5_result']['credito_confirmado']=True;self.deny('C5_INVALIDO')
    def test_18_forged_g13_xml_rejected(self):self.a['g13_result']['xml_sha256']='0'*64;self.deny('G13_INVALIDO')
    def test_19_uses_exact_original_c5_trace(self):
        self.a['g13_result']['confronto_condicional_g12']['itens'][0]['rastro_parametros_g12_v1']['mva_fracao_utilizada']='0.4142'
        self.deny('PARAMETROS_L2')
    def test_20_duplicated_item_not_read(self):self.a['indice_item']=2;self.deny('C4_INVALIDO')
    def test_21_absent_c5_trace_rejected(self):
        self.a['g13_result']['confronto_condicional_g12']['itens'][0].pop('rastro_parametros_g12_v1')
        self.deny('C5_RASTRO')
    def test_22_negative_flags_in_absence(self):
        self.a=inputs(False);x=self.check();self.assertFalse(x['autoridade_fiscal']);self.assertFalse(x['credito_recuperavel_demonstrado'])


class C6ActualG12SidecarTests(unittest.TestCase):
    def test_23_actual_g12_records_row_when_identity_supplied(self):
        m=fixture.C5RealG12InstrumentationTests.engine()
        orig=m.buscar_mva
        m.buscar_mva=lambda *a,**kw:dict(orig(*a,**kw),registro_mva_id=781,
                                             importado_por='FONTE SINTETICA')
        r=m.confrontar_st_por_item_g12(db=object(),xml_bytes=fixture.C5RealG12InstrumentationTests.xml())
        self.assertEqual(r['itens_simulados'],1)
        item=r['itens'][0]
        row=item['proveniencia_l2_g12_v1']
        self.assertEqual(row['registro_mva_id'],781)
        self.assertEqual(row['mva_fracao_registo'],item['rastro_parametros_g12_v1']['mva_fracao_utilizada'])
        self.assertEqual(row['data_referencia'],'2026-04-01')
        self.assertIs(row['vinculo_adr020_comprovado'],False)
    def test_24_actual_g12_no_row_id_no_sidecar(self):
        m=fixture.C5RealG12InstrumentationTests.engine()
        r=m.confrontar_st_por_item_g12(db=object(),xml_bytes=fixture.C5RealG12InstrumentationTests.xml())
        self.assertEqual(r['itens_simulados'],1)
        self.assertNotIn('proveniencia_l2_g12_v1',r['itens'][0])
    def test_25_actual_g12_denied_rule_no_sidecar(self):
        m=fixture.C5RealG12InstrumentationTests.engine(authorized=False)
        r=m.confrontar_st_por_item_g12(db=object(),xml_bytes=fixture.C5RealG12InstrumentationTests.xml())
        self.assertEqual(r['itens_simulados'],0)
        self.assertNotIn('proveniencia_l2_g12_v1',r['itens'][0])


if __name__=='__main__':unittest.main(verbosity=2)
