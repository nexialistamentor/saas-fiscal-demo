from app.services.impacto_financeiro_service import calcular_impacto_financeiro
from app.services.score_tributario_service import calcular_score_tributario
from app.services.indice_inteligencia_service import calcular_indice_inteligencia


def gerar_radar_tributario(db, empresa_id):

    impactos = calcular_impacto_financeiro(db, empresa_id)
    score = calcular_score_tributario(db, empresa_id)
    indice = calcular_indice_inteligencia(db, empresa_id)

    impacto_total = sum(
        item["impacto_anual_estimado"] for item in impactos
    )

    top_ncm = score[:5]

    radar = {
        "impacto_financeiro_total": round(impacto_total, 2),
        "indice_inteligencia": indice["indice_inteligencia_tributaria"],
        "nivel_inteligencia": indice["nivel"],
        "top_ncm_criticos": top_ncm
    }

    return radar
