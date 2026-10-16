"""SOLVERIS P1-02B — RED scoped documental coverage / no-ST.

Somente teste: nao altera o motor, flags legadas, P1-02A nem pagamentos.
Dados NF-e artificiais e SEM autorizacao fiscal oficial.
"""
from __future__ import annotations

import importlib

import pytest

from app.motor_fiscal import analisar_xml
from app.xml_service import ler_xml_unico
from app.services.context_flags_service import inferir_flags_xml
from app.services.resultado_empresarial_service import compor_resultado_empresarial
from app.services.enterprise_paid_diagnostic_eligibility import (
    avaliar_elegibilidade_diagnostico_empresarial,
)

EMPRESA = 21
CHAVE_SINTETICA = "1" * 44


def _xml(*, com_grupo_icms: bool = True, chave: str = CHAVE_SINTETICA) -> bytes:
    # ICMS00 presente e legivel, mas SEM destaque de ST; nao confundir
    # ausencia de ST com parser que nao conseguiu ler o bloco tributario.
    icms = (
        "<imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST>"
        "<vBC>1499.00</vBC><vICMS>269.82</vICMS>"
        "</ICMS00></ICMS></imposto>"
    ) if com_grupo_icms else ""
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<nfeProc xmlns='http://www.portalfiscal.inf.br/nfe'>"
        "<NFe><infNFe Id='NFe" + chave + "' versao='4.00'>"
        "<ide><nNF>1</nNF><tpNF>1</tpNF>"
        "<dhEmi>2026-10-15T12:00:00-03:00</dhEmi></ide>"
        "<emit><CNPJ>11111111000111</CNPJ>"
        "<enderEmit><UF>PA</UF></enderEmit></emit>"
        "<dest><CNPJ>22222222000122</CNPJ>"
        "<enderDest><UF>PA</UF></enderDest></dest>"
        "<det nItem='1'><prod><NCM>22030000</NCM><CFOP>5102</CFOP>"
        "<qCom>1.0000</qCom><vProd>1499.00</vProd></prod>" + icms + "</det>"
        "<total><ICMSTot><vNF>1499.00</vNF></ICMSTot></total>"
        "</infNFe></NFe></nfeProc>"
    ).encode("utf-8")


def _resultado(xml: bytes, *, empresa_id: int = EMPRESA) -> dict:
    dados = analisar_xml(xml)
    assert "erro" not in dados, f"P102B_PARSER_UNEXPECTED: {dados!r}"
    documental = {
        "dados_fiscais": dados,
        "insights": [],
        "previsao_recuperacao": {"potencial_recuperacao_nota": None},
        "context_flags": inferir_flags_xml(dados, {}),
    }
    empresarial = {
        "empresa_id": empresa_id,
        "oportunidades": [],
        "creditos_detectados": [],
        "context_flags": {"dados_incompletos": True},
    }
    return compor_resultado_empresarial(empresa_id, documental, empresarial)


def test_p102b_causal_no_st_real_parser_bloqueado_na_p102a():
    xml = _xml()
    lido = ler_xml_unico(xml_bytes=xml)
    assert len(lido["itens"]) == 1
    assert lido["itens"][0]["base_icms"] == "1499.00"
    assert lido["itens"][0]["valor_st"] is None
    assert lido["itens"][0]["st_observado_xml"] is False
    resultado = _resultado(xml)
    assert resultado["dados_fiscais"]["icms_st"] is None
    assert resultado["context_flags"]["documental"]["dados_incompletos"] is True
    assert resultado["context_flags"]["empresarial"]["dados_incompletos"] is True
    # Protege o contrato anterior: NAO desbloquear a P1-02A por atalhos.
    assert avaliar_elegibilidade_diagnostico_empresarial(
        resultado, empresa_id=EMPRESA
    ) == {"eligible": False}


def test_p102b_parser_sem_bloco_icms_nao_prova_ausencia_legitima_st():
    lido = ler_xml_unico(xml_bytes=_xml(com_grupo_icms=False))
    assert lido["itens"][0]["base_icms"] is None
    assert lido["itens"][0]["valor_st"] is None
    resultado = _resultado(_xml(com_grupo_icms=False))
    assert avaliar_elegibilidade_diagnostico_empresarial(
        resultado, empresa_id=EMPRESA
    ) == {"eligible": False}


def test_p102b_documento_nao_prova_credito_e_fingerprints_nao_sao_pagamentos():
    resultado = _resultado(_xml())
    assert resultado["previsao_recuperacao"]["potencial_recuperacao_nota"] is None
    assert resultado["creditos_detectados"] == []
    assert resultado["insights"]["empresarial"] is None


def test_p102b_red_exige_cobertura_enterprise_escopada_com_evidencia_xml():
    # O escopo novo NAO muda inferir_flags_xml global nem a regra ST antiga.
    # O chamador futuro valida empresa, provenance e fingerprint antes da venda.
    # Este contrato e' informativo e SEM qualquer autorizacao de pagamento.
    try:
        module = importlib.import_module("app.services.enterprise_diagnostic_coverage")
    except ModuleNotFoundError as exc:
        if exc.name == "app.services.enterprise_diagnostic_coverage":
            pytest.fail("P102B_SCOPED_COVERAGE_MISSING", pytrace=False)
        raise
    avaliar = getattr(module, "avaliar_cobertura_nfe_documental", None)
    assert callable(avaliar), "P102B_SCOPED_COVERAGE_MISSING"

    def cobertura(xml: bytes, resultado: dict, empresa_id: int = EMPRESA):
        saida = avaliar(xml, resultado, empresa_id=empresa_id)
        assert type(saida) is dict, "P102B_COVERAGE_SCHEMA_INVALID"
        assert set(saida) == {
            "documental_suficiente", "empresarial_completo", "st_nao_destacado_observado"
        }, "P102B_COVERAGE_SCHEMA_INVALID"
        assert all(type(v) is bool for v in saida.values()), "P102B_COVERAGE_BOOL_REQUIRED"
        return saida

    sem_st = _xml()
    resultado = _resultado(sem_st)
    assert cobertura(sem_st, resultado) == {
        "documental_suficiente": True,
        "empresarial_completo": False,
        "st_nao_destacado_observado": True,
    }, "P102B_VALID_DOCUMENT_NO_ST_MUST_HAVE_SCOPED_COVERAGE"

    # Ausencia de qualquer grupo ICMS nao autoriza afirmar ST nao destacado.
    xml_sem_icms = _xml(com_grupo_icms=False)
    assert cobertura(xml_sem_icms, _resultado(xml_sem_icms)) == {
        "documental_suficiente": False,
        "empresarial_completo": False,
        "st_nao_destacado_observado": False,
    }, "P102B_NO_TAX_EVIDENCE_MUST_FAIL_CLOSED"

    # Um resultado de outra empresa nao pode adquirir cobertura.
    assert cobertura(sem_st, resultado, empresa_id=22) == {
        "documental_suficiente": False,
        "empresarial_completo": False,
        "st_nao_destacado_observado": False,
    }, "P102B_CROSS_TENANT_MUST_FAIL_CLOSED"

    # Dados malformados, mesmo que o XML seja sintaticamente valido, falham.
    assert cobertura(b"<xml-malformado", resultado) == {
        "documental_suficiente": False,
        "empresarial_completo": False,
        "st_nao_destacado_observado": False,
    }, "P102B_XML_MALFORMED_MUST_FAIL_CLOSED"
