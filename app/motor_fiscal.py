def calcular_imposto(valor: float):
    imposto = valor * 0.10
    total = valor + imposto

    return {
        "valor_original": valor,
        "imposto_calculado": imposto,
        "valor_com_imposto": total
    }
