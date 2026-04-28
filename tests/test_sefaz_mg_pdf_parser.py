"""Fase 1.5 — parser PDF da SAIF 062/2025: testes de unidade puros."""
from datetime import date
from unittest.mock import MagicMock, patch

from app.services.parsers.base_parser import ResultadoParser
from app.services.parsers.sefaz_mg_pdf_parser import (
    SefazMGPdfParser,
    _extrair_regra_da_linha,
    _extrair_regras_de_tabela,
    _identificar_header,
    _parece_pdf,
    _parse_ncm,
    _parse_valor,
    _parse_volume,
)


# ── Heurísticas puras ─────────────────────────────────────────────────


def test_parece_pdf_aceita_magic_bytes():
    assert _parece_pdf(b"%PDF-1.7\n...") is True


def test_parece_pdf_rejeita_html():
    assert _parece_pdf(b"<!DOCTYPE html><html>") is False


def test_parse_ncm_aceita_com_e_sem_ponto():
    assert _parse_ncm("2202.10.00") == "22021000"
    assert _parse_ncm("22021000") == "22021000"
    assert _parse_ncm("NCM 2202.99.00 — refrigerante") == "22029900"


def test_parse_ncm_rejeita_invalido():
    assert _parse_ncm("") is None
    assert _parse_ncm("não-aplicável") is None


def test_parse_valor_aceita_formatos_brasileiros():
    assert _parse_valor("R$ 7,50") == 7.50
    assert _parse_valor("12,30") == 12.30
    assert _parse_valor("R$1.000,00") in (1.0, 1000.0)  # ambiguidade ok


def test_parse_valor_rejeita_invalido():
    assert _parse_valor("") is None
    assert _parse_valor("livre") is None


def test_parse_volume_extrai_ml():
    assert _parse_volume("2000 ml") == 2000
    assert _parse_volume("Lata 350ml") == 350
    assert _parse_volume("garrafa") is None


def test_identificar_header_reconhece_ncm_marca_volume_pmpf():
    cols = _identificar_header(["NCM", "Marca", "Embalagem (ml)", "PMPF (R$)"])
    assert cols is not None
    assert cols["ncm"] == 0
    assert cols["marca"] == 1
    assert cols["volume"] == 2
    assert cols["pmpf"] == 3


def test_identificar_header_aceita_sinonimos_descricao_e_preco():
    cols = _identificar_header(["NCM", "Descrição", "Volume", "Preço"])
    assert cols is not None
    assert "marca" in cols and cols["marca"] == 1


def test_identificar_header_rejeita_linha_sem_ncm():
    assert _identificar_header(["Marca", "Volume", "PMPF"]) is None
    assert _identificar_header([None, "produto"]) is None


# ── Extracção de linha → RegraNormativa ───────────────────────────────


def test_extrair_regra_da_linha_constroi_regra_completa():
    cols = {"ncm": 0, "marca": 1, "volume": 2, "pmpf": 3}
    linha = ["2202.10.00", "COCA-COLA 2L", "2000 ml", "R$ 7,50"]
    regra = _extrair_regra_da_linha(linha, cols)
    assert regra is not None
    assert regra.estado == "MG"
    assert regra.ncm == "22021000"
    assert regra.mva == 0.0
    assert regra.aliquota_interna == 0.18
    assert regra.vigencia_inicio == date(2026, 1, 1)
    assert regra.vigencia_fim == date(2026, 6, 30)
    assert regra.nivel_confianca == "candidata_oficial"
    assert "7.50" in regra.fonte_legal or "7,50" in regra.fonte_legal
    assert "COCA-COLA" in regra.fonte_legal
    assert "2000ml" in regra.fonte_legal
    assert regra.url_fonte and regra.url_fonte.endswith(".pdf")


def test_extrair_regra_da_linha_recupera_volume_da_marca_se_coluna_ausente():
    cols = {"ncm": 0, "marca": 1, "pmpf": 2}
    linha = ["2202.10.00", "GUARANÁ ANTARCTICA 350 ml", "R$ 3,90"]
    regra = _extrair_regra_da_linha(linha, cols)
    assert regra is not None
    assert "350ml" in regra.fonte_legal
    assert "GUARAN" in regra.fonte_legal.upper()


def test_extrair_regra_da_linha_descarta_linha_sem_ncm():
    cols = {"ncm": 0, "pmpf": 1}
    assert _extrair_regra_da_linha(["TOTAL", "R$ 100,00"], cols) is None


def test_extrair_regra_da_linha_descarta_pmpf_zero():
    cols = {"ncm": 0, "pmpf": 1}
    assert _extrair_regra_da_linha(["2202.10.00", "0,00"], cols) is None


# ── Extracção de tabela inteira ───────────────────────────────────────


def test_extrair_regras_de_tabela_dois_skus():
    """Header na linha 0; duas linhas de dados subsequentes."""
    tabela = [
        ["NCM", "Marca", "Embalagem", "PMPF"],
        ["2202.10.00", "COCA-COLA", "2000 ml", "R$ 7,50"],
        ["2202.99.00", "GUARANÁ ANTARCTICA", "350 ml", "R$ 3,90"],
    ]
    regras = _extrair_regras_de_tabela(tabela)
    assert len(regras) == 2
    ncms = sorted(r.ncm for r in regras)
    assert ncms == ["22021000", "22029900"]


def test_extrair_regras_de_tabela_ignora_titulo_antes_do_header():
    """Algumas portarias colocam título da tabela antes do header real."""
    tabela = [
        ["ANEXO ÚNICO — PMPF Refrigerantes", None, None, None],
        ["NCM", "Marca", "Embalagem", "PMPF"],
        ["2202.10.00", "PEPSI", "2000 ml", "R$ 6,80"],
    ]
    regras = _extrair_regras_de_tabela(tabela)
    assert len(regras) == 1
    assert regras[0].ncm == "22021000"


def test_extrair_regras_de_tabela_descarta_quando_header_nao_tem_pmpf():
    """Tabela sem coluna PMPF/preço/R$ não é tabela PMPF — descartar."""
    tabela = [
        ["NCM", "Marca", "Volume"],
        ["2202.10.00", "X", "2000 ml"],
    ]
    assert _extrair_regras_de_tabela(tabela) == []


def test_extrair_regras_de_tabela_deduplica_linhas_iguais():
    tabela = [
        ["NCM", "Marca", "Embalagem", "PMPF"],
        ["2202.10.00", "COCA-COLA", "2000 ml", "R$ 7,50"],
        ["2202.10.00", "COCA-COLA", "2000 ml", "R$ 7,50"],
    ]
    regras = _extrair_regras_de_tabela(tabela)
    assert len(regras) == 1


# ── Parser end-to-end (com httpx mockado) ─────────────────────────────


def test_sefaz_mg_pdf_falha_graciosamente_quando_get_lanca():
    """fetch_com_diagnostico devolve resp=None em excepção — sem crash."""
    with patch("httpx.get", side_effect=Exception("dns down")):
        parser = SefazMGPdfParser()
        resultado = parser.extrair_seguro()
    assert isinstance(resultado, ResultadoParser)
    assert resultado.regras == []
    assert any("GET falhou" in e or "dns" in e for e in resultado.erros)
    assert resultado.diagnostico, "diagnostico HTTP deve registar a tentativa"


def test_sefaz_mg_pdf_aborta_quando_resposta_nao_e_pdf():
    """
    Servidor pode devolver HTML de erro/redirect com 200 — magic bytes
    detectam isso e abortamos antes de passar lixo ao pdfplumber.
    """
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
