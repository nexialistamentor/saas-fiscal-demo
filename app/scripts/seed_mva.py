from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import TabelaMVA
from datetime import date


def seed_mva():

    db: Session = SessionLocal()

    registros = [

        {
            "estado": "PA",
            "ncm": "22021000",
            "mva": 40.0,
            "aliquota_interna": 0.18,
            "vigencia_inicio": date(2024, 1, 1)
        },

        {
            "estado": "PA",
            "ncm": "22029900",
            "mva": 35.0,
            "aliquota_interna": 0.18,
            "vigencia_inicio": date(2024, 1, 1)
        },

        {
            "estado": "PA",
            "ncm": "21069090",
            "mva": 42.0,
            "aliquota_interna": 0.18,
            "vigencia_inicio": date(2024, 1, 1)
        }

    ]

    for r in registros:

        existente = (
            db.query(TabelaMVA)
            .filter(TabelaMVA.estado == r["estado"])
            .filter(TabelaMVA.ncm == r["ncm"])
            .first()
        )

        if not existente:

            nova = TabelaMVA(
                estado=r["estado"],
                ncm=r["ncm"],
                mva=r["mva"],
                aliquota_interna=r["aliquota_interna"],
                vigencia_inicio=r["vigencia_inicio"]
            )

            db.add(nova)

    db.commit()
    db.close()


if __name__ == "__main__":
    seed_mva()
