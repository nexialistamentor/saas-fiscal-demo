"""TabelaPMPF: buscar_pmpf com prioridade marca exacta > demais marcas, fallback mva."""

from datetime import date

import pytest

from app.database import SessionLocal
from app.models import TabelaMVA, TabelaPMPF
from app.services.tabela_normativa_service import buscar_pmpf, resolver_base_calculo_st


@pytest.fixture(autouse=True)
def limpar_pmpf():
    db = SessionLocal()
    db.query(TabelaPMPF).filter(TabelaPMPF.estado == "XT").delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(TabelaPMPF).filter(TabelaPMPF.estado == "XT").delete()
    db.commit()
    db.close()


def _add(db, marca, embalagem_ml, pmpf):
    db.add(
        TabelaPMPF(
            estado="XT",
            ncm="22021000",
            marca=marca,
            embalagem_ml=embalagem_ml,
            pmpf_reais=pmpf,
            aliquota_interna=0.18,
            vigencia_inicio=date(2024, 1, 1),
            nivel_confianca_fonte="oficial",
            fonte_legal="Teste",
        )
    )


def test_marca_exacta_prevalece():
    db = SessionLocal()
    _add(db, "DEMAIS MARCAS", None, 5.0)
    _add(db, "MARCA-X", None, 7.0)
    db.commit()
    r = buscar_pmpf(db, "XT", "22021000", marca="marca-x")
    db.close()
    assert r["pmpf_reais"] == 7.0
    assert r["marca"] == "MARCA-X"


def test_fallback_demais_marcas():
    db = SessionLocal()
    _add(db, "DEMAIS MARCAS", None, 5.0)
    db.commit()
    r = buscar_pmpf(db, "XT", "22021000", marca="OUTRA")
    db.close()
    assert r["pmpf_reais"] == 5.0


def test_sem_pmpf_retorna_none():
    db = SessionLocal()
    r = buscar_pmpf(db, "XT", "22021000")
    db.close()
    assert r is None


def test_resolver_fallback_para_iva_st_quando_sem_pmpf():
    """Sem PMPF para o par UF+NCM: usa IVA-ST via MVA (requer linha MVA na BD)."""
    db = SessionLocal()
    try:
        db.query(TabelaPMPF).filter(
            TabelaPMPF.estado == "PA", TabelaPMPF.ncm == "22021000"
        ).delete()
        db.query(TabelaMVA).filter(
            TabelaMVA.estado == "PA", TabelaMVA.ncm == "22021000"
        ).delete()
        db.commit()
        db.add(
            TabelaMVA(
                estado="PA",
                ncm="22021000",
                mva=30.0,
                aliquota_interna=0.18,
                vigencia_inicio=date(2020, 1, 1),
                vigencia_fim=None,
                nivel_confianca_fonte="oficial",
                fonte_legal="pytest resolver_base_calculo_st",
            )
        )
        db.commit()
        r = resolver_base_calculo_st(db, "PA", "22021000", valor_produto=10.0)
        assert r["metodo"] == "iva_st"
        assert r["base_calculo"] is not None
    finally:
        db.query(TabelaPMPF).filter(
            TabelaPMPF.estado == "PA", TabelaPMPF.ncm == "22021000"
        ).delete()
        db.query(TabelaMVA).filter(
            TabelaMVA.estado == "PA", TabelaMVA.ncm == "22021000"
        ).delete()
        db.commit()
        db.close()
