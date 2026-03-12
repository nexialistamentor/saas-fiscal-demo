from sqlalchemy import text


def registrar_snapshot_inteligencia(
    db,
    empresa_id,
    score_global,
    risco,
    maturidade
):
    """
    Armazena snapshot de inteligência tributária para análise histórica.
    Permite evolução temporal, comparação e inteligência preditiva.
    """
    query = text("""
        INSERT INTO inteligencia_snapshots (
            empresa_id,
            score_global,
            risco_tributario,
            maturidade_tributaria
        )
        VALUES (
            :empresa_id,
            :score_global,
            :risco,
            :maturidade
        )
    """)

    db.execute(
        query,
        {
            "empresa_id": empresa_id,
            "score_global": score_global,
            "risco": risco,
            "maturidade": maturidade
        }
    )

    db.commit()
