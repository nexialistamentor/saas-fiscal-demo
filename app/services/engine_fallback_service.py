def gerar_fallback(tipo: str, dados: dict):
    """
    Retorna resposta simplificada quando uma engine está degradada.
    """

    if tipo == "tax_planning":
        return {
            "analysis_type": tipo,
            "fallback": True,
            "mensagem": "Planejamento tributário simplificado (engine degradada)"
        }

    if tipo == "tax_recovery":
        faturamento = dados.get("faturamento", 0)

        estimativa = faturamento * 0.01

        return {
            "analysis_type": tipo,
            "fallback": True,
            "credito_estimado": estimativa,
            "mensagem": "Estimativa simplificada de recuperação tributária"
        }

    if tipo == "empresa_tax":
        faturamento = dados.get("faturamento", 0)

        imposto_estimado = faturamento * 0.06

        return {
            "analysis_type": tipo,
            "fallback": True,
            "imposto_estimado": imposto_estimado,
            "mensagem": "Cálculo tributário simplificado"
        }

    return {
        "analysis_type": tipo,
        "fallback": True,
        "mensagem": "Resposta simplificada devido a degradação da engine"
    }
