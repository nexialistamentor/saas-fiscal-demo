"""I8: ligacao criptografica/estrutural sintética, sem consultar SEFAZ."""
import base64
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import importlib
import unittest
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding,rsa
from cryptography.x509.oid import NameOID,ObjectIdentifier
from lxml import etree

NFE='http://www.portalfiscal.inf.br/nfe'
DS='http://www.w3.org/2000/09/xmldsig#'
N='{'+NFE+'}'
D='{'+DS+'}'
CAN='http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
CNPJ='11222333000181'  # somente exemplar artificial de digitos verificadores
OID=ObjectIdentifier('2.16.76.1.3.3')

def key(cnpj=CNPJ):
    first='35'+'2610'+cnpj+'55'+'001'+'000000001'+'1'+'00000001'
    assert len(first)==43
    mod=sum(int(c)*(2+(i%8)) for i,c in enumerate(reversed(first)))%11
    return first+str(0 if mod<2 else 11-mod)

def c14n(x):
    return etree.tostring(deepcopy(x),method='c14n',exclusive=False,with_comments=False)

class TestI8SignerIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.priv=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.today=datetime(2026,10,16,tzinfo=timezone.utc)
        cls.src=cls.build()

    @classmethod
    def cert(cls, *,cnpj=CNPJ,san=True,tag=0x13,ca=False,usage=True,date_bad=False,duplicate=False):
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'SINTETICO SEM ANCORA')])
        start=datetime(2027 if date_bad else 2026,1,1,tzinfo=timezone.utc)
        end=datetime(2028,1,1,tzinfo=timezone.utc)
        b=(x509.CertificateBuilder().subject_name(name).issuer_name(name)
           .public_key(cls.priv.public_key()).serial_number(12345)
           .not_valid_before(start).not_valid_after(end)
           .add_extension(x509.BasicConstraints(ca=ca,path_length=None),critical=True))
        if usage:
            b=b.add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,
                key_encipherment=False,data_encipherment=False,key_agreement=False,
                key_cert_sign=False,crl_sign=False,encipher_only=False,decipher_only=False),critical=True)
        if san:
            der=bytes([tag,14])+cnpj.encode('ascii')
            names=[x509.OtherName(OID,der)]
            if duplicate:names.append(x509.OtherName(OID,der))
            b=b.add_extension(x509.SubjectAlternativeName(names),critical=False)
        return b.sign(cls.priv,hashes.SHA256()).public_bytes(serialization.Encoding.DER)

    @classmethod
    def build(cls,*, cnpj_emit=CNPJ, cnpj_cert=CNPJ, cnpj_key=CNPJ, san=True,tag=0x13,
              ca=False, usage=True,date_bad=False,duplicate=False,
              issue='2026-10-16T14:00:00-03:00',tamper_signature=False):
        root=etree.Element(N+'nfeProc',nsmap={None:NFE})
        nf=etree.SubElement(root,N+'NFe')
        inf=etree.SubElement(nf,N+'infNFe',Id='NFe'+key(cnpj_key),versao='4.00')
        ide=etree.SubElement(inf,N+'ide');etree.SubElement(ide,N+'dhEmi').text=issue
        emit=etree.SubElement(inf,N+'emit');etree.SubElement(emit,N+'CNPJ').text=cnpj_emit
        sign=etree.SubElement(nf,D+'Signature',nsmap={None:DS})
        info=etree.SubElement(sign,D+'SignedInfo')
        etree.SubElement(info,D+'CanonicalizationMethod',Algorithm=CAN)
        etree.SubElement(info,D+'SignatureMethod',Algorithm='http://www.w3.org/2001/04/xmldsig-more#rsa-sha256')
        ref=etree.SubElement(info,D+'Reference',URI='#NFe'+key(cnpj_key))
        trans=etree.SubElement(ref,D+'Transforms')
        etree.SubElement(trans,D+'Transform',Algorithm=DS+'enveloped-signature')
        etree.SubElement(trans,D+'Transform',Algorithm=CAN)
        etree.SubElement(ref,D+'DigestMethod',Algorithm='http://www.w3.org/2001/04/xmlenc#sha256')
        etree.SubElement(ref,D+'DigestValue').text=base64.b64encode(hashlib.sha256(c14n(inf)).digest()).decode()
        sig=cls.priv.sign(c14n(info),padding.PKCS1v15(),hashes.SHA256())
        if tamper_signature:sig=b'X'+sig[1:]
        etree.SubElement(sign,D+'SignatureValue').text=base64.b64encode(sig).decode()
        keyinfo=etree.SubElement(sign,D+'KeyInfo')
        x509d=etree.SubElement(keyinfo,D+'X509Data')
        etree.SubElement(x509d,D+'X509Certificate').text=base64.b64encode(
            cls.cert(cnpj=cnpj_cert,san=san,tag=tag,ca=ca,usage=usage,
                     date_bad=date_bad,duplicate=duplicate)).decode()
        return etree.tostring(root,encoding='utf-8',xml_declaration=True)

    def module(self):
        try:return importlib.import_module('app.services.enterprise_nfe_i8_signer_identity')
        except ModuleNotFoundError as exc:
            if exc.name=='app.services.enterprise_nfe_i8_signer_identity':
                self.fail('I8_RED_CAUSAL_MISSING_MODULE')
            raise
    def run_check(self,raw=None,cnpj=CNPJ,chave=None):
        raw=self.src if raw is None else raw
        return self.module().vincular_signatario_nfe_i8(xml_bytes=raw,
             chave_nfe_esperada=key() if chave is None else chave,
             cnpj_emitente_esperado=cnpj,
             xml_sha256_esperado=hashlib.sha256(raw).hexdigest())
    def expect_stop(self,code,raw=None,**kwargs):
        with self.assertRaisesRegex(self.module().EnterpriseI8IdentityError,code):
            self.run_check(raw,**kwargs)

    def test_00_adapter_required(self):
        self.assertTrue(callable(self.module().vincular_signatario_nfe_i8))
    def test_01_valid_conciliation_no_authority(self):
        a=self.run_check()
        self.assertTrue(a['assinatura_matematica_i7_verificada'])
        self.assertTrue(a['cnpj_embutido_certificado_corresponde_emitente'])
        self.assertTrue(a['cnpj_chave_nfe_corresponde_emitente'])
        for prop in ('titularidade_juridica_verificada','cadeia_icp_brasil_verificada',
                     'revogacao_certificado_verificada','situacao_sefaz_confirmada',
                     'credito_fiscal_comprovado','apuracao_mensal_completa','checkout_autorizado'):
            self.assertIs(a[prop],False)
    def test_02_octet_string_allowed(self):
        self.assertTrue(self.run_check(self.build(tag=0x04))['cnpj_embutido_certificado_corresponde_emitente'])
    def test_03_san_cnpj_not_matching(self):
        self.expect_stop('CNPJ_CERT_DIVERGENTE',self.build(cnpj_cert='11444777000161'))
    def test_04_san_missing_denied(self):
        self.expect_stop('SAN_CNPJ_MISSING',self.build(san=False))
    def test_05_duplicate_othername_denied(self):
        self.expect_stop('SAN_CNPJ_CARDINALITY_INVALID',self.build(duplicate=True))
    def test_06_wrong_der_tag_denied(self):
        self.expect_stop('CNPJ_ASN1_UNSUPPORTED',self.build(tag=0x0c))
    def test_07_signature_tampered_denied(self):
        self.expect_stop('I7_SIGNATURE_NOT_VERIFIED',self.build(tamper_signature=True))
    def test_08_cnpj_xml_mismatch_expected_denied(self):
        self.expect_stop('CNPJ_EMITENTE_INVALID',cnpj='11444777000161')
    def test_09_xml_cnpj_differs_key_denied(self):
        self.expect_stop('CNPJ_CHAVE_DIVERGENTE',self.build(cnpj_emit='11444777000161',cnpj_cert='11444777000161'),cnpj='11444777000161')
    def test_10_cert_not_valid_at_issue_denied(self):
        self.expect_stop('CERT_OUTSIDE_DECLARED_ISSUE_DATE',self.build(date_bad=True))
    def test_11_ca_certificate_denied(self):
        self.expect_stop('CERT_USAGE_NOT_ELIGIBLE',self.build(ca=True))
    def test_12_undefined_key_usage_denied(self):
        self.expect_stop('CERT_USAGE_UNDEFINED',self.build(usage=False))
    def test_13_only_valid_cnpj(self):
        self.expect_stop('INPUT_INVALID',cnpj='11111111111111')
    def test_14_xml_content_tampered_denied(self):
        self.expect_stop('I7_SIGNATURE_NOT_VERIFIED',self.src.replace(b'14:00:00',b'15:00:00'))
    def test_15_noncanonical_issue_date_denied(self):
        self.expect_stop('ISSUE_DATE_INVALID',self.build(issue='not-a-date'))
    def test_16_no_personal_data_output(self):
        a=self.run_check()
        self.assertNotIn(CNPJ,str(a))
        self.assertNotIn(key(),str(a))
        self.assertNotIn('certificado_der',a)
    def test_17_deterministic_receipt(self):
        self.assertEqual(self.run_check(),self.run_check())
    def test_18_invalid_xml_sha_denied(self):
        with self.assertRaisesRegex(self.module().EnterpriseI8IdentityError,'I7_SIGNATURE_NOT_VERIFIED'):
            self.module().vincular_signatario_nfe_i8(xml_bytes=self.src,
                chave_nfe_esperada=key(),cnpj_emitente_esperado=CNPJ,
                xml_sha256_esperado='0'*64)
    def test_19_no_network(self):
        from unittest.mock import patch
        with patch('socket.create_connection',side_effect=AssertionError('NETWORK')):
            self.run_check()

    def test_20_cli_with_synthetic_document(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app.scripts.verificar_signatario_nfe_i8 import main
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'amostra.nexialista'
            path.write_bytes(self.src)
            with patch('builtins.print') as printer:
                rc=main([str(path)])
            self.assertEqual(rc,0)
            log='\n'.join(str(c.args[0]) for c in printer.call_args_list)
            self.assertIn('SOLVERIS_I8_OFFLINE_SIGNER_IDENTITY_MATCH_PASS',log)
            self.assertNotIn(CNPJ,log)
            self.assertNotIn(key(),log)

    def test_21_cli_missing_document_fails_closed(self):
        from unittest.mock import patch
        from app.scripts.verificar_signatario_nfe_i8 import main
        with patch('builtins.print') as printer:
            rc=main(['/nonexistent/solveris_i8_test.xml'])
        self.assertEqual(rc,2)
        self.assertIn('NOT_VERIFIED',str(printer.call_args_list))

if __name__=='__main__':unittest.main()
