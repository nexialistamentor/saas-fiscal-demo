"""Fase 1 — parsers: testes de contrato e fallback."""
from datetime import date
from unittest.mock import MagicMock, patch

from app.services.parsers.base_parser import (
    DiagnosticoHTTP,
    ResultadoParser,
    fetch_com_diagnostico,
)
from app.services.parsers.dou_parser import (
    DOUParser,
    _eh_shell_spa_sem_resultados,
    _extrair_publicacoes_html,
    _extrair_uf_do_titulo,
)
from app.services.parsers.sefaz_mg_parser import SefazMGParser, _extrair_pmpf_html
from app.services.parsers.sefaz_sp_parser import SefazSPParser, _extrair_regras_html
from app.services.pipeline_normativo import RegraNormativa, _validar_regra


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


# ── Diagnóstico HTTP ──────────────────────────────────────────────────


def test_resultado_parser_diagnostico_default_vazio():
    """Compatibilidade: campo `diagnostico` é opcional."""
    r = ResultadoParser(
        regras=[], erros=[], fonte="X",
        url_consultada="http://x", data_consulta="2026-01-01",
    )
    assert r.diagnostico == []


def test_fetch_com_diagnostico_captura_status_e_preview():
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.content = b"<html>ok</html>"
    fake_resp.text = "<html>ok</html>"
    fake_resp.headers = {"content-type": "text/html; charset=utf-8"}
    fake_resp.request.url = "http://exemplo/x"
    with patch("httpx.get", return_value=fake_resp):
        resp, diag = fetch_com_diagnostico("http://exemplo/x")
    assert resp is fake_resp
    assert isinstance(diag, DiagnosticoHTTP)
    assert diag.status_code == 200
    assert diag.bytes_recebidos == len(b"<html>ok</html>")
    assert "text/html" in diag.content_type
    assert diag.preview.startswith("<html>")
    assert diag.erro is None


def test_fetch_com_diagnostico_captura_excepcao_sem_lancar():
    with patch("httpx.get", side_effect=Exception("DNS fail")):
        resp, diag = fetch_com_diagnostico("http://exemplo/x")
    assert resp is None
    assert diag.status_code is None
    assert diag.bytes_recebidos == 0
    assert diag.erro and "DNS fail" in diag.erro


# ── DOU HTML scraping ─────────────────────────────────────────────────


def test_extrair_publicacoes_html_lista_resultado_busca_item():
    html = """
    <html><body>
      <div class="resultado-busca-item">
        <h5>Convênio ICMS 142/2018 — alíquota MG substituição tributária</h5>
        <a href="/web/dou/-/convenio-142">link</a>
      </div>
      <div class="resultado-busca-item">
        <h5>Portaria SRE/SP IVA-ST refrigerantes</h5>
        <a href="https://www.in.gov.br/web/dou/-/portaria-sre">link</a>
      </div>
    </body></html>
    """
    pubs = _extrair_publicacoes_html(html)
    titulos = [p["titulo"] for p in pubs]
    assert any("MG" in t for t in titulos)
    assert any("SRE/SP" in t for t in titulos)
    for p in pubs:
        assert p["url"].startswith("http")


def test_dou_parser_diagnostico_preenchido_em_falha():
    with patch("httpx.get", side_effect=Exception("timeout")):
        parser = DOUParser()
        resultado = parser.extrair_seguro()
    assert resultado.diagnostico, "diagnostico deve listar tentativas mesmo em falha"
    assert all(d.erro for d in resultado.diagnostico)


def test_eh_shell_spa_sem_resultados_detecta_doctype_sem_resultados():
    """
    HTML com <!DOCTYPE> e sem nenhum container de resultados é shell SPA
    do in.gov.br — aborto do scraping antes de produzir falsos positivos.
    """
    shell_spa = (
        "<!DOCTYPE html>\n<html><head><title>DOU</title></head>"
        "<body><div id=\"app-root\"></div></body></html>"
    )
    assert _eh_shell_spa_sem_resultados(shell_spa) is True


def test_eh_shell_spa_sem_resultados_aceita_html_com_resultados():
    """HTML com `resultado-busca-item` é renderizado server-side — válido."""
    html_real = (
        "<!DOCTYPE html><html><body>"
        "<div class=\"resultado-busca-item\"><h5>Portaria X</h5></div>"
        "</body></html>"
    )
    assert _eh_shell_spa_sem_resultados(html_real) is False


def test_dou_parser_aborta_quando_resposta_e_shell_spa():
    """
    Se o buscador devolve shell SPA (caso real em produção 2026-04), o
    parser regista DiagnosticoHTTP, anota o erro descritivo e devolve
    regras=[] em vez de tentar parsing fallback que produz falsos positivos.
    """
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    shell = (
        b"<!DOCTYPE html><html><head></head>"
        b"<body><div id=\"app-root\"></div></body></html>"
    )
    fake_resp.content = shell
    fake_resp.text = shell.decode()
    fake_resp.headers = {"content-type": "text/html; charset=utf-8"}
    fake_resp.request.url = "https://www.in.gov.br/consulta/-/buscar/dou"
    with patch("httpx.get", return_value=fake_resp):
        parser = DOUParser()
        resultado = parser.extrair_seguro()
    assert resultado.regras == []
    assert any("shell SPA" in e for e in resultado.erros)
    assert resultado.diagnostico, "diagnostico HTTP deve registar a chamada"


# ── SEFAZ-SP multi-URL ────────────────────────────────────────────────


def test_sefaz_sp_extrai_regra_via_bs4_em_tabela():
    html = """
    <html><body>
      <table>
        <tr><th>NCM</th><th>Descrição</th><th>IVA-ST</th></tr>
        <tr><td>2202.10.00</td><td>Refrigerantes</td><td>66%</td></tr>
        <tr><td>2202.99.00</td><td>Outras bebidas</td><td>72,5%</td></tr>
      </table>
    </body></html>
    """
    regras = _extrair_regras_html(html)
    assert len(regras) == 2
    ncms = sorted(r.ncm for r in regras)
    assert ncms == ["22021000", "22029900"]
    mvas = {r.ncm: r.mva for r in regras}
    assert mvas["22021000"] == 66.0
    assert mvas["22029900"] == 72.5


def test_sefaz_sp_falha_grava_diagnostico_e_devolve_baseline():
    """
    Mesmo com TODAS as URLs HTTP a falhar, o parser devolve a baseline
    subsidiária (knowledge cut-off oficial): MVA 66% para NCM 2202 em
    duas janelas — SRE 89/2025 (até 2026-06-30) e SRE 09/2026 (em diante).
    """
    with patch("httpx.get", side_effect=Exception("connection refused")):
        parser = SefazSPParser()
        resultado = parser.extrair_seguro()
    assert len(resultado.diagnostico) >= 1
    assert all(d.status_code is None for d in resultado.diagnostico)
    # Baseline sempre presente: 2 regras para refrigerantes NCM 2202.
    refrigerantes = [r for r in resultado.regras if r.ncm == "22021000"]
    assert len(refrigerantes) == 2
    assert {r.mva for r in refrigerantes} == {66.0}
    assert {r.estado for r in refrigerantes} == {"SP"}
    janelas = sorted((r.vigencia_inicio, r.vigencia_fim) for r in refrigerantes)
    assert janelas == [
        (date(2026, 1, 1), date(2026, 6, 30)),  # SRE 89/2025 — refrigerantes revogados
        (date(2026, 7, 1), None),               # SRE 09/2026 — sucessora
    ]


def test_sefaz_sp_baseline_sucessora_referencia_sre_09_26():
    """A regra com vigência ≥ 2026-07-01 deve referenciar a SRE 09/2026."""
    with patch("httpx.get", side_effect=Exception("offline")):
        parser = SefazSPParser()
        resultado = parser.extrair_seguro()
    sucessora = [
        r for r in resultado.regras
        if r.vigencia_inicio == date(2026, 7, 1) and r.ncm == "22021000"
    ]
    assert len(sucessora) == 1
    assert "SRE 09/2026" in sucessora[0].fonte_legal
    assert sucessora[0].vigencia_fim is None


# ── SEFAZ-MG ──────────────────────────────────────────────────────────


def test_sefaz_mg_extrai_pmpf_via_bs4():
    html = """
    <html><body>
      <table>
        <tr><th>NCM</th><th>Marca</th><th>Embalagem</th><th>PMPF</th></tr>
        <tr><td>2202.10.00</td><td>COCA-COLA</td><td>2000 ml</td><td>R$ 7,50</td></tr>
      </table>
    </body></html>
    """
    regras = _extrair_pmpf_html(html)
    assert len(regras) == 1
    assert regras[0].estado == "MG"
    assert regras[0].ncm == "22021000"
    assert "7.50" in regras[0].fonte_legal or "7,50" in regras[0].fonte_legal
    assert regras[0].nivel_confianca == "candidata_oficial"


def test_sefaz_mg_falha_grava_diagnostico_com_preview_extendido():
    with patch("httpx.get", side_effect=Exception("dns")):
        parser = SefazMGParser()
        resultado = parser.extrair_seguro()
    assert resultado.diagnostico
    assert resultado.regras == []


def test_sefaz_mg_extrai_pmpf_aplica_vigencia_semestral():
    """
    SAIF 062/2025 vigora 2026-01-01 → 2026-06-30 (ciclo semestral).
    Toda regra extraída deve carregar essa janela explícita; a sucessora
    (SAIF 0xx/2026) será publicada para o segundo semestre.
    """
    html = """
    <html><body>
      <table>
        <tr><th>NCM</th><th>Marca</th><th>Embalagem</th><th>PMPF</th></tr>
        <tr><td>2202.10.00</td><td>COCA-COLA</td><td>2000 ml</td><td>R$ 7,50</td></tr>
      </table>
    </body></html>
    """
    regras = _extrair_pmpf_html(html)
    assert len(regras) == 1
    assert regras[0].vigencia_inicio == date(2026, 1, 1)
    assert regras[0].vigencia_fim == date(2026, 6, 30)


def test_sefaz_mg_html_sem_pmpf_aponta_para_pdf_anexos():
    """
    HTML 200 mas sem tabela PMPF — caso real da SAIF 062/2025, cuja tabela
    reside no PDF anexo. O parser deve registar um erro descritivo
    apontando para o PDF e identificando a Fase 1.5 (parser PDF dedicado),
    em vez de mensagens genéricas de "estrutura mudou".
    """
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    html_sem_pmpf = (
        b"<!DOCTYPE html><html><body>"
        b"<h1>Portaria SAIF 062/2025</h1>"
        b"<p>Veja anexos para a tabela de PMPF.</p>"
        b"</body></html>"
    )
    fake_resp.content = html_sem_pmpf
    fake_resp.text = html_sem_pmpf.decode()
    fake_resp.headers = {"content-type": "text/html; charset=utf-8"}
    fake_resp.request.url = (
        "https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/"
        "portarias/2025/port_saif062_2025.html"
    )
    with patch("httpx.get", return_value=fake_resp):
        parser = SefazMGParser()
        resultado = parser.extrair_seguro()
    assert resultado.regras == []
    erro_pdf = next(
        (e for e in resultado.erros if "anexos" in e.lower() and ".pdf" in e.lower()),
        None,
    )
    assert erro_pdf is not None, (
        f"erro descritivo apontando para PDF anexos não encontrado. erros={resultado.erros}"
    )
    assert "Fase 1.5" in erro_pdf
    assert "port_saif062_2025_anexos.pdf" in erro_pdf
