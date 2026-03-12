from sqlalchemy import text


def calcular_potencial_recuperacao(db, empresa_id):

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

    oportunidades = []

    for row in resultado:

        ncm = row.ncm
        st_pago = row.st_pago or 0
        base_st = row.base_st or 0
        volume = row.volume_operacoes or 0

        if base_st == 0:
            continue

        aliquota_media = st_pago / base_st

        potencial_recuperacao = (st_pago * 0.15)

        score_oportunidade = potencial_recuperacao * volume

        oportunidades.append({
            "ncm": ncm,
            "potencial_recuperacao": round(potencial_recuperacao, 2),
            "score_oportunidade": round(score_oportunidade, 2),
            "volume_operacoes": volume
        })

    oportunidades.sort(
        key=lambda x: x["score_oportunidade"],
        reverse=True
    )

    return oportunidades
