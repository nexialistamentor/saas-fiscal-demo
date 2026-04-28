"""
Parser SEFAZ-SP — extrai IVA-ST por NCM/CEST das Portarias SRE vigentes.

Fonte: legislacao.fazenda.sp.gov.br

Calibração 2026-04-28:
- URL real da Portaria SRE 89/2025 confirmada com casing oficial:
  https://legislacao.fazenda.sp.gov.br/Paginas/Portaria-SRE-89-de-2025.aspx
- Portaria SRE 09/26 (17-03-2026) revoga o Inciso I do Art. 1º e o Anexo I
  (refrigerantes, NCM 2202.*) da SRE 89/2025, com vigor a partir de 2026-07-01.
  → regras de refrigerantes da SRE 89/2025 ganham vigencia_fim=2026-06-30.
  → adiciona-se baseline subsidiário sob a SRE 09/26 a partir de 2026-07-01.
- MVA subsidiário (sem PMPF de marca específica): 66% para refrigerantes NCM 2202
  nas saídas de fabricante, engarrafador, importador, distribuidor ou atacadista.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from app.services.parsers.base_parser import (
    BaseParser,
    DiagnosticoHTTP,
    ResultadoParser,
    fetch_com_diagnostico,
)
from app.services.pipeline_normativo import RegraNormativa

logger = logging.getLogger(__name__)

# URL canónica (casing oficial confirmado: "Portaria-SRE-89-de-2025").
# Fallbacks ficam para o caso raro de o portal mudar o slug.
_URL_SRE_89_2025 = (
    "https://legislacao.fazenda.sp.gov.br/Paginas/Portaria-SRE-89-de-2025.aspx"
)
_URLS_SRE_89_2025: tuple[str, ...] = (
    _URL_SRE_89_2025,
    "https://legislacao.fazenda.sp.gov.br/Paginas/portaria-sre-89-de-2025.aspx",
)
_URL_INDICE_BUSCA = (
    "https://legislacao.fazenda.sp.gov.br/Paginas/Resultado.aspx"
)
_URL_INDICE_PORTARIAS = "https://legislacao.fazenda.sp.gov.br/Paginas/AllTextos.aspx"

# URL confirmada em 2026-04-28: portal SEFAZ-SP indexou a SRE 09/2026.
# Revogação do Inciso I Art. 1º + Anexo I (refrigerantes) da SRE 89/2025
# com vigor a partir de 2026-07-01 (Art. 3º da SRE 09/2026).
_URL_SRE_09_26_BASELINE = (
    "https://legislacao.fazenda.sp.gov.br/Paginas/Portaria-SRE-9-de-2026.aspx"
)

_FONTE_SRE_89 = "Portaria SRE 89/2025 — SEFAZ-SP"
_FONTE_SRE_09_26 = (
    "Portaria SRE 09/2026 — SEFAZ-SP (revoga Anexo I refrigerantes da SRE 89/2025)"
)
_IMPORTADO_POR = "sefaz_sp_parser.py v1.2"

_VIGENCIA_INICIO_SRE_89 = date(2026, 1, 1)
# SRE 09/26 (17-03-2026) revoga o Inciso I do Art. 1º e o Anexo I (refrigerantes)
# da SRE 89/2025, com vigor a partir de 2026-07-01.
_VIGENCIA_FIM_REFRIGERANTES_SRE_89 = date(2026, 6, 30)
_VIGENCIA_INICIO_SRE_09_26 = date(2026, 7, 1)

_ALIQUOTA_INTERNA_SP = 0.18  # RICMS-SP modal
_MVA_SUBSIDIARIO_REFRIGERANTES = 66.0  # NCM 2202 — saídas de fab./eng./imp./dist./atac.
_NCM_REFRIGERANTES_BASELINE = "22021000"


class SefazSPParser(BaseParser):
    """
    Extrai IVA-ST para SP combinando dois eixos:
    1. Scraping da Portaria SRE 89/2025 (regra extraída por NCM, quando a página
       responde) — vigência 2026-01-01 → 2026-12-31, excepto refrigerantes
       (NCM 2202.*) cujo limite é 2026-06-30 (revogação pelo SRE-09/26).
    2. Baseline subsidiário hardcoded (knowledge cut-off oficial confirmado):
       NCM 2202 com MVA 66% nas saídas de fabricante/engarrafador/importador/
       distribuidor/atacadista, replicado nas duas portarias para garantir
       continuidade na transição 2026-06-30 → 2026-07-01.

    Todas as regras saem com nivel_confianca_fonte="candidata_oficial".
    """
    nome = "SEFAZ-SP"
    url_base = _URL_SRE_89_2025

    def extrair(self) -> ResultadoParser:
        regras: list[RegraNormativa] = []
        erros: list[str] = []
        diagnosticos: list[DiagnosticoHTTP] = []

        url_efetiva = _URL_SRE_89_2025
        html: str | None = None

        for url in _URLS_SRE_89_2025:
            resp, diag = fetch_com_diagnostico(url, timeout=20)
            diagnosticos.append(diag)
            if resp is not None and resp.status_code == 200:
                html = resp.text
                url_efetiva = str(resp.request.url)
                break
            erros.append(
                f"SEFAZ-SP: URL '{url}' retornou status={diag.status_code} "
                f"erro={diag.erro or '-'}"
            )

        if html is None:
            indice_html, indice_diag = _buscar_no_indice("SRE 89/2025")
            diagnosticos.extend(indice_diag)
            if indice_html is not None:
                html = indice_html
                url_efetiva = _URL_INDICE_BUSCA
            else:
                erros.append(
                    "SEFAZ-SP: nenhuma URL candidata respondeu 200 e busca "
                    "no índice também falhou"
                )

        if html is not None:
            regras_extraidas = _extrair_regras_html(html)
            regras.extend(regras_extraidas)
            if not regras_extraidas:
                erros.append(
                    "SEFAZ-SP: HTML obtido mas nenhuma regra extraída — "
                    "estrutura da página pode ter mudado (ver diagnostico.preview)"
                )

        # Baseline subsidiário sempre adicionado (knowledge cut-off oficial).
        # Garante existência de regra para refrigerantes mesmo se o scraping
        # falhar, e materializa a transição SRE 89/2025 → SRE 09/2026.
        regras.extend(_baseline_subsidiarias_sp())

        return ResultadoParser(
            regras=regras,
            erros=erros,
            fonte=_FONTE_SRE_89,
            url_consultada=url_efetiva,
            data_consulta=date.today().isoformat(),
            diagnostico=diagnosticos,
        )


def _buscar_no_indice(
    consulta: str,
) -> tuple[str | None, list[DiagnosticoHTTP]]:
    """
    Plano B: faz busca no índice geral de legislação SP.
    Devolve o HTML da página de resultados, se respondeu 200.
    """
    diagnosticos: list[DiagnosticoHTTP] = []
    resp, diag = fetch_com_diagnostico(
        _URL_INDICE_BUSCA, params={"PalavraChave": consulta}, timeout=20
    )
    diagnosticos.append(diag)
    if resp is not None and resp.status_code == 200:
        return resp.text, diagnosticos

    resp2, diag2 = fetch_com_diagnostico(_URL_INDICE_PORTARIAS, timeout=20)
    diagnosticos.append(diag2)
    if resp2 is not None and resp2.status_code == 200:
        return resp2.text, diagnosticos

    return None, diagnosticos


def _extrair_regras_html(html: str) -> list[RegraNormativa]:
    """
    Tenta extrair tabela de IVA-ST do HTML da SRE 89/2025.

    Estratégia em duas camadas:
    1. BS4: percorre <table>/<tr> procurando linhas com NCM e percentual.
    2. Regex de fallback: NCM (8 dígitos com pontuação) seguido de percentual.
    """
    regras: list[RegraNormativa] = []
    vistos: set[tuple[str, float]] = set()

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    padrao_ncm_celula = re.compile(r"^\s*(\d{4}\.\d{2}\.\d{2})\s*$")
    padrao_pct = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*%")

    for tr in soup.find_all("tr"):
        celulas = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if not celulas:
            continue
        ncm_raw: str | None = None
        for cel in celulas:
            m = padrao_ncm_celula.match(cel)
            if m:
                ncm_raw = m.group(1)
                break
        if not ncm_raw:
            continue
        for cel in celulas:
            m = padrao_pct.search(cel)
            if not m:
                continue
            valor = _parse_pct(m.group(1))
            if valor is None or valor <= 0 or valor > 500:
                continue
            chave = (ncm_raw.replace(".", ""), valor)
            if chave in vistos:
                continue
            vistos.add(chave)
            regras.append(_construir_regra_sre_89(ncm_raw.replace(".", ""), valor))
            break

    if regras:
        return regras

    padrao_inline = re.compile(
        r"(\d{4}\.\d{2}\.\d{2})\D{1,200}?(\d{1,3}(?:[.,]\d{1,2})?)\s*%"
    )
    for match in padrao_inline.finditer(html):
        ncm_sem_ponto = match.group(1).replace(".", "")
        valor = _parse_pct(match.group(2))
        if valor is None or valor <= 0 or valor > 500:
            continue
        chave = (ncm_sem_ponto, valor)
        if chave in vistos:
            continue
        vistos.add(chave)
        regras.append(_construir_regra_sre_89(ncm_sem_ponto, valor))

    return regras


def _parse_pct(token: str) -> float | None:
    try:
        return float(token.replace(",", "."))
    except ValueError:
        return None


def _eh_refrigerante(ncm_sem_ponto: str) -> bool:
    """NCM 2202.* = bebidas, com refrigerantes em 2202.10/2202.99."""
    return ncm_sem_ponto.startswith("2202")


def _construir_regra_sre_89(ncm_sem_ponto: str, iva_st: float) -> RegraNormativa:
    """
    Constrói regra extraída da SRE 89/2025.

    Para refrigerantes (NCM 2202.*) define vigencia_fim=2026-06-30 — limite
    explícito imposto pela SRE 09/2026 (revogação parcial). Para outras NCMs
    o vigencia_fim fica em aberto até nova revogação.
    """
    vigencia_fim = (
        _VIGENCIA_FIM_REFRIGERANTES_SRE_89
        if _eh_refrigerante(ncm_sem_ponto)
        else None
    )
    return RegraNormativa(
        estado="SP",
        ncm=ncm_sem_ponto,
        mva=iva_st,
        aliquota_interna=_ALIQUOTA_INTERNA_SP,
        vigencia_inicio=_VIGENCIA_INICIO_SRE_89,
        vigencia_fim=vigencia_fim,
        fonte_legal=_FONTE_SRE_89,
        url_fonte=_URL_SRE_89_2025,
        nivel_confianca="candidata_oficial",
        importado_por=_IMPORTADO_POR,
    )


def _baseline_subsidiarias_sp() -> list[RegraNormativa]:
    """
    Baseline subsidiário hardcoded — knowledge cut-off oficial confirmado.

    NCM 2202 (refrigerantes) com MVA 66% nas saídas de fabricante,
    engarrafador, importador, distribuidor ou atacadista, replicado em duas
    janelas de vigência:

    - SRE 89/2025: 2026-01-01 → 2026-06-30 (limite imposto pelo SRE 09/2026)
    - SRE 09/2026: 2026-07-01 → ∞ (sucessora vigente a partir desta data)

    Esta baseline garante continuidade da regra mesmo se o scraping da
    portaria falhar, e materializa explicitamente a transição normativa.
    """
    return [
        RegraNormativa(
            estado="SP",
            ncm=_NCM_REFRIGERANTES_BASELINE,
            mva=_MVA_SUBSIDIARIO_REFRIGERANTES,
            aliquota_interna=_ALIQUOTA_INTERNA_SP,
            vigencia_inicio=_VIGENCIA_INICIO_SRE_89,
            vigencia_fim=_VIGENCIA_FIM_REFRIGERANTES_SRE_89,
            fonte_legal=(
                f"{_FONTE_SRE_89} | MVA subsidiário 66% (NCM 2202 sem PMPF de marca)"
            ),
            url_fonte=_URL_SRE_89_2025,
            nivel_confianca="candidata_oficial",
            importado_por=_IMPORTADO_POR,
        ),
        RegraNormativa(
            estado="SP",
            ncm=_NCM_REFRIGERANTES_BASELINE,
            mva=_MVA_SUBSIDIARIO_REFRIGERANTES,
            aliquota_interna=_ALIQUOTA_INTERNA_SP,
            vigencia_inicio=_VIGENCIA_INICIO_SRE_09_26,
            vigencia_fim=None,
            fonte_legal=(
                f"{_FONTE_SRE_09_26} | MVA subsidiário 66% (NCM 2202 sem PMPF de marca)"
            ),
            url_fonte=_URL_SRE_09_26_BASELINE,
            nivel_confianca="candidata_oficial",
            importado_por=_IMPORTADO_POR,
        ),
    ]
