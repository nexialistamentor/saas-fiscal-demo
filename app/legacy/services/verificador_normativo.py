from sqlalchemy.orm import Session
from app.models import TabelaMVA


def verificar_divergencias(db: Session, estado: str, dados):

    divergencias = []

    for r in dados:

        registro = (
            db.query(TabelaMVA)
            .filter(TabelaMVA.estado == estado)
            .filter(TabelaMVA.ncm == r["ncm"])
            .first()
        )

        if not registro:
            divergencias.append({
                "ncm": r["ncm"],
                "tipo": "REGRA_NOVA",
                "mva_nova": r["mva"]
            })
            continue

        if registro.mva != r["mva"]:

            divergencias.append({
                "ncm": r["ncm"],
                "tipo": "MVA_ALTERADA",
                "mva_atual": registro.mva,
                "mva_nova": r["mva"]
            })

    return divergencias
