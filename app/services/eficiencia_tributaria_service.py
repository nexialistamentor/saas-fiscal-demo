from app.services.impacto_financeiro_service import calcular_impacto_financeiro
from sqlalchemy import text


def calcular_eficiencia_tributaria(db, empresa_id):

    impactos = calcular_impacto_financeiro(db, empresa_id)

    impacto_total = sum(
        item["impacto_anual_estimado"] for item in impactos
    )

    query = text("""
        SELECT COUNT(*) AS total_operacoes
        FROM itens_fiscais i
        JOIN documentos_fiscais d
            ON i.documento_id = d.id
        WHERE d.empresa_id = :empresa_id
    """)

    resultado = db.execute(
        query,
        {"empresa_id": empresa_id}
    ).fetchone()

    total_operacoes = resultado.total_operacoes if resultado else 0

    eficiencia = 0

    if total_operacoes > 0:
        eficiencia = impacto_total / total_operacoes

    return {
        "impacto_total_estimado": round(impacto_total, 2),
        "total_operacoes": total_operacoes,
        "indice_eficiencia_tributaria": round(eficiencia, 2)
    }
