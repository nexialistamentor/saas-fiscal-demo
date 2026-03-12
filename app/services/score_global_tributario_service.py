from app.services.maturidade_tributaria_service import calcular_maturidade_tributaria
from app.services.eficiencia_tributaria_service import calcular_eficiencia_tributaria
from app.services.risco_tributario_service import calcular_risco_tributario


def calcular_score_global_tributario(db, empresa_id):

    maturidade = calcular_maturidade_tributaria(db, empresa_id)
    eficiencia = calcular_eficiencia_tributaria(db, empresa_id)
    risco = calcular_risco_tributario(db, empresa_id)

    score = (
        maturidade["score_maturidade_tributaria"] * 0.5 +
        eficiencia["indice_eficiencia_tributaria"] * 0.3 -
        risco["score_risco_tributario"] * 0.2
    )

    if score > 60000:
        nivel = "elite"
    elif score > 30000:
        nivel = "avancado"
    else:
        nivel = "em_desenvolvimento"

    return {
        "score_global_tributario": round(score, 2),
        "nivel_empresa": nivel
    }
