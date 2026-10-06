"""Contract R1: arithmetic over supplied evidence, not fiscal certification.

No DB, provider, payment, normative limit or declaration submission is involved.
Amounts are canonical decimal strings. This contract deliberately fails until
the pure apuration service exists. Existing production contracts stay untouched.
"""
import importlib
import unittest


def apurar(receitas, *, empresa_id=1, ano=2026):
    service = importlib.import_module("app.services.mei_receita_anual_apuracao")
    return service.apurar_receitas_anuais(
        empresa_id=empresa_id, ano_calendario=ano, receitas=receitas,
    )


def receita(identidade, valor="100.00", *, empresa=1, data="2026-01-10",
            categoria="servicos", origem="documento", estado="vigente"):
    return dict(identidade_receita=identidade, empresa_id=empresa,
                data_receita=data, valor=valor, categoria=categoria,
                origem=origem, estado=estado)


class ApuracaoAnualContract(unittest.TestCase):
    def test_empresa_e_ano_isolados_sem_projecao_mensal(self):
        result = apurar([
            receita("a", "100.10"), receita("b", "0.20", data="2026-12-31"),
            receita("outra", "900.00", empresa=2),
            receita("anterior", "900.00", data="2025-12-31"),
            receita("seguinte", "900.00", data="2027-01-01"),
        ])
        self.assertEqual(result["total_receitas_incluidas"], "100.30")
        self.assertEqual(result["empresa_id"], 1)
        self.assertEqual(result["ano_calendario"], 2026)
        self.assertFalse(result["completude_anual_comprovada"])

    def test_receita_identica_reenviada_conta_uma_vez(self):
        item = receita("mesma")
        result = apurar([item, dict(item)])
        self.assertEqual(result["total_receitas_incluidas"], "100.00")
        self.assertEqual(result["duplicatas_ignoradas"], 1)

    def test_identidade_repetida_divergente_bloqueia_total(self):
        with self.assertRaisesRegex(ValueError, "RECEITA_IDENTIDADE_CONFLITANTE"):
            apurar([receita("mesma"), receita("mesma", "200.00")])

    def test_sem_nota_e_documentadas_separadas_com_origem(self):
        result = apurar([
            receita("nota", "10.00", categoria="comercio_industria"),
            receita("venda-sem-nota", "20.00", origem="informada_sem_nota"),
        ])
        self.assertEqual(result["totais_por_categoria"],
                         {"comercio_industria": "10.00", "servicos": "20.00"})
        self.assertEqual(result["totais_por_origem"],
                         {"documento": "10.00", "informada_sem_nota": "20.00"})
        self.assertEqual({r["identidade_receita"] for r in result["receitas_incluidas"]},
                         {"nota", "venda-sem-nota"})

    def test_mes_sem_evidencia_nao_vira_zero(self):
        result = apurar([])
        self.assertEqual(result["total_receitas_incluidas"], "0.00")
        self.assertEqual(len(result["meses"]), 12)
        self.assertTrue(all(m["total_receitas_incluidas"] is None
                            and m["estado"] == "nao_informado"
                            for m in result["meses"]))
        self.assertFalse(result["completude_anual_comprovada"])

    def test_eventos_fiscais_ambiguos_nao_sao_receita_confirmada(self):
        result = apurar([receita("normal", "10.00"),
                         receita("evento", "90.00", estado="pendente_revisao")])
        self.assertEqual(result["total_receitas_incluidas"], "10.00")
        self.assertEqual([r["identidade_receita"] for r in result["pendencias"]], ["evento"])

    def test_entrada_malformada_falha_sem_coercao_silenciosa(self):
        for changes in ({"valor": "NaN"}, {"valor": "-1.00"},
                        {"valor": 10.0}, {"data_receita": "2026-02-30"},
                        {"categoria": "desconhecida"}, {"estado": "cancelada"},
                        {"origem": "total_mensal"}, {"identidade_receita": ""}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                apurar([{**receita("a"), **changes}])


if __name__ == "__main__":
    unittest.main()
