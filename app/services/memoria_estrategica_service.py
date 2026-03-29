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
    query_uf = text("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN uf_emit IS NOT NULL OR uf_dest IS NOT NULL THEN 1 ELSE 0 END) AS preenchidos
        FROM documentos_fiscais
        WHERE empresa_id = :empresa_id
    """)
    row = db.execute(query_uf, {"empresa_id": empresa_id}).fetchone()
    total = row[0] or 0
    preenchidos = row[1] or 0
    uf_cobertura = round((preenchidos / total) * 100, 2) if total > 0 else None

    query = text("""
        INSERT INTO inteligencia_snapshots (
            empresa_id,
            score_global,
            risco_tributario,
            maturidade_tributaria,
            uf_cobertura,
            criado_em
        )
        VALUES (
            :empresa_id,
            :score_global,
            :risco,
            :maturidade,
            :uf_cobertura,
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
            "uf_cobertura": uf_cobertura,
            "criado_em": datetime.utcnow()
        }
    )

    db.commit()
