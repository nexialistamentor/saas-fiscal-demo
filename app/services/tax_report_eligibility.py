"""Elegibilidade determinística do Tax Report; projeção apenas informativa."""

import math


def resultado_tem_credito_tax_report_elegivel(resultado):
    if type(resultado) is not dict:
        return False
    creditos = resultado.get("creditos_detectados")
    if type(creditos) is not list:
        return False
    tem_positivo = False
    for credito in creditos:
        if (
            type(credito) is not dict
            or credito.get("tipo") != "CREDITO_ST_ESTIMADO"
        ):
            return False
        valor = credito.get("valor_estimado")
        if type(valor) not in (int, float):
            return False
        # Inteiros são finitos; evita conversão/overflow para inteiros grandes.
        if type(valor) is float and not math.isfinite(valor):
            return False
        if valor > 0:
            tem_positivo = True
    return tem_positivo


def projetar_tax_report_eligibility(resultado):
    """Projeta somente a decisão sem conceder autorização comercial."""
    return {"eligible": resultado_tem_credito_tax_report_elegivel(resultado)}
