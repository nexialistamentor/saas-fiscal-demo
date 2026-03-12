"""
Motor de Score Tributário por Produto (NCM).

Gera score consolidado de risco e oportunidade fiscal por NCM,
base para dashboards e priorização automática.
"""

from app.services.ranking_estrategico_service import gerar_ranking_estrategico


def calcular_score_tributario(db, empresa_id):
    """
    Calcula score tributário consolidado por NCM.

    Funções:
    - Gerar score tributário consolidado
    - Priorizar NCM com maior impacto fiscal
    - Base para dashboards estratégicos

    Returns:
        list: Lista de dicts com 'ncm' e 'score_tributario', ordenada decrescente
    """
    ranking = gerar_ranking_estrategico(db, empresa_id)
    resultados = []

    for item in ranking:
        score_final = (
            item["score"] * 0.5 +
            item["creditos"] * 0.3 +
            item["distorcao"] * 0.2
        )

        resultados.append({
            "ncm": item["ncm"],
            "score_tributario": round(score_final, 2)
        })

    resultados.sort(
        key=lambda x: x["score_tributario"],
        reverse=True
    )

    return resultados
