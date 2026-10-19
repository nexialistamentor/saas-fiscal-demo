"""G1.4 — 28 isolated synthetic tests, no DB, customer XML, SEFAZ, network."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
TARGET=Path(os.environ.get('SOLVERIS_G14_MODULE_PATH',str(ROOT/'app/services/enterprise_g14_operational_normative_scope.py')))
app=ModuleType('app');app.__path__=[]
services=ModuleType('app.services');services.__path__=[]
models=ModuleType('app.models')
class Empresa:pass
models.Empresa=Empresa
bridge=ModuleType('app.services.enterprise_g13_subject_st_bridge')
bridge.projetar_confronto_st_sujeito_g13=lambda **kw: None
with patch.dict(sys.modules,{'app':app,'app.models':models,'app.services':services,
    'app.services.enterprise_g13_subject_st_bridge':bridge}):
    spec=importlib.util.spec_from_file_location('_g14_under_test',TARGET)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

K='1'*44
CNPJ='12345678000190'
SRC='FONTE FICTICIA APENAS TESTE'

def xml(*,cest='0100100',ncm='10019010',cfop='5102',cst='10',mod='4',
        date='2026-04-15T12:00:00-03:00',issuer='PA',dest='PA',count=1,
        duplicate_cest=False, model='55',fin='1',out='1',operation='1'):
    parts=[]
    for i in range(1,count+1):
        cesttag='' if cest is None else f'<CEST>{cest}</CEST>'
        if duplicate_cest: cesttag+=cesttag
        parts.append(f'<det nItem="{i}"><prod><NCM>{ncm}</NCM><CFOP>{cfop}</CFOP>{cesttag}'
            f'<vProd>100.00</vProd></prod><imposto><ICMS><ICMS10>'
            f'<CST>{cst}</CST><modBCST>{mod}</modBCST>'
            '<vBC>100.00</vBC><pICMS>18.00</pICMS><vICMS>18.00</vICMS>'
            '<vBCST>140.00</vBCST><vICMSST>7.20</vICMSST>'
            '</ICMS10></ICMS></imposto></det>')
    return (f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{K}">'
        f'<ide><mod>{model}</mod><tpNF>{out}</tpNF><finNFe>{fin}</finNFe><idDest>{operation}</idDest>'
        f'<dhEmi>{date}</dhEmi></ide><emit><CNPJ>{CNPJ}</CNPJ>'
        f'<enderEmit><UF>{issuer}</UF></enderEmit></emit><dest><enderDest><UF>{dest}</UF></enderDest></dest>'
        +''.join(parts)+'</infNFe></NFe>').encode()

def make_g13(raw,*,count=1,simulated=1):
    return {'schema_version':'SOLVERIS_ENTERPRISE_G13_SUBJECT_ST_ITEM_BRIDGE_V1',
        'empresa_id':41,'relatorio_id':77,'documento_id':10,
        'xml_sha256':hashlib.sha256(raw).hexdigest(),'posse_e_proveniencia_interna_i2':True,
        'competencia_declarada':'2026-04','itens_total':count,
        'confronto_condicional_g12':{'itens_total':count,'itens':[
            {'indice_item':i,'competencia':'2026-04','ncm':'10019010',
             'cfop':'5102','comparacao_condicional':i<=simulated,
             'estado':'SIMULACAO_CONDICIONAL_MVA' if i<=simulated else 'NAO_AVALIADO',
             'metodo_base':'iva_st' if i<=simulated else None,
             'fonte_legal_informada':SRC if i<=simulated else None}
            for i in range(1,count+1)]},
        **dict.fromkeys(('assinatura_certificado_icp_brasil_comprovados','autenticidade_sefaz_verificada',
            'norma_legal_verificada_por_fonte_primaria','cest_e_enquadramento_por_operacao_verificados',
            'icms_proprio_independente','efd_escrituracao_verificada','recolhimento_verificado',
            'credito_confirmado','autoridade_fiscal','checkout_autorizado','usavel_comercialmente'),False)}

def candidate(index=1):
    return {'indice_item':index,'uf':'PA','ncm':'10019010','cest':'0100100',
        'cfop':'5102','cst':'10','regime':'real','operacao':'saida_interna',
        'metodo_base':'iva_st','vigencia_inicio':'2026-01-01','vigencia_fim':None,
        'fonte_legal':SRC,'url_fonte':'https://normas.exemplo.invalid/ato/TESTE',
        'sha256_texto_normativo_declarado':'a'*64,'versao_ato':'VERSAO-SINTETICA'}

class Db:
    def __init__(self):
        self.emp=SimpleNamespace(id=41,user_id=7,optante_mei=False,regime_tributario='real')
        self.reads=0;self.writes=0
    def get(self,what,key):
        self.reads+=1
        return self.emp if what is Empresa and key==41 else None
    def add(self,*args):self.writes+=1;raise AssertionError('DB_WRITE_NOT_ALLOWED')
    def commit(self):self.writes+=1;raise AssertionError('DB_COMMIT_NOT_ALLOWED')

class Tests(unittest.TestCase):
    def setUp(self):
        self.raw=xml();self.g=make_g13(self.raw);self.db=Db()
        self.p=patch.object(module,'projetar_confronto_st_sujeito_g13',side_effect=lambda **kw:copy.deepcopy(self.g))
        self.mock=self.p.start();self.addCleanup(self.p.stop)
    def run_case(self,candidates=None,**kwargs):
        args=dict(db=self.db,authenticated_user_id=7,empresa_id=41,relatorio_id=77,
                  xml_bytes=self.raw,candidatos_normativos=[candidate()] if candidates is None else candidates)
        args.update(kwargs)
        return module.cotejar_enquadramento_normativo_operacao_g14(**args)
    def stopped(self,reason,**kwargs):
        with self.assertRaisesRegex(module.EnterpriseG14GateError,reason):self.run_case(**kwargs)
    def assert_no_trust(self,r):
        for field in ('fonte_primaria_autenticada','enquadramento_legal_autorizado',
           'cest_aplicabilidade_juridica_comprovada','excecoes_e_beneficios_verificados',
           'icms_proprio_independente','documento_autenticado_sefaz',
           'efd_escrituracao_verificada','recolhimento_verificado','autoridade_fiscal',
           'credito_confirmado','checkout_autorizado','usavel_comercialmente'):
            self.assertIs(r[field],False,field)
    def test_01_positive_structural_not_legal(self):
        r=self.run_case();self.assertEqual(r['itens_cotejados_estruturalmente'],1)
        self.assertEqual(r['estado'],'CANDIDATOS_ESTRUTURAIS_SEM_AUTORIDADE');self.assert_no_trust(r)
    def test_02_missing_candidate(self):
        r=self.run_case([]);self.assertEqual(r['itens'][0]['motivo'],'SEM_CANDIDATO_EXPLICITO_PARA_ITEM');self.assert_no_trust(r)
    def test_03_missing_cest(self):
        self.raw=xml(cest=None);self.g=make_g13(self.raw)
        r=self.run_case();self.assertEqual(r['itens'][0]['motivo'],'CEST_AUSENTE_NAO_PROVA_NAO_INCIDENCIA')
    def test_04_wrong_cest(self):
        c=candidate();c['cest']='9999999';r=self.run_case([c]);self.assertEqual(r['itens'][0]['motivo'],'DIMENSOES_CANDIDATAS_DIVERGENTES')
    def test_05_wrong_uf(self):
        c=candidate();c['uf']='SP';self.assertEqual(self.run_case([c])['itens_cotejados_estruturalmente'],0)
    def test_06_wrong_ncm(self):
        c=candidate();c['ncm']='00000000';self.assertEqual(self.run_case([c])['itens_cotejados_estruturalmente'],0)
    def test_07_wrong_cfop(self):
        c=candidate();c['cfop']='5405';self.assertEqual(self.run_case([c])['itens_cotejados_estruturalmente'],0)
    def test_08_wrong_cst(self):
        c=candidate();c['cst']='70';self.assertEqual(self.run_case([c])['itens_cotejados_estruturalmente'],0)
    def test_09_wrong_regime(self):
        c=candidate();c['regime']='presumido';self.assertEqual(self.run_case([c])['itens_cotejados_estruturalmente'],0)
    def test_10_future_regulation(self):
        c=candidate();c['vigencia_inicio']='2026-07-01';self.assertEqual(self.run_case([c])['itens'][0]['motivo'],'VIGENCIA_CANDIDATA_NAO_COBRE_EMISSAO')
    def test_11_expired_regulation(self):
        c=candidate();c['vigencia_fim']='2026-03-01';self.assertEqual(self.run_case([c])['itens_cotejados_estruturalmente'],0)
    def test_12_wrong_legal_source(self):
        c=candidate();c['fonte_legal']='OUTRO ATO';self.assertEqual(self.run_case([c])['itens'][0]['motivo'],'FONTE_CANDIDATA_DIVERGE_MOTOR_L2')
    def test_13_g12_not_simulated(self):
        self.g=make_g13(self.raw,simulated=0)
        self.assertEqual(self.run_case()['itens'][0]['motivo'],'G12_SEM_SIMULACAO_ITEM')
    def test_14_not_intrastate(self):
        self.raw=xml(dest='SP');self.g=make_g13(self.raw)
        self.stopped('G14_OPERACAO_OU_COMPETENCIA_INCOMPATIVEL')
    def test_15_unauthorized_owner_stops(self):
        self.db.emp.user_id=8;self.stopped('G14_REGIME_OU_SUJEITO_NAO_COMPROVADOS')
    def test_16_g13_failed_stops(self):
        self.p.stop();p=patch.object(module,'projetar_confronto_st_sujeito_g13',side_effect=ValueError('wrong owner'))
        p.start();self.addCleanup(p.stop);self.stopped('G14_G13_SUJEITO_DOCUMENTO_NAO_VERIFICADOS')
    def test_17_hash_mismatch_stops(self):
        self.g['xml_sha256']='0'*64;self.stopped('G14_G13_IDENTIDADE_OU_AUTORIDADE_INCOMPATIVEL')
    def test_18_forged_credit_flag_stops(self):
        self.g['checkout_autorizado']=True;self.stopped('G14_G13_IDENTIDADE_OU_AUTORIDADE_INCOMPATIVEL')
    def test_19_bad_candidate_extra_trust_flag_stops(self):
        c=candidate();c['fonte_primaria_autenticada']=True;self.stopped('G14_CANDIDATO_MALFORMADO_OU_DUPLICADO',candidates=[c])
    def test_20_duplicate_candidate_stops(self):
        self.stopped('G14_CANDIDATO_MALFORMADO_OU_DUPLICADO',candidates=[candidate(),candidate()])
    def test_21_invalid_source_http_stops(self):
        c=candidate();c['url_fonte']='http://example.com';self.stopped('G14_CANDIDATO_MALFORMADO_OU_DUPLICADO',candidates=[c])
    def test_22_empty_hash_stops(self):
        c=candidate();c['sha256_texto_normativo_declarado']='';self.stopped('G14_CANDIDATO_MALFORMADO_OU_DUPLICADO',candidates=[c])
    def test_23_invalid_date_stops(self):
        c=candidate();c['vigencia_inicio']='2026-02-31';self.stopped('G14_CANDIDATO_MALFORMADO_OU_DUPLICADO',candidates=[c])
    def test_24_fake_old_document_not_authentic(self):
        r=self.run_case();self.assertFalse(r['documento_autenticado_sefaz']);self.assertFalse(r['fonte_primaria_autenticada'])
    def test_25_multi_partial(self):
        self.raw=xml(count=2);self.g=make_g13(self.raw,count=2,simulated=1)
        r=self.run_case();self.assertEqual(r['itens_cotejados_estruturalmente'],1)
        self.assertEqual(r['estado'],'COBERTURA_CANDIDATA_PARCIAL');self.assert_no_trust(r)
    def test_26_duplicate_xml_cest_stops(self):
        self.raw=xml(duplicate_cest=True);self.g=make_g13(self.raw)
        self.stopped('G14_CLASSIFICACAO_XML_CARDINALIDADE_INVALIDA')
    def test_27_wrong_item_identity_stops(self):
        self.g['confronto_condicional_g12']['itens'][0]['ncm']='99999999';self.stopped('G14_NCM_CFOP_G13_DIVERGENTE')
    def test_28_read_only_db(self):
        self.run_case();self.assertEqual(self.db.writes,0);self.assertEqual(self.db.reads,1)

if __name__=='__main__':unittest.main()
