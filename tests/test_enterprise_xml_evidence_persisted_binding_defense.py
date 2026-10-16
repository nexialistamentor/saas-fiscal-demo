"""P1-03B defesa pura e estatica; nao inicializa app.database nem opera banco.

Run: python -B tests/test_enterprise_xml_evidence_persisted_binding_defense.py
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "app/services/enterprise_xml_evidence_binding.py"
REGISTRY = ROOT / "app/services/registro_analise_service.py"
KEY = '1' * 44
XML = b'<NFe><infNFe Id="NFe' + KEY.encode('ascii') + b'"><vNF>100.00</vNF></infNFe></NFe>'


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Defense(unittest.TestCase):
    def setUp(self):
        self.binding = _mod('p103b_binding_defense', MODULE)
        self.doc = SimpleNamespace(id=91, usuario_id=11, empresa_id=21, chave_nfe=KEY,
                                   conteudo_sha256=hashlib.sha256(XML).hexdigest())

    def _build(self, xml=XML, doc=None, chave=KEY):
        return self.binding.construir_vinculo_documento_relatorio(
            xml, empresa_id=21, relatorio_id=501,
            documento=self.doc if doc is None else doc, xml_chave=chave,
        )

    def test_01_prova_valida_nao_reescreve_bytes(self):
        before = bytes(XML)
        proof = self._build()
        self.assertEqual(XML, before)
        self.assertEqual(proof['xml_sha256'], hashlib.sha256(XML).hexdigest())
        self.assertEqual(proof['usuario_id'], 11)
        self.assertEqual(set(proof), {
            'schema_version', 'xml_sha256', 'empresa_id', 'usuario_id',
            'relatorio_id', 'documento_id', 'xml_chave',
        })

    def test_02_xml_diferente_mesma_chave_nao_e_vinculado(self):
        with self.assertRaisesRegex(ValueError, 'P103B_XML_EVIDENCE_UNVERIFIED'):
            self._build(XML.replace(b'100.00', b'200.00'))

    def test_03_hash_divergente_documento_nao_vincula(self):
        doc = SimpleNamespace(**vars(self.doc))
        doc.conteudo_sha256 = '0' * 64
        with self.assertRaises(ValueError):
            self._build(doc=doc)

    def test_04_tenant_owner_e_ids_invalidos_nao_vinculam(self):
        for attr, value in (
            ('empresa_id', 22), ('usuario_id', 0), ('id', True),
            ('chave_nfe', '2' * 44), ('conteudo_sha256', None),
        ):
            doc = SimpleNamespace(**vars(self.doc))
            setattr(doc, attr, value)
            with self.subTest(attr=attr), self.assertRaises(ValueError):
                self._build(doc=doc)

    def test_05_xml_malformado_dtd_key_falsa_bloqueados(self):
        payloads = (
            b'<NFe>',
            b'<!DOCTYPE x [<!ENTITY boom "BOMB">]>' + XML,
            XML.replace(KEY.encode(), b'2' * 44),
            XML.replace(b'<infNFe', b'<semIdentidade').replace(b'</infNFe>', b'</semIdentidade>'),
        )
        for xml in payloads:
            with self.subTest(xml=xml[:30]), self.assertRaises(ValueError):
                self._build(xml)

    def test_06_prova_nao_e_um_direito_a_compra(self):
        tree = ast.parse(MODULE.read_text(encoding='utf-8-sig'))
        all_imports = {
            node.module
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        } | {
            alias.name
            for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names
        }
        forbidden = {'app.database', 'app.models', 'app.services.tax_report_checkout_intent',
                     'app.services.tax_report_acquisition'}
        self.assertFalse(forbidden & all_imports)
        regtree = ast.parse(REGISTRY.read_text(encoding='utf-8-sig'))
        fn = next(n for n in regtree.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'executar_e_registrar_analise_xml')
        calls = {(n.lineno, n.func.id) for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        evidence_lines = [n for n, name in calls if name == 'construir_vinculo_documento_relatorio']
        seal_lines = [n for n, name in calls if name == 'selar_resultado_nao_mei']
        self.assertTrue(evidence_lines and seal_lines and min(evidence_lines) < min(seal_lines))


if __name__ == '__main__':
    unittest.main(verbosity=2)
