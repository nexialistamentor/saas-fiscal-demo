"""
Parser DOU — extrai MVA/PMPF de publicações estruturadas do Diário Oficial da União.
Evolução do _consultar_dou() em normative_watchdog_agent.py.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx

from app.services.parsers.base_parser import BaseParser, ResultadoParser
from app.services.pipeline_normativo import RegraNormativa

logger = logging.getLogger(__name__)

_DOU_API = "https://www.in.gov.br/consulta/-/buscar/dou"
_TERMOS_MVA = [
    "MVA substituição tributária ICMS",
    "margem valor agregado ICMS-ST",
    "IVA-ST refrigerantes",
    "PMPF bebidas substituição tributária",
    "Convênio ICMS alíquota substituição",
]
_IMPORTADO_POR = "dou_parser.py v1.0"


class DOUParser(BaseParser):
    """
    Consulta o DOU e tenta extrair regras normativas estruturadas.
    Publicações não estruturadas → nivel_confianca_fonte="candidata_oficial"
    para revisão pelo AG-VALIDACAO antes de promover a "oficial".
    """
    nome = "DOU"
    url_base = _DOU_API

    def __init__(self, dias_atras: int = 30):
        self.dias_atras = dias_atras

    def extrair(self) -> ResultadoParser:
        data_inicio = (date.today() - timedelta(days=self.dias_atras)).strftime("%d-%m-%Y")
        data_fim = date.today().strftime("%d-%m-%Y")
        regras: list[RegraNormativa] = []
        erros: list[str] = []
        publicacoes_relevantes: list[dict] = []

        for termo in _TERMOS_MVA:
            try:
                resp = httpx.get(
                    _DOU_API,
                    params={
                        "q": termo,
                        "exactDate": "personalizado",
                        "initialDate": data_inicio,
                        "finalDate": data_fim,
                        "s": "do1",
                    },
                    timeout=15,
                    headers={"User-Agent": "SaasFiscalMonitor/1.0"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("content") or []
                    publicacoes_relevantes.extend(items[:5])
                else:
                    erros.append(f"DOU retornou {resp.status_code} para termo '{termo}'")
            except Exception as exc:
                erros.append(f"DOU falhou para termo '{termo}': {exc}")

        # Tentativa de extracção estruturada
        # DOU raramente publica tabelas MVA em JSON — maioria é texto livre
        # Publicações detectadas → nivel_confianca_fonte="candidata_oficial"
        # para processamento pelo AG-VALIDACAO
        for pub in publicacoes_relevantes:
            titulo = pub.get("title") or pub.get("titulo") or ""
            url = pub.get("href") or pub.get("url") or _DOU_API
            uf = _extrair_uf_do_titulo(titulo)
            if uf:
                regras.append(RegraNormativa(
                    estado=uf,
                    ncm="",  # NCM não identificável sem estrutura
                    mva=0.0,  # Valor não extraível de texto livre
                    aliquota_interna=0.0,
                    vigencia_inicio=date.today(),
                    vigencia_fim=None,
                    fonte_legal=f"DOU: {titulo[:200]}",
                    url_fonte=url,
                    nivel_confianca="candidata_oficial",
                    importado_por=_IMPORTADO_POR,
                ))

        return ResultadoParser(
            regras=regras,
            erros=erros,
            fonte="DOU",
            url_consultada=_DOU_API,
            data_consulta=date.today().isoformat(),
        )


def _extrair_uf_do_titulo(titulo: str) -> str | None:
    """Heurística: detecta UF mencionada no título da publicação."""
    _UFS = [
        "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT",
        "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
    ]
    titulo_upper = titulo.upper()
    for uf in _UFS:
        if f" {uf} " in titulo_upper or f"/{uf}" in titulo_upper or titulo_upper.startswith(uf):
            return uf
    return None
