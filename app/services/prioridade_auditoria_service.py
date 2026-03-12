from app.services.anomalias_tributarias_service import detectar_anomalias_tributarias
from app.services.impacto_financeiro_service import calcular_impacto_financeiro
from app.services.score_tributario_service import calcular_score_tributario


def calcular_prioridade_auditoria(db, empresa_id):

    anomalias = detectar_anomalias_tributarias(db, empresa_id)
    impactos = calcular_impacto_financeiro(db, empresa_id)
    scores = calcular_score_tributario(db, empresa_id)

    mapa = {}

    for item in scores:
        mapa[item["ncm"]] = {
            "ncm": item["ncm"],
            "score": item["score_tributario"],
            "impacto": 0,
            "anomalia": 0
        }

    for item in impactos:
        ncm = item["ncm"]
        if ncm in mapa:
            mapa[ncm]["impacto"] = item["impacto_anual_estimado"]

    for item in anomalias:
        ncm = item["ncm"]
        if ncm in mapa:
            mapa[ncm]["anomalia"] = item["variacao_detectada"]

    resultado = []

    for item in mapa.values():

        prioridade = (
            item["score"] * 0.4 +
            item["impacto"] * 0.4 +
            item["anomalia"] * 0.2
        )

        resultado.append({
            "ncm": item["ncm"],
            "prioridade_auditoria": round(prioridade, 2)
        })

    resultado.sort(
        key=lambda x: x["prioridade_auditoria"],
        reverse=True
    )

    return resultado
