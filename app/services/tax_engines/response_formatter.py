def formatar_resposta_tributaria(
    regime: str,
    tributos: dict,
    bases_calculo: dict,
    alertas: list,
    analysis_type: str = "empresa_tax",
    erro: str | None = None
):
    return {
        "analysis_type": analysis_type,
        "success": erro is None,
        "data": {
            "regime": regime,
            "tributos": tributos,
            "bases_calculo": bases_calculo,
            "alertas": alertas
        },
        "erro": erro
    }
