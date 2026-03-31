from app.services.context_flags_service import default_context_flags


def gerar_fallback(tipo: str, dados: dict):
    """
    Retorna resposta simplificada quando uma engine está degradada.
    """

    if tipo == "tax_planning":
        flags = default_context_flags()
        flags["usa_estimativa"] = True
        return {
            "analysis_type": tipo,
            "fallback": True,
            "mensagem": "Planejamento tributário simplificado (engine degradada)",
            "context_flags": flags,
        }

    if tipo == "tax_recovery":
        faturamento = dados.get("faturamento", 0)

        estimativa = faturamento * 0.01

        flags = default_context_flags()
        flags["usa_estimativa"] = True
        return {
            "analysis_type": tipo,
            "fallback": True,
            "credito_estimado": estimativa,
            "mensagem": "Estimativa simplificada de recuperação tributária",
            "context_flags": flags,
        }

    if tipo == "empresa_tax":
        faturamento = dados.get("faturamento", 0)

        imposto_estimado = faturamento * 0.06

        flags = default_context_flags()
        flags["usa_estimativa"] = True
        return {
            "analysis_type": tipo,
            "fallback": True,
            "imposto_estimado": imposto_estimado,
            "mensagem": "Cálculo tributário simplificado",
            "context_flags": flags,
        }

    flags = default_context_flags()
    flags["usa_estimativa"] = True
    return {
        "analysis_type": tipo,
        "fallback": True,
        "mensagem": "Resposta simplificada devido a degradação da engine",
        "context_flags": flags,
    }
