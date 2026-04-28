"""
Parser SEFAZ-MG — extrai PMPF de refrigerantes da Portaria SAIF vigente.
Fonte: fazenda.mg.gov.br

Calibração 2026-04-28:
- A SAIF 062/2025 publica o preâmbulo em HTML mas a tabela PMPF reside
  no PDF anexo (`port_saif062_2025_anexos.pdf`). Tentar regex sobre o
  HTML é inviável e produz só falsos negativos. Por isso, quando o HTML
  responde 200 mas nenhum PMPF é extraído, este parser regista um erro
  descritivo apontando para o PDF e remete a extracção para o parser
  PDF dedicado em `sefaz_mg_pdf_parser.py` (Fase 1.5).
- O HTML obtido é gravado em `debug_mg.html` na raiz do projecto para
  inspecção manual e auditoria. Está no .gitignore — nunca commitado.
- Vigência: a SAIF 062/2025 vigora 2026-01-01 → 2026-06-30 (ciclo
  semestral de PMPF). A sucessora (SAIF 0xx/2026) será publicada para
  o segundo semestre.
"""
from __future__ import annotations

import logging
import pathlib
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

# Ficheiro de inspecção manual — gravado em cwd cada vez que conseguimos
# obter HTML da SAIF 062/2025. Está no .gitignore — nunca commitado.
_DEBUG_HTML_PATH = pathlib.Path("debug_mg.html")

# URLs candidatas para a Portaria SAIF 062/2025 — a estrutura do portal MG
# muda entre subdomínios (`www.fazenda.mg.gov.br` e `legislacao.fazenda...`)
# e entre extensões (.html / .htm). Testamos várias antes de desistir.
_URLS_SAIF_062_2025: tuple[str, ...] = (
    "https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/portarias/2025/port_saif062_2025.html",
    "https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/portarias/2025/port_saif062_2025.htm",
    "https://legislacao.fazenda.mg.gov.br/Saif/Listagem/Portarias/2025/port_saif062_2025.html",
)
_URL_INDICE_MG = (
    "https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/portarias/"
)

# Anexo PDF da SAIF 062/2025 — onde reside efectivamente a tabela PMPF.
# O HTML serve apenas como índice/preâmbulo legal. Parser PDF dedicado
# fica em `sefaz_mg_pdf_parser.py` (Fase 1.5, pdfplumber).
_URL_PDF_ANEXOS = (
    "https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/"
    "portarias/2025/port_saif062_2025_anexos.pdf"
)

_FONTE_LEGAL = "Portaria SAIF 062/2025 — SEFAZ-MG"
_IMPORTADO_POR = "sefaz_mg_parser.py v1.3"
# Vigência semestral da SAIF 062/2025: 2026-01-01 → 2026-06-30.
_VIGENCIA_INICIO = date(2026, 1, 1)
_VIGENCIA_FIM = date(2026, 6, 30)
_ALIQUOTA_MG = 0.18  # RICMS-MG alíquota modal
_PREVIEW_MG_LEN = 1000  # MG precisa de mais contexto para inspeccionar tabela


class SefazMGParser(BaseParser):
    """
    Extrai PMPF para MG da Portaria SAIF 062/2025.

    Estratégia:
    1. Tenta as URLs candidatas da portaria directa (preview de 1000 chars
       no diagnóstico para inspeccionar estrutura HTML real).
    2. Se nenhuma responder com 200, faz GET ao índice geral de portarias.
    3. Para cada HTML obtido, tenta extrair PMPF via BS4 + regex de fallback.
    """
    nome = "SEFAZ-MG"
    url_base = _URLS_SAIF_062_2025[0]

    def extrair(self) -> ResultadoParser:
        regras: list[RegraNormativa] = []
        erros: list[str] = []
        diagnosticos: list[DiagnosticoHTTP] = []

        url_efetiva = _URLS_SAIF_062_2025[0]
        html: str | None = None

        for url in _URLS_SAIF_062_2025:
            resp, diag = fetch_com_diagnostico(
                url, timeout=20, preview_len=_PREVIEW_MG_LEN
            )
            diagnosticos.append(diag)
            if resp is not None and resp.status_code == 200:
                html = resp.text
                url_efetiva = str(resp.request.url)
                _persistir_html_para_inspecao(html, url_efetiva, erros)
                break
            erros.append(
                f"SEFAZ-MG: URL '{url}' retornou status={diag.status_code} "
                f"erro={diag.erro or '-'}"
            )

        if html is None:
            resp_idx, diag_idx = fetch_com_diagnostico(
                _URL_INDICE_MG, timeout=20, preview_len=_PREVIEW_MG_LEN
            )
            diagnosticos.append(diag_idx)
            if resp_idx is not None and resp_idx.status_code == 200:
                _persistir_html_para_inspecao(resp_idx.text, _URL_INDICE_MG, erros)
                erros.append(
                    "SEFAZ-MG: portaria directa indisponível — índice de "
                    "portarias acessível mas SAIF 062/2025 não localizada "
                    "automaticamente (ver debug_mg.html para inspecção)"
                )
            else:
                erros.append(
                    "SEFAZ-MG: nenhuma URL respondeu 200, índice também falhou"
                )

        if html is not None:
            regras = _extrair_pmpf_html(html)
            if not regras:
                erros.append(
                    "SEFAZ-MG: PMPF nos anexos PDF — "
                    f"{_URL_PDF_ANEXOS} "
                    "Parser PDF necessário (Fase 1.5)"
                )

        return ResultadoParser(
            regras=regras,
            erros=erros,
            fonte=_FONTE_LEGAL,
            url_consultada=url_efetiva,
            data_consulta=date.today().isoformat(),
            diagnostico=diagnosticos,
        )


def _persistir_html_para_inspecao(
    html: str, url_origem: str, erros: list[str]
) -> None:
    """
    Grava o HTML obtido em `debug_mg.html` (cwd) para inspecção manual.

    Como a estrutura real da SAIF 062/2025 é desconhecida — e ajustar regex
    sem ver o documento real é arriscar falsos positivos — usamos este
    snapshot para calibrar o parser entre execuções. Falhas de I/O são
    registadas em `erros` mas nunca interrompem a extracção.
    """
    try:
        cabecalho = (
            f"<!-- SEFAZ-MG snapshot — origem: {url_origem} "
            f"data: {date.today().isoformat()} bytes: {len(html)} -->\n"
        )
        _DEBUG_HTML_PATH.write_text(cabecalho + html, encoding="utf-8")
        logger.info(
            "SEFAZ-MG: HTML guardado em %s (%d bytes) — inspeccionar antes "
            "de calibrar regex",
            _DEBUG_HTML_PATH.resolve(),
            len(html),
        )
    except Exception as exc:
        erros.append(f"SEFAZ-MG: falha ao gravar {_DEBUG_HTML_PATH}: {exc}")


def _extrair_pmpf_html(html: str) -> list[RegraNormativa]:
    """
    Extrai PMPF de tabela HTML da portaria MG.

    Padrão esperado (sujeito a calibração com HTML real):
        NCM | Marca | Embalagem (ml) | PMPF (R$)

    Estratégia:
    1. BS4: percorre <table>/<tr>; captura linhas com NCM + valor monetário.
    2. Regex de fallback: NCM próximo de R$ XX,XX (até 200 chars de distância).
    """
    regras: list[RegraNormativa] = []
    vistos: set[tuple[str, float, str]] = set()

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    padrao_ncm = re.compile(r"^\s*(\d{4}\.?\d{2}\.?\d{2})\s*$")
    padrao_valor = re.compile(r"R?\$?\s*(\d{1,4}[,\.]\d{2})")
    padrao_volume = re.compile(r"(\d{2,5})\s*ml", re.IGNORECASE)

    for tr in soup.find_all("tr"):
        celulas = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if not celulas:
            continue
        ncm_idx: int | None = None
        ncm_raw: str | None = None
        for idx, cel in enumerate(celulas):
            m = padrao_ncm.match(cel)
            if m:
                ncm_idx = idx
                ncm_raw = m.group(1).replace(".", "")
                break
        if ncm_raw is None or ncm_idx is None:
            continue
        # As outras células são candidatas a marca / volume / valor.
        # Evitamos casar o regex de valor contra a própria célula NCM
        # (que tem pontuação igual à de R$ XXXX.XX).
        outras = [c for i, c in enumerate(celulas) if i != ncm_idx]
        valor: float | None = None
        for cel in outras:
            mv = padrao_valor.search(cel)
            if mv:
                try:
                    valor = float(mv.group(1).replace(",", "."))
                    break
                except ValueError:
                    continue
        if valor is None or valor <= 0:
            continue
        marca = ""
        embalagem_ml = 0
        for cel in outras:
            mvol = padrao_volume.search(cel)
            if mvol:
                embalagem_ml = int(mvol.group(1))
                continue
            if padrao_valor.search(cel):
                continue
            if not marca and len(cel) >= 2:
                marca = cel
        chave = (ncm_raw, valor, marca)
        if chave in vistos:
            continue
        vistos.add(chave)
        regras.append(_construir_regra(ncm_raw, valor, marca, embalagem_ml))

    if regras:
        return regras

    padrao_inline = re.compile(
        r"(\d{4}\.?\d{2}\.?\d{2})\D{1,400}?R?\$?\s*(\d{1,4}[,\.]\d{2})"
    )
    for match in padrao_inline.finditer(html):
        ncm_sem_ponto = match.group(1).replace(".", "")
        try:
            valor = float(match.group(2).replace(",", "."))
        except ValueError:
            continue
        if valor <= 0:
            continue
        chave = (ncm_sem_ponto, valor, "")
        if chave in vistos:
            continue
        vistos.add(chave)
        regras.append(_construir_regra(ncm_sem_ponto, valor, "", 0))

    return regras


def _construir_regra(
    ncm_sem_ponto: str, pmpf: float, marca: str, embalagem_ml: int
) -> RegraNormativa:
    detalhe = []
    if marca:
        detalhe.append(marca)
    if embalagem_ml:
        detalhe.append(f"{embalagem_ml}ml")
    detalhe.append(f"R${pmpf:.2f}")
    sufixo = " | PMPF " + " ".join(detalhe)
    return RegraNormativa(
        estado="MG",
        ncm=ncm_sem_ponto,
        mva=0.0,  # MG usa PMPF — valor real registado no fonte_legal
        aliquota_interna=_ALIQUOTA_MG,
        vigencia_inicio=_VIGENCIA_INICIO,
        vigencia_fim=_VIGENCIA_FIM,
        fonte_legal=f"{_FONTE_LEGAL}{sufixo}",
        url_fonte=_URLS_SAIF_062_2025[0],
        nivel_confianca="candidata_oficial",
        importado_por=_IMPORTADO_POR,
    )
