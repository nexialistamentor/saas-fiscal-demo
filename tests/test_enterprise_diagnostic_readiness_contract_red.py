"""P1-04A RED — leitura interna e restrita de prontidao diagnostica Enterprise.

Executar diretamente com Python -B. Nada de HTTP, auth real, pagamento,
checkout, grants, migracoes, banco produtivo, ou mudancas no MEI.
O futuro servico le entidades persistidas da sessao fornecida e NUNCA escreve.
Diagnostico DOCUMENTAL apresentavel nao equivale a uma auditoria empresarial
completa nem concede autorizacao de venda ou de credito fiscal.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import importlib
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / 'app/services/enterprise_diagnostic_readiness.py'
PREEXISTENTES = (
    'app/services/enterprise_paid_diagnostic_eligibility.py',
    'app/services/enterprise_diagnostic_coverage.py',
    'app/services/enterprise_diagnostic_amount_binding.py',
    'app/services/enterprise_xml_evidence_binding.py',
    'app/services/resultado_provenance_service.py',
)
EMPRESA = 21
UTILIZADOR = 11
RELATORIO = 501
DOCUMENTO = 91
CHAVE = '1' * 44
XML = (
    "<?xml version='1.0' encoding='UTF-8'?>"
    "<nfeProc xmlns='http://www.portalfiscal.inf.br/nfe'>"
    "<NFe><infNFe Id='NFe" + CHAVE + "' versao='4.00'>"
    "<emit><CNPJ>11111111000111</CNPJ><enderEmit><UF>PA</UF></enderEmit></emit>"
    "<dest><enderDest><UF>PA</UF></enderDest></dest>"
    "<det nItem='1'><prod><NCM>22030000</NCM><CFOP>5102</CFOP>"
    "<qCom>1.0000</qCom><vProd>1499.00</vProd></prod>"
    "<imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST>"
    "<vBC>1499.00</vBC><vICMS>269.82</vICMS>"
    "</ICMS00></ICMS></imposto></det>"
    "<total><ICMSTot><vNF>1499.00</vNF></ICMSTot></total>"
    "</infNFe></NFe></nfeProc>"
).encode('utf-8')

NEGADO = {
    'documental_suficiente': False,
    'empresarial_completo': False,
    'st_nao_destacado_observado': False,
    'politica_diagnostico_elegivel': False,
    'diagnostico_documental_apresentavel': False,
    'checkout_autorizado': False,
}
DOCUMENTAL_LIMITADO = {
    'documental_suficiente': True,
    'empresarial_completo': False,
    'st_nao_destacado_observado': True,
    'politica_diagnostico_elegivel': False,
    'diagnostico_documental_apresentavel': True,
    'checkout_autorizado': False,
}


def _carregar_candidata():
    if not SERVICE.is_file():
        raise AssertionError('P104_READINESS_MODULE_MISSING')
    try:
        module = importlib.import_module('app.services.enterprise_diagnostic_readiness')
    except (ModuleNotFoundError, ImportError) as exc:
        raise AssertionError('P104_READINESS_MODULE_IMPORT_FAILED') from exc
    f = getattr(module, 'avaliar_prontidao_diagnostico_enterprise', None)
    if not callable(f):
        raise AssertionError('P104_READINESS_API_MISSING')
    return f


def _contexto_persistido():
    from app.services.enterprise_xml_evidence_binding import (
        construir_vinculo_documento_relatorio, KEY,
    )
    from app.services.resultado_provenance_service import (
        selar_resultado_nao_mei, fingerprint_resultado_json,
    )
    doc = SimpleNamespace(
        id=DOCUMENTO, usuario_id=UTILIZADOR, empresa_id=EMPRESA,
        chave_nfe=CHAVE, conteudo_sha256=hashlib.sha256(XML).hexdigest(),
    )
    proof = construir_vinculo_documento_relatorio(
        XML, empresa_id=EMPRESA, relatorio_id=RELATORIO,
        documento=doc, xml_chave=CHAVE,
    )
    payload = {
        'empresa_id': EMPRESA,
        'dados_fiscais': {
            'chave_nfe': CHAVE,
            'valor_total_nota': '1499.00',
            'uf_emit': 'PA', 'uf_dest': 'PA',
            'cnpj_emitente': '11111111000111', 'icms_st': None,
        },
        'insights': {'documental': [], 'empresarial': None},
        'previsao_recuperacao': {'potencial_recuperacao_nota': None},
        'creditos_detectados': [], 'oportunidades': [],
        'context_flags': {
            'documental': {'dados_incompletos': True},
            'empresarial': {'dados_incompletos': True},
        },
        KEY: proof,
    }
    sealed = selar_resultado_nao_mei(
        payload,
        producer_id='app.services.resultado_empresarial_service.compor_resultado_empresarial',
    )
    rel = SimpleNamespace(
        id=RELATORIO, user_id=UTILIZADOR, empresa_id=EMPRESA,
        analysis_type='xml_analise', xml_chave=CHAVE, status='ok',
        resultado_json=sealed, fingerprint=fingerprint_resultado_json(sealed),
    )
    return rel, doc


class _LeituraDB:
    """Porta minima de leitura; qualquer escrita ou acesso estranho falha."""
    def __init__(self, rel, doc):
        self.rel = rel
        self.doc = doc
        self.requests = []
        self.writes = 0

    def get(self, model, ident):
        self.requests.append((getattr(model, '__name__', ''), ident))
        if getattr(model, '__name__', '') == 'RelatorioAnalise' and ident == RELATORIO:
            return self.rel
        if getattr(model, '__name__', '') == 'DocumentoFiscal' and ident == DOCUMENTO:
            return self.doc
        return None

    def __getattr__(self, name):
        if name in ('add', 'add_all', 'flush', 'commit', 'rollback', 'delete', 'execute',
                    'scalar', 'scalars', 'query', 'merge', 'begin'):
            self.writes += 1
            raise AssertionError('P104_READINESS_DB_WRITE_OR_UNAUTHORIZED_QUERY_' + name)
        raise AttributeError(name)


def _exigir_schema(value):
    assert type(value) is dict and set(value) == set(NEGADO), 'P104_RESULT_SCHEMA_DIVERGENT'
    assert all(type(v) is bool for v in value.values()), 'P104_FLAGS_NOT_BOOL'
    return value


class TestP104EnterpriseCommercialReadinessRED(unittest.TestCase):
    def test_01_baseline_p102_p103_nao_deve_desaparecer(self):
        for name in PREEXISTENTES:
            with self.subTest(name=name):
                self.assertTrue((ROOT / name).is_file(), 'P104_PREEXISTING_AUTHORITY_MISSING')
        self.assertTrue((ROOT / 'app/jobs/analysis_job.py').is_file())

    def test_02_controle_de_identidade_documental_nao_prova_comercio(self):
        self.assertNotEqual(hashlib.sha256(XML).hexdigest(),
                            hashlib.sha256(XML.replace(b'1499.00', b'1499.01')).hexdigest())
        self.assertEqual(DOCUMENTAL_LIMITADO['checkout_autorizado'], False)
        self.assertEqual(DOCUMENTAL_LIMITADO['empresarial_completo'], False)

    def test_03_escopo_documental_pode_ser_apresentavel_sem_venda(self):
        avaliar = _carregar_candidata()
        rel, doc = _contexto_persistido()
        db = _LeituraDB(rel, doc)
        original = deepcopy(rel.resultado_json)
        got = _exigir_schema(avaliar(
            db, authenticated_user_id=UTILIZADOR, empresa_id=EMPRESA,
            relatorio_id=RELATORIO, xml_bytes=XML,
        ))
        self.assertEqual(got, DOCUMENTAL_LIMITADO,
                         'P104_SCOPED_DOCUMENTAL_DIAGNOSTIC_BLOCKED_OR_OVERCLAIMED')
        self.assertIn(('RelatorioAnalise', RELATORIO), db.requests)
        self.assertIn(('DocumentoFiscal', DOCUMENTO), db.requests)
        self.assertEqual(db.writes, 0)
        self.assertEqual(rel.resultado_json, original, 'P104_SEALED_PAYLOAD_MUTATED')

    def test_04_titularidade_sha_proveniencia_e_escopo_falham_fechado(self):
        avaliar = _carregar_candidata()
        rel, doc = _contexto_persistido()
        situations = []
        situations.append(('usuario_invalido', rel, doc, UTILIZADOR + 1, EMPRESA, XML))
        situations.append(('tenant_invalido', rel, doc, UTILIZADOR, EMPRESA + 1, XML))
        situations.append(('xml_mudado_mesma_chave', rel, doc, UTILIZADOR, EMPRESA,
                           XML.replace(b'1499.00', b'1499.01')))
        situations.append(('documento_ausente', rel, None, UTILIZADOR, EMPRESA, XML))
        changed = deepcopy(doc); changed.conteudo_sha256 = '0' * 64
        situations.append(('hash_documento', rel, changed, UTILIZADOR, EMPRESA, XML))
        changed = deepcopy(doc); changed.usuario_id = UTILIZADOR + 1
        situations.append(('outro_proprietario', rel, changed, UTILIZADOR, EMPRESA, XML))
        changed = deepcopy(rel); changed.fingerprint = '0' * 64
        situations.append(('fingerprint_corrompido', changed, doc, UTILIZADOR, EMPRESA, XML))
        changed = deepcopy(rel); changed.status = 'erro'
        situations.append(('relatorio_erro', changed, doc, UTILIZADOR, EMPRESA, XML))
        changed = deepcopy(rel); changed.resultado_json = deepcopy(rel.resultado_json)
        changed.resultado_json.pop('_enterprise_xml_evidence')
        from app.services.resultado_provenance_service import fingerprint_resultado_json
        changed.fingerprint = fingerprint_resultado_json(changed.resultado_json)
        situations.append(('sem_vinculo_legado', changed, doc, UTILIZADOR, EMPRESA, XML))

        for label, report, document, who, tenant, raw in situations:
            with self.subTest(label=label):
                db = _LeituraDB(report, document)
                got = _exigir_schema(avaliar(
                    db, authenticated_user_id=who, empresa_id=tenant,
                    relatorio_id=RELATORIO, xml_bytes=raw,
                ))
                self.assertEqual(got, NEGADO, 'P104_UNVERIFIED_DOCUMENTAL_PRESENTED_' + label)
                self.assertEqual(db.writes, 0)

    def test_05_checkout_legado_e_produtor_nao_podem_ser_substituidos(self):
        avaliar = _carregar_candidata()
        tree = ast.parse(SERVICE.read_text(encoding='utf-8-sig'))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imports.add(node.module or '')
            elif isinstance(node, ast.Import):
                imports.update(x.name for x in node.names)
        forbidden = {
            'app.services.tax_report_eligibility',
            'app.services.tax_report_checkout_intent',
            'app.services.tax_report_acquisition',
            'app.services.checkout_offer_prerequisite',
            'app.services.checkout_offer_catalog',
            'app.services.mercado_pago_gateway',
        }
        self.assertFalse(forbidden & imports, 'P104_LEGACY_COMMERCIAL_PIPELINE_CONTAMINATED')
        self.assertTrue(callable(avaliar))


if __name__ == '__main__':
    unittest.main(verbosity=2)
