from app.database import SessionLocal
from app.legacy.services.importador_normativo import importar_mvas
from app.legacy.data.mvas_pa import MVA_PA


def executar_importacao():

    db = SessionLocal()

    importar_mvas(db, MVA_PA)

    db.close()


if __name__ == "__main__":
    executar_importacao()
