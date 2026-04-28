from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.fiscal_utils import resolver_aliquota_e_mva


def gerar_ranking_restituicao(db: Session, empresa_id: int):

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
        st_pago = float(row.st_pago or 0)
        base_st = float(row.base_st or 0)
        res = resolver_aliquota_e_mva(db, "", ncm)
        aliquota = res["aliquota"]
        st_devida = base_st * aliquota
        restituicao = max(st_pago - st_devida, 0)
        ranking.append({
            "ncm": ncm,
            "restituicao_estimada": float(restituicao),
            "percentual_impacto": 0,
            "aliquota_fonte": res["fonte"],
        })

    ranking.sort(key=lambda x: x["restituicao_estimada"], reverse=True)

    return ranking
