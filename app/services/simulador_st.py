"""
Motor de Simulação de Substituição Tributária (ICMS-ST).

Permite ao sistema:
- Simular nova ST
- Comparar com ST paga
- Estimar restituição
- Estimar impacto de mudança normativa

Utilizado por: InsightEngine, motor de decisão tributária, analisador de impacto fiscal.
"""


def simular_st(valor_produto, mva, aliquota):
    base_calculo = valor_produto * (1 + mva)
    st_calculada = base_calculo * aliquota
    return {
        "base_calculo": base_calculo,
        "st_calculada": st_calculada
    }
