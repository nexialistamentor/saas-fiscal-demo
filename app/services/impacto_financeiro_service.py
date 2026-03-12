from app.services.ranking_estrategico_service import gerar_ranking_estrategico


def calcular_impacto_financeiro(db, empresa_id):

    ranking = gerar_ranking_estrategico(db, empresa_id)

    impactos = []

    for item in ranking:

        impacto_anual = (
            item["potencial"]
            + item["creditos"]
        ) * 12

        prioridade = impacto_anual + item["score"]

        impactos.append({
            "ncm": item["ncm"],
            "impacto_anual_estimado": round(impacto_anual, 2),
            "prioridade_fiscal": round(prioridade, 2)
        })

    impactos.sort(
        key=lambda x: x["prioridade_fiscal"],
        reverse=True
    )

    return impactos
