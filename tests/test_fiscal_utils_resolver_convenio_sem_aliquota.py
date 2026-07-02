"""resolver_aliquota_e_mva com nivel convenio_base_sem_aliquota."""

from datetime import date

from app.database import SessionLocal
from app.models import TabelaMVA
from app.services.fiscal_utils import resolver_aliquota_e_mva


def test_convenio_base_sem_aliquota_usa_fallback_e_estimativa():
    db = SessionLocal()
    try:
        db.query(TabelaMVA).filter(
            TabelaMVA.estado == "PA", TabelaMVA.ncm == "99999998"
        ).delete()
        db.commit()

        db.add(
            TabelaMVA(
                estado="PA",
                ncm="99999998",
                mva=40.0,
                aliquota_interna=0.0,
                vigencia_inicio=date(2018, 10, 16),
                vigencia_fim=None,
                nivel_confianca_fonte="convenio_base_sem_aliquota",
                fonte_legal="Convênio 142/2018 Anexo II (MVA)",
            )
        )
        db.commit()

        res = resolver_aliquota_e_mva(db, "PA", "99999998", data_referencia=date(2026, 1, 1))
        assert res["fonte"] == "tabela"
        assert res["confianca"] == "estimativa"
        assert res["mva"] == 0.40
        assert res["aliquota"] == 0.18
        assert res["aviso"] is not None
        assert "RICMS" in res["aviso"]
    finally:
        db.query(TabelaMVA).filter(
            TabelaMVA.estado == "PA", TabelaMVA.ncm == "99999998"
        ).delete()
        db.commit()
        db.close()
