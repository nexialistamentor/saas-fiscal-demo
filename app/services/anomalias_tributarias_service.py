from sqlalchemy import text


def detectar_anomalias_tributarias(db, empresa_id):
    query = text("""
        SELECT
            ncm,
            AVG(valor_st) AS media_st,
            MAX(valor_st) AS max_st,
            MIN(valor_st) AS min_st,
            COUNT(*) AS volume
        FROM itens_fiscais i
        JOIN documentos_fiscais d
            ON i.documento_id = d.id
        WHERE d.empresa_id = :empresa_id
        GROUP BY ncm
    """)

    resultados = db.execute(
        query,
        {"empresa_id": empresa_id}
    ).fetchall()

    anomalias = []

    for row in resultados:
        media = row.media_st or 0
        max_val = row.max_st
        min_val = row.min_st
        if media == 0 or max_val is None or min_val is None:
            continue
        variacao = (max_val - min_val) / media

        if variacao > 2:
            anomalias.append({
                "ncm": row.ncm,
                "variacao_detectada": round(variacao, 2),
                "volume_operacoes": row.volume
            })

    anomalias.sort(
        key=lambda x: x["variacao_detectada"],
        reverse=True
    )

    return anomalias
