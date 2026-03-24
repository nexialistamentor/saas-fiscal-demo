from sqlalchemy import text


def obter_historico_inteligencia(db, empresa_id):
    """
    Consulta histórico temporal da inteligência tributária da empresa.

    Função do serviço:
    - Consultar evolução do score global
    - Consultar evolução do risco tributário
    - Consultar evolução da maturidade fiscal
    - Analisar histórico temporal da empresa
    """
    query = text("""
        SELECT
            score_global,
            risco_tributario,
            maturidade_tributaria,
            uf_cobertura,
            criado_em
        FROM inteligencia_snapshots
        WHERE empresa_id = :empresa_id
        ORDER BY criado_em ASC
    """)

    resultados = db.execute(
        query,
        {"empresa_id": empresa_id}
    ).fetchall()

    historico = []

    for row in resultados:
        historico.append({
            "score_global": row.score_global,
            "risco_tributario": row.risco_tributario,
            "maturidade_tributaria": row.maturidade_tributaria,
            "uf_cobertura": row.uf_cobertura,
            "data_snapshot": row.criado_em
        })

    return historico
