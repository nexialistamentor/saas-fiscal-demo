from app.services.historico_inteligencia_service import obter_historico_inteligencia


def comparar_periodos_inteligencia(db, empresa_id):
    """
    Motor de Comparação Temporal da Empresa.

    Função do motor:
    - Comparar snapshots consecutivos
    - Avaliar evolução recente da empresa
    - Detectar mudança fiscal recente
    """
    historico = obter_historico_inteligencia(db, empresa_id)

    if len(historico) < 2:
        return {
            "comparacao": "insuficiente"
        }

    ultimo = historico[-1]
    anterior = historico[-2]

    variacao = ultimo["score_global"] - anterior["score_global"]

    if variacao > 0:
        resultado = "melhora"
    elif variacao < 0:
        resultado = "piora"
    else:
        resultado = "estavel"

    return {
        "score_periodo_anterior": anterior["score_global"],
        "score_periodo_atual": ultimo["score_global"],
        "variacao": variacao,
        "resultado": resultado
    }
