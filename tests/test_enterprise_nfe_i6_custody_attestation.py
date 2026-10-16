"""I6 contrato: custodiante externo com Ed25519; sem SEFAZ, DB, XML real ou certificados."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import importlib
import unittest
from unittest.mock import patch
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

import test_enterprise_nfe_i5_observation_link as i5_fixture
import test_enterprise_nfe_sefaz_operador_i4n as i4_fixture


NOW = datetime(2026, 10, 16, 19, 0, tzinfo=timezone.utc)


class TestEnterpriseI6CustodyAttestation(unittest.TestCase):
    def setUp(self):
        self.base = i5_fixture.TestEnterpriseI5ObservationLink(methodName='test_00_adapter_exists')
        self.base.setUp()
        self.xml = self.base.fixture.raw
        self.soap = i4_fixture.soap(i4_fixture.key('SP'))
        # Apenas fixture sintética; nunca uma chave assinadora de produção.
        self.priv = Ed25519PrivateKey.from_private_bytes(b'\x91'*32)
        self.pub = self.priv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
        try:
            self.module = importlib.import_module('app.services.enterprise_nfe_i6_custody_attestation')
        except ModuleNotFoundError as e:
            if e.name == 'app.services.enterprise_nfe_i6_custody_attestation':
                self.fail('I6_RED_CAUSAL_MISSING_MODULE')
            raise
        self.att = self._attestation()

    def _linked(self):
        return self.base._invoke()

    def _attestation(self, soap=None):
        s = self.soap if soap is None else soap
        with patch('app.services.tax_engines.pis_cofins_engine.calcular_pis_cofins',
                   return_value={'tributos':{'pis':15.18,'cofins':69.92}}):
            from app.services.enterprise_nfe_i5_observation_link import vincular_observacao_nfe_i5
            linked = vincular_observacao_nfe_i5(
                db=self.base.fixture.db, authenticated_user_id=7, empresa_id=41,
                relatorio_id=77, xml_bytes=self.xml, resposta_soap=s)
        v = dict(
            schema_version=self.module.SCHEMA,
            issuer='SOLVERIS_ENTERPRISE_EXPLICIT_EXTERNAL_CUSTODIAN',
            scope='ENTERPRISE_ONLY_SINGLE_NFE_OBSERVATION',
            event_id='550e8400-e29b-41d4-a716-446655440000',
            public_key_sha256=hashlib.sha256(self.pub).hexdigest(),
            observed_at_utc='2026-10-16T18:59:00Z',
            xml_sha256=linked['xml_sha256'], chave_sha256=linked['chave_sha256'],
            resposta_soap_sha256=linked['resposta_soap_sha256'],
            endpoint_sha256=hashlib.sha256(linked['endpoint_catalogado'].encode()).hexdigest(),
            autorizador=linked['autorizador_catalogado'],uf_emissora=linked['uf_emissora_chave'],
            certificate_der_sha256='a'*64,
            tls_validation_declaration='TLS_VALIDATION_DECLARED_BY_CUSTODIAN_NOT_INDEPENDENTLY_PROVEN',
            client_certificate_declared=True,
        )
        return self._sign(v)

    def _sign(self, v):
        a=dict(v)
        a.pop('signature_ed25519_b64',None)
        signature = self.priv.sign(self.module._signing_bytes(a))
        a['signature_ed25519_b64'] = base64.b64encode(signature).decode('ascii')
        return a

    def _run(self, **changes):
        inp = dict(db=self.base.fixture.db, authenticated_user_id=7,
                   empresa_id=41, relatorio_id=77, xml_bytes=self.xml,
                   resposta_soap=self.soap, atestado=self.att,
                   trusted_public_key=self.pub, now_utc=NOW)
        inp.update(changes)
        with patch('app.services.tax_engines.pis_cofins_engine.calcular_pis_cofins',
                   return_value={'tributos':{'pis':15.18,'cofins':69.92}}):
            return self.module.vincular_custodia_nfe_i6(**inp)

    def _fail(self, reason, **changes):
        with self.assertRaisesRegex(self.module.EnterpriseI6CustodyError, reason):
            self._run(**changes)

    def test_00_module_required(self):
        self.assertTrue(callable(self.module.vincular_custodia_nfe_i6))

    def test_01_valid_signed_record_not_sefaz_proof(self):
        r=self._run()
        self.assertTrue(r['assinatura_custodiante_verificada'])
        for f in ('origem_sefaz_criptograficamente_comprovada','tls_mtls_comprovado_independentemente',
                  'assinatura_xml_nfe_verificada','situacao_sefaz_confirmada',
                  'efd_competencia_reconciliada','apuracao_mensal_completa',
                  'direito_creditorio_comprovado','checkout_autorizado'):
            self.assertIs(r[f],False,f)
        self.assertEqual(self.base.fixture.db.writes,0)

    def test_02_signature_tampered(self):
        a=deepcopy(self.att);a['uf_emissora']='RJ'
        self._fail('SIGNATURE_INVALID',atestado=a)

    def test_03_untrusted_key_rejected(self):
        key=Ed25519PrivateKey.from_private_bytes(b'\x92'*32)
        pub=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self._fail('TRUST_ANCHOR_DIGEST_MISMATCH',trusted_public_key=pub)

    def test_04_short_pubkey_rejected(self):
        self._fail('TRUST_ANCHOR_OR_CLOCK_INVALID',trusted_public_key=b'a'*16)

    def test_05_unsigned_rejected(self):
        a=dict(self.att);a['signature_ed25519_b64']=''
        self._fail('SIGNATURE_FORMAT_INVALID',atestado=a)

    def test_06_expired_receipt(self):
        self._fail('EXPIRED_OR_FUTURE',now_utc=NOW+timedelta(minutes=6))

    def test_07_future_receipt(self):
        self._fail('EXPIRED_OR_FUTURE',now_utc=NOW-timedelta(minutes=2))

    def test_08_time_no_tz(self):
        self._fail('CLOCK_INVALID',now_utc=NOW.replace(tzinfo=None))

    def test_09_invalid_signed_date(self):
        a=dict(self.att);a['observed_at_utc']='2026-10-16T18:59:00-03:00';a=self._sign(a)
        self._fail('TIME_FORMAT_INVALID',atestado=a)

    def test_10_extra_field_denied(self):
        a=dict(self.att);a['origem_sefaz_confirmada']=True
        self._fail('SCHEMA_INVALID',atestado=a)

    def test_11_missing_field_denied(self):
        a=dict(self.att);del a['certificate_der_sha256']
        self._fail('SCHEMA_INVALID',atestado=a)

    def test_12_wrong_scope(self):
        a=self._sign({**self.att,'scope':'MEI'})
        self._fail('CUSTODIAN_CLAIMS_INVALID',atestado=a)

    def test_13_wrong_issuer(self):
        a=self._sign({**self.att,'issuer':'SELF_ISSUED'})
        self._fail('CUSTODIAN_CLAIMS_INVALID',atestado=a)

    def test_14_incomplete_tls_declaration(self):
        a=self._sign({**self.att,'client_certificate_declared':False})
        self._fail('CUSTODIAN_CLAIMS_INVALID',atestado=a)

    def test_15_signed_other_soap_denied(self):
        self._fail('IDENTITY_MISMATCH',atestado=self._attestation(i4_fixture.soap(i4_fixture.key('SP'),'101')))

    def test_16_xml_bytes_changed_denied(self):
        self._fail('I5_NOT_VERIFIED',xml_bytes=self.xml.replace(b'1000.00',b'2000.00'))

    def test_17_wrong_db_owner_denied(self):
        self._fail('I5_NOT_VERIFIED',authenticated_user_id=9)

    def test_18_wrong_report_denied(self):
        self._fail('I5_NOT_VERIFIED',relatorio_id=9)

    def test_19_wrong_endpoint_digest_even_if_signed(self):
        a=self._sign({**self.att,'endpoint_sha256':'b'*64})
        self._fail('IDENTITY_MISMATCH',atestado=a)

    def test_20_wrong_certificate_digest_format(self):
        a=self._sign({**self.att,'certificate_der_sha256':'short'})
        self._fail('DIGEST_FORMAT_INVALID',atestado=a)

    def test_21_wrong_event_uuid(self):
        a=self._sign({**self.att,'event_id':'not-a-uuid'})
        self._fail('EVENT_ID_INVALID',atestado=a)

    def test_22_noncanonical_signature(self):
        a=dict(self.att);a['signature_ed25519_b64']='!'*88
        self._fail('SIGNATURE_INVALID',atestado=a)

    def test_23_synthetically_cancelled_never_authority(self):
        soap=i4_fixture.soap(i4_fixture.key('SP'),'101')
        att=self._attestation(soap)
        r=self._run(resposta_soap=soap,atestado=att)
        self.assertFalse(r['situacao_sefaz_confirmada'])
        self.assertFalse(r['checkout_autorizado'])

    def test_24_no_pii_or_raw_bytes_in_receipt(self):
        r=self._run()
        self.assertNotIn('chave_nfe',r)
        self.assertNotIn('cnpj',str(r).lower())
        self.assertNotIn('certificate_der_sha256',r)
        self.assertNotIn('signature_ed25519_b64',r)
        self.assertNotIn('soap_bytes',r)
        self.assertNotIn('valor',str(r).lower())

    def test_25_receipt_deterministic(self):
        self.assertEqual(self._run(),self._run())

    def test_26_input_not_mutated(self):
        original=deepcopy(self.att)
        originalreport=deepcopy(self.base.fixture.report.resultado_json)
        self._run()
        self.assertEqual(self.att,original)
        self.assertEqual(self.base.fixture.report.resultado_json,originalreport)

    def test_27_hash_not_sufficient_without_signature(self):
        a=dict(self.att)
        a['signature_ed25519_b64']=base64.b64encode(bytes(64)).decode()
        self._fail('SIGNATURE_INVALID',atestado=a)


if __name__=='__main__': unittest.main()
