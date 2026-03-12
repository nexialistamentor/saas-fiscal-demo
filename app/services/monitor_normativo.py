from sqlalchemy.orm import Session
from app.services.verificador_normativo import verificar_divergencias
from app.services.atualizacao_normativa_service import atualizar_mva


def monitorar_atualizacoes(db: Session, estado: str, dados):

    divergencias = verificar_divergencias(db, estado, dados)

    for d in divergencias:

        if d["tipo"] == "REGRA_NOVA":

            atualizar_mva(
                db=db,
                estado=estado,
                ncm=d["ncm"],
                nova_mva=d.get("mva_nova", 0),
                aliquota=0.18
            )

        if d["tipo"] == "MVA_ALTERADA":

            atualizar_mva(
                db=db,
                estado=estado,
                ncm=d["ncm"],
                nova_mva=d["mva_nova"],
                aliquota=0.18
            )

    return divergencias
