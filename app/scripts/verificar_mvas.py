from app.database import SessionLocal
from app.data.mvas_pa import MVA_PA
from app.services.verificador_normativo import verificar_divergencias


def executar_verificacao():

    db = SessionLocal()

    divergencias = verificar_divergencias(db, "PA", MVA_PA)

    for d in divergencias:
        print(d)

    db.close()


if __name__ == "__main__":
    executar_verificacao()
