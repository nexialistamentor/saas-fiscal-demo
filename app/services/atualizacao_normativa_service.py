from sqlalchemy.orm import Session
from app.models import TabelaMVA
from datetime import date


def atualizar_mva(db: Session, estado: str, ncm: str, nova_mva: float, aliquota: float):

    registro = (
        db.query(TabelaMVA)
        .filter(TabelaMVA.estado == estado)
        .filter(TabelaMVA.ncm == ncm)
        .first()
    )

    if registro:

        registro.mva = nova_mva
        registro.aliquota_interna = aliquota

    else:

        novo = TabelaMVA(
            estado=estado,
            ncm=ncm,
            mva=nova_mva,
            aliquota_interna=aliquota,
            vigencia_inicio=date.today()
        )

        db.add(novo)

    db.commit()
