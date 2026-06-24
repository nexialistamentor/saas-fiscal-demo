from sqlalchemy import text

from app.services.fiscal_utils import resolver_aliquota_e_mva


def calcular_potencial_recuperacao(db, empresa_id):

    query = text("""
        SELECT
            i.ncm,
            SUM(i.valor_st) AS st_pago,
            SUM(i.base_st) AS base_st,
            COUNT(*) AS volume_operacoes
        FROM itens_fiscais i
        INNER JOIN documentos_fiscais d ON i.documento_id = d.id
        WHERE d.empresa_id = :empresa_id
        GROUP BY i.ncm
    """)

    resultado = db.execute(query, {"empresa_id": empresa_id}).fetchall()

    oportunidades = []

    for row in resultado:

        ncm = row.ncm
        st_pago = float(row.st_pago or 0)
        base_st = float(row.base_st or 0)
        volume = int(row.volume_operacoes or 0)

        if base_st == 0:
            continue

        res = resolver_aliquota_e_mva(db, "", ncm)
        if not res.get("calculo_autorizado", True) or res.get("calculo_parcial", False):
            continue
        aliquota = res["aliquota"]

        st_devida = base_st * aliquota

        potencial_recuperacao = max(0.0, st_pago - st_devida)

        if potencial_recuperacao == 0:
            continue

        score_oportunidade = potencial_recuperacao * volume

        oportunidades.append({
            "ncm": ncm,
            "potencial_recuperacao": round(potencial_recuperacao, 2),
            "score_oportunidade": round(score_oportunidade, 2),
            "volume_operacoes": volume,
            "aliquota_fonte": res["fonte"],
        })

    oportunidades.sort(
        key=lambda x: x["score_oportunidade"],
        reverse=True
    )

    return oportunidades
