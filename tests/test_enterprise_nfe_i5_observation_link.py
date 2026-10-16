"""I5: provas sintéticas, reuse real I2/I4N, sem SEFAZ nem DB/credenciais.

O fixture I2 ja publicado e instanciado como dependencia sem reexecutar a
sua suite (esta sera rodada separadamente nas regressoes).
"""
import hashlib
import importlib
import unittest
from unittest.mock import patch
import test_enterprise_i2_documentary_bridge_contract as i2_fixtures
import test_enterprise_nfe_sefaz_operador_i4n as i4_fixtures


class TestEnterpriseI5ObservationLink(unittest.TestCase):
    def setUp(self):
        self.fixture = i2_fixtures.EnterpriseI2BridgeTests(methodName='test_00_real_contract_exists')
        self.fixture.setUp()
        self.fixture.raw = self._real_dv_xml(self.fixture.raw)
        # I2 synthetic key may fail national DV; keep fixture result/document consistent.
        self.fixture.hash = hashlib.sha256(self.fixture.raw).hexdigest()
        self.fixture.doc.conteudo_sha256 = self.fixture.hash
        self.fixture.payload['_enterprise_xml_evidence']['xml_sha256'] = self.fixture.hash
        self.fixture._seal()
        try:
            self.bridge = importlib.import_module('app.services.enterprise_nfe_i5_observation_link')
        except ModuleNotFoundError as exc:
            if exc.name == 'app.services.enterprise_nfe_i5_observation_link':
                self.fail('I5_RED_CAUSAL_MISSING_MODULE')
            raise

    def _real_dv_xml(self, xml):
        # I2 fixture synthetic key can be invalid; use a valid I4N model-55 key.
        new = i4_fixtures.key('SP')
        old = i2_fixtures._KEY
        replaced = xml.replace(old.encode(), new.encode())
        self.fixture.doc.chave_nfe = new
        self.fixture.report.xml_chave = new
        self.fixture.payload['_enterprise_xml_evidence']['xml_chave'] = new
        self.fixture.payload['dados_fiscais']['chave_nfe'] = new
        return replaced

    def _invoke(self, soap=None, **kwargs):
        chave = i4_fixtures.key('SP')
        data = dict(db=self.fixture.db, authenticated_user_id=7,
                    empresa_id=41, relatorio_id=77,
                    xml_bytes=self.fixture.raw,
                    resposta_soap=i4_fixtures.soap(chave))
        if soap is not None: data['resposta_soap'] = soap
        data.update(kwargs)
        with patch('app.services.tax_engines.pis_cofins_engine.calcular_pis_cofins',
                   return_value={'tributos': {'pis': 15.18, 'cofins': 69.92}}):
            return self.bridge.vincular_observacao_nfe_i5(**data)

    def _stop(self, code, **changes):
        with self.assertRaisesRegex(self.bridge.EnterpriseI5ObservationError, code):
            self._invoke(**changes)

    def test_00_adapter_exists(self):
        self.assertTrue(callable(self.bridge.vincular_observacao_nfe_i5))

    def test_01_normal_status_100_not_authority(self):
        x=self._invoke()
        self.assertEqual(x['cstat_observado'],'100')
        self.assertEqual(x['situacao_observada'],'AUTORIZADA_CONFORME_RETORNO')
        self.assertEqual(x['uf_emissora_chave'],'SP')
        self.assertFalse(x['origem_resposta_atestada'])
        self.assertFalse(x['situacao_sefaz_confirmada'])
        self.assertFalse(x['direito_creditorio_comprovado'])
        self.assertFalse(x['checkout_autorizado'])
        self.assertEqual(self.fixture.db.writes,0)

    def test_02_digest_exact_bytes(self):
        x=self._invoke()
        self.assertEqual(x['xml_sha256'],hashlib.sha256(self.fixture.raw).hexdigest())
        self.assertEqual(x['resposta_soap_sha256'],hashlib.sha256(i4_fixtures.soap(i4_fixtures.key('SP'))).hexdigest())
        self.assertEqual(len(x['recibo_fingerprint_sha256']),64)

    def test_03_cancel_does_not_claim_credit(self):
        x=self._invoke(soap=i4_fixtures.soap(i4_fixtures.key('SP'),'101'))
        self.assertEqual(x['situacao_observada'],'CANCELADA_CONFORME_RETORNO')
        self.assertFalse(x['autorizado_para_calculo_comercial'])

    def test_04_absence_217_refused_authority(self):
        x=self._invoke(soap=i4_fixtures.soap(i4_fixtures.key('SP'),'217'))
        self.assertFalse(x['situacao_sefaz_confirmada'])

    def test_05_rate_limited_656_refused_authority(self):
        x=self._invoke(soap=i4_fixtures.soap(i4_fixtures.key('SP'),'656'))
        self.assertEqual(x['situacao_observada'],'CONSUMO_INDEVIDO_BLOQUEADO')

    def test_06_unexpected_cstat_no_elevation(self):
        x=self._invoke(soap=i4_fixtures.soap(i4_fixtures.key('SP'),'999'))
        self.assertFalse(x['apuracao_mensal_completa'])

    def test_07_other_key_rejected(self):
        self._stop('I5_SOAP_RESPONSE_INVALID', soap=i4_fixtures.soap(i4_fixtures.key('PA')))

    def test_08_different_xml_digest_refused(self):
        self._stop('I5_DOCUMENTARY_I2_NOT_VALIDATED',xml_bytes=self.fixture.raw.replace(b'1000.00',b'2000.00'))

    def test_09_wrong_user_refused(self):
        self._stop('I5_DOCUMENTARY_I2_NOT_VALIDATED',authenticated_user_id=17)

    def test_10_wrong_company_refused(self):
        self._stop('I5_DOCUMENTARY_I2_NOT_VALIDATED',empresa_id=42)

    def test_11_wrong_report_refused(self):
        self._stop('I5_DOCUMENTARY_I2_NOT_VALIDATED',relatorio_id=17)

    def test_12_invalid_provenance_refused(self):
        self.fixture.report.fingerprint='0'*64
        self._stop('I5_DOCUMENTARY_I2_NOT_VALIDATED')

    def test_13_invalid_xml_refused(self):
        self._stop('I5_XML_PARSE_INVALID',xml_bytes=b'<nfe')

    def test_14_missing_or_oversize_soap(self):
        for v in (b'',b'x'*(256*1024+1),None):
            with self.subTest(value=str(v)[:12]):
                self._stop('I5_INPUT_INVALID',resposta_soap=v)

    def test_15_bad_model_65(self):
        old = i4_fixtures.key('SP')
        raw = old[:20] + '65' + old[22:43]
        factor = sum(int(n)*(2+(i % 8)) for i,n in enumerate(reversed(raw))) % 11
        invalid_model = raw + str(0 if factor < 2 else 11-factor)
        self.assertEqual(invalid_model[20:22], '65')
        data = self.fixture.raw.replace(old.encode(), invalid_model.encode())
        self.assertNotEqual(data,self.fixture.raw)
        self._stop('I5_NATIONAL_KEY_INVALID',xml_bytes=data)

    def test_16_no_pii_in_receipt(self):
        x=self._invoke()
        self.assertNotIn('chave_nfe',x)
        self.assertNotIn('cnpj',str(x).lower())
        self.assertNotIn('valor',str(x).lower())
        self.assertNotIn('soap_bytes',x)
        self.assertNotIn('certificado',str(x).lower())

    def test_17_receipt_stable_for_same_inputs(self):
        self.assertEqual(self._invoke(),self._invoke())

    def test_18_no_mutation(self):
        before=self.fixture.report.resultado_json.copy()
        self._invoke()
        self.assertEqual(before,self.fixture.report.resultado_json)
        self.assertEqual(self.fixture.db.writes,0)

    def test_19_missing_db_or_invalid_type(self):
        self._stop('I5_INPUT_INVALID',db=None)
        self._stop('I5_INPUT_INVALID',xml_bytes='xml')
        self._stop('I5_INPUT_INVALID',empresa_id=True)

    def test_20_any_boolean_authority_is_false(self):
        x=self._invoke()
        for k,v in x.items():
            if type(v) is bool:self.assertIs(v,False,k)

    def test_21_i2_bogus_document_evidence_rejected(self):
        with patch('app.services.enterprise_nfe_i5_observation_link.projetar_diagnostico_integral_i2',
                   return_value={'checkout_autorizado':False,'documental_i2':{'estado':'DOCUMENTO_INTERNO_RECONCILIADO',
                                 'xml_sha256':'0'*64,'chave_nfe':i4_fixtures.key('SP'),
                                 'documento_id':10,'relatorio_id':77}}):
            self._stop('I5_PROOF_IDENTITY_MISMATCH')

if __name__ == '__main__':unittest.main()
