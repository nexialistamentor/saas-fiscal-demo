from sqlalchemy import text
from app.database import SessionLocal


def calcular_estoque_fiscal(empresa_id: int):

    db = SessionLocal()

    query = text("""
        SELECT
            i.ncm,
            SUM(
                CASE
                    WHEN i.cfop LIKE '1%' OR i.cfop LIKE '2%' THEN COALESCE(i.quantidade, 1)
                    WHEN i.cfop LIKE '5%' OR i.cfop LIKE '6%' THEN -COALESCE(i.quantidade, 1)
                    ELSE 0
                END
            ) as estoque_fiscal
        FROM itens_fiscais i
        JOIN documentos_fiscais d ON i.documento_id = d.id
        WHERE d.empresa_id = :empresa_id
        GROUP BY i.ncm
    """)

    result = db.execute(query, {"empresa_id": empresa_id}).fetchall()

    db.close()

    return [dict(r._mapping) for r in result]


def salvar_auditoria(empresa_id: int):

    db = SessionLocal()

    estoque = calcular_estoque_fiscal(empresa_id)

    for item in estoque:

        db.execute(text("""
            INSERT INTO auditoria_estoque (
                empresa_id,
                ncm,
                estoque_fiscal
            )
            VALUES (
                :empresa_id,
                :ncm,
                :estoque_fiscal
            )
        """), {
            "empresa_id": empresa_id,
            "ncm": item["ncm"],
            "estoque_fiscal": item["estoque_fiscal"]
        })

    db.commit()
    db.close()
