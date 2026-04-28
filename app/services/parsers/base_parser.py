"""
Contrato base para parsers de fontes normativas.
Todo parser retorna list[RegraNormativa] para consumo pelo pipeline_normativo.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from app.services.pipeline_normativo import RegraNormativa


@dataclass
class ResultadoParser:
    regras: list[RegraNormativa]
    erros: list[str]
    fonte: str          # ex: "SEFAZ-SP/SRE-89-2025"
    url_consultada: str
    data_consulta: str  # ISO YYYY-MM-DD


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
            )
