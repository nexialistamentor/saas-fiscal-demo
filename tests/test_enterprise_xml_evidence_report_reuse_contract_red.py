"""SOLVERIS P1-03 — RED de vinculação de evidência, TEST ONLY.

Executa o corpo AST REAL de executar_e_registrar_analise_xml com dependências
controladas, sem importar app.database, SQLAlchemy, parser, aplicação ou tocar BD.
Este contrato NÃO prova autenticidade NF-e ou conformidade E2E.
"""
from __future__ import annotations

import ast
import hashlib
import logging
import time
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app/services/registro_analise_service.py"
KEY = "1" * 44
XML_A = b'<NFe Id="NFe' + KEY.encode() + b'" total="1499.00" />'
XML_B = b'<NFe Id="NFe' + KEY.encode() + b'" total="1599.00" />'


class DuplicateDocument(Exception):
    def __init__(self, chave_nfe=None, documento_id=0, *, conteudo_sha256=None):
        super().__init__("documento duplicado")
        self.chave_nfe = chave_nfe
        self.documento_id = documento_id
        self.conteudo_sha256 = conteudo_sha256


class Column:
    def __init__(self, name):
        self.name = name

    def __eq__(self, value):
        return (self.name, value)

    def desc(self):
        return self


class Empresa:
    id = Column("id")


class RelatorioAnalise:
    id = Column("id")
    empresa_id = Column("empresa_id")
    analysis_type = Column("analysis_type")
    xml_chave = Column("xml_chave")


class FakeQuery:
    def __init__(self, candidate):
        self.candidate = candidate
        self.conditions = []

    def filter(self, *conditions):
        self.conditions.extend(conditions)
        return self

    def order_by(self, *args):
        return self

    def first(self):
        if self.candidate is None:
            return None
        for name, value in self.conditions:
            if getattr(self.candidate, name, object()) != value:
                return None
        return self.candidate


class FakeDB:
    def __init__(self):
        self.empresa = SimpleNamespace(id=21, user_id=11)
        self.relatorio = SimpleNamespace(
            id=501, user_id=11, empresa_id=21,
            analysis_type="xml_analise", xml_chave=KEY, status="ok",
            # A fonte documental conserva estes bytes, nao so a chave fiscal.
            documento_sha256=hashlib.sha256(XML_A).hexdigest(),
        )

    def query(self, model):
        if model is Empresa:
            return FakeQuery(self.empresa)
        if model is RelatorioAnalise:
            return FakeQuery(self.relatorio)
        raise AssertionError("P103_UNEXPECTED_DB_QUERY")


def funcao_real_isolada(xml_que_entrou):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"), filename=str(SOURCE))
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name == "executar_e_registrar_analise_xml"]
    if len(funcs) != 1:
        raise AssertionError("P103_ORCHESTRATOR_FUNCTION_MISSING_OR_AMBIGUOUS")

    # Somente a funcao real, sem os imports/efeitos de inicializacao do modulo.
    isolated = ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[]))

    def persistir_documento(db, usuario_atual, empresa, xml_bytes):
        assert db is not None and usuario_atual.id == 11 and empresa.id == 21
        assert xml_bytes == xml_que_entrou
        if xml_bytes == XML_A:
            raise DuplicateDocument(
                documento_id=91, conteudo_sha256=hashlib.sha256(XML_A).hexdigest()
            )
        if xml_bytes == XML_B:
            # Mesma chave mas SHA-256 de bytes diferentes: colisao de CHAVE,
            # nao duplicacao de conteudo. O documento antigo NAO e equivalente.
            raise DuplicateDocument(chave_nfe=KEY, documento_id=91)
        raise AssertionError("P103_UNEXPECTED_XML")

    def bloquear_criacao(*args, **kwargs):
        raise AssertionError("P103_UNEXPECTED_NEW_REPORT_SIDE_EFFECT")

    env = {
        "RelatorioAnalise": RelatorioAnalise,
        "Empresa": Empresa,
        "DuplicataFiscalError": DuplicateDocument,
        "IntegrityError": type("FakeIntegrityError", (Exception,), {}),
        "time": time,
        "logger": logging.getLogger("solveris.p103.test.only"),
        "verificar_limite_analises": lambda *a, **k: None,
        "executar_analise_xml": lambda b: {
            "dados_fiscais": {"chave_nfe": KEY, "valor_total_nota": "1499.00"}
        },
        "processar_e_persistir_xml": persistir_documento,
        "criar_registro_analise": bloquear_criacao,
        "finalizar_registro_analise": bloquear_criacao,
        "contar_alertas_empresa": bloquear_criacao,
        "calcular_score_global_tributario": bloquear_criacao,
        "compor_resultado_empresarial": bloquear_criacao,
        "selar_resultado_nao_mei": bloquear_criacao,
        "incrementar_uso_analise": bloquear_criacao,
    }
    exec(compile(isolated, str(SOURCE), "exec"), env)
    return env["executar_e_registrar_analise_xml"]


class TestEvidenceReuse(unittest.TestCase):
    def test_01_mesmos_bytes_podem_reutilizar_o_mesmo_relatorio(self):
        db = FakeDB()
        f = funcao_real_isolada(XML_A)
        rel, projecao = f(db=db, xml_bytes=XML_A, user_id=11, empresa_id=21)
        self.assertIs(rel, db.relatorio)
        self.assertEqual(projecao["status"], "duplicado")
        self.assertEqual(projecao["xml_chave"], KEY)

    def test_02_shas_de_bytes_distintos_sao_diferentes(self):
        self.assertNotEqual(XML_A, XML_B)
        self.assertNotEqual(hashlib.sha256(XML_A).digest(), hashlib.sha256(XML_B).digest())
        self.assertEqual(XML_A.split(b'"')[1], XML_B.split(b'"')[1])

    def test_03_mesma_chave_com_bytes_diferentes_nao_reutiliza_relatorio(self):
        db = FakeDB()
        f = funcao_real_isolada(XML_B)
        try:
            retorno = f(db=db, xml_bytes=XML_B, user_id=11, empresa_id=21)
        except (DuplicateDocument, ValueError):
            # Fail closed. Caso uma futura implementacao altere o tipo da
            # excecao, ratificar explicitamente antes de atualizar o RED.
            return
        self.fail(
            "P103_XML_BYTES_CHANGED_REUSED_OLD_REPORT: "
            f"o XML diferente recebeu indevidamente {retorno!r}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
