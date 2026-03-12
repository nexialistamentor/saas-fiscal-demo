from app.services.detector_creditos_service import detectar_creditos
from app.services.impacto_financeiro_service import calcular_impacto_financeiro


def ranking_oportunidades_recuperacao(db, empresa_id):

    creditos = detectar_creditos(db, empresa_id)
    impactos = calcular_impacto_financeiro(db, empresa_id)

    mapa = {}

    for item in impactos:
        mapa[item["ncm"]] = {
            "ncm": item["ncm"],
            "impacto": item["impacto_anual_estimado"],
            "creditos": 0
        }

    for item in creditos:
        ncm = item["ncm"]
        if ncm not in mapa:
            mapa[ncm] = {
                "ncm": ncm,
                "impacto": 0,
                "creditos": item["credito_estimado"]
            }
        else:
            mapa[ncm]["creditos"] = item["credito_estimado"]

    ranking = []

    for item in mapa.values():

        potencial = item["impacto"] + item["creditos"]

        ranking.append({
            "ncm": item["ncm"],
            "potencial_recuperacao": round(potencial, 2)
        })

    ranking.sort(
        key=lambda x: x["potencial_recuperacao"],
        reverse=True
    )

    return ranking
