from sqlalchemy import text
from app.services.analisador_distorcao_service import detectar_distorcoes


def calcular_complexidade_tributaria(db, empresa_id):
    query = text("""
        SELECT COUNT(DISTINCT i.ncm) AS total_ncms,
               COUNT(*) AS total_operacoes
        FROM itens_fiscais i
        JOIN documentos_fiscais d
            ON i.documento_id = d.id
        WHERE d.empresa_id = :empresa_id
    """)

    resultado = db.execute(
        query,
        {"empresa_id": empresa_id}
    ).fetchone()

    total_ncms = resultado.total_ncms if resultado else 0
    total_operacoes = resultado.total_operacoes if resultado else 0

    distorcoes = detectar_distorcoes(db, empresa_id)
    total_distorcoes = len(distorcoes)

    complexidade = (
        total_ncms * 0.4 +
        total_operacoes * 0.3 +
        total_distorcoes * 0.3
    )

    if complexidade > 50000:
        nivel = "alta"
    elif complexidade > 10000:
        nivel = "media"
    else:
        nivel = "baixa"

    return {
        "total_ncms": total_ncms,
        "total_operacoes": total_operacoes,
        "distorcoes_detectadas": total_distorcoes,
        "score_complexidade": round(complexidade, 2),
        "nivel_complexidade": nivel
    }
