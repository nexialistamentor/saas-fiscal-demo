"""Fase 1 — parsers: testes de contrato e fallback."""
from datetime import date
from unittest.mock import patch

from app.services.parsers.base_parser import ResultadoParser
from app.services.parsers.dou_parser import DOUParser, _extrair_uf_do_titulo
from app.services.parsers.sefaz_sp_parser import SefazSPParser, _extrair_regras_html
from app.services.parsers.sefaz_mg_parser import SefazMGParser
from app.services.pipeline_normativo import _validar_regra, RegraNormativa


# ── Validação do pipeline ─────────────────────────────────────────────


def test_validar_regra_sem_fonte_legal():
    r = RegraNormativa("SP", "22021000", 66.0, 0.18, date(2026, 1, 1), None,
                       "", "", "candidata_oficial", "test")
    erros = _validar_regra(r)
    assert any("fonte_legal" in e for e in erros)


def test_validar_regra_sem_url():
    r = RegraNormativa("SP", "22021000", 66.0, 0.18, date(2026, 1, 1), None,
                       "Portaria SRE 89/2025", "", "candidata_oficial", "test")
    erros = _validar_regra(r)
    assert any("url_fonte" in e for e in erros)


def test_validar_regra_valida():
    r = RegraNormativa("SP", "22021000", 66.0, 0.18, date(2026, 1, 1), None,
                       "Portaria SRE 89/2025",
                       "https://legislacao.fazenda.sp.gov.br/...",
                       "candidata_oficial", "test")
    assert _validar_regra(r) == []


# ── DOU Parser ────────────────────────────────────────────────────────


def test_extrair_uf_do_titulo_detecta_sp():
    assert _extrair_uf_do_titulo("Portaria SRE/SP sobre substituição tributária") == "SP"


def test_extrair_uf_do_titulo_nao_detecta_generico():
    assert _extrair_uf_do_titulo("Convênio ICMS 142/2018") is None


def test_dou_parser_falha_graciosamente():
    with patch("httpx.get", side_effect=Exception("timeout")):
        parser = DOUParser()
        resultado = parser.extrair_seguro()
    assert isinstance(resultado, ResultadoParser)
    assert len(resultado.erros) > 0
    assert resultado.regras == []


# ── SEFAZ-SP Parser ───────────────────────────────────────────────────


def test_sefaz_sp_extrai_regra_de_html_simulado():
    html_simulado = """
    <table>
    <tr><td>2202.10.00</td><td>Refrigerantes</td><td>66%</td></tr>
    </table>
    """
    regras = _extrair_regras_html(html_simulado)
    assert len(regras) >= 1
    assert regras[0].estado == "SP"
    assert regras[0].mva == 66.0
    assert regras[0].nivel_confianca == "candidata_oficial"


def test_sefaz_sp_parser_falha_graciosamente():
    with patch("httpx.get", side_effect=Exception("connection refused")):
        parser = SefazSPParser()
        resultado = parser.extrair_seguro()
    assert isinstance(resultado, ResultadoParser)
    assert len(resultado.erros) > 0


# ── Orquestrador ──────────────────────────────────────────────────────


def test_orquestrador_dry_run_nao_grava():
    from app.services.parsers.orquestrador_parsers import executar_parsers
    mock_resultado = ResultadoParser(
        regras=[], erros=[], fonte="TEST",
        url_consultada="http://test", data_consulta="2026-01-01"
    )
    with patch("app.services.parsers.dou_parser.DOUParser.extrair_seguro",
               return_value=mock_resultado), \
         patch("app.services.parsers.sefaz_sp_parser.SefazSPParser.extrair_seguro",
               return_value=mock_resultado), \
         patch("app.services.parsers.sefaz_mg_parser.SefazMGParser.extrair_seguro",
               return_value=mock_resultado):
        resultado = executar_parsers(dry_run=True)
    assert resultado["dry_run"] is True
