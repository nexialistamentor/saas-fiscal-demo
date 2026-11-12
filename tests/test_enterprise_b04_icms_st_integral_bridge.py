"""B04: testes do wrapper que liga G13 a cadeia integral I0-I1-I2.

Sem conexao DB real -- projetar_diagnostico_integral_i2 e
projetar_confronto_st_sujeito_g13 sao mockados via unittest.mock,
mesmo padrao de tests/test_enterprise_g113_c5_parameter_trace.py e
tests/test_enterprise_b03_item_reconciliation.py.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.enterprise_b04_icms_st_integral_bridge import (
    projetar_diagnostico_integral_icms_st, SCHEMA_VERSION,
)
from app.services.enterprise_g13_subject_st_bridge import EnterpriseG13GateError

DB_SENTINELA = object()


def _cobertura_base():
    return {
        "schema_version": "I2_MOCK",
        "cobertura": [
            {"id": "icms_st", "grupo": "icms_st", "origem": "pendente",
             "produtor_ou_chave": "st_service", "estado": "nao_integrado_ao_snapshot",
             "causa": "X", "autoridade_fiscal": False, "resultado_bruto_nao_validado": None},
            {"id": "mva", "grupo": "icms_st", "origem": "pendente",
             "produtor_ou_chave": "fiscal_utils", "estado": "nao_integrado_ao_snapshot",
             "causa": "X", "autoridade_fiscal": False, "resultado_bruto_nao_validado": None},
            {"id": "consistencia_fiscal", "grupo": "icms_st", "origem": "pendente",
             "produtor_ou_chave": "tax_consistency_engine", "estado": "nao_integrado_ao_snapshot",
             "causa": "X", "autoridade_fiscal": False, "resultado_bruto_nao_validado": None},
            {"id": "pmpf", "grupo": "icms_st", "origem": "pendente",
             "produtor_ou_chave": "tabela_normativa_service", "estado": "nao_integrado_ao_snapshot",
             "causa": "X", "autoridade_fiscal": False, "resultado_bruto_nao_validado": None},
        ],
    }


def _g13_sucesso():
    return {
        "estado": "SIMULACAO_CONDICIONAL_VINCULADA_NAO_AUTORIZADA",
        "itens_total": 2, "itens_simulados": 2,
        "chave_nfe": "1" * 44, "documento_id": 10, "competencia_declarada": "2026-01",
        "confronto_condicional_g12": {"estado": "G12_SIMULACAO_CONDICIONAL_SEM_AUTORIDADE"},
    }


def _g13_sem_simulacao():
    return {
        "estado": "SEM_SIMULACAO_VINCULADA",
        "itens_total": 2, "itens_simulados": 0,
        "chave_nfe": "1" * 44, "documento_id": 10, "competencia_declarada": "2026-01",
        "confronto_condicional_g12": {"estado": "G12_SEM_SIMULACAO"},
    }


class TestProjetarDiagnosticoIntegralIcmsSt(unittest.TestCase):

    @patch("app.services.enterprise_b04_icms_st_integral_bridge.projetar_confronto_st_sujeito_g13")
    @patch("app.services.enterprise_b04_icms_st_integral_bridge.projetar_diagnostico_integral_i2")
    def test_sucesso_atualiza_so_as_tres_capacidades_relevantes(self, mock_i2, mock_g13):
        mock_i2.return_value = _cobertura_base()
        mock_g13.return_value = _g13_sucesso()

        r = projetar_diagnostico_integral_icms_st(
            db=DB_SENTINELA, authenticated_user_id=1, empresa_id=1,
            relatorio_id=1, xml_bytes=b"x",
        )
        itens = {e["id"]: e for e in r["cobertura"]}

        for nome in ("icms_st", "mva", "consistencia_fiscal"):
            self.assertEqual(itens[nome]["estado"], "informativo_sem_prova")
            self.assertFalse(itens[nome]["autoridade_fiscal"])
            self.assertIsNotNone(itens[nome]["resultado_bruto_nao_validado"])

        # pmpf NAO e tocado -- G12/G13 so cobrem iva_st, nao PMPF
        self.assertEqual(itens["pmpf"]["estado"], "nao_integrado_ao_snapshot")

        self.assertEqual(r["schema_version"], SCHEMA_VERSION)
        self.assertEqual(r["icms_st_g13"]["itens_simulados"], 2)

    @patch("app.services.enterprise_b04_icms_st_integral_bridge.projetar_confronto_st_sujeito_g13")
    @patch("app.services.enterprise_b04_icms_st_integral_bridge.projetar_diagnostico_integral_i2")
    def test_falha_g13_marca_falha_motor_sem_crash(self, mock_i2, mock_g13):
        mock_i2.return_value = _cobertura_base()
        mock_g13.side_effect = EnterpriseG13GateError("G13_I2_DOCUMENTO_OU_POSSE_NAO_COMPROVADOS")

        r = projetar_diagnostico_integral_icms_st(
            db=DB_SENTINELA, authenticated_user_id=1, empresa_id=1,
            relatorio_id=1, xml_bytes=b"x",
        )
        itens = {e["id"]: e for e in r["cobertura"]}

        for nome in ("icms_st", "mva", "consistencia_fiscal"):
            self.assertEqual(itens[nome]["estado"], "falha_motor")
            self.assertIn("G13_I2_DOCUMENTO_OU_POSSE_NAO_COMPROVADOS", itens[nome]["causa"])

        self.assertEqual(r["icms_st_g13"]["estado"], "falha_motor")
        self.assertIsNone(r["icms_st_g13"]["itens_total"])

    @patch("app.services.enterprise_b04_icms_st_integral_bridge.projetar_confronto_st_sujeito_g13")
    @patch("app.services.enterprise_b04_icms_st_integral_bridge.projetar_diagnostico_integral_i2")
    def test_sem_simulacao_nenhuma_vira_nao_apurado_nao_informativo(self, mock_i2, mock_g13):
        """itens_simulados == 0: G12/G13 rodaram mas nao ha item com ST
        aplicavel -- nao e 'informativo_sem_prova' (nao ha simulacao a
        reportar), e sim 'nao_apurado' (ja no enum ESTADOS)."""
        mock_i2.return_value = _cobertura_base()
        mock_g13.return_value = _g13_sem_simulacao()

        r = projetar_diagnostico_integral_icms_st(
            db=DB_SENTINELA, authenticated_user_id=1, empresa_id=1,
            relatorio_id=1, xml_bytes=b"x",
        )
        itens = {e["id"]: e for e in r["cobertura"]}

        for nome in ("icms_st", "mva", "consistencia_fiscal"):
            self.assertEqual(itens[nome]["estado"], "nao_apurado")
            self.assertFalse(itens[nome]["autoridade_fiscal"])

        self.assertEqual(r["icms_st_g13"]["itens_simulados"], 0)

    @patch("app.services.enterprise_b04_icms_st_integral_bridge.projetar_confronto_st_sujeito_g13")
    @patch("app.services.enterprise_b04_icms_st_integral_bridge.projetar_diagnostico_integral_i2")
    def test_g13_precomputado_e_usado_sem_recalcular(self, mock_i2, mock_g13):
        """Quando g13_precomputado e passado com identidade correta, a
        ponte NAO deve chamar projetar_confronto_st_sujeito_g13 de novo."""
        import hashlib
        xml_bytes = b"conteudo_xml_teste"
        sha = hashlib.sha256(xml_bytes).hexdigest()
        mock_i2.return_value = _cobertura_base()
        g13_pronto = dict(_g13_sucesso())
        g13_pronto["empresa_id"] = 7
        g13_pronto["relatorio_id"] = 99
        g13_pronto["xml_sha256"] = sha

        r = projetar_diagnostico_integral_icms_st(
            db=DB_SENTINELA, authenticated_user_id=1, empresa_id=7,
            relatorio_id=99, xml_bytes=xml_bytes,
            g13_precomputado=g13_pronto,
        )
        mock_g13.assert_not_called()
        itens = {e["id"]: e for e in r["cobertura"]}
        self.assertEqual(itens["icms_st"]["estado"], "informativo_sem_prova")

    @patch("app.services.enterprise_b04_icms_st_integral_bridge.projetar_confronto_st_sujeito_g13")
    @patch("app.services.enterprise_b04_icms_st_integral_bridge.projetar_diagnostico_integral_i2")
    def test_g13_precomputado_identidade_divergente_falha_fechado(self, mock_i2, mock_g13):
        """g13_precomputado com empresa_id/relatorio_id/xml_sha256 errados
        deve ser rejeitado (EnterpriseG13GateError), nunca usado as cegas."""
        mock_i2.return_value = _cobertura_base()
        g13_adulterado = dict(_g13_sucesso())
        g13_adulterado["empresa_id"] = 999
        g13_adulterado["relatorio_id"] = 1
        g13_adulterado["xml_sha256"] = "0" * 64

        r = projetar_diagnostico_integral_icms_st(
            db=DB_SENTINELA, authenticated_user_id=1, empresa_id=1,
            relatorio_id=1, xml_bytes=b"x",
            g13_precomputado=g13_adulterado,
        )
        mock_g13.assert_not_called()
        itens = {e["id"]: e for e in r["cobertura"]}
        for nome in ("icms_st", "mva", "consistencia_fiscal"):
            self.assertEqual(itens[nome]["estado"], "falha_motor")

    @patch("app.services.enterprise_b04_icms_st_integral_bridge.projetar_confronto_st_sujeito_g13")
    @patch("app.services.enterprise_b04_icms_st_integral_bridge.projetar_diagnostico_integral_i2")
    def test_nunca_promove_autoridade_fiscal_mesmo_em_sucesso(self, mock_i2, mock_g13):
        mock_i2.return_value = _cobertura_base()
        mock_g13.return_value = _g13_sucesso()

        r = projetar_diagnostico_integral_icms_st(
            db=DB_SENTINELA, authenticated_user_id=1, empresa_id=1,
            relatorio_id=1, xml_bytes=b"x",
        )
        for e in r["cobertura"]:
            self.assertFalse(e["autoridade_fiscal"])


if __name__ == "__main__":
    unittest.main()
