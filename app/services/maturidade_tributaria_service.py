from app.services.indice_inteligencia_service import calcular_indice_inteligencia
from app.services.eficiencia_tributaria_service import calcular_eficiencia_tributaria
from app.services.risco_tributario_service import calcular_risco_tributario
from app.services.complexidade_tributaria_service import calcular_complexidade_tributaria


def calcular_maturidade_tributaria(db, empresa_id):

    indice = calcular_indice_inteligencia(db, empresa_id)
    eficiencia = calcular_eficiencia_tributaria(db, empresa_id)
    risco = calcular_risco_tributario(db, empresa_id)
    complexidade = calcular_complexidade_tributaria(db, empresa_id)

    score = (
        indice["indice_inteligencia_tributaria"] * 0.3 +
        eficiencia["indice_eficiencia_tributaria"] * 0.3 +
        complexidade["score_complexidade"] * 0.2 -
        risco["score_risco_tributario"] * 0.2
    )

    if score > 50000:
        nivel = "avancado"
    elif score > 20000:
        nivel = "intermediario"
    else:
        nivel = "iniciante"

    return {
        "score_maturidade_tributaria": round(score, 2),
        "nivel_maturidade": nivel
    }
