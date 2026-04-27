from app.database import SessionLocal
from app.legacy.data.mvas_pa import MVA_PA
from app.legacy.services.monitor_normativo import monitorar_atualizacoes


def executar_sincronizacao():

    db = SessionLocal()

    divergencias = monitorar_atualizacoes(db, "PA", MVA_PA)

    for d in divergencias:
        print(d)

    db.close()


if __name__ == "__main__":
    executar_sincronizacao()
