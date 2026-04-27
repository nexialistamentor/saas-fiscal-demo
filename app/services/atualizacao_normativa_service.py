from sqlalchemy.orm import Session
from app.models import TabelaMVA
from datetime import date


def atualizar_mva(
    db: Session,
    estado: str,
    ncm: str,
    nova_mva: float,
    aliquota: float,
    fonte_legal: str | None = None,
    url_fonte: str | None = None,
    nivel_confianca_fonte: str = "oficial",
    importado_por: str | None = None,
):

    registro = (
        db.query(TabelaMVA)
        .filter(TabelaMVA.estado == estado)
        .filter(TabelaMVA.ncm == ncm)
        .first()
    )

    if registro:

        registro.mva = nova_mva
        registro.aliquota_interna = aliquota
        registro.nivel_confianca_fonte = nivel_confianca_fonte
        if fonte_legal is not None:
            registro.fonte_legal = fonte_legal
        if url_fonte is not None:
            registro.url_fonte = url_fonte
        if importado_por is not None:
            registro.importado_por = importado_por

    else:

        novo = TabelaMVA(
            estado=estado,
            ncm=ncm,
            mva=nova_mva,
            aliquota_interna=aliquota,
            vigencia_inicio=date.today(),
            fonte_legal=fonte_legal,
            url_fonte=url_fonte,
            nivel_confianca_fonte=nivel_confianca_fonte,
            importado_por=importado_por,
        )

        db.add(novo)

    db.commit()
