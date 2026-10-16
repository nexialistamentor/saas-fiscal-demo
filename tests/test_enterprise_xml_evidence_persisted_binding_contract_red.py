"""P1-03B RED — origem documental vinculada ao relatorio persistido.

Somente biblioteca padrao; executar diretamente com Python -B, sem conftest,
app.database, banco, upload, pagamento ou runtime da aplicacao.
Aprovacao aqui NAO autoriza venda nem prova autenticidade SEFAZ.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "app/services/enterprise_xml_evidence_binding.py"
REGISTRY = ROOT / "app/services/registro_analise_service.py"
MODELS = ROOT / "app/models.py"
KEY = "1" * 44
XML = b'<NFe><infNFe Id="NFe' + KEY.encode("ascii") + b'"><vNF>100.00</vNF></infNFe></NFe>'
PRODUCER = "app.services.resultado_empresarial_service.compor_resultado_empresarial"


def _load(name: str, file: Path):
    spec = importlib.util.spec_from_file_location(name, str(file))
    if spec is None or spec.loader is None:
        raise AssertionError("P103B_MODULE_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sealed_report(proof):
    provenance = _load(
        "p103b_provenance_pure",
        ROOT / "app/services/resultado_provenance_service.py",
    )
    business = {
        "empresa_id": 21,
        "dados_fiscais": {"chave_nfe": KEY, "valor_total_nota": "100.00"},
    }
    if proof is not None:
        business["_enterprise_xml_evidence"] = proof
    sealed = provenance.selar_resultado_nao_mei(business, producer_id=PRODUCER)
    return SimpleNamespace(
        id=501,
        user_id=11,
        empresa_id=21,
        analysis_type="xml_analise",
        xml_chave=KEY,
        status="ok",
        resultado_json=sealed,
        fingerprint=provenance.fingerprint_resultado_json(sealed),
    )


def _document():
    return SimpleNamespace(
        id=91,
        usuario_id=11,
        empresa_id=21,
        chave_nfe=KEY,
        conteudo_sha256=hashlib.sha256(XML).hexdigest(),
    )


class TestEnterprisePersistedEvidenceBindingRED(unittest.TestCase):
    def test_01_controle_sha_distingue_xml_alterado_com_mesma_chave(self):
        changed = XML.replace(b"100.00", b"200.00")
        self.assertNotEqual(XML, changed)
        self.assertNotEqual(
            hashlib.sha256(XML).hexdigest(),
            hashlib.sha256(changed).hexdigest(),
        )

    def test_02_models_tem_digests_separados_a_conciliar(self):
        tree = ast.parse(MODELS.read_text(encoding="utf-8-sig"))
        classes = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
        }
        for name, field in (("DocumentoFiscal", "conteudo_sha256"),
                            ("RelatorioAnalise", "fingerprint")):
            cls = classes[name]
            attrs = {
                target.id
                for node in cls.body if isinstance(node, ast.Assign)
                for target in node.targets if isinstance(target, ast.Name)
            }
            self.assertIn(field, attrs)

    def test_03_exige_vinculo_no_snapshot_selado_e_verificador_fail_closed(self):
        if not SERVICE.is_file():
            self.fail("P103B_PERSISTED_XML_BINDING_MODULE_MISSING")
        mod = _load("p103b_binding_pure", SERVICE)
        build = getattr(mod, "construir_vinculo_documento_relatorio", None)
        validate = getattr(mod, "validar_vinculo_documento_relatorio", None)
        self.assertTrue(callable(build) and callable(validate),
                        "P103B_PERSISTED_XML_BINDING_API_MISSING")

        doc = _document()
        proof = build(
            XML, empresa_id=21, relatorio_id=501, documento=doc,
            xml_chave=KEY,
        )
        self.assertIsInstance(proof, dict)
        self.assertEqual(proof.get("schema_version"), "ENTERPRISE_XML_EVIDENCE_V1")
        self.assertEqual(proof.get("xml_sha256"), doc.conteudo_sha256)
        self.assertEqual(proof.get("empresa_id"), 21)
        self.assertEqual(proof.get("relatorio_id"), 501)
        self.assertEqual(proof.get("documento_id"), doc.id)
        self.assertEqual(proof.get("xml_chave"), KEY)
        report = _sealed_report(proof)
        self.assertIs(validate(report, doc, empresa_id=21), True)

        wrong_hash = SimpleNamespace(**vars(doc))
        wrong_hash.conteudo_sha256 = hashlib.sha256(XML + b" ").hexdigest()
        self.assertIs(validate(report, wrong_hash, empresa_id=21), False,
                      "P103B_XML_SHA_MISMATCH_ACCEPTED")
        wrong_doc_id = SimpleNamespace(**vars(doc))
        wrong_doc_id.id = 999
        self.assertIs(validate(report, wrong_doc_id, empresa_id=21), False,
                      "P103B_DOC_ID_MISMATCH_ACCEPTED")
        wrong_doc_tenant = SimpleNamespace(**vars(doc))
        wrong_doc_tenant.empresa_id = 22
        self.assertIs(validate(report, wrong_doc_tenant, empresa_id=21), False,
                      "P103B_CROSS_TENANT_DOCUMENT_ACCEPTED")
        wrong_owner = SimpleNamespace(**vars(doc))
        wrong_owner.usuario_id = 99
        self.assertIs(validate(report, wrong_owner, empresa_id=21), False,
                      "P103B_DOC_OWNER_MISMATCH_ACCEPTED")
        wrong_key = SimpleNamespace(**vars(doc))
        wrong_key.chave_nfe = "2" * 44
        self.assertIs(validate(report, wrong_key, empresa_id=21), False,
                      "P103B_NFE_KEY_MISMATCH_ACCEPTED")
        wrong_report = SimpleNamespace(**vars(report))
        wrong_report.id = 999
        self.assertIs(validate(wrong_report, doc, empresa_id=21), False,
                      "P103B_REPORT_ID_MISMATCH_ACCEPTED")
        corrupted = SimpleNamespace(**vars(report))
        corrupted.fingerprint = "0" * 64
        self.assertIs(validate(corrupted, doc, empresa_id=21), False,
                      "P103B_FINGERPRINT_MISMATCH_ACCEPTED")
        old_report = _sealed_report(None)
        self.assertIs(validate(old_report, doc, empresa_id=21), False,
                      "P103B_LEGACY_REPORT_WITHOUT_BINDING_ACCEPTED")
        self.assertIs(validate(report, doc, empresa_id=22), False,
                      "P103B_WRONG_REQUEST_TENANT_ACCEPTED")
        altered = SimpleNamespace(**vars(report))
        altered.resultado_json = dict(report.resultado_json)
        altered.resultado_json["_enterprise_xml_evidence"] = dict(proof, xml_sha256="0"*64)
        self.assertIs(validate(altered, doc, empresa_id=21), False,
                      "P103B_MUTATED_PERSISTED_SNAPSHOT_ACCEPTED")
        # Esta funcao nao confere pagamento, SEFAZ nem cobertura fiscal completa.

    def test_04_exige_produtor_real_antes_da_selagem_resultado(self):
        tree = ast.parse(REGISTRY.read_text(encoding="utf-8-sig"))
        func = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "executar_e_registrar_analise_xml"
        )
        call_lines = [
            (node.lineno, node.func.id)
            for node in ast.walk(func)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        origins = [n for n, fn in call_lines if fn == "construir_vinculo_documento_relatorio"]
        seals = [n for n, fn in call_lines if fn == "selar_resultado_nao_mei"]
        finals = [n for n, fn in call_lines if fn == "finalizar_registro_analise"]
        if not (origins and seals and finals and min(origins) < min(seals) < min(finals)):
            self.fail("P103B_PERSISTED_EVIDENCE_WRITER_NOT_WIRED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
