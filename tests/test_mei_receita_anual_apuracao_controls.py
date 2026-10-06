"""Additional controls; R1 remains immutable."""
from copy import deepcopy
from decimal import localcontext
import unittest

from app.services.mei_receita_anual_apuracao import apurar_receitas_anuais


def item(key, value="0.00", **changes):
    return dict(identidade_receita=key, empresa_id=1, data_receita="2026-01-01",
                valor=value, categoria="servicos", origem="documento",
                estado="vigente", **changes)


class ApuracaoControls(unittest.TestCase):
    def test_zero_documentado_distingue_mes_desconhecido_sem_completude(self):
        result = apurar_receitas_anuais(empresa_id=1, ano_calendario=2026,
                                       receitas=[item("zero")])
        self.assertEqual(result["meses"][0]["total_receitas_incluidas"], "0.00")
        self.assertEqual(result["meses"][0]["estado"], "parcial")
        self.assertIsNone(result["meses"][1]["total_receitas_incluidas"])
        self.assertFalse(result["completude_anual_comprovada"])

    def test_centavos_preservados_com_contexto_decimal_externo_restrito(self):
        entradas = [item("a", "9999999999999.99"), item("b", "0.01")]
        original = deepcopy(entradas)
        with localcontext() as contexto:
            contexto.prec = 3
            result = apurar_receitas_anuais(empresa_id=1, ano_calendario=2026,
                                           receitas=entradas)
            self.assertEqual(contexto.prec, 3)
        self.assertEqual(result["total_receitas_incluidas"], "10000000000000.00")
        self.assertEqual(entradas, original)
        result["receitas_incluidas"][0]["valor"] = "0.00"
        self.assertEqual(entradas, original)

    def test_identidade_com_data_alterada_nao_escapa_pelo_filtro_anual(self):
        antiga = {**item("mesma", "10.00"), "data_receita": "2025-12-31"}
        with self.assertRaisesRegex(ValueError, "RECEITA_IDENTIDADE_CONFLITANTE"):
            apurar_receitas_anuais(empresa_id=1, ano_calendario=2026,
                                   receitas=[antiga, item("mesma", "10.00")])

    def test_escopo_e_registros_invalidos_bloqueiam(self):
        for empresa, ano, entradas in ((True, 2026, []), (1, True, []),
                                      (1, 2026, None),
                                      (1, 2026, [{**item("a"), "valor": "0.001"}]),
                                      (1, 2026, [{**item("a"), "extra": "ignorar"}])):
            with self.subTest(empresa=empresa, ano=ano, entradas=entradas):
                with self.assertRaises(ValueError):
                    apurar_receitas_anuais(empresa_id=empresa, ano_calendario=ano,
                                           receitas=entradas)


if __name__ == "__main__":
    unittest.main()
