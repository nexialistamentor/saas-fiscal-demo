"""I0: prova causal local do compositor real -> contrato Enterprise completo.

Nao simula lei, direitos fiscais, pagamentos ou deteccao de achados no motor.
"""
import importlib
import unittest

from app.services.resultado_empresarial_service import compor_resultado_empresarial


class EnterpriseIntegralProjectionContractTests(unittest.TestCase):
    def _adapter(self):
        try:
            return importlib.import_module("app.services.enterprise_integral_projection")
        except ModuleNotFoundError as exc:
            if exc.name == "app.services.enterprise_integral_projection":
                self.fail("I0_RED_CAUSAL_ADAPTER_NOT_PRESENT")
            raise

    def _result(self):
        documental = {"insights": [{"tipo": "OBSERVADO_XML"}], "dados_fiscais": {"chave_nfe": "1" * 44},
                      "previsao_recuperacao": {}, "context_flags": {"dados_incompletos": False}}
        inteligencia = {
            "empresa_id": 41, "oportunidades": [{"tipo": "DISTORCAO_MVA", "valor_estimado": 4}],
            "creditos_detectados": [], "risco_tributario": {"nivel_risco": "medio"},
            "resultados_engines": {
                "pis_cofins": {
                    "tributos": {"pis": 12.5, "cofins": 57.6},
                    "creditos": {"pis": 1.25, "cofins": 5.76, "fonte": "insumos_tributados"},
                    "bases_calculo": {"icms_excluido": 8.0}, "regime": "real",
                },
                "irpj": {"total_irpj": 37.0, "adicional_irpj": 2.0},
                "csll": {"valor": 11.0},
                "lucro_real": {"valor": 1.0},
                "tax_planning": {"comparacao": {}},
                "motor_ainda_nao_catalogado": {"resultado": "interno"},
            },
            "comparativo_regime": {"lucro_real": 101, "lucro_presumido": 102},
            "context_flags": {"dados_incompletos": True},
        }
        return compor_resultado_empresarial(41, documental, inteligencia)

    def test_00_contract_requires_integral_adapter(self):
        self.assertTrue(callable(self._adapter().projetar_diagnostico_integral_i0))

    def test_01_no_omission_of_pis_cofins_irpj_csll_and_manifest(self):
        module = self._adapter()
        proj = module.projetar_diagnostico_integral_i0(resultado=self._result(), empresa_id=41)
        catalog = {x["id"]: x for x in proj["cobertura"]}
        self.assertGreaterEqual(len(catalog), 48)
        self.assertEqual(len(catalog), len(proj["cobertura"]))
        for name in ("pis", "cofins", "credito_pis", "credito_cofins", "irpj", "irpj_adicional", "csll", "lucro_real", "lucro_presumido", "icms_st", "mva", "pmpf", "benchmark", "tendencia", "adr020", "danfe_ocr", "nfse_efd_recolhimentos"):
            self.assertIn(name, catalog)
        self.assertNotIn("mei", catalog)
        self.assertEqual(catalog["pis"]["resultado_bruto_nao_validado"], 12.5)
        self.assertEqual(catalog["cofins"]["resultado_bruto_nao_validado"], 57.6)
        self.assertEqual(catalog["irpj_adicional"]["resultado_bruto_nao_validado"], 2.0)
        self.assertEqual(catalog["creditos_st"]["resultado_bruto_nao_validado"], [])
        self.assertEqual(catalog["pis"]["estado"], "informativo_sem_prova")
        self.assertIn("ST_NAO_E_ICMS_PROPRIO", catalog["pis"]["causa"])
        self.assertEqual(catalog["mva"]["estado"], "nao_integrado_ao_snapshot")
        self.assertEqual(proj["engines_nao_catalogadas"], ["motor_ainda_nao_catalogado"])
        self.assertFalse(proj["checkout_autorizado"])
        self.assertFalse(proj["diagnostico_empresarial_completo"])

    def test_02_missing_pis_does_not_hide_cofins(self):
        module = self._adapter()
        resultado = self._result()
        del resultado["resultados_engines"]["pis_cofins"]["tributos"]["pis"]
        proj = module.projetar_diagnostico_integral_i0(resultado=resultado, empresa_id=41)
        by_id = {x["id"]: x for x in proj["cobertura"]}
        self.assertEqual(by_id["pis"]["estado"], "nao_apurado")
        self.assertEqual(by_id["cofins"]["estado"], "informativo_sem_prova")

    def test_03_blocked_engine_is_not_mistaken_for_no_tax_due(self):
        module = self._adapter()
        resultado = self._result()
        resultado["resultados_engines"]["pis_cofins"] = {"erro": "regime ausente", "codigo": "REGIME_FISCAL_INDISPONIVEL", "estado_l3": "bloqueado"}
        proj = module.projetar_diagnostico_integral_i0(resultado=resultado, empresa_id=41)
        entries = {x["id"]: x for x in proj["cobertura"]}
        self.assertEqual(entries["pis"]["estado"], "falha_motor")
        self.assertEqual(entries["cofins"]["causa"], "REGIME_FISCAL_INDISPONIVEL")
        self.assertIsNone(entries["pis"]["resultado_bruto_nao_validado"])

    def test_04_snapshot_must_match_company(self):
        module = self._adapter()
        with self.assertRaisesRegex(module.EnterpriseIntegralProjectionError, "I0_EMPRESA_DIVERGENTE"):
            module.projetar_diagnostico_integral_i0(resultado=self._result(), empresa_id=42)

    def test_05_projection_does_not_mutate_engine_evidence(self):
        module = self._adapter()
        original = self._result()
        proj = module.projetar_diagnostico_integral_i0(resultado=original, empresa_id=41)
        by_id = {x["id"]: x for x in proj["cobertura"]}
        by_id["irpj"]["resultado_bruto_nao_validado"]["total_irpj"] = 999999
        self.assertEqual(original["resultados_engines"]["irpj"]["total_irpj"], 37.0)
        self.assertEqual({x["estado"] for x in proj["cobertura"]}.difference(module.ESTADOS), set())

    def test_06_absent_engines_still_get_all_sections(self):
        module = self._adapter()
        original = self._result()
        original.pop("resultados_engines")
        proj = module.projetar_diagnostico_integral_i0(resultado=original, empresa_id=41)
        by_id = {x["id"]: x for x in proj["cobertura"]}
        self.assertEqual(by_id["pis"]["estado"], "nao_apurado")
        self.assertEqual(by_id["csll"]["estado"], "nao_apurado")
        self.assertEqual(by_id["nfe_xml"]["estado"], "informativo_sem_prova")
        self.assertFalse(proj["checkout_autorizado"])


if __name__ == "__main__":
    unittest.main()
