from app.services.impacto_financeiro_service import calcular_impacto_financeiro
from app.services.detector_creditos_service import detectar_creditos


def projetar_recuperacao_tributaria(db, empresa_id):
    """Motor de Projeção de Recuperação Tributária.

    Estima quanto a empresa pode recuperar em créditos tributários
    nos próximos 12 meses, usando impacto financeiro e tendência de créditos.
    """
    impactos = calcular_impacto_financeiro(db, empresa_id)
    creditos = detectar_creditos(db, empresa_id)

    total_creditos = sum(
        item["credito_estimado"] for item in creditos
    )

    impacto_total = sum(
        item["impacto_anual_estimado"] for item in impactos
    )

    projecao = total_creditos + impacto_total

    return {
        "creditos_identificados": round(total_creditos, 2),
        "impacto_anual_estimado": round(impacto_total, 2),
        "recuperacao_projetada_12m": round(projecao, 2)
    }
