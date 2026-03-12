from app.services.anomalias_tributarias_service import detectar_anomalias_tributarias
from app.services.analisador_distorcao_service import detectar_distorcoes
from app.services.detector_creditos_service import detectar_creditos


def calcular_risco_tributario(db, empresa_id):
    anomalias = detectar_anomalias_tributarias(db, empresa_id)
    distorcoes = detectar_distorcoes(db, empresa_id)
    creditos = detectar_creditos(db, empresa_id)

    score_anomalias = sum(item["variacao_detectada"] for item in anomalias)
    score_distorcoes = sum(item["distorcao"] for item in distorcoes)
    score_creditos = sum(item["credito_estimado"] for item in creditos)

    risco = (
        score_anomalias * 0.4 +
        score_distorcoes * 0.3 +
        score_creditos * 0.3
    )

    if risco > 100000:
        nivel = "alto"
    elif risco > 30000:
        nivel = "medio"
    else:
        nivel = "baixo"

    return {
        "score_risco_tributario": round(risco, 2),
        "nivel_risco": nivel
    }
