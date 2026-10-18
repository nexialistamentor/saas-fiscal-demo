"""G1.2 synthetic contract: no company XML, no DB, no web, no payments."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
from datetime import date
import xml.etree.ElementTree as etree

ROOT = Path(__file__).resolve().parents[1]
ENGINE_SOURCE = ROOT / 'g1_reference_engine.py'
TARGET = Path(os.environ.get('SOLVERIS_G12_MODULE_PATH', str(ROOT / 'app/services/enterprise_g12_st_item_reconciliation.py')))

# Isolated stubs for staged RED/GREEN. The Windows runner additionally performs
# a real import smoke against the actual Git checkout, not these stubs.
app = types.ModuleType('app');app.__path__=[]
serv = types.ModuleType('app.services');serv.__path__=[]
cons_pkg = types.ModuleType('app.services.tax_consistency');cons_pkg.__path__=[]
xml_service = types.ModuleType('app.xml_service')
fiscal = types.ModuleType('app.services.fiscal_utils')
table = types.ModuleType('app.services.tabela_normativa_service')
motor = types.ModuleType('app.motor_fiscal')

s = importlib.util.spec_from_file_location('app.services.tax_consistency.tax_consistency_engine', ENGINE_SOURCE)
cons = importlib.util.module_from_spec(s);s.loader.exec_module(cons)

class MotorFiscal:
    @staticmethod
    def calcular_base_st(v,m):return max(0,round(v*(1+m/100),2))
    @staticmethod
    def calcular_icms_st(b,ali,own):return max(0,round(b*ali/100-own,2))
motor.MotorFiscal=MotorFiscal

def parser(*,xml_bytes):
    root=etree.fromstring(xml_bytes)
    ns={'n':'http://www.portalfiscal.inf.br/nfe'}
    inf=root.find('.//n:infNFe',ns)
    key=inf.get('Id')[3:]
    items=[]
    for det in inf.findall('n:det',ns):
        group=det.find('n:imposto/n:ICMS',ns)
        t=group[0] if group is not None and len(group)==1 else None
        f=lambda path: det.findtext(path,namespaces=ns)
        items.append({'ncm':f('n:prod/n:NCM'),'cfop':f('n:prod/n:CFOP'),
                      'base_st':t.findtext('n:vBCST',namespaces=ns) if t is not None else None,
                      'valor_st':t.findtext('n:vICMSST',namespaces=ns) if t is not None else None,
                      'st_observado_xml':t is not None and t.find('n:vBCST',ns) is not None and t.find('n:vICMSST',ns) is not None})
    return {'chave_nfe':key,'uf_emit':inf.findtext('n:emit/n:enderEmit/n:UF',namespaces=ns),
            'uf_dest':inf.findtext('n:dest/n:enderDest/n:UF',namespaces=ns),'itens':items}
xml_service.ler_xml_unico=parser
fiscal.resolver_aliquota_e_mva=lambda *a,**k:None
table.buscar_mva=lambda *a,**k:None
table.resolver_base_calculo_st=lambda *a,**k:None
mods={'app':app,'app.services':serv,'app.services.tax_consistency':cons_pkg,
      'app.services.tax_consistency.tax_consistency_engine':cons,
      'app.services.fiscal_utils':fiscal,'app.services.tabela_normativa_service':table,
      'app.motor_fiscal':motor,'app.xml_service':xml_service}
with patch.dict(sys.modules,mods):
    spec=importlib.util.spec_from_file_location('_g12_test_target',TARGET)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

K='1'*44

def mkxml(*, count=1, group='ICMS10', mod='4', extras='', reduction='',
          out='1',fin='1', iddest='1', modnfe='55', uf='PA', uf_dest='PA',
          key=K, icms='18.00', vprod='100.00', st='7.20', base='140.00'):
    det=[]
    for n in range(1,count+1):
        det.append(f'''<det nItem="{n}"><prod><NCM>10019010</NCM><CFOP>5102</CFOP>
        <qCom>1</qCom><vProd>{vprod}</vProd>{extras}</prod><imposto><ICMS>
        <{group}><modBCST>{mod}</modBCST><vBC>100.00</vBC><pICMS>18.00</pICMS>
        <vICMS>{icms}</vICMS><vBCST>{base}</vBCST><vICMSST>{st}</vICMSST>
        {reduction}</{group}></ICMS></imposto></det>''')
    return (f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{key}">'
            f'<ide><mod>{modnfe}</mod><tpNF>{out}</tpNF><finNFe>{fin}</finNFe><idDest>{iddest}</idDest>'
            f'<dhEmi>2026-04-15T12:00:00-03:00</dhEmi></ide>'
            f'<emit><enderEmit><UF>{uf}</UF></enderEmit></emit>'
            f'<dest><enderDest><UF>{uf_dest}</UF></enderDest></dest>'
            +''.join(det)+'</infNFe></NFe>').encode()

def norm(*a,**kw):
    return {'calculo_autorizado':True,'calculo_parcial':False,'mva_autorizada':True,
            'aliquota_autorizada':True,'confianca':'oficial','aliquota':0.18,'mva':0.40}

def rule(*a,**kw):
    return {'nivel_confianca_fonte':'oficial','vigencia_inicio':date(2026,1,1),
            'vigencia_fim':None, 'fonte_legal':'SINTETICO NAO VIGENTE REAL',
            'aliquota_interna':0.18, 'mva':40.0}

def base(*a,**kw):
    return {'metodo':'iva_st','confianca':'oficial',
            'fonte_legal':'SINTETICO NAO VIGENTE REAL','aliquota_interna':0.18,
            'base_calculo':140.0}

class G12(unittest.TestCase):
    def setUp(self):
        self.p1=patch.object(m,'resolver_aliquota_e_mva',side_effect=norm)
        self.p2=patch.object(m,'buscar_mva',side_effect=rule)
        self.p3=patch.object(m,'resolver_base_calculo_st',side_effect=base)
        for p in (self.p1,self.p2,self.p3):p.start();self.addCleanup(p.stop)
    def run_case(self,**kw):return m.confrontar_st_por_item_g12(db=object(),xml_bytes=mkxml(**kw))
    def check_block(self,r):
        for key in ('autoridade_fiscal','norma_juridicamente_ratificada',
                    'documento_autenticado_sefaz','credito_confirmado','checkout_autorizado','usavel_comercialmente'):
            self.assertIs(r[key],False,key)
    def test_01_conditional_calls_real_contracts(self):
        r=self.run_case();self.assertEqual(r['estado'],'G12_SIMULACAO_CONDICIONAL_SEM_AUTORIDADE')
        self.assertEqual(r['itens_simulados'],1)
        self.assertTrue(r['confronto_g1']['coincidencia_numerica']);self.check_block(r)
    def test_02_different_st_observed_still_not_credit(self):
        r=self.run_case(st='2.00');self.assertEqual(len(r['confronto_g1']['divergencias']),1);self.check_block(r)
    def test_03_two_item_exact(self):
        r=self.run_case(count=2);self.assertEqual(r['itens_simulados'],2);self.assertEqual(r['confronto_g1']['comparacoes_realizadas'],4)
    def test_04_wrong_mode_bypass_blocked(self):
        r=self.run_case(mod='0');self.assertEqual(r['itens_simulados'],0);self.check_block(r)
    def test_05_pmpf_resolver_priority_blocks(self):
        with patch.object(m,'resolver_base_calculo_st',return_value={'metodo':'pmpf','confianca':'oficial'}):
            r=self.run_case();self.assertEqual(r['itens_simulados'],0)
            self.assertEqual(r['itens'][0]['motivo'],'G12_PMPF_OU_BASE_COM_PRIORIDADE_NAO_COTEJADA')
    def test_06_partial_norm_block(self):
        with patch.object(m,'resolver_aliquota_e_mva',return_value={'calculo_autorizado':False,'calculo_parcial':True}):
            self.assertEqual(self.run_case()['itens_simulados'],0)
    def test_07_expired_rule_block(self):
        with patch.object(m,'buscar_mva',return_value={**rule(), 'vigencia_inicio':date(2027,1,1)}):
            self.assertEqual(self.run_case()['itens'][0]['motivo'],'G12_VIGENCIA_NORMATIVA_INVALIDA')
    def test_08_alias_rate_mismatch_block(self):
        with patch.object(m,'buscar_mva',return_value={**rule(), 'aliquota_interna':0.17}):
            self.assertEqual(self.run_case()['itens_simulados'],0)
    def test_09_wrong_source_level_block(self):
        with patch.object(m,'buscar_mva',return_value={**rule(), 'nivel_confianca_fonte':'estimativa'}):
            self.assertEqual(self.run_case()['itens_simulados'],0)
    def test_10_extra_freight_block(self):
        self.assertEqual(self.run_case(extras='<vFrete>1.00</vFrete>')['itens_simulados'],0)
    def test_11_malformed_freight_block(self):
        self.assertEqual(self.run_case(extras='<vFrete>NaN</vFrete>')['itens_simulados'],0)
    def test_12_reduction_block(self):
        self.assertEqual(self.run_case(reduction='<pRedBCST>10.00</pRedBCST>')['itens_simulados'],0)
    def test_13_wrong_icms_own_block(self):
        self.assertEqual(self.run_case(icms='2.00')['itens_simulados'],0)
    def test_14_not_model55(self):
        self.assertEqual(self.run_case(modnfe='65')['estado'],'G12_OPERACAO_NAO_SUPORTADA')
    def test_15_interstate_block(self):
        self.assertEqual(self.run_case(uf_dest='SP')['estado'],'G12_UF_INTERESTADUAL_NAO_SUPORTADA')
    def test_16_wrong_key_block(self):
        self.assertEqual(self.run_case(key='12')['estado'],'G12_CHAVE_INVALIDA')
    def test_17_many_items_block(self):
        self.assertEqual(self.run_case(count=501)['estado'],'G12_CARDINALIDADE_ITENS_INVALIDA')
    def test_18_xxe_block(self):
        self.assertEqual(m.confrontar_st_por_item_g12(db=object(),xml_bytes=b'<!DOCTYPE a [<!ENTITY x SYSTEM "file:///etc/passwd">]><a>&x;</a>')['estado'],'G12_XML_NAO_PARSEAVEL')
    def test_19_no_db_block(self):
        self.assertEqual(m.confrontar_st_por_item_g12(db=None,xml_bytes=mkxml())['estado'],'G12_ENTRADA_INVALIDA')
    def test_20_throw_resolver_block(self):
        with patch.object(m,'resolver_aliquota_e_mva',side_effect=RuntimeError('offline')):
            self.assertEqual(self.run_case()['itens_simulados'],0)
    def test_21_own_icms_is_explicit_xml_component(self):
        r=self.run_case();self.assertIs(r['icms_proprio_recalculado_por_fonte_independente'],False)
        self.assertIn('vICMS_XML',r['itens'][0]['formula'])
    def test_22_base_engine_mismatch_block(self):
        with patch.object(m,'resolver_base_calculo_st',return_value={**base(), 'base_calculo':141.0}):
            self.assertEqual(self.run_case()['itens'][0]['motivo'],'G12_DIVERGENCIA_ENTRE_MOTORES_EXISTENTES')
    def test_23_forbid_future_no_timezone(self):
        xml=mkxml().replace(b'-03:00',b'')
        self.assertEqual(m.confrontar_st_por_item_g12(db=object(),xml_bytes=xml)['estado'],'G12_DATA_NAO_COMPROVADA')
    def test_24_no_double_nfe(self):
        src=mkxml().decode();xml=src.replace('</NFe>','</NFe><NFe/>').encode()
        self.assertEqual(m.confrontar_st_por_item_g12(db=object(),xml_bytes=xml)['estado'],'G12_XML_NAO_PARSEAVEL')

if __name__=='__main__':unittest.main()
