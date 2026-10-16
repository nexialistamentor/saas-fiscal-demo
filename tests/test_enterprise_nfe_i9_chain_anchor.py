"""I9: cadeia RSA sintética, âncora explícita pinada, sem raízes ICP nem rede."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import importlib
import unittest
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.x509.oid import NameOID, ObjectIdentifier
from lxml import etree
import test_enterprise_nfe_i8_signer_identity as i8f

NOW=datetime(2026,10,16,15,0,tzinfo=timezone.utc)
DS='{http://www.w3.org/2000/09/xmldsig#}'

class TestI9PinnedChain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.int_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.leaf_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.root_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'RAIZ SINTETICA SEM ICP')])
        cls.int_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'INTERMEDIARIA SINTETICA')])
        cls.leaf_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'EMITENTE SINTETICO')])
        cls.root=cls.cert('root')
        cls.inter=cls.cert('inter')
        cls.leaf=cls.cert('leaf')
        i8f.TestI8SignerIdentity.setUpClass()
        cls.raw=cls.xml_for(cls.leaf)
        cls.root_sha=hashlib.sha256(cls.root).hexdigest()

    @classmethod
    def cert(cls,role,*,bad_ca=False,bad_key_usage=False,expired=False,bad_parent=False,pathlen=None,unknown_critical=False):
        if role=='root':
            subject=cls.root_name;issuer=cls.root_name;key=cls.root_key;issuer_key=cls.root_key;ca=True;count=10
        elif role=='inter':
            subject=cls.int_name;issuer=cls.root_name if not bad_parent else cls.int_name
            key=cls.int_key;issuer_key=cls.root_key;ca=not bad_ca;count=20
        else:
            subject=cls.leaf_name;issuer=cls.int_name if not bad_parent else cls.root_name
            key=cls.leaf_key;issuer_key=cls.int_key;ca=False;count=30
        start=NOW-timedelta(days=3) if expired else NOW-timedelta(days=1)
        end=NOW-timedelta(days=2) if expired else NOW+timedelta(days=2)
        b=(x509.CertificateBuilder().subject_name(subject).issuer_name(issuer)
             .public_key(key.public_key()).serial_number(count)
             .not_valid_before(start).not_valid_after(end)
             .add_extension(x509.BasicConstraints(ca=ca,path_length=pathlen if ca else None),critical=True)
             .add_extension(x509.KeyUsage(digital_signature=not ca,content_commitment=False,
                key_encipherment=False,data_encipherment=False,key_agreement=False,
                key_cert_sign=ca and not bad_key_usage,crl_sign=ca,
                encipher_only=False,decipher_only=False),critical=True)
             .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),critical=False))
        if role=='leaf':
            b=b.add_extension(x509.SubjectAlternativeName([
                x509.OtherName(ObjectIdentifier('2.16.76.1.3.3'),bytes([0x13,14])+i8f.CNPJ.encode())
            ]),critical=False)
        if unknown_critical:
            b=b.add_extension(x509.UnrecognizedExtension(ObjectIdentifier('1.2.3.4.556677'),b'\x05\x00'),critical=True)
        b=b.add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()),critical=False)
        return b.sign(issuer_key,hashes.SHA256()).public_bytes(serialization.Encoding.DER)

    @classmethod
    def xml_for(cls,leaf_der):
        root=etree.fromstring(i8f.TestI8SignerIdentity.build())
        cert=root.find('.//'+DS+'X509Certificate')
        cert.text=base64.b64encode(leaf_der).decode()
        signed=root.find('.//'+DS+'SignedInfo')
        signature=root.find('.//'+DS+'SignatureValue')
        signature.text=base64.b64encode(cls.leaf_key.sign(
            i8f.c14n(signed),padding.PKCS1v15(),hashes.SHA256())).decode()
        return etree.tostring(root,encoding='utf-8',xml_declaration=True)

    def module(self):
        try:return importlib.import_module('app.services.enterprise_nfe_i9_chain_anchor')
        except ModuleNotFoundError as exc:
            if exc.name=='app.services.enterprise_nfe_i9_chain_anchor':unittest.TestCase.fail(self,'I9_RED_CAUSAL_MISSING_MODULE')
            raise

    def runcheck(self,**kwargs):
        a=dict(xml_bytes=self.raw,chave_nfe_esperada=i8f.key(),
               cnpj_emitente_esperado=i8f.CNPJ,xml_sha256_esperado=hashlib.sha256(self.raw).hexdigest(),
               intermediarios_der=(self.inter,),raiz_confiada_der=self.root,
               raiz_sha256_aprovado=self.root_sha,instante_referencia_utc=NOW)
        a.update(kwargs)
        return self.module().verificar_cadeia_nfe_i9(**a)

    def expect_stop(self,needle,**kwargs):
        with self.assertRaisesRegex(self.module().EnterpriseI9ChainError,needle):
            self.runcheck(**kwargs)

    def test_00_module_exists(self):self.assertTrue(callable(self.module().verificar_cadeia_nfe_i9))
    def test_01_chain_verifies_but_icp_remains_false(self):
        r=self.runcheck()
        self.assertTrue(r['cadeia_assinaturas_ate_ancora_pinada_verificada'])
        self.assertTrue(r['assinatura_xml_i7_e_identidade_i8_verificadas'])
        self.assertEqual(r['intermediarios'],1)
        for k in ('cadeia_icp_brasil_verificada','revogacao_crl_ocsp_verificada',
                  'situacao_sefaz_confirmada','checkout_autorizado','apuracao_mensal_completa',
                  'direito_creditorio_comprovado','politicas_icp_brasil_e_caminho_rfc5280_completos'):
            self.assertIs(r[k],False,k)
    def test_02_root_wrong_pin(self):self.expect_stop('ROOT_PIN_MISMATCH',raiz_sha256_aprovado='0'*64)
    def test_03_root_not_a_der_cert(self):self.expect_stop('CERT_DER_SIZE_INVALID',raiz_confiada_der=b'fake',raiz_sha256_aprovado=hashlib.sha256(b'fake').hexdigest())
    def test_04_missing_intermediate(self):self.expect_stop('CHAIN_ISSUER_SUBJECT_MISMATCH',intermediarios_der=())
    def test_05_wrong_intermediate(self):
        alt=self.cert('inter',bad_parent=True)
        self.expect_stop('CHAIN_ISSUER_SUBJECT_MISMATCH',intermediarios_der=(alt,))
    def test_06_middle_signature_forged(self):
        k=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        alt=(x509.CertificateBuilder().subject_name(self.int_name).issuer_name(self.root_name)
             .public_key(self.int_key.public_key()).serial_number(25)
             .not_valid_before(NOW-timedelta(days=1)).not_valid_after(NOW+timedelta(days=1))
             .add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True)
             .add_extension(x509.KeyUsage(digital_signature=False,content_commitment=False,
                  key_encipherment=False,data_encipherment=False,key_agreement=False,key_cert_sign=True,
                  crl_sign=True,encipher_only=False,decipher_only=False),critical=True)
             .sign(k,hashes.SHA256()).public_bytes(serialization.Encoding.DER))
        self.expect_stop('CHAIN_CERT_SIGNATURE_INVALID',intermediarios_der=(alt,))
    def test_07_intermediate_ca_flag_false(self):self.expect_stop('CA_NOT_AUTHORIZED_TO_SIGN',intermediarios_der=(self.cert('inter',bad_ca=True),))
    def test_08_intermediate_wrong_key_usage(self):self.expect_stop('CA_NOT_AUTHORIZED_TO_SIGN',intermediarios_der=(self.cert('inter',bad_key_usage=True),))
    def test_09_intermediate_expired(self):self.expect_stop('CERT_REFERENCE_TIME_INVALID',intermediarios_der=(self.cert('inter',expired=True),))
    def test_10_root_path_len_zero_blocks_intermediate(self):
        root=self.cert('root',pathlen=0)
        self.expect_stop('CA_PATH_LENGTH_EXCEEDED',raiz_confiada_der=root,raiz_sha256_aprovado=hashlib.sha256(root).hexdigest())
    def test_11_unhandled_critical_ca_extension(self):self.expect_stop('CA_CRITICAL_EXTENSION_UNHANDLED',intermediarios_der=(self.cert('inter',unknown_critical=True),))
    def test_12_leaf_signature_modified(self):
        raw=self.raw.replace(b'2026-10-16T14:00',b'2026-10-16T13:00')
        self.expect_stop('I8_IDENTITY_NOT_VERIFIED',xml_bytes=raw,xml_sha256_esperado=hashlib.sha256(raw).hexdigest())
    def test_13_wrong_emit_cnpj(self):self.expect_stop('I8_IDENTITY_NOT_VERIFIED',cnpj_emitente_esperado='11444777000161')
    def test_14_bad_input_list(self):self.expect_stop('INPUT_INVALID',intermediarios_der=[self.inter])
    def test_15_too_many_ca(self):self.expect_stop('INPUT_INVALID',intermediarios_der=(self.inter,)*6)
    def test_16_time_no_timezone(self):self.expect_stop('INPUT_INVALID',instante_referencia_utc=NOW.replace(tzinfo=None))
    def test_17_future_expired_time(self):self.expect_stop('CERT_REFERENCE_TIME_INVALID',instante_referencia_utc=NOW+timedelta(days=365))
    def test_18_repeat_root(self):self.expect_stop('CHAIN_REPEATED_CERTIFICATE',intermediarios_der=(self.root,))
    def test_19_no_personal_data_in_receipt(self):
        r=self.runcheck();self.assertNotIn(i8f.CNPJ,str(r));self.assertNotIn(i8f.key(),str(r));self.assertNotIn('certificado_der',r)
    def test_20_result_deterministic(self):self.assertEqual(self.runcheck(),self.runcheck())
    def test_21_wrong_xml_digest(self):self.expect_stop('I8_IDENTITY_NOT_VERIFIED',xml_sha256_esperado='1'*64)
    def test_22_root_not_self_issued(self):
        other=self.cert('inter')
        self.expect_stop('ROOT_NOT_SELF_ISSUED',intermediarios_der=(),raiz_confiada_der=other,raiz_sha256_aprovado=hashlib.sha256(other).hexdigest())
    def test_23_network_never_called(self):
        with patch('socket.create_connection',side_effect=AssertionError('NETWORK')):self.runcheck()

if __name__=='__main__':unittest.main()
