"""I7: provas sinteticas RSA-SHA1/RSA-SHA256; NUNCA NF-e real, SEFAZ ou BD."""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import unittest
from copy import deepcopy
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from lxml import etree

NS = 'http://www.portalfiscal.inf.br/nfe'
DS = 'http://www.w3.org/2000/09/xmldsig#'
N = '{'+NS+'}'
D = '{'+DS+'}'
CAN = 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
ENV = DS+'enveloped-signature'
RSA1=DS+'rsa-sha1'
DIG1=DS+'sha1'
RSA256='http://www.w3.org/2001/04/xmldsig-more#rsa-sha256'
DIG256='http://www.w3.org/2001/04/xmlenc#sha256'


def key(model='55'):
    raw='35'+'2610'+'12345678000123'+model+'001'+'000000001'+'1'+'00000001'
    s=sum(int(c)*(2+(i%8)) for i,c in enumerate(reversed(raw)))%11
    return raw+str(0 if s<2 else 11-s)


def canonical(n):
    return etree.tostring(deepcopy(n),method='c14n',exclusive=False,with_comments=False)


class TestI7NFeXmlSignature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        now=datetime(2026,10,16,tzinfo=timezone.utc)
        issuer=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'TESTE SINTETICO NAO CONFIAVEL')])
        cert=(x509.CertificateBuilder().subject_name(issuer).issuer_name(issuer)
              .public_key(cls.private.public_key()).serial_number(1234567)
              .not_valid_before(now-timedelta(days=90))
              .not_valid_after(now+timedelta(days=90))
              .sign(cls.private,hashes.SHA256()))
        cls.cert=cert.public_bytes(serialization.Encoding.DER)
        cls.xml256=cls.make_xml('sha256')
        cls.xml1=cls.make_xml('sha1')

    @classmethod
    def make_xml(cls,mode='sha256',noncanonical=False):
        algo=hashes.SHA256 if mode=='sha256' else hashes.SHA1
        hashfun=hashlib.sha256 if mode=='sha256' else hashlib.sha1
        sm=RSA256 if mode=='sha256' else RSA1
        dm=DIG256 if mode=='sha256' else DIG1
        root=etree.Element(N+'nfeProc',nsmap={None:NS})
        nfe=etree.SubElement(root,N+'NFe')
        inf=etree.SubElement(nfe,N+'infNFe',Id='NFe'+key(),versao='4.00')
        ide=etree.SubElement(inf,N+'ide')
        etree.SubElement(ide,N+'mod').text='55'
        etree.SubElement(ide,N+'tpNF').text='1'
        etree.SubElement(ide,N+'dhEmi').text='2026-09-15T10:00:00-03:00'
        sign=etree.SubElement(nfe,D+'Signature',nsmap={None:DS})
        signed=etree.SubElement(sign,D+'SignedInfo')
        etree.SubElement(signed,D+'CanonicalizationMethod',Algorithm=CAN)
        etree.SubElement(signed,D+'SignatureMethod',Algorithm=sm)
        ref=etree.SubElement(signed,D+'Reference',URI='#NFe'+key())
        trans=etree.SubElement(ref,D+'Transforms')
        etree.SubElement(trans,D+'Transform',Algorithm=ENV)
        etree.SubElement(trans,D+'Transform',Algorithm=CAN)
        etree.SubElement(ref,D+'DigestMethod',Algorithm=dm)
        etree.SubElement(ref,D+'DigestValue').text=base64.b64encode(hashfun(canonical(inf)).digest()).decode('ascii')
        etree.SubElement(sign,D+'SignatureValue').text=base64.b64encode(cls.private.sign(canonical(signed),padding.PKCS1v15(),algo())).decode('ascii')
        info=etree.SubElement(sign,D+'KeyInfo')
        x509data=etree.SubElement(info,D+'X509Data')
        etree.SubElement(x509data,D+'X509Certificate').text=base64.b64encode(cls.cert).decode('ascii')
        prot=etree.SubElement(root,N+'protNFe')
        etree.SubElement(prot,N+'chNFe').text=key()
        return etree.tostring(root,encoding='utf-8',xml_declaration=True)

    def module(self):
        try: return importlib.import_module('app.services.enterprise_nfe_i7_xml_signature')
        except ModuleNotFoundError as exc:
            if exc.name=='app.services.enterprise_nfe_i7_xml_signature':
                self.fail('I7_RED_CAUSAL_MODULE_MISSING')
            raise

    def runcheck(self,raw=None,chave=None,digest=None):
        raw=self.xml256 if raw is None else raw
        return self.module().verificar_assinatura_nfe_i7(xml_bytes=raw,
                 chave_nfe_esperada=key() if chave is None else chave,
                 xml_sha256_esperado=hashlib.sha256(raw).hexdigest() if digest is None else digest)

    def failcheck(self,code,raw=None,**kwargs):
        with self.assertRaisesRegex(self.module().EnterpriseI7SignatureError,code):
            self.runcheck(raw,**kwargs)

    def rewrite(self,func,raw=None):
        x=etree.fromstring(self.xml256 if raw is None else raw)
        func(x)
        return etree.tostring(x,encoding='utf-8')

    def test_00_module_required(self):
        self.assertTrue(callable(self.module().verificar_assinatura_nfe_i7))

    def test_01_real_rsa_sha256_mathematical_verification_only(self):
        r=self.runcheck()
        self.assertTrue(r['assinatura_matematica_verificada'])
        self.assertTrue(r['digest_infNFe_verificado'])
        self.assertEqual(r['algoritmo_observado'],'RSA_SHA256')
        self.assertEqual(r['uf_emissora_chave'],'SP')
        self.assertFalse(r['situacao_sefaz_confirmada'])
        self.assertFalse(r['cadeia_icp_brasil_verificada'])
        self.assertFalse(r['checkout_autorizado'])

    def test_02_legacy_rsa_sha1_detected_and_not_authority(self):
        r=self.runcheck(self.xml1)
        self.assertEqual(r['algoritmo_observado'],'RSA_SHA1_LEGADO_COLISAO_RISCO')
        self.assertFalse(r['cadeia_icp_brasil_verificada'])

    def test_03_different_xml_hash_denied(self):
        self.failcheck('XML_SHA256_MISMATCH',digest='a'*64)

    def test_04_inf_nfe_tampered_ref_digest_denied(self):
        raw=self.rewrite(lambda x:setattr(x.find('.//'+N+'mod'),'text','65'))
        self.failcheck('REFERENCE_DIGEST_INVALID',raw)

    def test_05_signedinfo_tampered_denied(self):
        raw=self.rewrite(lambda x: x.find('.//'+D+'SignatureMethod').set('Extra','tamper'))
        self.failcheck('SIGNATURE_VALUE_INVALID',raw)

    def test_06_signature_corrupted_denied(self):
        def tamper(x):
            el=x.find('.//'+D+'SignatureValue');t=el.text;el.text=('A' if t[0]!='A' else 'B')+t[1:]
        self.failcheck('SIGNATURE_VALUE_INVALID',self.rewrite(tamper))

    def test_07_wrong_embedded_certificate_denied(self):
        other=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cert=(x509.CertificateBuilder()
              .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'OTHER')]))
              .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'OTHER')]))
              .public_key(other.public_key()).serial_number(899)
              .not_valid_before(datetime(2026,1,1,tzinfo=timezone.utc))
              .not_valid_after(datetime(2027,1,1,tzinfo=timezone.utc))
              .sign(other,hashes.SHA256()))
        val=base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode()
        raw=self.rewrite(lambda x:setattr(x.find('.//'+D+'X509Certificate'),'text',val))
        self.failcheck('SIGNATURE_VALUE_INVALID',raw)

    def test_08_duplicate_inf_nfe_reference_denied(self):
        def duplicate(x):
            nfe=x.find(N+'NFe');nfe.insert(1,deepcopy(nfe.find(N+'infNFe')))
        self.failcheck('STRUCTURE_CARDINALITY_INVALID',self.rewrite(duplicate))

    def test_09_duplicate_id_elsewhere_denied(self):
        def duplicate(x):
            el=etree.SubElement(x,N+'aux');el.set('Id','NFe'+key())
        self.failcheck('REFERENCE_ID_NOT_UNIQUE',self.rewrite(duplicate))

    def test_10_second_signature_denied(self):
        def duplicate(x):
            nfe=x.find(N+'NFe');nfe.append(deepcopy(nfe.find(D+'Signature')))
        self.failcheck('SIGNATURE_CARDINALITY_INVALID',self.rewrite(duplicate))

    def test_11_external_reference_uri_denied(self):
        raw=self.rewrite(lambda x:x.find('.//'+D+'Reference').set('URI','https://example.com'))
        self.failcheck('REFERENCE_OR_C14N_UNSUPPORTED',raw)

    def test_12_unsupported_transform_denied(self):
        raw=self.rewrite(lambda x:x.find('.//'+D+'Transform').set('Algorithm','http://evil.example/xslt'))
        self.failcheck('TRANSFORMS_UNSUPPORTED',raw)

    def test_13_only_nfe_55_model_accepted(self):
        self.failcheck('NFE_KEY_INVALID',chave=key('65'))

    def test_14_dtd_forbidden(self):
        raw=b'<!DOCTYPE nfeProc [<!ENTITY x "hello">]>'+self.xml256
        self.failcheck('XML_DTD_FORBIDDEN',raw)

    def test_15_big_xml_denied(self):
        self.failcheck('INPUT_INVALID',b' '*2097153)

    def test_16_invalid_xml_denied(self):
        self.failcheck('XML_INVALID',b'<root')

    def test_17_unsigned_xml_denied(self):
        raw=self.rewrite(lambda x:x.find(N+'NFe').remove(x.find('.//'+D+'Signature')))
        self.failcheck('SIGNATURE_CARDINALITY_INVALID',raw)

    def test_18_wrong_expected_key_denied(self):
        from test_enterprise_nfe_sefaz_nacional_i3n import key as other_key
        self.failcheck('SIGNED_REFERENCE_TARGET_INVALID',chave=other_key('PA'))

    def test_19_pii_absent_in_receipt(self):
        r=self.runcheck()
        self.assertNotIn('cnpj',str(r).lower())
        self.assertNotIn('chave_nfe',r)
        self.assertNotIn('certificate_der',r)
        self.assertNotIn('nome',str(r).lower())
        self.assertNotIn('soap',str(r).lower())

    def test_20_noncommercial_when_signed(self):
        r=self.runcheck()
        for f in ('revogacao_certificado_verificada','titularidade_emitente_verificada',
                  'situacao_sefaz_confirmada','protocolo_sefaz_autenticado','norma_vigente_verificada',
                  'apuracao_mensal_completa','direito_creditorio_comprovado','checkout_autorizado'):
            self.assertIs(r[f],False,f)

    def test_21_no_network_or_file_reads(self):
        with patch('socket.create_connection',side_effect=AssertionError('network')):
            self.runcheck()

    def test_22_sha1_document_tamper_denied(self):
        raw=self.rewrite(lambda x:setattr(x.find('.//'+N+'mod'),'text','65'),raw=self.xml1)
        self.failcheck('REFERENCE_DIGEST_INVALID',raw)

    def test_23_reject_weird_boolean_hash(self):
        self.failcheck('INPUT_INVALID',digest=True)

    def test_24_cli_offline_signed_xml_pass(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app.scripts.verificar_assinatura_nfe_i7 import main
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'exemplo.nexialista'
            path.write_bytes(self.xml256)
            with patch('builtins.print') as out:
                self.assertEqual(main([str(path)]),0)
            msg='\n'.join(str(call.args[0]) for call in out.call_args_list)
            self.assertIn('SOLVERIS_I7_OFFLINE_SIGNATURE_MATH_PASS',msg)
            self.assertNotIn(key(),msg)
            self.assertIn('SEFAZ_AUTENTICADA=FALSE',msg)

    def test_25_cli_invalid_signature_denied(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app.scripts.verificar_assinatura_nfe_i7 import main
        invalid=self.rewrite(lambda x:setattr(x.find('.//'+N+'mod'),'text','65'))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'nfe.xml'
            path.write_bytes(invalid)
            with patch('builtins.print') as out:
                self.assertEqual(main([str(path)]),2)
            message='\n'.join(str(c.args[0]) for c in out.call_args_list)
            self.assertIn('SIGNATURE_NOT_VERIFIED',message)
            self.assertNotIn(key(),message)


if __name__ == '__main__':unittest.main()
