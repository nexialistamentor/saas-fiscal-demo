"""I2 causal: XML real sintético -> posse -> hash -> itens -> I1.

Sem rede, BD produtiva, SEFAZ, escrita, checkout ou inferencia normativa.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import importlib
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.models import DocumentoFiscal, Empresa, RelatorioAnalise
from app.services.resultado_provenance_service import (
    fingerprint_resultado_json, selar_resultado_nao_mei,
)

_CNPJ = '12345678000190'
_KEY = '1' * 44


def _xml(*, icms_group='ICMS10', icms='80.00', st='20.00', total='1000.00',
         item_product='1000.00', emit=_CNPJ, date_text='2026-09-12T10:00:00-03:00',
         doc_type='1', fin='1', ncm='22030000', cfop='5102', extra=''):
    group = (f'<nfe:{icms_group}><nfe:orig>0</nfe:orig><nfe:CST>10</nfe:CST>'
             f'<nfe:vBC>1000.00</nfe:vBC>'
             + (f'<nfe:vICMS>{icms}</nfe:vICMS>' if icms is not None else '')
             + (f'<nfe:vST>{st}</nfe:vST>' if st is not None else '')
             + f'</nfe:{icms_group}>')
    data = f'''<nfe:nfeProc xmlns:nfe="http://www.portalfiscal.inf.br/nfe">
<nfe:NFe><nfe:infNFe Id="NFe{_KEY}"><nfe:ide><nfe:dhEmi>{date_text}</nfe:dhEmi>
<nfe:tpNF>{doc_type}</nfe:tpNF><nfe:finNFe>{fin}</nfe:finNFe></nfe:ide>
<nfe:emit><nfe:CNPJ>{emit}</nfe:CNPJ></nfe:emit>
<nfe:det nItem="1"><nfe:prod><nfe:NCM>{ncm}</nfe:NCM><nfe:CFOP>{cfop}</nfe:CFOP>
<nfe:vProd>{item_product}</nfe:vProd></nfe:prod><nfe:imposto><nfe:ICMS>{group}</nfe:ICMS></nfe:imposto></nfe:det>
<nfe:total><nfe:ICMSTot><nfe:vNF>{total}</nfe:vNF></nfe:ICMSTot></nfe:total>
{extra}</nfe:infNFe></nfe:NFe>
<nfe:protNFe><nfe:infProt><nfe:chNFe>{_KEY}</nfe:chNFe></nfe:infProt></nfe:protNFe>
</nfe:nfeProc>'''
    return data.encode('utf-8')


class _DB:
    def __init__(self, emp, report, doc):
        self.items = {(Empresa, 41): emp, (RelatorioAnalise, 77): report,
                      (DocumentoFiscal, 10): doc}
        self.writes = 0

    def get(self, model, ident):
        return self.items.get((model, ident))

    def add(self, *_):
        self.writes += 1
        raise AssertionError('I2_DB_WRITE_FORBIDDEN')

    def commit(self):
        self.writes += 1
        raise AssertionError('I2_DB_COMMIT_FORBIDDEN')


class EnterpriseI2BridgeTests(unittest.TestCase):
    def setUp(self):
        try:
            self.bridge = importlib.import_module('app.services.enterprise_i2_documentary_bridge')
        except ModuleNotFoundError as exc:
            if exc.name == 'app.services.enterprise_i2_documentary_bridge':
                self.fail('I2_RED_CAUSAL_ADAPTER_NOT_PRESENT')
            raise
        self.raw = _xml()
        self.hash = hashlib.sha256(self.raw).hexdigest()
        self.emp = SimpleNamespace(id=41, user_id=7, cnpj=_CNPJ, regime_tributario='real', optante_mei=False)
        self.item = SimpleNamespace(id=12, documento_id=10, ncm='22030000', cfop='5102',
                                    valor_produto=1000.0, valor_icms=80.0)
        self.doc = SimpleNamespace(id=10, empresa_id=41, usuario_id=7, tipo='saida',
                                   conteudo_sha256=self.hash, chave_nfe=_KEY, cnpj_emitente=_CNPJ,
                                   data_emissao=date(2026, 9, 12), itens=[self.item])
        self.payload = {
            'empresa_id': 41,
            'dados_fiscais': {'chave_nfe': _KEY, 'cnpj_emitente': _CNPJ},
            'context_flags': {'empresarial': {'dados_incompletos': True}},
            'resultados_engines': {},
            '_enterprise_xml_evidence': {
                'schema_version': 'ENTERPRISE_XML_EVIDENCE_V1',
                'xml_sha256': self.hash, 'empresa_id': 41,
                'usuario_id': 7, 'relatorio_id': 77, 'documento_id': 10,
                'xml_chave': _KEY,
            },
        }
        self.report = SimpleNamespace(id=77, empresa_id=41, user_id=7,
                                      analysis_type='xml_analise', status='ok', xml_chave=_KEY)
        self._seal()
        self.db = _DB(self.emp, self.report, self.doc)

    def _seal(self):
        self.report.resultado_json = selar_resultado_nao_mei(
            self.payload, producer_id='app.services.resultado_empresarial_service.compor_resultado_empresarial')
        self.report.fingerprint = fingerprint_resultado_json(self.report.resultado_json)

    def _run(self, **kwargs):
        args = dict(db=self.db, authenticated_user_id=7, empresa_id=41,
                    relatorio_id=77, xml_bytes=self.raw)
        args.update(kwargs)
        return self.bridge.projetar_diagnostico_integral_i2(**args)

    def _stop(self, expected, **kwargs):
        with self.assertRaisesRegex(self.bridge.EnterpriseI2EvidenceError, expected):
            self._run(**kwargs)

    def test_00_real_contract_exists(self):
        self.assertTrue(callable(self.bridge.projetar_diagnostico_integral_i2))

    def test_01_positive_real_xml_bound_to_real_provenance_and_i1_engine(self):
        with patch('app.services.tax_engines.pis_cofins_engine.calcular_pis_cofins',
                   return_value={'tributos': {'pis': 15.18, 'cofins': 69.92}}) as calc:
            result = self._run()
        call, kw = calc.call_args
        self.assertEqual(call[0]['faturamento'], 1000.0)
        self.assertEqual(call[0]['icms'], 80.0)
        self.assertNotIn('icms_pago', call[0])
        self.assertNotIn('icms_devido', call[0])
        self.assertEqual(result['documental_i2']['itens_xml_observados'][0]['icms_st_separado_observado'], '20.00')
        self.assertEqual(result['pis_cofins_i1']['simulacao_nao_comercial']['pis'], 15.18)
        self.assertEqual(len(result['cobertura']), 52)
        self.assertFalse(result['checkout_autorizado'])
        self.assertFalse(result['comprovacao_normativa'])
        self.assertFalse(result['documental_i2']['autenticidade_sefaz_verificada'])
        self.assertEqual(result['uso'], 'INTERNO_NAO_PUBLICAVEL')
        self.assertEqual(self.db.writes, 0)

    def test_02_bytes_diferentes_mesmachave_recusados(self):
        changed = self.raw.replace(b'1000.00', b'2000.00')
        self._stop('I2_BYTES_HASH_MISMATCH', xml_bytes=changed)

    def test_03_snapshot_adulterado_recusado(self):
        self.report.resultado_json['empresa_id'] = 42
        self._stop('I2_REPORT_FINGERPRINT_INVALID')

    def test_04_empresa_alheia_recusada(self):
        self.emp.user_id = 8
        self._stop('I2_SUBJECT_REGIME_OR_OWNER_INVALID')

    def test_05_mei_recusado(self):
        self.emp.optante_mei = True
        self._stop('I2_SUBJECT_REGIME_OR_OWNER_INVALID')

    def test_06_relatorio_sem_proveniencia_recusado(self):
        self.report.resultado_json.pop('_resultado_provenance')
        self.report.fingerprint = fingerprint_resultado_json(self.report.resultado_json)
        self._stop('I2_REPORT_FINGERPRINT_INVALID')

    def test_07_chave_no_report_alterada_recusada(self):
        self.report.xml_chave = '2' * 44
        self._stop('I2_XML_REPORT_BINDING_INVALID')

    def test_08_item_db_valor_icms_divergente_recusado(self):
        self.item.valor_icms = 800.0
        self._stop('I2_ITEM_DB_XML_MISMATCH')

    def test_09_sem_icms_proprio_nao_finge_zero(self):
        self.raw = _xml(icms_group='ICMS60', icms=None, st='20.00')
        new = hashlib.sha256(self.raw).hexdigest()
        self.doc.conteudo_sha256 = new
        self.payload['_enterprise_xml_evidence']['xml_sha256'] = new
        self._seal()
        self._stop('I2_ICMS_PROPRIO_NOT_OBSERVED')

    def test_10_st_separado_nao_e_icms_proprio(self):
        result = self._run()
        self.assertEqual(result['documental_i2']['itens_xml_observados'][0]['icms_proprio_observado'], '80.00')
        self.assertEqual(result['documental_i2']['itens_xml_observados'][0]['icms_st_separado_observado'], '20.00')

    def test_11_nao_aceitar_nfe_de_entrada(self):
        self.doc.tipo = 'entrada'
        self._stop('I2_DOCUMENT_OWNER_OR_TYPE_INVALID')

    def test_12_sem_autenticidade_sefaz_mesmo_com_protocolo(self):
        result = self._run()
        self.assertIs(result['documental_i2']['autenticidade_sefaz_verificada'], False)
        self.assertEqual(result['documental_i2']['limite'], 'NF_E_UNICA_NAO_COMPROVA_FATURACAO_DA_COMPETENCIA')

    def test_13_sem_vnf_igual_produtos_bloqueado(self):
        self.raw = _xml(total='1200.00')
        new = hashlib.sha256(self.raw).hexdigest()
        self.doc.conteudo_sha256 = new
        self.payload['_enterprise_xml_evidence']['xml_sha256'] = new
        self._seal()
        self._stop('I2_DOC_TOTAL_NOT_EQUAL_ITEM_PRODUCTS')

    def test_14_relatorio_nao_aprovado_bloqueado(self):
        self.report.status = 'processando'
        self._stop('I2_REPORT_OWNER_OR_STATUS_INVALID')

    def test_15_empresas_regime_nao_elegivel(self):
        self.emp.regime_tributario = 'simples'
        self._stop('I2_SUBJECT_REGIME_OR_OWNER_INVALID')

    def test_16_hash_igual_mas_item_db_de_outra_nota_recusado(self):
        self.item.documento_id = 99
        self._stop('I2_ITEM_DB_IDENTITY_INVALID')

    def test_17_nao_converte_documento_de_saida_em_receita_mensal_completa(self):
        result = self._run()
        self.assertFalse(result['diagnostico_empresarial_completo'])
        self.assertEqual(result['documental_i2']['competencia_observada'], '2026-09')
        self.assertEqual(result['pis_cofins_i1']['estado'], 'simulacao_sem_prova')
        by = {x['id']: x for x in result['cobertura']}
        self.assertIsNone(by['credito_pis']['simulacao_condicional'])
        self.assertIsNone(by['credito_cofins']['simulacao_condicional'])

    def test_18_documento_mais_um_item_que_db_recusado(self):
        self.doc.itens = []
        self._stop('I2_ITEM_DB_CARDINALITY_MISMATCH')

    def test_19_xml_fora_tipo_recusado(self):
        self.raw = b'<doc/>'
        new = hashlib.sha256(self.raw).hexdigest()
        self.doc.conteudo_sha256 = new
        self.payload['_enterprise_xml_evidence']['xml_sha256'] = new
        self._seal()
        self._stop('I2_NOT_NFE')


if __name__ == '__main__':
    unittest.main()
