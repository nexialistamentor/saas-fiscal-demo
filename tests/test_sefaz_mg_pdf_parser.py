"""Parser PDF SAIF 062/2025 (MG PMPF) — Opção A NCM por anexo."""
from datetime import date
from unittest.mock import MagicMock, patch

from app.services.parsers.base_parser import ResultadoParser
from app.services.parsers.sefaz_mg_pdf_parser import (
    SefazMGPdfParser,
    _detectar_anexo_na_tabela,
    _extrair_regra_da_linha,
    _extrair_regras_de_tabela,
    _mapear_colunas_saif,
    _parece_pdf,
    _parse_valor,
    _parse_volume,
    extrair_regras_mg_pdf_de_bytes,
)


def test_parece_pdf_aceita_magic_bytes():
    assert _parece_pdf(b"%PDF-1.7\n...") is True


def test_parece_pdf_rejeita_html():
    assert _parece_pdf(b"<!DOCTYPE html><html>") is False


def test_parse_valor_formatos_br():
    assert _parse_valor("R$ 7,50") == 7.50
    assert _parse_valor("1,54") == 1.54


def test_parse_volume_extrai_ml():
    assert _parse_volume("2000 ml") == 2000
    assert _parse_volume("Lata 350ml") == 350


def test_detectar_anexo_na_tabela():
    tabela = [
        ["ANEXO I - REFRIGERANTES"],
        ["ITEM", "EMBALAGEM", "MARCA", "PMPF"],
    ]
    assert _detectar_anexo_na_tabela(tabela) == "I"


def test_mapear_colunas_saif_compacto():
    tabela = [
        ["ANEXO II"],
        ["ITEM", "EMBALAGEM", "MARCA", "CÓDIGO\nFABRICANTE", "PMPF"],
        ["1", "PET 400ml", "Bioleve", "133", "3,84"],
    ]
    m = _mapear_colunas_saif(tabela)
    assert m is not None
    cols, primeira, fmt = m
    assert fmt == "compacto"
    assert primeira == 2
    assert cols["pmpf"] == 4


def test_mapear_colunas_saif_largo_anexo_i():
    """Replica estrutura do PDF oficial — linha ITEM duplicada + mesclas."""
    tabela = [
        ["", "", "", "", "ANEXO I - REFRIGERANTES"],
        ["", "", None, "ITEM", "ITEM", None, "EMBALAGEM", None, None, "MARCA", None, None, "", "CÓDIGO DO", "", "PMPF", "PMPF", None],
        [None, None, None, None, None, None, None, None, None, None, None, None, None, "FABRICANTE"],
        ["", "", "", "", "1", "", "", "Copo até 360ml", "", "", "Guaramil (todos)", "", "", "57", "", "", "1,54", ""],
    ]
    m = _mapear_colunas_saif(tabela)
    assert m is not None
    cols, primeira, fmt = m
    assert fmt == "largo"
    assert primeira == 3
    assert cols["item"] == 4
    assert cols["pmpf"] == 16


def test_extrair_regras_de_tabela_anexo_i_ncm_fixo():
    tabela = [
        ["", "", "", "", "ANEXO I - REFRIGERANTES"],
        ["", "", None, "ITEM", "ITEM", None, "EMBALAGEM", None, None, "MARCA", None, None, "", "CÓDIGO DO", "", "PMPF", "PMPF", None],
        [None, None, None, None, None, None, None, None, None, None, None, None, None, "FABRICANTE"],
        ["", "", "", "", "1", "", "", "Copo até 360ml", "", "", "Guaramil (todos)", "", "", "57", "", "", "1,54", ""],
        ["", "", "", "", "53", "", "", "Lata 300 a 349ml", "", "", "Guaraná Kuat", "", "", "2", "", "", "3,72", ""],
    ]
    regras = _extrair_regras_de_tabela(tabela, anexo_romano="I", ncm_fixo="22021000")
    assert len(regras) == 2
    assert all(r.ncm == "22021000" for r in regras)
    ps = [r.pmpf_reais for r in regras]
    assert ps == [1.54, 3.72]
    assert regras[0].nivel_confianca == "candidata_oficial"
    assert regras[0].importado_por == "sefaz_mg_pdf_parser_v1"
    assert regras[0].vigencia_inicio == date(2026, 1, 1)


def test_extrair_regra_da_linha_descarta_sem_item():
    cols = {"item": 4, "embalagem": 7, "marca": 10, "pmpf": 16}
    linha = [""] * 17
    linha[4] = "TOTAL"
    linha[16] = "999,99"
    assert (
        _extrair_regra_da_linha(
            linha,
            cols,
            anexo_romano="I",
            ncm_fixo="22021000",
        )
        is None
    )


def test_extrair_regras_pdf_bytes_so_anexo_i():
    """Integração leve: PDF real baixado em mock HTTP."""
    import io

    try:
        import pdfplumber  # noqa: F401
    except ImportError:
        return

    try:
        import httpx

        url = (
            "https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/"
            "portarias/2025/port_saif062_2025_anexos.pdf"
        )
        raw = httpx.get(url, follow_redirects=True, timeout=120).content
    except Exception:
        return
    if not _parece_pdf(raw):
        return  # URL devolveu HTML, redirect ou bloqueio — tratar como falha externa

    regs, erros = extrair_regras_mg_pdf_de_bytes(raw, apenas_anexos=frozenset({"I"}))
    assert not erros
    assert len(regs) >= 100
    assert all(r.estado == "MG" and r.ncm == "22021000" for r in regs[:50])


def test_sefaz_mg_pdf_falha_graciosamente_quando_get_lanca():
    with patch("httpx.get", side_effect=Exception("dns down")):
        parser = SefazMGPdfParser()
        resultado = parser.extrair_seguro()
    assert isinstance(resultado, ResultadoParser)
    assert resultado.regras == []
    assert any("GET falhou" in e or "dns" in e for e in resultado.erros)
    assert resultado.diagnostico


def test_sefaz_mg_pdf_aborta_quando_resposta_nao_e_pdf():
    fake = MagicMock()
    fake.status_code = 200
    fake.content = b"<html>Not a PDF</html>"
    fake.text = "<html>Not a PDF</html>"
    fake.headers = {"content-type": "text/html"}
    fake.request.url = "https://www.fazenda.mg.gov.br/.../port_saif062_2025_anexos.pdf"
    with patch("httpx.get", return_value=fake):
        resultado = SefazMGPdfParser().extrair_seguro()
    assert resultado.regras == []
    assert any("%PDF-" in e for e in resultado.erros)


def test_sefaz_mg_pdf_aborta_quando_status_diferente_de_200():
    fake = MagicMock()
    fake.status_code = 404
    fake.content = b""
    fake.text = ""
    fake.headers = {"content-type": "text/html"}
    fake.request.url = "https://www.fazenda.mg.gov.br/.../port_saif062_2025_anexos.pdf"
    with patch("httpx.get", return_value=fake):
        resultado = SefazMGPdfParser().extrair_seguro()
    assert resultado.regras == []
    assert any("status=404" in e for e in resultado.erros)
