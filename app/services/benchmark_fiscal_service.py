from sqlalchemy import text


def gerar_benchmark_empresas(db, empresa_ids: list[int] | None = None):

    if empresa_ids is not None and len(empresa_ids) == 0:
        return []

    if empresa_ids is not None:
        placeholders = ", ".join(f":id{i}" for i in range(len(empresa_ids)))
        query = text(f"""
            SELECT
                d.empresa_id,
                SUM(i.valor_st) AS total_st,
                COUNT(*) AS volume_operacoes
            FROM itens_fiscais i
            JOIN documentos_fiscais d
                ON i.documento_id = d.id
            WHERE d.empresa_id IN ({placeholders})
            GROUP BY d.empresa_id
        """)
        params = {f"id{i}": eid for i, eid in enumerate(empresa_ids)}
        resultados = db.execute(query, params).fetchall()
    else:
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
