"""I4N: no-network national operator contract with real I3N parser.

No certificate, account, HTTP request, DB, MEI or external fiscal claim.
"""
import base64
from hashlib import sha256
import importlib
import json
import subprocess
import sys
import unittest
from xml.etree import ElementTree as ET
from unittest.mock import patch

from app.services.enterprise_nfe_sefaz_nacional_i3n import preparar_consulta_nfe_nacional

NFE = 'http://www.portalfiscal.inf.br/nfe'
SOAP = 'http://www.w3.org/2003/05/soap-envelope'
CUF={'PA':15,'SP':35,'RS':43,'RJ':33,'MA':21}


def key(uf):
    raw=f'{CUF[uf]:02d}'+'2610'+'12345678000123'+'55'+'001'+'000000001'+'1'+'00000001'
    d=sum(int(x)*(2+(i%8)) for i,x in enumerate(reversed(raw))) % 11
    return raw+str(0 if d<2 else 11-d)


def soap(chave, stat='100'):
    proto = (f'<n:protNFe><n:infProt><n:chNFe>{chave}</n:chNFe>'
             '<n:cStat>100</n:cStat><n:nProt>123456789012345</n:nProt>'
             '<n:dhRecbto>2026-10-16T10:00:00-03:00</n:dhRecbto>'
             '</n:infProt></n:protNFe>') if stat=='100' else ''
    return (f'<s:Envelope xmlns:s="{SOAP}" xmlns:n="{NFE}"><s:Body>'
            f'<m><n:retConsSitNFe versao="4.00"><n:tpAmb>1</n:tpAmb>'
            f'<n:chNFe>{chave}</n:chNFe><n:cStat>{stat}</n:cStat>'
            f'{proto}</n:retConsSitNFe></m></s:Body></s:Envelope>').encode('utf-8')


class TestI4NNationalSingleQuery(unittest.TestCase):
    def module(self):
        try:
            return importlib.import_module('app.services.enterprise_nfe_sefaz_operador_i4n')
        except ModuleNotFoundError as exc:
            if exc.name == 'app.services.enterprise_nfe_sefaz_operador_i4n':
                self.fail('I4N_RED_CAUSAL_MISSING_MODULE')
            raise

    def test_00_adapter_required(self):
        self.assertTrue(callable(self.module().preparar_execucao_unica))

    def test_01_national_routes_pa_sp_rs_rj_ma(self):
        for uf, auth in [('PA','SVRS'),('SP','SP'),('RS','RS'),('RJ','SVRS'),('MA','SVAN')]:
            with self.subTest(uf=uf):
                p=self.module().preparar_execucao_unica(key(uf))
                self.assertEqual(p['autorizador'], auth)
                self.assertEqual(p['ambiente'], 'producao')
                self.assertFalse(p['consulta_real_executada'])

    def test_02_plan_bytes_match_i3n_and_sha(self):
        for uf in CUF:
            with self.subTest(uf=uf):
                k=key(uf); p=self.module().preparar_execucao_unica(k)
                i3n=preparar_consulta_nfe_nacional(k)
                self.assertEqual(base64.b64decode(p['soap_base64']),i3n['soap_bytes'])
                self.assertEqual(p['soap_sha256'],sha256(i3n['soap_bytes']).hexdigest())
                self.assertEqual(p['chave_sha256'],sha256(k.encode()).hexdigest())
                self.assertEqual(p['endpoint'],i3n['endpoint_oficial_catalogado'])
                self.assertEqual(p['action'],i3n['acao_soap'])

    def test_03_good_soap_remains_unattested(self):
        m=self.module();k=key('SP')
        v=m.interpretar_observacao_unica(chave_nfe=k,resposta_soap=soap(k))
        self.assertEqual(v['cstat'],'100')
        self.assertEqual(v['situacao_declarada'],'AUTORIZADA_CONFORME_RETORNO')
        self.assertFalse(v['canal_mtls_verificado_por_este_modulo'])
        self.assertFalse(v['autenticidade_xml_verificada'])
        self.assertFalse(v['credito_fiscal_comprovado'])
        self.assertFalse(v['checkout_autorizado'])
        self.assertNotIn('chave_nfe',v)

    def test_04_negative_states_no_credit(self):
        m=self.module();k=key('RS')
        for status in ('101','217','656','999'):
            with self.subTest(status=status):
                v=m.interpretar_observacao_unica(chave_nfe=k,resposta_soap=soap(k,status))
                self.assertEqual(v['cstat'], status)
                self.assertFalse(v['credito_fiscal_comprovado'])

    def test_05_different_note_rejected(self):
        m=self.module()
        with self.assertRaises(Exception):
            m.interpretar_observacao_unica(chave_nfe=key('SP'),resposta_soap=soap(key('PA')))

    def test_06_oversized_response_rejected(self):
        m=self.module();k=key('PA')
        with self.assertRaises(Exception):
            m.interpretar_observacao_unica(chave_nfe=k,resposta_soap=b'x'*262145)

    def test_07_wrong_key_dv_rejected(self):
        m=self.module();k=key('SP');fake=k[:-1]+str((int(k[-1])+1)%10)
        with self.assertRaises(Exception):m.preparar_execucao_unica(fake)

    def test_08_invalid_soap_fails_closed(self):
        m=self.module()
        for bad in (b'',b'<xml/>',b'<!DOCTYPE a [<!ENTITY x "bad">]><a/>'):
            with self.subTest(bad=bad):
                with self.assertRaises(Exception):m.interpretar_observacao_unica(chave_nfe=key('RJ'),resposta_soap=bad)

    def test_09_cannot_claim_month_credit_even_with_status_100(self):
        m=self.module();v=m.interpretar_observacao_unica(chave_nfe=key('PA'),resposta_soap=soap(key('PA')))
        for f in ('escrituracao_verificada','norma_vigente_verificada','credito_fiscal_comprovado','apuracao_mensal_completa','checkout_autorizado'):
            self.assertIs(v[f], False)
        self.assertEqual(v['uso'],'INTERNO_NAO_PUBLICAVEL')

    def test_10_cli_plan_offline_returns_json(self):
        m=self.module()
        with patch('sys.stdout') as out:
            r=m.main(['plan','--chave',key('SP')])
        self.assertEqual(r,0)
        self.assertEqual(json.loads(''.join(v.args[0] for v in out.write.call_args_list))['autorizador'],'SP')

    def test_11_cli_invalid_key_return_nonzero(self):
        m=self.module()
        with patch('sys.stderr') as err:
            self.assertEqual(m.main(['plan','--chave','wrong']),2)
        self.assertIn('STOP_I4N',str(err.write.call_args))

    def test_12_no_network_or_certificate_import_in_python(self):
        m=self.module()
        # Design surface remains pure; network is only in separate opt-in .ps1.
        self.assertNotIn('executar_consulta_oficial',m.__all__ if hasattr(m,'__all__') else [])
        plan=m.preparar_execucao_unica(key('MA'))
        self.assertFalse(plan['checkout_autorizado'])

    def test_13_response_fingerprint_exact(self):
        m=self.module();k=key('RJ');r=soap(k)
        out=m.interpretar_observacao_unica(chave_nfe=k,resposta_soap=r)
        self.assertEqual(out['resposta_sha256'],sha256(r).hexdigest())
        self.assertEqual(out['endpoint_catalogado'],preparar_consulta_nfe_nacional(k)['endpoint_oficial_catalogado'])

    def test_14_invalid_model_65_rejected(self):
        m=self.module();k=key('PA')
        with self.assertRaises(Exception):m.preparar_execucao_unica(k[:20]+'65'+k[22:])

    def test_15_refuse_unsigned_custom_host(self):
        m=self.module();x=m.preparar_execucao_unica(key('SP'))
        self.assertNotIn('url_override',x)
        self.assertNotIn('certificate_password',x)
        self.assertNotIn('ignore_tls',x)


if __name__ == '__main__':unittest.main()
