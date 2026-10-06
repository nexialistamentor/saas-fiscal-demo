"""R2: inventory of persisted fiscal metadata, never automatic revenue.

The existing DocumentoFiscal lacks issuer, operation nature and fiscal status.
This boundary selects candidates for review; it must not invent these facts.
It does not query a DB or provide authentication. A later tenant-scoped reader
must supply these records and prove ownership independently.
"""
import importlib
import unittest


def selecionar(documentos):
    service = importlib.import_module("app.services.mei_receita_documental_selection")
    return service.selecionar_documentos_para_conferencia(
        empresa_id=1, ano_calendario=2026, documentos=documentos,
    )


def documento(numero, **mudancas):
    return {"id": numero, "empresa_id": 1, "data_emissao": "2026-01-10",
            "tipo": "saida", "valor_total": 100.0, "chave_nfe": str(numero).zfill(44),
            "conteudo_sha256": str(numero).zfill(64), **mudancas}


class DocumentalSelectionContract(unittest.TestCase):
    def test_seleciona_apenas_empresa_e_ano_sem_confundir_365_dias(self):
        result = selecionar([
            documento(1), documento(2, data_emissao="2026-12-31"),
            documento(3, empresa_id=2), documento(4, data_emissao="2025-12-31"),
            documento(5, data_emissao="2027-01-01"),
        ])
        self.assertEqual([d["documento_id"] for d in result["documentos_para_revisao"]], [1, 2])
        self.assertEqual(result["receitas_confirmadas"], [])
        self.assertIsNone(result["total_receita_confirmada"])
        self.assertFalse(result["completude_anual_comprovada"])

    def test_saida_nao_prova_venda_e_entrada_nao_e_descartada_por_presuncao(self):
        result = selecionar([documento(1), documento(2, tipo="entrada")])
        self.assertEqual(len(result["documentos_para_revisao"]), 2)
        self.assertEqual(result["receitas_confirmadas"], [])
        for registro in result["documentos_para_revisao"]:
            self.assertTrue({"EMITENTE_NAO_COMPROVADO", "NATUREZA_OPERACAO_NAO_COMPROVADA",
                             "ESTADO_FISCAL_NAO_COMPROVADO"}.issubset(registro["motivos"]))
            self.assertIsNone(registro["categoria_receita"])

    def test_data_ausente_nao_desaparece_nem_recebe_ano_inventado(self):
        result = selecionar([documento(1, data_emissao=None),
                             documento(2, empresa_id=2, data_emissao=None)])
        self.assertEqual([d["documento_id"] for d in result["documentos_sem_periodo"]], [1])
        self.assertEqual(result["documentos_para_revisao"], [])
        self.assertIsNone(result["total_receita_confirmada"])

    def test_mesmo_documento_repetido_nao_duplica_inventario(self):
        item = documento(1)
        result = selecionar([item, dict(item)])
        self.assertEqual(len(result["documentos_para_revisao"]), 1)
        self.assertEqual(result["duplicatas_ignoradas"], 1)
        with self.assertRaisesRegex(ValueError, "DOCUMENTO_IDENTIDADE_CONFLITANTE"):
            selecionar([item, documento(1, valor_total=200.0)])

    def test_metadados_invalidos_nao_se_tornam_evidencia_valida(self):
        for mudancas in ({"data_emissao": "2026-02-30"}, {"id": True},
                         {"empresa_id": True}, {"valor_total": float("nan")},
                         {"valor_total": -1.0}, {"tipo": "inventado"}):
            with self.subTest(mudancas=mudancas), self.assertRaises(ValueError):
                selecionar([documento(1, **mudancas)])


if __name__ == "__main__":
    unittest.main()
