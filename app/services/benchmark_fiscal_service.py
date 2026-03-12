from sqlalchemy import text


def gerar_benchmark_empresas(db):

    query = text("""
        SELECT
            d.empresa_id,
            SUM(i.valor_st) AS total_st,
            COUNT(*) AS volume_operacoes
        FROM itens_fiscais i
        JOIN documentos_fiscais d
            ON i.documento_id = d.id
        GROUP BY d.empresa_id
    """)

    resultados = db.execute(query).fetchall()

    ranking = []

    for row in resultados:

        eficiencia = 0
        if row.volume_operacoes:
            eficiencia = row.total_st / row.volume_operacoes

        ranking.append({
            "empresa_id": row.empresa_id,
            "eficiencia_tributaria": round(eficiencia, 2),
            "volume_operacoes": row.volume_operacoes
        })

    ranking.sort(
        key=lambda x: x["eficiencia_tributaria"],
        reverse=True
    )

    return ranking
