"""resolver_aliquota_e_mva com nivel convenio_base_sem_aliquota."""

from datetime import date

from app.database import SessionLocal
from app.models import TabelaMVA
from app.services.fiscal_utils import resolver_aliquota_e_mva


def test_convenio_base_sem_aliquota_usa_fallback_e_estimativa():
    db = SessionLocal()
    try:
        db.query(TabelaMVA).filter(
            TabelaMVA.estado == "XS", TabelaMVA.ncm == "22021000"
        ).delete()
        db.commit()

        db.add(
            TabelaMVA(
                estado="XS",
                ncm="22021000",
                mva=40.0,
                aliquota_interna=0.0,
                vigencia_inicio=date(2018, 10, 16),
                vigencia_fim=None,
                nivel_confianca_fonte="convenio_base_sem_aliquota",
                fonte_legal="Convênio 142/2018 Anexo II (MVA)",
            )
        )
        db.commit()

        res = resolver_aliquota_e_mva(db, "XS", "22021000")
        assert res["fonte"] == "tabela"
        assert res["confianca"] == "estimativa"
        assert res["mva"] == 0.40
        assert res["aliquota"] == 0.18
        assert res["aviso"] is not None
        assert "RICMS" in res["aviso"]
    finally:
        db.query(TabelaMVA).filter(
            TabelaMVA.estado == "XS", TabelaMVA.ncm == "22021000"
        ).delete()
        db.commit()
        db.close()
