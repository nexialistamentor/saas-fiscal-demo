from app.services.historico_inteligencia_service import obter_historico_inteligencia


def analisar_tendencia_inteligencia(db, empresa_id):
    """
    Motor de Análise de Tendência da Inteligência Tributária.

    Função do motor:
    - Avaliar evolução da inteligência tributária
    - Detectar melhoria ou deterioração fiscal
    - Identificar tendência da gestão tributária
    """
    historico = obter_historico_inteligencia(db, empresa_id)

    if len(historico) < 2:
        return {
            "tendencia": "insuficiente",
            "variacao_score": 0
        }

    primeiro = historico[0]["score_global"]
    ultimo = historico[-1]["score_global"]

    variacao = ultimo - primeiro

    if variacao > 10000:
        tendencia = "melhoria_forte"
    elif variacao > 0:
        tendencia = "melhoria"
    elif variacao < -10000:
        tendencia = "queda_forte"
    elif variacao < 0:
        tendencia = "queda"
    else:
        tendencia = "estavel"

    return {
        "score_inicial": primeiro,
        "score_atual": ultimo,
        "variacao_score": variacao,
        "tendencia": tendencia
    }
