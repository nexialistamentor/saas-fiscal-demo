from sqlalchemy.orm import Session
from sqlalchemy import text


def gerar_mapa_oportunidades(db: Session, empresa_id: int):

    mapa = {
        "restituicao_st": 0,
        "mva_distorcida": 0,
        "estoque_st": 0,
        "anomalia_preco": 0
    }

    try:
        query = text("""
            SELECT
                tipo,
                SUM(valor_estimado) as impacto_total
            FROM insights
            WHERE empresa_id = :empresa_id
            GROUP BY tipo
        """)
        resultado = db.execute(query, {"empresa_id": empresa_id}).fetchall()
    except Exception:
        return mapa

    for row in resultado:

        tipo = row.tipo
        valor = float(row.impacto_total or 0)

        if tipo == "PRODUTO_COM_RESTITUICAO_RELEVANTE":
            mapa["restituicao_st"] += valor

        if tipo in ("DISTORCAO_MVA", "DISTORCAO_MVA_REAL"):
            mapa["mva_distorcida"] += valor

        if tipo == "ESTOQUE_COM_ST":
            mapa["estoque_st"] += valor

        if tipo == "ANOMALIA_PRECO":
            mapa["anomalia_preco"] += valor

    return mapa
