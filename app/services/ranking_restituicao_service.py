from sqlalchemy.orm import Session
from sqlalchemy import text


def gerar_ranking_restituicao(db: Session, empresa_id: int):

    db.rollback()

    query = text("""
        SELECT
            i.ncm,
            SUM(i.valor_st) AS st_pago,
            SUM(i.base_st) AS base_st,
            COUNT(*) AS volume_operacoes
        FROM itens_fiscais i
        INNER JOIN documentos_fiscais d ON i.documento_id = d.id
        WHERE d.empresa_id = :empresa_id
        GROUP BY i.ncm
    """)

    resultado = db.execute(query, {"empresa_id": empresa_id}).fetchall()

    ranking = []

    for row in resultado:

        ncm = row.ncm
        st_pago = row.st_pago or 0
        base_st = row.base_st or 0

        # temporário até integrar tabela normativa
        aliquota = 0.18

        st_devida = base_st * aliquota

        restituicao = st_pago - st_devida

        ranking.append({
            "ncm": ncm,
            "restituicao_estimada": float(restituicao),
            "percentual_impacto": 0
        })

    ranking.sort(key=lambda x: x["restituicao_estimada"], reverse=True)

    return ranking
