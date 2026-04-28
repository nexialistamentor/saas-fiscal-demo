"""
Parser SEFAZ-SP — extrai IVA-ST por NCM/CEST da Portaria SRE vigente.
Fonte: legislacao.fazenda.sp.gov.br
"""
from __future__ import annotations

import logging
import re
from datetime import date

import httpx

from app.services.parsers.base_parser import BaseParser, ResultadoParser
from app.services.pipeline_normativo import RegraNormativa

logger = logging.getLogger(__name__)

# Portaria vigente em 2026-01-01 para bebidas/refrigerantes
_URL_SRE_89_2025 = (
    "https://legislacao.fazenda.sp.gov.br/Paginas/portaria-sre-89-2025.aspx"
)
_FONTE_LEGAL = "Portaria SRE 89/2025 — SEFAZ-SP"
_IMPORTADO_POR = "sefaz_sp_parser.py v1.0"
_VIGENCIA_INICIO = date(2026, 1, 1)


class SefazSPParser(BaseParser):
    """
    Extrai IVA-ST para SP da Portaria SRE 89/2025.
    Resultado → nivel_confianca_fonte="candidata_oficial".
    Validação cruzada pelo AG-VALIDACAO antes de promover a "oficial".
    """
    nome = "SEFAZ-SP"
    url_base = _URL_SRE_89_2025

    def extrair(self) -> ResultadoParser:
        regras: list[RegraNormativa] = []
        erros: list[str] = []

        try:
            resp = httpx.get(
                _URL_SRE_89_2025,
                timeout=20,
                follow_redirects=True,
                headers={"User-Agent": "SaasFiscalMonitor/1.0"},
            )
            if resp.status_code != 200:
                erros.append(f"SEFAZ-SP retornou {resp.status_code}")
                return ResultadoParser(
                    regras=[], erros=erros,
                    fonte=_FONTE_LEGAL,
                    url_consultada=_URL_SRE_89_2025,
                    data_consulta=date.today().isoformat(),
                )

            html = resp.text
            regras = _extrair_regras_html(html)
            if not regras:
                erros.append(
                    "SEFAZ-SP: HTML obtido mas nenhuma regra extraída — "
                    "estrutura da página pode ter mudado"
                )

        except Exception as exc:
            erros.append(f"SEFAZ-SP: {exc}")

        return ResultadoParser(
            regras=regras,
            erros=erros,
            fonte=_FONTE_LEGAL,
            url_consultada=_URL_SRE_89_2025,
            data_consulta=date.today().isoformat(),
        )


def _extrair_regras_html(html: str) -> list[RegraNormativa]:
    """
    Tenta extrair tabela de IVA-ST do HTML da portaria SP.
    Padrão esperado: tabela com NCM | CEST | IVA-ST (%)
    """
    regras: list[RegraNormativa] = []
    # Padrão: NCM de 8 dígitos seguido de percentual IVA-ST
    # ex: "2202.10.00" ... "66%"
    padrao_ncm = re.compile(r'(\d{4}\.\d{2}\.\d{2})\D+?(\d{2,3}(?:\.\d+)?)\s*%')

    for match in padrao_ncm.finditer(html):
        ncm_raw = match.group(1).replace(".", "")
        iva_st = float(match.group(2))

        if iva_st <= 0 or iva_st > 500:
            continue

        regras.append(RegraNormativa(
            estado="SP",
            ncm=ncm_raw,
            mva=iva_st,
            aliquota_interna=0.18,  # RICMS/SP alíquota modal verificada
            vigencia_inicio=_VIGENCIA_INICIO,
            vigencia_fim=None,
            fonte_legal=_FONTE_LEGAL,
            url_fonte=_URL_SRE_89_2025,
            nivel_confianca="candidata_oficial",
            importado_por=_IMPORTADO_POR,
        ))

    return regras
