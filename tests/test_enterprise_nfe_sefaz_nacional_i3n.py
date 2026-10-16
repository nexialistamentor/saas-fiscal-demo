"""I3N: censo 27 UFs, autorizador NFe e retorno SOAP estritamente offline."""
import importlib
import unittest
from xml.etree import ElementTree as ET

NFE = 'http://www.portalfiscal.inf.br/nfe'
SOAP = 'http://www.w3.org/2003/05/soap-envelope'
CUF = {'RO':11,'AC':12,'AM':13,'RR':14,'PA':15,'AP':16,'TO':17,
       'MA':21,'PI':22,'CE':23,'RN':24,'PB':25,'PE':26,'AL':27,'SE':28,'BA':29,
       'MG':31,'ES':32,'RJ':33,'SP':35,'PR':41,'SC':42,'RS':43,'MS':50,'MT':51,'GO':52,'DF':53}
SVRS = set('AC AL AP CE DF ES PA PB PI RJ RN RO RR SC SE TO'.split())


def key(uf):
    base=f'{CUF[uf]:02d}'+'2610'+'12345678000123'+'55'+'001'+'000000001'+'1'+'00000001'
    assert len(base) == 43, len(base)
    soma=sum(int(v)*(2+(i%8)) for i,v in enumerate(reversed(base)))
    resto=soma%11
    return base+str(0 if resto<2 else 11-resto)


def soap(key_value, status='100', tp='1', ver='4.00', extra=''):
    proto=(f'<n:protNFe><n:infProt><n:chNFe>{key_value}</n:chNFe>'
           f'<n:cStat>100</n:cStat><n:nProt>123456789012345</n:nProt>'
           f'<n:dhRecbto>2026-10-16T10:00:00-03:00</n:dhRecbto>'
           f'</n:infProt></n:protNFe>') if status=='100' else ''
    return (f'<s:Envelope xmlns:s="{SOAP}" xmlns:n="{NFE}"><s:Body>'
            f'<m><n:retConsSitNFe versao="{ver}"><n:tpAmb>{tp}</n:tpAmb>'
            f'<n:chNFe>{key_value}</n:chNFe><n:cStat>{status}</n:cStat>'
            f'{proto}{extra}</n:retConsSitNFe></m></s:Body></s:Envelope>').encode()


class TestEnterpriseNfeNacionalI3N(unittest.TestCase):
    def module(self):
        return importlib.import_module('app.services.enterprise_nfe_sefaz_nacional_i3n')

    def test_00_contract_required(self):
        try: self.module()
        except ModuleNotFoundError as exc:
            if exc.name=='app.services.enterprise_nfe_sefaz_nacional_i3n':
                self.fail('I3N_RED_MISSING_MODULE')
            raise

    def test_01_all_27_states_have_explicit_normal_authorizer(self):
        m=self.module()
        self.assertEqual(len(CUF), 27)
        for uf in CUF:
            with self.subTest(uf=uf):
                route=m.preparar_consulta_nfe_nacional(key(uf))
                expected='SVRS' if uf in SVRS else 'SVAN' if uf=='MA' else uf
                self.assertEqual(route['autorizador'],expected)
                self.assertTrue(route['endpoint_oficial_catalogado'].startswith('https://'))
                self.assertFalse(route['consulta_real_executada'])

    def test_02_pa_sp_rs_rj_ma_route_differences(self):
        m=self.module()
        p=[m.preparar_consulta_nfe_nacional(key(uf)) for uf in ('PA','SP','RS','RJ','MA')]
        self.assertEqual([x['autorizador'] for x in p],['SVRS','SP','RS','SVRS','SVAN'])
        self.assertNotEqual(p[0]['endpoint_oficial_catalogado'],p[1]['endpoint_oficial_catalogado'])
        self.assertNotEqual(p[1]['endpoint_oficial_catalogado'],p[2]['endpoint_oficial_catalogado'])

    def test_03_soap_request_contains_own_uf_and_nfe_key(self):
        m=self.module()
        for uf in ('PA','SP','RS'):
            with self.subTest(uf=uf):
                k=key(uf)
                route=m.preparar_consulta_nfe_nacional(k)
                root=ET.fromstring(route['soap_bytes'])
                el=root.find('.//{'+NFE+'}consSitNFe')
                self.assertEqual(el.get('versao'),'4.00')
                self.assertEqual(el.find('{'+NFE+'}chNFe').text,k)
                self.assertIn(b'<tpAmb>1</tpAmb>',route['soap_bytes'])

    def test_04_valid_dv_required(self):
        m=self.module(); k=key('SP'); invalid=k[:-1]+str((int(k[-1])+1)%10)
        with self.assertRaisesRegex(m.NfeConsultaNacionalError,'DV_INCORRETO'):
            m.preparar_consulta_nfe_nacional(invalid)

    def test_05_nfce_model_not_silently_accepted(self):
        m=self.module(); k=key('SP')
        with self.assertRaisesRegex(m.NfeConsultaNacionalError,'MODELO'):
            m.preparar_consulta_nfe_nacional(k[:20]+'65'+k[22:])

    def test_06_unknown_cuf_rejected(self):
        m=self.module()
        with self.assertRaisesRegex(m.NfeConsultaNacionalError,'CUF'):
            m.preparar_consulta_nfe_nacional('00'+key('SP')[2:])

    def test_07_invalid_or_untyped_key_rejected(self):
        m=self.module()
        for wrong in (None,1,b'1'*44,'abc','12'*22):
            with self.subTest(wrong=wrong):
                with self.assertRaises(m.NfeConsultaNacionalError):
                    m.preparar_consulta_nfe_nacional(wrong)

    def test_08_response_from_multiple_ufs_is_observed_not_approved(self):
        m=self.module()
        for uf in ('PA','SP','RS'):
            with self.subTest(uf=uf):
                k=key(uf); x=m.interpretar_consulta_nfe_nacional(resposta_soap=soap(k), chave_esperada=k)
                self.assertEqual(x['situacao_declarada_pela_resposta'],'AUTORIZADA_CONFORME_RETORNO')
                self.assertEqual(x['autorizador'],m.preparar_consulta_nfe_nacional(k)['autorizador'])
                self.assertFalse(x['situacao_oficial_confirmada'])
                self.assertFalse(x['checkout_autorizado'])
                self.assertFalse(x['credito_fiscal_comprovado'])

    def test_09_cancel_response_blocks_authorization(self):
        m=self.module(); k=key('SP')
        for c,expected in [('101','CANCELADA_CONFORME_RETORNO'),('217','NAO_CONSTA_CONFORME_RETORNO'),('656','CONSUMO_INDEVIDO_BLOQUEADO'),('999','NAO_CONCLUSIVO')]:
            with self.subTest(c=c):
                x=m.interpretar_consulta_nfe_nacional(resposta_soap=soap(k,c),chave_esperada=k)
                self.assertEqual(x['situacao_declarada_pela_resposta'],expected)

    def test_10_response_key_mismatch(self):
        m=self.module()
        with self.assertRaisesRegex(m.NfeConsultaNacionalError,'RESPOSTA_DIVERGENTE'):
            m.interpretar_consulta_nfe_nacional(resposta_soap=soap(key('PA')),chave_esperada=key('SP'))

    def test_11_response_env_not_production(self):
        m=self.module(); k=key('RS')
        with self.assertRaisesRegex(m.NfeConsultaNacionalError,'AMBIENTE'):
            m.interpretar_consulta_nfe_nacional(resposta_soap=soap(k,tp='2'),chave_esperada=k)

    def test_12_protocol_missing_denied(self):
        m=self.module(); k=key('SP')
        data=soap(k).replace(b'<n:protNFe>',b'<fake>').replace(b'</n:protNFe>',b'</fake>')
        with self.assertRaisesRegex(m.NfeConsultaNacionalError,'PROTOCOL_REQUIRED'):
            m.interpretar_consulta_nfe_nacional(resposta_soap=data,chave_esperada=k)

    def test_13_schema_or_soap_fault_denied(self):
        m=self.module(); k=key('RS')
        for data in (b'<wrong/>',b'<!DOCTYPE bad [<!ENTITY e "bad">]>'+soap(k),
                     f'<s:Envelope xmlns:s="{SOAP}"><s:Body><s:Fault/></s:Body></s:Envelope>'.encode()):
            with self.assertRaises(m.NfeConsultaNacionalError):
                m.interpretar_consulta_nfe_nacional(resposta_soap=data,chave_esperada=k)

    def test_14_cancel_event_overrides_positive(self):
        m=self.module(); k=key('SP')
        ev=(f'<n:retEvento><n:infEvento><n:chNFe>{k}</n:chNFe>'
            '<n:tpEvento>110111</n:tpEvento><n:cStat>135</n:cStat>'
            '</n:infEvento></n:retEvento>')
        x=m.interpretar_consulta_nfe_nacional(resposta_soap=soap(k,extra=ev),chave_esperada=k)
        self.assertEqual(x['situacao_declarada_pela_resposta'],'CANCELADA_CONFORME_RETORNO')

    def test_15_no_taxation_inference_from_authorizer_or_uf(self):
        m=self.module()
        for uf in ('SP','RS','PA'):
            x=m.preparar_consulta_nfe_nacional(key(uf))
            for field in ('aliquota_icms','credito_fiscal','ncm','cst','valor_tributo','direito_creditorio'):
                self.assertNotIn(field,x)
            self.assertFalse(x['autoridade_fiscal'])

    def test_16_not_automatic_contingency_or_external_calls(self):
        m=self.module()
        for uf in CUF:
            x=m.preparar_consulta_nfe_nacional(key(uf))
            self.assertNotIn('SVC-',x['autorizador'])
            self.assertNotIn('fallback',x)
            self.assertFalse(x['consulta_real_executada'])

    def test_17_invalid_protocol_cstat_denied(self):
        m=self.module(); k=key('PA')
        bad=soap(k).replace(b'<n:nProt>123456789012345</n:nProt>',b'<n:nProt>invalid</n:nProt>')
        with self.assertRaisesRegex(m.NfeConsultaNacionalError,'PROTOCOL_INCOMPLETE'):
            m.interpretar_consulta_nfe_nacional(resposta_soap=bad,chave_esperada=k)

if __name__=='__main__': unittest.main()
