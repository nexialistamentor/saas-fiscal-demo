from sqlalchemy.orm import Session
from sqlalchemy import text


def detectar_creditos(db: Session, empresa_id: int):

    query = text("""
        SELECT
            i.ncm,
            SUM(i.valor_st) as st_pago,
            SUM(i.base_st) as base_st
        FROM itens_fiscais i
        INNER JOIN documentos_fiscais d ON i.documento_id = d.id
        WHERE d.empresa_id = :empresa_id
        GROUP BY i.ncm
    """)

    resultado = db.execute(query, {"empresa_id": empresa_id}).fetchall()

    creditos = []

    for row in resultado:

        ncm = row.ncm
        st_pago = float(row.st_pago or 0)
        base_st = float(row.base_st or 0)

        aliquota = 0.18

        st_correta = base_st * aliquota

        credito = st_pago - st_correta

        if credito > 0:

            creditos.append({
                "ncm": ncm,
                "credito_estimado": credito
            })

    return creditos
