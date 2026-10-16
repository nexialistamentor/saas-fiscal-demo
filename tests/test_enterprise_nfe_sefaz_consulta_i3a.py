"""I3A official NFeConsultaProtocolo4 wire-format and strict response. No network."""
import importlib
import unittest
from xml.etree import ElementTree as ET

NFE='http://www.portalfiscal.inf.br/nfe'
SOAP='http://www.w3.org/2003/05/soap-envelope'
KEY='15261012345678000123550010000000011000000019'


def ret(status='100', key=KEY, tp='1', protocol='123456789012345', protocol_status='100', extra='', ver='4.00'):
    info = (f'<n:protNFe><n:infProt><n:chNFe>{key}</n:chNFe><n:cStat>{protocol_status}</n:cStat>'
            f'<n:nProt>{protocol}</n:nProt><n:dhRecbto>2026-10-16T11:01:00-03:00</n:dhRecbto>'
            '</n:infProt></n:protNFe>') if status=='100' else ''
    return (f'<s:Envelope xmlns:s="{SOAP}" xmlns:n="{NFE}"><s:Body>'
            f'<nfeResultMsg><n:retConsSitNFe versao="{ver}"><n:tpAmb>{tp}</n:tpAmb>'
            f'<n:chNFe>{key}</n:chNFe><n:cStat>{status}</n:cStat>{info}{extra}'
            '</n:retConsSitNFe></nfeResultMsg></s:Body></s:Envelope>').encode()


class TestNfeSefazConsultaI3A(unittest.TestCase):
    def module(self):
        return importlib.import_module('app.services.enterprise_nfe_sefaz_consulta_i3a')

    def test_00_adapter_required(self):
        try: self.module()
        except ModuleNotFoundError as e:
            if e.name == 'app.services.enterprise_nfe_sefaz_consulta_i3a':
                self.fail('I3A_RED_MISSING_ADAPTER')
            raise

    def test_01_request_is_pa_production_soap12(self):
        m=self.module(); x=m.construir_envelope_consulta_pa(KEY); root=ET.fromstring(x)
        self.assertEqual(root.tag, '{'+SOAP+'}Envelope')
        self.assertEqual(root.find('.//{'+NFE+'}consSitNFe').get('versao'),'4.00')
        self.assertEqual(root.find('.//{'+NFE+'}chNFe').text,KEY)
        self.assertNotIn(b'<signature',x.lower())
        self.assertEqual(m.ENDPOINT_PA_PRODUCAO,'https://nfe.svrs.rs.gov.br/ws/NfeConsulta/NfeConsulta4.asmx')

    def test_02_fake_nfce_rejected(self):
        m=self.module()
        with self.assertRaisesRegex(m.NfeSefazConsultaError,'MODELO'):
            m.construir_envelope_consulta_pa(KEY[:20]+'65'+KEY[22:])

    def test_03_non_pa_key_rejected(self):
        m=self.module()
        with self.assertRaisesRegex(m.NfeSefazConsultaError,'CHAVE'):
            m.construir_envelope_consulta_pa('35'+KEY[2:])

    def test_04_auth_response_not_fiscal_certificate(self):
        m=self.module(); x=m.interpretar_resposta_consulta_pa(soap_bytes=ret(),chave_esperada=KEY)
        self.assertEqual(x['situacao_declarada_pela_resposta'],'AUTORIZADA_CONFORME_RETORNO')
        self.assertEqual(x['protocolo_declarado'],'123456789012345')
        self.assertFalse(x['situacao_oficial_confirmada'])
        self.assertFalse(x['assinatura_xml_verificada'])
        self.assertFalse(x['checkout_autorizado'])
        self.assertFalse(x['credito_fiscal_comprovado'])

    def test_05_cancel_and_missing(self):
        m=self.module()
        for status,expected in [('101','CANCELADA_CONFORME_RETORNO'),('217','NAO_CONSTA_CONFORME_RETORNO'),('656','CONSUMO_INDEVIDO_BLOQUEADO'),('999','NAO_CONCLUSIVO')]:
            with self.subTest(status=status):
                x=m.interpretar_resposta_consulta_pa(soap_bytes=ret(status),chave_esperada=KEY)
                self.assertEqual(x['situacao_declarada_pela_resposta'],expected)

    def test_06_denied(self):
        m=self.module()
        for c in ('110','301','302'):
            with self.subTest(c=c):
                x=m.interpretar_resposta_consulta_pa(soap_bytes=ret(c),chave_esperada=KEY)
                self.assertEqual(x['situacao_declarada_pela_resposta'],'DENEGADA_CONFORME_RETORNO')

    def test_07_wrong_key_status_proof(self):
        m=self.module()
        with self.assertRaisesRegex(m.NfeSefazConsultaError,'KEY_DIVERGENTE'):
            m.interpretar_resposta_consulta_pa(soap_bytes=ret(key=KEY[:-1]+'8'),chave_esperada=KEY)

    def test_08_wrong_protocol_status(self):
        m=self.module()
        with self.assertRaisesRegex(m.NfeSefazConsultaError,'PROTOCOL_STATUS'):
            m.interpretar_resposta_consulta_pa(soap_bytes=ret(protocol_status='999'),chave_esperada=KEY)

    def test_09_missing_protocol(self):
        m=self.module()
        x=ret().replace(b'<n:protNFe>',b'<n:fake>').replace(b'</n:protNFe>',b'</n:fake>')
        with self.assertRaisesRegex(m.NfeSefazConsultaError,'PROTOCOL_REQUIRED'):
            m.interpretar_resposta_consulta_pa(soap_bytes=x,chave_esperada=KEY)

    def test_10_wrong_environment(self):
        m=self.module()
        with self.assertRaisesRegex(m.NfeSefazConsultaError,'AMBIENTE'):
            m.interpretar_resposta_consulta_pa(soap_bytes=ret(tp='2'),chave_esperada=KEY)

    def test_11_unknown_version(self):
        m=self.module()
        with self.assertRaisesRegex(m.NfeSefazConsultaError,'VERSION'):
            m.interpretar_resposta_consulta_pa(soap_bytes=ret(ver='3.10'),chave_esperada=KEY)

    def test_12_soap_fault(self):
        m=self.module()
        x=f'<s:Envelope xmlns:s="{SOAP}"><s:Body><s:Fault/></s:Body></s:Envelope>'.encode()
        with self.assertRaisesRegex(m.NfeSefazConsultaError,'FAULT'):
            m.interpretar_resposta_consulta_pa(soap_bytes=x,chave_esperada=KEY)

    def test_13_xml_entity(self):
        m=self.module()
        x=b'<!DOCTYPE bad [<!ENTITY danger "oops">]>'+ret()
        with self.assertRaisesRegex(m.NfeSefazConsultaError,'MALFORMED'):
            m.interpretar_resposta_consulta_pa(soap_bytes=x,chave_esperada=KEY)

    def test_14_size_limit(self):
        m=self.module()
        with self.assertRaisesRegex(m.NfeSefazConsultaError,'SIZE'):
            m.interpretar_resposta_consulta_pa(soap_bytes=b'A'*300000,chave_esperada=KEY)

    def test_15_cancel_event_supersedes_authorization(self):
        m=self.module()
        e=(f'<n:retEvento><n:infEvento xmlns:n="{NFE}"><n:chNFe>{KEY}</n:chNFe>'
           '<n:tpEvento>110111</n:tpEvento><n:cStat>135</n:cStat></n:infEvento></n:retEvento>')
        x=m.interpretar_resposta_consulta_pa(soap_bytes=ret(extra=e),chave_esperada=KEY)
        self.assertEqual(x['situacao_declarada_pela_resposta'],'CANCELADA_CONFORME_RETORNO')

    def test_16_cancel_event_wrong_key(self):
        m=self.module()
        e=(f'<n:retEvento><n:infEvento xmlns:n="{NFE}"><n:chNFe>{KEY[:-1]}8</n:chNFe>'
           '<n:tpEvento>110111</n:tpEvento><n:cStat>135</n:cStat></n:infEvento></n:retEvento>')
        with self.assertRaisesRegex(m.NfeSefazConsultaError,'EVENT_KEY_MISMATCH'):
            m.interpretar_resposta_consulta_pa(soap_bytes=ret(extra=e),chave_esperada=KEY)

    def test_17_foreign_xml_rejected(self):
        m=self.module()
        with self.assertRaisesRegex(m.NfeSefazConsultaError,'NOT_SOAP12'):
            m.interpretar_resposta_consulta_pa(soap_bytes=b'<retConsSitNFe/>',chave_esperada=KEY)

if __name__=='__main__': unittest.main()
