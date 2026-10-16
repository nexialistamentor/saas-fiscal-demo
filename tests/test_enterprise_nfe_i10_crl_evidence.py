"""I10: LCR sintéticas e raiz sintética; nunca dados ou consultas reais."""
from datetime import datetime,timedelta,timezone
from copy import deepcopy
import hashlib
import importlib
import unittest
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtensionOID,ObjectIdentifier

import test_enterprise_nfe_i9_chain_anchor as i9f

NOW=i9f.NOW

class TestI10OfflineCRLEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        i9f.TestI9PinnedChain.setUpClass()
        cls.f=i9f.TestI9PinnedChain(methodName='test_00_module_exists')
        cls.leaf_crl=cls.crl('inter')
        cls.middle_crl=cls.crl('root')
        cls.sample=(cls.leaf_crl,cls.middle_crl)

    @classmethod
    def crl(cls,role,*,revoked=None,expired=False,future=False,wrong_issuer=False,
            wrong_key=False,no_number=False,zero_number=False,unknown_critical=False,
            delta=False,idp=False,bad_aki=False,bad_entry=False):
        if role=='inter':
            name=cls.f.int_name;key=cls.f.int_key;issuer_key=cls.f.int_key
        else:
            name=cls.f.root_name;key=cls.f.root_key;issuer_key=cls.f.root_key
        if wrong_key:
            issuer_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        if wrong_issuer:
            name=x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME,'OTHER SYNTHETIC CA')])
        first=NOW-timedelta(days=3) if expired else NOW+timedelta(hours=1) if future else NOW-timedelta(hours=1)
        last=NOW-timedelta(hours=1) if expired else NOW+timedelta(hours=2) if future else NOW+timedelta(hours=1)
        b=(x509.CertificateRevocationListBuilder().issuer_name(name)
           .last_update(first).next_update(last))
        if not no_number:
            b=b.add_extension(x509.CRLNumber(0 if zero_number else 123),critical=False)
        if bad_aki:
            b=b.add_extension(x509.AuthorityKeyIdentifier(b'0'*20,None,None),critical=False)
        else:
            b=b.add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),critical=False)
        if unknown_critical:
            b=b.add_extension(x509.UnrecognizedExtension(ObjectIdentifier('1.2.3.444.5'),b'\x05\x00'),critical=True)
        if delta:
            b=b.add_extension(x509.DeltaCRLIndicator(90),critical=True)
        if idp:
            b=b.add_extension(x509.IssuingDistributionPoint(full_name=None,relative_name=None,
                only_contains_user_certs=False,only_contains_ca_certs=False,
                only_some_reasons=None,indirect_crl=True,only_contains_attribute_certs=False),critical=True)
        if revoked is not None:
            entry=(x509.RevokedCertificateBuilder().serial_number(revoked)
                   .revocation_date(NOW+timedelta(days=2) if future else NOW-timedelta(minutes=15)))
            if bad_entry:
                entry=entry.add_extension(x509.UnrecognizedExtension(ObjectIdentifier('1.2.3.444.6'),b'\x05\x00'),critical=True)
            b=b.add_revoked_certificate(entry.build())
        return b.sign(issuer_key, hashes.SHA256()).public_bytes(serialization.Encoding.DER)

    def module(self):
        try:return importlib.import_module('app.services.enterprise_nfe_i10_crl_evidence')
        except ModuleNotFoundError as exc:
            if exc.name=='app.services.enterprise_nfe_i10_crl_evidence':
                self.fail('I10_RED_CAUSAL_MISSING_MODULE')
            raise

    def runcheck(self,**kwargs):
        raw=self.f.raw
        a=dict(xml_bytes=raw,chave_nfe_esperada=i9f.i8f.key(),
            cnpj_emitente_esperado=i9f.i8f.CNPJ,
            xml_sha256_esperado=hashlib.sha256(raw).hexdigest(),
            intermediarios_der=(self.f.inter,),raiz_confiada_der=self.f.root,
            raiz_sha256_aprovado=self.f.root_sha,instante_referencia_utc=NOW,
            lcrs_der=self.sample,
            lcrs_sha256_aprovados=tuple(hashlib.sha256(c).hexdigest() for c in self.sample))
        a.update(kwargs)
        return self.module().verificar_lcr_nfe_i10(**a)

    def crlcheck(self,crls):
        return self.runcheck(lcrs_der=crls,
            lcrs_sha256_aprovados=tuple(hashlib.sha256(c).hexdigest() for c in crls))

    def failcheck(self,needle,**kwargs):
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,needle):
            self.runcheck(**kwargs)

    def test_00_module_required(self):
        self.assertTrue(callable(self.module().verificar_lcr_nfe_i10))
    def test_01_signed_supplied_crls_not_official(self):
        r=self.runcheck()
        self.assertTrue(r['assinaturas_lcrs_fornecidas_verificadas'])
        self.assertTrue(r['certificados_nao_listados_nas_lcrs_fornecidas'])
        self.assertEqual(r['quantidade_lcrs_avaliadas'],2)
        for n in ('origem_oficial_das_lcrs_verificada','atualidade_externa_das_lcrs_verificada',
                  'revogacao_oficial_global_verificada','politica_icp_brasil_completa_verificada',
                  'cadeia_icp_brasil_verificada','ocsp_verificado','antirreplay_duravel_verificado',
                  'situacao_sefaz_confirmada','direito_creditorio_comprovado','checkout_autorizado'):
            self.assertIs(r[n],False,n)
    def test_02_leaf_revoked_refused(self):
        crls=(self.crl('inter',revoked=30),self.middle_crl)
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_CERTIFICATE_LISTED'):
            self.crlcheck(crls)
    def test_03_intermediate_revoked_refused(self):
        crls=(self.leaf_crl,self.crl('root',revoked=20))
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_CERTIFICATE_LISTED'):
            self.crlcheck(crls)
    def test_04_crl_pin_wrong(self):
        self.failcheck('CRL_DIGEST_MISMATCH',lcrs_sha256_aprovados=('0'*64,hashlib.sha256(self.middle_crl).hexdigest()))
    def test_05_missing_crl_refused(self):
        self.failcheck('INPUT_INVALID',lcrs_der=(self.leaf_crl,))
    def test_06_extra_crl_refused(self):
        self.failcheck('INPUT_INVALID',lcrs_der=self.sample+(self.leaf_crl,))
    def test_07_wrong_issuer(self):
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_ISSUER_MISMATCH'):
            self.crlcheck((self.crl('inter',wrong_issuer=True),self.middle_crl))
    def test_08_wrong_signer(self):
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_SIGNATURE_INVALID'):
            self.crlcheck((self.crl('inter',wrong_key=True),self.middle_crl))
    def test_09_crl_expired(self):
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_REFERENCE_WINDOW_INVALID'):
            self.crlcheck((self.crl('inter',expired=True),self.middle_crl))
    def test_10_crl_future(self):
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_REFERENCE_WINDOW_INVALID'):
            self.crlcheck((self.crl('inter',future=True),self.middle_crl))
    def test_11_crl_missing_number(self):
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_NUMBER_MISSING'):
            self.crlcheck((self.crl('inter',no_number=True),self.middle_crl))
    def test_12_crl_zero_number(self):
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_NUMBER_MISSING'):
            self.crlcheck((self.crl('inter',zero_number=True),self.middle_crl))
    def test_13_bad_authority_key_id(self):
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_AUTHORITY_KEY_MISMATCH'):
            self.crlcheck((self.crl('inter',bad_aki=True),self.middle_crl))
    def test_14_unknown_critical_extension(self):
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_CRITICAL_EXTENSION_UNHANDLED'):
            self.crlcheck((self.crl('inter',unknown_critical=True),self.middle_crl))
    def test_15_delta_crl(self):
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_CRITICAL_EXTENSION_UNHANDLED|CRL_DELTA_UNSUPPORTED'):
            self.crlcheck((self.crl('inter',delta=True),self.middle_crl))
    def test_16_indirect_crl(self):
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_CRITICAL_EXTENSION_UNHANDLED|CRL_INDIRECT_OR_SCOPED_UNSUPPORTED'):
            self.crlcheck((self.crl('inter',idp=True),self.middle_crl))
    def test_17_critical_revocation_entry(self):
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_ENTRY_CRITICAL_UNHANDLED'):
            self.crlcheck((self.crl('inter',revoked=989,bad_entry=True),self.middle_crl))
    def test_18_missing_valid_root(self):
        self.failcheck('I9_CHAIN_NOT_VERIFIED',raiz_sha256_aprovado='f'*64)
    def test_19_document_mismatch(self):
        self.failcheck('I9_CHAIN_NOT_VERIFIED',xml_sha256_esperado='0'*64)
    def test_20_strict_type_checks(self):
        self.failcheck('INPUT_INVALID',lcrs_der=list(self.sample))
        self.failcheck('INPUT_INVALID',lcrs_sha256_aprovados=['a'*64,'a'*64])
        self.failcheck('INPUT_INVALID',instante_referencia_utc=NOW.replace(tzinfo=None))
    def test_21_crl_raw_reject(self):
        fake=b'abc'
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_BYTES_INVALID'):
            self.crlcheck((fake,self.middle_crl))
    def test_22_crl_malformed_der(self):
        fake=b'x'*300
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_DER_INVALID'):
            self.crlcheck((fake,self.middle_crl))
    def test_23_receipt_no_pii(self):
        r=self.runcheck()
        self.assertNotIn(i9f.i8f.key(),str(r));self.assertNotIn(i9f.i8f.CNPJ,str(r))
        self.assertNotIn('lcrs_der',r)
    def test_24_deterministic_and_pure(self):
        a=self.runcheck();b=self.runcheck()
        self.assertEqual(a,b)
    def test_25_network_blocked(self):
        with patch('socket.create_connection',side_effect=AssertionError('NETWORK')):self.runcheck()
    def test_26_duplicate_crls_rejected(self):
        self.failcheck('CRL_DUPLICATED',lcrs_der=(self.leaf_crl,self.leaf_crl),
            lcrs_sha256_aprovados=(hashlib.sha256(self.leaf_crl).hexdigest(),)*2)
    def test_27_self_signed_crl_not_trust(self):
        fake=self.crl('root',revoked=989)
        with self.assertRaisesRegex(self.module().EnterpriseI10CRLError,'CRL_ISSUER_MISMATCH'):
            self.crlcheck((fake,self.middle_crl))

if __name__ == '__main__':unittest.main()
