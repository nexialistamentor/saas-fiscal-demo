"""I11: aquisição/custódia LCR puramente sintética; nenhuma raiz ITI real."""
from copy import deepcopy
from datetime import timedelta
import base64
import hashlib
import importlib
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

import test_enterprise_nfe_i10_crl_evidence as i10fixture

NOW = i10fixture.NOW
ZERO = '0'*64

class TestI11SignedCRLProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        i10fixture.TestI10OfflineCRLEvidence.setUpClass()

    def setUp(self):
        self.base=i10fixture.TestI10OfflineCRLEvidence(methodName='test_00_module_required')
        self.priv=Ed25519PrivateKey.from_private_bytes(b'\xa6'*32)  # fixture exclusiva de teste
        self.pub=self.priv.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self.i10args=self.args()

    def module(self):
        try:
            return importlib.import_module('app.services.enterprise_nfe_i11_crl_provenance')
        except ModuleNotFoundError as exc:
            if exc.name=='app.services.enterprise_nfe_i11_crl_provenance':
                self.fail('I11_RED_CAUSAL_MISSING_MODULE')
            raise

    def args(self):
        b=self.base
        raw=b.f.raw
        return dict(xml_bytes=raw,chave_nfe_esperada=i10fixture.i9f.i8f.key(),
             cnpj_emitente_esperado=i10fixture.i9f.i8f.CNPJ,
             xml_sha256_esperado=hashlib.sha256(raw).hexdigest(),
             intermediarios_der=(b.f.inter,),raiz_confiada_der=b.f.root,
             raiz_sha256_aprovado=b.f.root_sha,instante_referencia_utc=NOW,
             lcrs_der=b.sample,
             lcrs_sha256_aprovados=tuple(hashlib.sha256(x).hexdigest() for x in b.sample))

    def sign(self,data):
        manifest=deepcopy(data);manifest.pop('assinatura_ed25519_base64',None)
        manifest['assinatura_ed25519_base64']=base64.b64encode(
            self.priv.sign(self.module()._signed_bytes(manifest))).decode('ascii')
        return manifest

    def manifest(self,**mods):
        m=self.module()
        i10=self.base.runcheck()
        a=dict(schema_version=m.SCHEMA,
               issuer='CUSTODIANTE_EXTERNO_CONTROLADO',scope='SOLVERIS_ENTERPRISE_NFE_LCR',
               event_id='550e8400-e29b-41d4-a716-446655440000',
               sequencia=1,manifesto_anterior_sha256=ZERO,
               chave_publica_sha256=hashlib.sha256(self.pub).hexdigest(),
               observado_em_utc='2026-10-16T15:00:00Z',
               xml_sha256=i10['xml_sha256'],chave_sha256=i10['chave_sha256'],
               recibo_i10_sha256=hashlib.sha256(m._json_bytes(i10)).hexdigest(),
               raiz_sha256=i10['raiz_aprovada_sha256'],
               lcrs=m._crl_items(self.i10args['lcrs_der'], self.i10args['lcrs_sha256_aprovados']),
               declaracao_procedencia=m._DECLARATION)
        a.update(mods)
        return self.sign(a)

    def runcheck(self,**mods):
        data=dict(parametros_i10=self.i10args,manifesto=self.manifest(),
                  trusted_public_key=self.pub,estado_previo_aprovado=None,agora_utc=NOW)
        data.update(mods)
        return self.module().conferir_proveniencia_lcr_i11(**data)

    def failcheck(self,reason,**mods):
        with self.assertRaisesRegex(self.module().EnterpriseI11ProvenanceError,reason):
            self.runcheck(**mods)

    def continuation(self,mutate=None):
        prior=self.runcheck()['estado_proposto_para_custodia_externa']
        manifest=self.manifest(sequencia=2,manifesto_anterior_sha256=prior['manifesto_sha256'])
        if mutate:mutate(prior,manifest)
        return prior,self.sign(manifest)

    def test_00_module_required(self):
        self.assertTrue(callable(self.module().conferir_proveniencia_lcr_i11))
    def test_01_valid_synthetic_signature_no_official_authority(self):
        r=self.runcheck()
        self.assertTrue(r['assinatura_custodiante_verificada'])
        self.assertFalse(r['comparacao_rollback_com_estado_fornecido'])
        for key in ('origem_oficial_iti_verificada','estado_previo_autenticado_pelo_modulo',
            'antirollback_duravel_verificado','temporalidade_externa_autenticada',
            'cadeia_icp_brasil_verificada','revogacao_oficial_global_verificada',
            'situacao_sefaz_confirmada','efd_competencia_reconciliada',
            'apuracao_mensal_completa','direito_creditorio_comprovado','checkout_autorizado'):
            self.assertIs(r[key],False,key)
    def test_02_sequence_and_proposed_state(self):
        r=self.runcheck();self.assertEqual(r['sequencia'],1)
        self.assertEqual(r['estado_proposto_para_custodia_externa']['sequencia'],1)
        self.assertEqual(len(r['estado_proposto_para_custodia_externa']['lcrs']),2)
    def test_03_signed_continuation(self):
        previous,manifest=self.continuation()
        r=self.runcheck(manifesto=manifest,estado_previo_aprovado=previous)
        self.assertTrue(r['comparacao_rollback_com_estado_fornecido'])
        self.assertEqual(r['sequencia'],2)
        self.assertFalse(r['antirollback_duravel_verificado'])
    def test_04_tampered_crl_hash_in_manifest(self):
        m=self.manifest();m['lcrs'][0]['der_sha256']='f'*64
        self.failcheck('MANIFEST_SIGNATURE_INVALID',manifesto=m)
    def test_05_tampered_signed_manifest(self):
        m=self.manifest();m['raiz_sha256']='f'*64
        self.failcheck('MANIFEST_SIGNATURE_INVALID',manifesto=m)
    def test_06_wrong_key(self):
        k=Ed25519PrivateKey.from_private_bytes(b'\xa7'*32)
        pub=k.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self.failcheck('CUSTODIAN_KEY_MISMATCH',trusted_public_key=pub)
    def test_07_short_key(self):self.failcheck('INPUT_INVALID',trusted_public_key=b'a')
    def test_08_bad_signature_encoding(self):
        m=self.manifest();m['assinatura_ed25519_base64']='x'
        self.failcheck('MANIFEST_SIGNATURE_FORMAT_INVALID',manifesto=m)
    def test_09_bad_signature_crypto(self):
        m=self.manifest();m['assinatura_ed25519_base64']=base64.b64encode(bytes(64)).decode()
        self.failcheck('MANIFEST_SIGNATURE_INVALID',manifesto=m)
    def test_10_extra_manifest_field(self):
        m=self.manifest();m['official']=True
        self.failcheck('MANIFEST_SCHEMA_INVALID',manifesto=m)
    def test_11_missing_manifest_field(self):
        m=self.manifest();del m['lcrs']
        self.failcheck('MANIFEST_SCHEMA_INVALID',manifesto=m)
    def test_12_source_claim_untrusted(self):
        self.failcheck('MANIFEST_CLAIMS_INVALID',manifesto=self.manifest(declaracao_procedencia='ITI_CERTIFIED'))
    def test_13_future_manifest(self):
        self.failcheck('MANIFEST_TIME_EXPIRED_OR_FUTURE',agora_utc=NOW-timedelta(seconds=1))
    def test_14_expired_manifest(self):
        self.failcheck('MANIFEST_TIME_EXPIRED_OR_FUTURE',agora_utc=NOW+timedelta(minutes=6))
    def test_15_utc_required(self):
        self.failcheck('INPUT_INVALID',agora_utc=NOW.replace(tzinfo=None))
    def test_16_wrong_document_digest_even_signed(self):
        self.failcheck('MANIFEST_EVIDENCE_IDENTITY_MISMATCH',manifesto=self.manifest(xml_sha256='b'*64))
    def test_17_different_crl_pins_even_signed(self):
        m=self.manifest();m['lcrs'][0]['der_sha256']='b'*64
        self.failcheck('MANIFEST_EVIDENCE_IDENTITY_MISMATCH',manifesto=self.sign(m))
    def test_18_wrong_crl_number_even_signed(self):
        m=self.manifest();m['lcrs'][0]['numero']+=1
        self.failcheck('MANIFEST_EVIDENCE_IDENTITY_MISMATCH',manifesto=self.sign(m))
    def test_19_signed_wrong_i10_hash(self):
        self.failcheck('MANIFEST_EVIDENCE_IDENTITY_MISMATCH',manifesto=self.manifest(recibo_i10_sha256='c'*64))
    def test_20_bootstrap_sequence_not_one(self):
        self.failcheck('PREVIOUS_STATE_MISSING',manifesto=self.manifest(sequencia=2))
    def test_21_predecessor_missing_on_continue(self):
        _,m=self.continuation();self.failcheck('PREVIOUS_STATE_MISSING',manifesto=m)
    def test_22_sequence_reuse_denied(self):
        p,m=self.continuation();m=self.manifest(sequencia=1,manifesto_anterior_sha256=p['manifesto_sha256'])
        self.failcheck('ROLLBACK_SEQUENCE_OR_ROOT_INVALID',manifesto=m,estado_previo_aprovado=p)
    def test_23_wrong_previous_digest(self):
        p,m=self.continuation();p['manifesto_sha256']='f'*64
        self.failcheck('ROLLBACK_SEQUENCE_OR_ROOT_INVALID',manifesto=m,estado_previo_aprovado=p)
    def test_24_crl_number_rollback(self):
        p,m=self.continuation();p['lcrs'][0]['numero']+=1
        self.failcheck('CRL_ROLLBACK_DETECTED',manifesto=m,estado_previo_aprovado=p)
    def test_25_same_number_different_bytes(self):
        p,m=self.continuation();p['lcrs'][0]['der_sha256']='a'*64
        self.failcheck('CRL_SAME_NUMBER_DIFFERENT_BYTES',manifesto=m,estado_previo_aprovado=p)
    def test_26_root_changed_from_previous(self):
        p,m=self.continuation();p['raiz_sha256']='a'*64
        self.failcheck('ROLLBACK_SEQUENCE_OR_ROOT_INVALID',manifesto=m,estado_previo_aprovado=p)
    def test_27_invalid_prior_state(self):
        p,m=self.continuation();p['sequencia']=True
        self.failcheck('PREVIOUS_STATE_INVALID',manifesto=m,estado_previo_aprovado=p)
    def test_28_missing_lcr_from_i10(self):
        p=dict(self.i10args);p['lcrs_der']=p['lcrs_der'][:1]
        self.failcheck('I10_EVIDENCE_NOT_VERIFIED',parametros_i10=p)
    def test_29_no_pii_output(self):
        r=str(self.runcheck())
        self.assertNotIn(i10fixture.i9f.i8f.CNPJ,r)
        self.assertNotIn(i10fixture.i9f.i8f.key(),r)
        self.assertNotIn('assinatura_ed25519_base64',r)
        self.assertNotIn('private_key',r)
    def test_30_no_network_and_determinism(self):
        with patch('socket.create_connection',side_effect=AssertionError('NO NETWORK')):
            a=self.runcheck();b=self.runcheck();self.assertEqual(a,b)
    def test_31_bad_reference_state_no_prior(self):
        self.failcheck('PREVIOUS_STATE_MISSING',manifesto=self.manifest(manifesto_anterior_sha256='a'*64))

if __name__ == '__main__':unittest.main()
