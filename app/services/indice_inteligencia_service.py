from app.services.impacto_financeiro_service import calcular_impacto_financeiro


def calcular_indice_inteligencia(db, empresa_id):
    impactos = calcular_impacto_financeiro(db, empresa_id)

    if not impactos:
        return {
            "indice_inteligencia_tributaria": 0,
            "nivel": "baixo"
        }

    impacto_total = sum(
        item["impacto_anual_estimado"] for item in impactos
    )

    indice = impacto_total / len(impactos)

    if indice > 100000:
        nivel = "alto"
    elif indice > 30000:
        nivel = "medio"
    else:
        nivel = "baixo"

    return {
        "indice_inteligencia_tributaria": round(indice, 2),
        "nivel": nivel
    }
