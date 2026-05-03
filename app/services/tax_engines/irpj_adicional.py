"""Adicional de IRPJ sobre base presumida — limiar mensal (RIR 2018, art. 622)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

# Limiar por mês de calendário da base presumida sujeita ao adicional de 10%.
LIMIAR_ADICIONAL_IRPJ_REAIS_POR_MES = 20_000.0


def periodo_meses_from_context(context: Mapping[str, Any]) -> int:
    """
    Meses de apuração para escalar R$ 20.000/mês.

    Com ``data_referencia`` pontual (ou ausente), assume-se apuração mensal: 1 mês.
    Não inferimos duração agregada sem evidência no contexto.
    """
    ref = context.get("data_referencia")
    if ref is None:
        return 1
    if isinstance(ref, datetime):
        return 1
    if isinstance(ref, date):
        return 1
    return 1


def limiar_adicional_irpj(context: Mapping[str, Any]) -> float:
    return LIMIAR_ADICIONAL_IRPJ_REAIS_POR_MES * periodo_meses_from_context(context)


def calcular_adicional_irpj_presumido(
    base_calculo: float, context: Mapping[str, Any]
) -> float:
    limiar = limiar_adicional_irpj(context)
    excesso = base_calculo - limiar
    if excesso <= 0:
        return 0.0
    return excesso * 0.10
