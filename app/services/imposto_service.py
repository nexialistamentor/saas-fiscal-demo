


    




def calcular_imposto(valor: float, aliquota: float = 0.06) -> dict:
    imposto = valor * aliquota

    return {
        "valor_base": valor,
        "aliquota": aliquota,
        "imposto": imposto,
        "total_com_imposto": valor + imposto
    }