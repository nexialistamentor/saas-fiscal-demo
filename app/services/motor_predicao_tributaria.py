from sqlalchemy.orm import Session

from app.models import DocumentoFiscal, NotaFiscalItem
from app.services.analisador_impacto import calcular_impacto_st
from app.services.fiscal_utils import resolver_aliquota_e_mva, uf_do_documento
from app.services.tabela_normativa_service import buscar_mva


def prever_impacto_st(db: Session, empresa_id: int):

    previsoes = []

    itens = (
        db.query(NotaFiscalItem)
        .join(NotaFiscalItem.documento)
        .filter(DocumentoFiscal.empresa_id == empresa_id)
        .all()
    )

    impacto_total = 0

    for item in itens:

        valor = item.valor_produto or 0
        st_pago = item.valor_st or 0

        if valor <= 0:
            continue

        doc = item.documento
        uf = uf_do_documento(doc)
        ncm = (item.ncm or "").strip()

        if uf:
            regra = buscar_mva(
                db,
                uf,
                item.ncm,
                data_referencia=doc.data_emissao if doc else None,
            )
            if not regra:
                continue
            mva_dec = regra["mva"] / 100
            aliquota_dec = regra["aliquota_interna"]
        else:
            res = resolver_aliquota_e_mva(
                db,
                "",
                ncm,
                data_referencia=doc.data_emissao if doc else None,
            )
            mva_dec = res["mva"]
            aliquota_dec = res["aliquota"]

        analise = calcular_impacto_st(
            valor_produto=valor,
            st_pago=st_pago,
            mva=mva_dec,
            aliquota=aliquota_dec,
        )

        impacto_total += analise["impacto"]

    if impacto_total != 0:

        previsoes.append({
            "tipo": "ALERTA_PREDITIVO_TRIBUTARIO",
            "impacto": "estrategico",
            "valor_estimado": impacto_total,
            "descricao": "Tendência de impacto tributário baseada no padrão atual de operações.",
            "recomendacao": "avaliar estratégia tributária preventiva."
        })

    return previsoes
