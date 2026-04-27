from sqlalchemy.orm import Session
from app.services.atualizacao_normativa_service import atualizar_mva


def importar_mvas(db: Session, dados):

    for r in dados:

        atualizar_mva(
            db=db,
            estado=r["estado"],
            ncm=r["ncm"],
            nova_mva=r["mva"],
            aliquota=r["aliquota"]
        )
