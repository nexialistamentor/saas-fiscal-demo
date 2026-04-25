from sqlalchemy.orm import Session
from app.models import NotaFiscalItem, DocumentoFiscal
from app.services.tabela_normativa_service import buscar_mva
from app.services.analisador_impacto import calcular_impacto_st


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

        uf = (item.documento.uf_dest or item.documento.uf_emit or "PA").upper()
        regra = buscar_mva(db, uf, item.ncm)

        if not regra:
            continue

        analise = calcular_impacto_st(
            valor_produto=valor,
            st_pago=st_pago,
            mva=regra["mva"] / 100,
            aliquota=regra["aliquota_interna"]
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
