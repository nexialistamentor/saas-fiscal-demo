from app.services.motor_preditivo_service import calcular_potencial_recuperacao
from app.services.detector_creditos_service import detectar_creditos
from app.services.analisador_distorcao_service import detectar_distorcoes


def gerar_ranking_estrategico(db, empresa_id):

    ranking = {}

    oportunidades = calcular_potencial_recuperacao(db, empresa_id)
    creditos = detectar_creditos(db, empresa_id)
    distorcoes = detectar_distorcoes(db, empresa_id)

    for item in oportunidades:

        ncm = item["ncm"]

        ranking[ncm] = {
            "ncm": ncm,
            "score": item["score_oportunidade"],
            "potencial": item["potencial_recuperacao"],
            "creditos": 0,
            "distorcao": 0
        }

    for credito in creditos:

        ncm = credito["ncm"]

        if ncm not in ranking:
            ranking[ncm] = {
                "ncm": ncm,
                "score": 0,
                "potencial": 0,
                "creditos": 0,
                "distorcao": 0
            }

        ranking[ncm]["creditos"] += credito["credito_estimado"]

    for dist in distorcoes:

        ncm = dist["ncm"]

        if ncm not in ranking:
            ranking[ncm] = {
                "ncm": ncm,
                "score": 0,
                "potencial": 0,
                "creditos": 0,
                "distorcao": 0
            }

        ranking[ncm]["distorcao"] += dist["distorcao"]

    resultado = list(ranking.values())

    resultado.sort(
        key=lambda x: (
            x["score"]
            + x["creditos"]
            + x["distorcao"]
        ),
        reverse=True
    )

    return resultado
