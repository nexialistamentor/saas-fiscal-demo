"""
Classe base para engines tributárias.
Garante padronização de execução, logging e tratamento de erro.
"""

from datetime import date, datetime


class TempoNormativoAusenteError(Exception):
    """Levantada quando nenhum dado temporal normativo está disponível no contexto."""


class BaseTaxEngine:
    """
    Classe base para todas as engines tributárias.
    Padroniza execução, logging e tratamento de erro.
    """

    name = "base_tax_engine"
    versao = "1.0"

    def execute(self, context: dict):
        raise NotImplementedError("Engine deve implementar execute()")

    def resolver_ano_referencia(self, context: dict) -> int:
        """
        Resolve o ano normativo a partir do contexto.

        Prioridade: ano_referencia > data_referencia > data_emissao > ano_calendario.
        Levanta TempoNormativoAusenteError se nenhum dado temporal estiver presente.
        """
        if not context:
            raise TempoNormativoAusenteError(
                "Cálculo bloqueado: ano ou data de referência normativa ausente."
            )

        ano = context.get("ano_referencia")
        if ano is not None:
            try:
                return int(ano)
            except (TypeError, ValueError):
                pass

        for key in ("data_referencia", "data_emissao"):
            valor = context.get(key)
            if valor is not None:
                if isinstance(valor, datetime):
                    return valor.year
                if isinstance(valor, date):
                    return valor.year

        ano_cal = context.get("ano_calendario")
        if ano_cal is not None:
            try:
                return int(ano_cal)
            except (TypeError, ValueError):
                pass

        raise TempoNormativoAusenteError(
            "Cálculo bloqueado: ano ou data de referência normativa ausente."
        )

    def log_inicio(self):
        pass

    def log_fim(self):
        pass
