from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.fiscal_utils import resolver_aliquota_e_mva


def detectar_distorcoes(db: Session, empresa_id: int):
    query = text("""
        SELECT
            i.ncm,
            AVG(i.valor_produto) as preco_medio,
            SUM(i.base_st) as base_st
        FROM itens_fiscais i
        INNER JOIN documentos_fiscais d ON i.documento_id = d.id
        WHERE d.empresa_id = :empresa_id
        GROUP BY i.ncm
    """)

    resultado = db.execute(query, {"empresa_id": empresa_id}).fetchall()

    distorcoes = []

    for row in resultado:
        ncm = row.ncm
        preco_medio = float(row.preco_medio or 0)
        base_st = float(row.base_st or 0)

        if preco_medio == 0:
            continue

        margem_real = (preco_medio - base_st) / preco_medio

        res = resolver_aliquota_e_mva(db, "", ncm)
        mva_oficial = res["mva"]
        distorcao = mva_oficial - margem_real

        if distorcao > 0.20:
            distorcoes.append({
                "ncm": ncm,
                "distorcao": distorcao,
                "mva_fonte": res["fonte"],
            })

    return distorcoes
