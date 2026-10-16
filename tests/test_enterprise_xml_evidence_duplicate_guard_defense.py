"""P1-03A: defesa isolada AST contra reutilizacao por chave/bytes divergentes.

Nao importa BD, ORM, app.main, nem executa HTTP, SQL ou persistencia.
O teste RED original permanece integralmente intocado.
"""
import hashlib
import unittest

from test_enterprise_xml_evidence_report_reuse_contract_red import (
    DuplicateDocument, FakeDB, KEY, XML_A, XML_B, funcao_real_isolada,
)


class TestDuplicateGuardDefense(unittest.TestCase):
    def test_01_conflito_mesma_chave_sem_sha_da_duplicata_falha_fechado(self):
        db = FakeDB()
        func = funcao_real_isolada(XML_B)
        with self.assertRaises(DuplicateDocument):
            func(db=db, xml_bytes=XML_B, user_id=11, empresa_id=21)

    def test_02_sha_informado_divergente_nao_autoriza_reutilizacao(self):
        original = DuplicateDocument.__init__

        def falsificado(self, chave_nfe=None, documento_id=0, *, conteudo_sha256=None):
            return original(self, chave_nfe=chave_nfe, documento_id=documento_id,
                            conteudo_sha256="f" * 64)

        try:
            DuplicateDocument.__init__ = falsificado
            db = FakeDB()
            func = funcao_real_isolada(XML_A)
            with self.assertRaises(DuplicateDocument):
                func(db=db, xml_bytes=XML_A, user_id=11, empresa_id=21)
        finally:
            DuplicateDocument.__init__ = original

    def test_03_duplicado_mesmo_sha_pode_reutilizar_relatorio_no_fixture(self):
        db = FakeDB()
        f = funcao_real_isolada(XML_A)
        rel, retorno = f(db=db, xml_bytes=XML_A, user_id=11, empresa_id=21)
        self.assertIs(rel, db.relatorio)
        self.assertEqual(retorno['status'], 'duplicado')

    def test_04_guard_nao_prova_vinculacao_persistida(self):
        """Prova que o RED usa atributo ficticio inexistente no ORM.

        Nao confundir a verificacao de bytes com elo criptografico do
        resultado. Esta e a proxima obrigacao P1-03B antes do checkout.
        """
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        src = (root / 'app/models.py').read_text(encoding='utf-8-sig')
        block = src.split('class RelatorioAnalise(Base):',1)[1].split('\nclass ',1)[0]
        self.assertNotIn('documento_sha256 = Column(', block)
        self.assertIn('fingerprint = Column(', block)


if __name__ == '__main__':
    unittest.main(verbosity=2)
