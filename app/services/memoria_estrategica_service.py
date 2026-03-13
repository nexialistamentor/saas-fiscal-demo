from sqlalchemy import text
from datetime import datetime


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
            maturidade_tributaria,
            criado_em
        )
        VALUES (
            :empresa_id,
            :score_global,
            :risco,
            :maturidade,
            :criado_em
        )
    """)

    db.execute(
        query,
        {
            "empresa_id": empresa_id,
            "score_global": score_global,
            "risco": risco,
            "maturidade": maturidade,
            "criado_em": datetime.utcnow()
        }
    )

    db.commit()
