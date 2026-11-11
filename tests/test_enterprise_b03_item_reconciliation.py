"""B03: testes do orquestrador confrontar_documento_b03/confrontar_xml_b03.
Sem conexao DB real (resolver_aliquota_e_mva e mockado via unittest.mock,
seguindo o mesmo padrao de tests/test_enterprise_g113_c5_parameter_trace.py
-- db e so um objeto sentinela, nunca uma sessao real).

Inclui teste de regressao explicito para o bug de unidades (fracao vs
percentual) corrigido em 2026-11-11: sem a conversao *100, todo calculo
sai 100x menor -- ver app/services/enterprise_b03_item_reconciliation.py.
"""
from __future__ import annotations

from datetime import date
import unittest
from unittest.mock import patch

from app.services.enterprise_b03_item_reconciliation import (
    confrontar_documento_b03, confrontar_xml_b03, SCHEMA,
)

DB_SENTINELA = object()  # nunca usado de facto -- resolver_aliquota_e_mva e mockado


def _regra_autorizada(mva_fracao=0.45, aliquota_fracao=0.19):
    return {
        "aliquota": aliquota_fracao, "mva": mva_fracao, "fonte": "tabela",
        "uf": "PA", "ncm": "22021000", "confianca": "oficial",
        "calculo_autorizado": True, "calculo_parcial": False,
        "mva_autorizada": True, "aliquota_autorizada": True,
        "bloqueio_normativo": False, "motivo_bloqueio": None,
    }


def _regra_bloqueada(motivo="lacuna_normativa"):
    return {
        "aliquota": None, "mva": None, "fonte": None, "uf": "SP",
        "ncm": "99999999", "confianca": None,
        "calculo_autorizado": False, "calculo_parcial": False,
        "mva_autorizada": False, "aliquota_autorizada": False,
        "bloqueio_normativo": True, "motivo_bloqueio": motivo,
    }


class TestConfrontarDocumentoB03(unittest.TestCase):

    @patch("app.services.enterprise_b03_item_reconciliation.resolver_aliquota_e_mva")
    def test_sem_divergencia_quando_valores_batem(self, mock_resolver):
        mock_resolver.return_value = _regra_autorizada()
        # valor_produto=300, mva=45%, aliquota=19% -> base_st=435.00, icms_st=25.65
        # (regressao: sem a conversao fracao->percentual estes valores seriam
        # 100x menores -- ver nota no modulo)
        itens = [{
            "ncm": "22021000", "cfop": "5405", "st_observado_xml": True,
            "valor_st": 25.65, "base_st": 435.00, "valor_produto": 300.0,
        }]
        resultado = confrontar_documento_b03(
            db=DB_SENTINELA, chave_nfe="1" * 44, itens_xml=itens,
            uf_operacao="PA", data_operacao=date(2024, 1, 1), xml_bytes=b"x",
        )
        self.assertEqual(resultado["estado"], "SEM_DIVERGENCIA")
        self.assertFalse(resultado["autoridade_fiscal"])
        self.assertEqual(resultado["schema_version"], SCHEMA)

    @patch("app.services.enterprise_b03_item_reconciliation.resolver_aliquota_e_mva")
    def test_divergencia_quando_valor_xml_diverge_do_calculado(self, mock_resolver):
        mock_resolver.return_value = _regra_autorizada()
        itens = [{
            "ncm": "22021000", "cfop": "5405", "st_observado_xml": True,
            "valor_st": 999999.99, "base_st": 435.00, "valor_produto": 300.0,
        }]
        resultado = confrontar_documento_b03(
            db=DB_SENTINELA, chave_nfe="1" * 44, itens_xml=itens,
            uf_operacao="PA", data_operacao=date(2024, 1, 1), xml_bytes=b"x",
        )
        self.assertEqual(resultado["estado"], "DIVERGENCIA_ENCONTRADA")
        divergencias = resultado["resultado_bruto"]["divergencias"]
        self.assertEqual(len(divergencias), 1)
        self.assertEqual(divergencias[0]["valor_xml"], "999999.99")
        self.assertEqual(divergencias[0]["valor_motor"], "25.65")

    @patch("app.services.enterprise_b03_item_reconciliation.resolver_aliquota_e_mva")
    def test_nao_avaliado_quando_falta_autoridade_normativa(self, mock_resolver):
        mock_resolver.return_value = _regra_bloqueada("lacuna_normativa")
        itens = [{
            "ncm": "99999999", "cfop": "5405", "st_observado_xml": True,
            "valor_st": 10.0, "base_st": 10.0, "valor_produto": 300.0,
        }]
        resultado = confrontar_documento_b03(
            db=DB_SENTINELA, chave_nfe="1" * 44, itens_xml=itens,
            uf_operacao="SP", data_operacao=date(2024, 1, 1), xml_bytes=b"x",
        )
        self.assertEqual(resultado["estado"], "NAO_AVALIADO")
        self.assertFalse(resultado["autoridade_fiscal"])
        self.assertEqual(
            resultado["blocos_normativos"][0]["motivo_bloqueio"], "lacuna_normativa"
        )
        # nunca inventar valor calculado quando falta autoridade
        self.assertIsNone(resultado["resultado_bruto"].get("consistente"))

    def test_falha_fechada_quando_campos_essenciais_ausentes(self):
        """Regressao: confrontar_documento_b03 crashava com AttributeError
        (None.isoformat()) antes da correcao de fail-closed em 2026-11-11."""
        resultado = confrontar_documento_b03(
            db=DB_SENTINELA, chave_nfe="SYNTHETIC_NOT_A_REAL_ACCESS_KEY",
            itens_xml=[], uf_operacao=None, data_operacao=None, xml_bytes=b"x",
        )
        self.assertEqual(resultado["estado"], "NAO_AVALIADO")
        self.assertIn("uf_operacao", resultado["motivo"])
        self.assertIn("data_operacao", resultado["motivo"])

    @patch("app.services.enterprise_b03_item_reconciliation.resolver_aliquota_e_mva")
    def test_valor_produto_ausente_bloqueia_item_sem_crash(self, mock_resolver):
        mock_resolver.return_value = _regra_autorizada()
        itens = [{
            "ncm": "22021000", "cfop": "5405", "st_observado_xml": True,
            "valor_st": 25.65, "base_st": 435.00, "valor_produto": None,
        }]
        resultado = confrontar_documento_b03(
            db=DB_SENTINELA, chave_nfe="1" * 44, itens_xml=itens,
            uf_operacao="PA", data_operacao=date(2024, 1, 1), xml_bytes=b"x",
        )
        self.assertEqual(resultado["estado"], "NAO_AVALIADO")
        self.assertEqual(
            resultado["blocos_normativos"][0]["motivo_bloqueio"],
            "valor_produto_ausente_ou_invalido",
        )


class TestConfrontarXmlB03(unittest.TestCase):
    """Testa a camada de parsing (confrontar_xml_b03) com ler_xml_unico
    mockado -- isolado do parser XML real e da sua dependencia circular
    conhecida de import (app.xml_service -> app.models -> app.database)."""

    @patch("app.services.enterprise_b03_item_reconciliation.resolver_aliquota_e_mva")
    @patch("app.services.enterprise_b03_item_reconciliation.ler_xml_unico")
    def test_ponta_a_ponta_sem_divergencia(self, mock_ler_xml, mock_resolver):
        mock_resolver.return_value = _regra_autorizada()
        mock_ler_xml.return_value = {
            "chave_nfe": "1" * 44, "uf_emit": "PA", "uf_dest": "PA",
            "data_emissao": "2024-01-01T10:00:00-03:00",
            "itens": [{
                "ncm": "22021000", "cfop": "5405", "st_observado_xml": True,
                "valor_st": "25.65", "base_st": "435.00", "valor_produto": "300.00",
            }],
        }
        resultado = confrontar_xml_b03(db=DB_SENTINELA, xml_bytes=b"<xml/>")
        self.assertEqual(resultado["estado"], "SEM_DIVERGENCIA")

    @patch("app.services.enterprise_b03_item_reconciliation.ler_xml_unico")
    def test_erro_de_parse_xml_nao_propaga_excecao(self, mock_ler_xml):
        mock_ler_xml.side_effect = ValueError("XML malformado")
        resultado = confrontar_xml_b03(db=DB_SENTINELA, xml_bytes=b"lixo")
        self.assertEqual(resultado["estado"], "NAO_AVALIADO")
        self.assertIn("ERRO_PARSE_XML", resultado["motivo"])


if __name__ == "__main__":
    unittest.main()
