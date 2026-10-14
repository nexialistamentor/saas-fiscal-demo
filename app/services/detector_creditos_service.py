from sqlalchemy.orm import Session
from sqlalchemy import Date, text

from app.services.fiscal_utils import resolver_aliquota_e_mva, uf_do_documento


def detectar_creditos(db: Session, empresa_id: int):

    query = text("""
        SELECT
            i.ncm,
            d.uf_dest,
            d.uf_emit,
            d.data_emissao,
            SUM(i.valor_st) as st_pago,
            SUM(i.base_st) as base_st
        FROM itens_fiscais i
        INNER JOIN documentos_fiscais d ON i.documento_id = d.id
        WHERE d.empresa_id = :empresa_id
          AND i.st_observado_xml IS TRUE
        GROUP BY i.ncm, d.uf_dest, d.uf_emit, d.data_emissao
    """).columns(data_emissao=Date)

    resultado = db.execute(query, {"empresa_id": empresa_id}).fetchall()

    creditos = []

    for row in resultado:
        ncm = row.ncm
        st_pago = float(row.st_pago or 0)
        base_st = float(row.base_st or 0)

        res = resolver_aliquota_e_mva(
            db, uf_do_documento(row), ncm, data_referencia=row.data_emissao,
        )
        if not res.get("calculo_autorizado", False) or res.get("calculo_parcial", False):
            continue
        aliquota = res["aliquota"]
        st_correta = base_st * aliquota
        credito = st_pago - st_correta

        if credito > 0:
            creditos.append({
                "ncm": ncm,
                "credito_estimado": credito,
                "aliquota_fonte": res["fonte"],
            })

    return creditos
