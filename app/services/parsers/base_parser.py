"""
Contrato base para parsers de fontes normativas.
Todo parser retorna list[RegraNormativa] para consumo pelo pipeline_normativo.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx

from app.services.pipeline_normativo import RegraNormativa

logger = logging.getLogger(__name__)

USER_AGENT = "SaasFiscalMonitor/1.1 (+monitor normativo; contacto via repo)"
PREVIEW_LEN = 500


@dataclass
class DiagnosticoHTTP:
    """
    Snapshot de uma chamada HTTP feita por um parser.
    Permite diagnosticar comportamento real em produção sem debugger.
    """
    url: str
    status_code: int | None
    bytes_recebidos: int
    content_type: str
    preview: str  # primeiros N caracteres do body
    erro: str | None = None


@dataclass
class ResultadoParser:
    regras: list[RegraNormativa]
    erros: list[str]
    fonte: str          # ex: "SEFAZ-SP/SRE-89-2025"
    url_consultada: str
    data_consulta: str  # ISO YYYY-MM-DD
    diagnostico: list[DiagnosticoHTTP] = field(default_factory=list)


class BaseParser(ABC):
    """Interface que todo parser normativo deve implementar."""

    nome: str = "base"
    url_base: str = ""

    @abstractmethod
    def extrair(self) -> ResultadoParser:
        """
        Consulta a fonte, extrai regras e retorna ResultadoParser.
        Nunca lança excepção — erros vão para ResultadoParser.erros.
        """
        ...

    def extrair_seguro(self) -> ResultadoParser:
        """Wrapper com try/except — garante que falhas não quebram o pipeline."""
        try:
            return self.extrair()
        except Exception as exc:
            return ResultadoParser(
                regras=[],
                erros=[f"{self.nome}: falha crítica na extracção: {exc}"],
                fonte=self.nome,
                url_consultada=self.url_base,
                data_consulta=date.today().isoformat(),
                diagnostico=[],
            )


def fetch_com_diagnostico(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = 20.0,
    preview_len: int = PREVIEW_LEN,
    extra_headers: dict[str, str] | None = None,
) -> tuple[httpx.Response | None, DiagnosticoHTTP]:
    """
    GET com diagnóstico estruturado.

    Nunca lança — devolve (response_or_none, diagnostico).
    O diagnóstico contém status_code, content_type, bytes e um preview do body
    para investigação em produção sem precisar de debugger.
    """
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}
    if extra_headers:
        headers.update(extra_headers)

    try:
        resp = httpx.get(
            url,
            params=params,
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
        )
        body_text = resp.text or ""
        diagnostico = DiagnosticoHTTP(
            url=str(resp.request.url),
            status_code=resp.status_code,
            bytes_recebidos=len(resp.content or b""),
            content_type=resp.headers.get("content-type", ""),
            preview=body_text[:preview_len],
        )
        logger.info(
            "fetch %s status=%s bytes=%d ctype=%s",
            diagnostico.url,
            diagnostico.status_code,
            diagnostico.bytes_recebidos,
            diagnostico.content_type,
        )
        return resp, diagnostico
    except Exception as exc:
        diagnostico = DiagnosticoHTTP(
            url=url,
            status_code=None,
            bytes_recebidos=0,
            content_type="",
            preview="",
            erro=str(exc),
        )
        logger.warning("fetch %s falhou: %s", url, exc)
        return None, diagnostico
