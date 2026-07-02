"""Garante que buscar_mva prefere 'oficial' sobre 'convenio_base'."""

from datetime import date

from app.database import SessionLocal
from app.models import TabelaMVA
from app.services.tabela_normativa_service import buscar_mva


def test_oficial_prevalece_sobre_convenio_base():
    db = SessionLocal()
    try:
        db.query(TabelaMVA).filter(
            TabelaMVA.estado == "XT", TabelaMVA.ncm == "99999999"
        ).delete()
        db.commit()

        db.add(
            TabelaMVA(
                estado="XT",
                ncm="99999999",
                mva=40.0,
                aliquota_interna=0.18,
                vigencia_inicio=date(2018, 1, 1),
                nivel_confianca_fonte="convenio_base",
            )
        )
        db.add(
            TabelaMVA(
                estado="XT",
                ncm="99999999",
                mva=35.0,
                aliquota_interna=0.17,
                vigencia_inicio=date(2022, 1, 1),
                nivel_confianca_fonte="oficial",
            )
        )
        db.commit()

        resultado = buscar_mva(db, "XT", "99999999", data_referencia=date(2026, 1, 1))
        assert resultado is not None
        assert resultado["nivel_confianca_fonte"] == "oficial"
        assert resultado["mva"] == 35.0
    finally:
        db.query(TabelaMVA).filter(
            TabelaMVA.estado == "XT", TabelaMVA.ncm == "99999999"
        ).delete()
        db.commit()
        db.close()
