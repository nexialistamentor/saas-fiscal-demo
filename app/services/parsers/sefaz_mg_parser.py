"""
Parser SEFAZ-MG — extrai PMPF de refrigerantes da Portaria SAIF vigente.
Fonte: fazenda.mg.gov.br
"""
from __future__ import annotations

import logging
import re
from datetime import date

import httpx

from app.services.parsers.base_parser import BaseParser, ResultadoParser
from app.services.pipeline_normativo import RegraNormativa

logger = logging.getLogger(__name__)

_URL_SAIF_062_2025 = (
    "https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/portarias/2025/"
    "port_saif062_2025.html"
)
_FONTE_LEGAL = "Portaria SAIF 062/2025 — SEFAZ-MG"
_IMPORTADO_POR = "sefaz_mg_parser.py v1.0"
_VIGENCIA_INICIO = date(2025, 1, 1)
_ALIQUOTA_MG = 0.18  # RICMS-MG alíquota modal


class SefazMGParser(BaseParser):
    nome = "SEFAZ-MG"
    url_base = _URL_SAIF_062_2025

    def extrair(self) -> ResultadoParser:
        regras: list[RegraNormativa] = []
        erros: list[str] = []

        try:
            resp = httpx.get(
                _URL_SAIF_062_2025,
                timeout=20,
                follow_redirects=True,
                headers={"User-Agent": "SaasFiscalMonitor/1.0"},
            )
            if resp.status_code != 200:
                erros.append(f"SEFAZ-MG retornou {resp.status_code}")
                return ResultadoParser(
                    regras=[], erros=erros,
                    fonte=_FONTE_LEGAL,
                    url_consultada=_URL_SAIF_062_2025,
                    data_consulta=date.today().isoformat(),
                )

            html = resp.text
            regras = _extrair_pmpf_html(html)
            if not regras:
                erros.append(
                    "SEFAZ-MG: HTML obtido mas nenhum PMPF extraído — "
                    "estrutura da página pode ter mudado"
                )

        except Exception as exc:
            erros.append(f"SEFAZ-MG: {exc}")

        return ResultadoParser(
            regras=regras,
            erros=erros,
            fonte=_FONTE_LEGAL,
            url_consultada=_URL_SAIF_062_2025,
            data_consulta=date.today().isoformat(),
        )


def _extrair_pmpf_html(html: str) -> list[RegraNormativa]:
    """
    Extrai PMPF de tabela HTML da portaria MG.
    Padrão: NCM | Marca | Embalagem (ml) | PMPF (R$)
    """
    regras: list[RegraNormativa] = []
    # Padrão básico: valor monetário R$ XX,XX
    padrao_pmpf = re.compile(
        r'(\d{4}\.?\d{2}\.?\d{2})\D+?'  # NCM
        r'([A-Z][A-Z\s\-]+?)\s+'         # Marca
        r'(\d+)\s*ml\D+?'                # Volume
        r'R?\$?\s*(\d+[,\.]\d{2})'       # PMPF
    )

    for match in padrao_pmpf.finditer(html):
        ncm_raw = match.group(1).replace(".", "")
        marca = match.group(2).strip()
        embalagem_ml = int(match.group(3))
        pmpf_str = match.group(4).replace(",", ".")
        pmpf = float(pmpf_str)

        if pmpf <= 0:
            continue

        # PMPF vai para tabela_pmpf via pipeline — RegraNormativa é para tabela_mva
        # Por agora registamos como regra com mva=0 e nota no fonte_legal
        regras.append(RegraNormativa(
            estado="MG",
            ncm=ncm_raw,
            mva=0.0,  # MG usa PMPF — valor real em tabela_pmpf
            aliquota_interna=_ALIQUOTA_MG,
            vigencia_inicio=_VIGENCIA_INICIO,
            vigencia_fim=None,
            fonte_legal=f"{_FONTE_LEGAL} | PMPF {marca} {embalagem_ml}ml = R${pmpf:.2f}",
            url_fonte=_URL_SAIF_062_2025,
            nivel_confianca="candidata_oficial",
            importado_por=_IMPORTADO_POR,
        ))

    return regras
