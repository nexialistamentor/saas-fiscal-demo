"""TabelaPMPF: buscar_pmpf com prioridade marca exacta > demais marcas, fallback mva."""

from datetime import date

import pytest

from app.database import SessionLocal
from app.models import TabelaMVA, TabelaPMPF
from app.services.tax_engines.base_tax_engine import TempoNormativoAusenteError
from app.services.tabela_normativa_service import (
    buscar_mva,
    buscar_pmpf,
    resolver_base_calculo_st,
    verificar_cobertura_normativa_st,
)

_REF = date(2026, 1, 1)


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
    r = buscar_pmpf(db, "XT", "22021000", marca="marca-x", data_referencia=_REF)
    db.close()
    assert r["pmpf_reais"] == 7.0
    assert r["marca"] == "MARCA-X"


def test_fallback_demais_marcas():
    db = SessionLocal()
    _add(db, "DEMAIS MARCAS", None, 5.0)
    db.commit()
    r = buscar_pmpf(db, "XT", "22021000", marca="OUTRA", data_referencia=_REF)
    db.close()
    assert r["pmpf_reais"] == 5.0


def test_sem_pmpf_retorna_none():
    db = SessionLocal()
    r = buscar_pmpf(db, "XT", "22021000", data_referencia=_REF)
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
        r = resolver_base_calculo_st(
            db, "PA", "22021000", valor_produto=10.0, data_referencia=_REF
        )
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


def test_buscar_pmpf_sem_data_referencia_levanta_erro():
    db = SessionLocal()
    try:
        with pytest.raises(TempoNormativoAusenteError):
            buscar_pmpf(db, "XT", "22021000")
    finally:
        db.close()


def test_buscar_mva_sem_data_referencia_levanta_erro():
    db = SessionLocal()
    try:
        with pytest.raises(TempoNormativoAusenteError):
            buscar_mva(db, "PA", "22021000")
    finally:
        db.close()


def test_resolver_base_calculo_st_sem_data_referencia_levanta_erro():
    db = SessionLocal()
    try:
        with pytest.raises(TempoNormativoAusenteError):
            resolver_base_calculo_st(db, "PA", "22021000", valor_produto=10.0)
    finally:
        db.close()


def test_cobertura_st_vigente_retorna_vigente():
    db = SessionLocal()
    try:
        db.query(TabelaMVA).filter(TabelaMVA.estado == "XT", TabelaMVA.ncm == "11112222").delete()
        db.commit()
        db.add(TabelaMVA(
            estado="XT", ncm="11112222", mva=30.0, aliquota_interna=0.18,
            vigencia_inicio=date(2024, 1, 1), vigencia_fim=None,
            nivel_confianca_fonte="oficial", fonte_legal="Teste",
        ))
        db.commit()
        r = verificar_cobertura_normativa_st(db, "XT", "11112222", _REF)
        assert r == "vigente"
    finally:
        db.query(TabelaMVA).filter(TabelaMVA.estado == "XT", TabelaMVA.ncm == "11112222").delete()
        db.commit()
        db.close()


def test_cobertura_st_sem_regra_retorna_sem_regra():
    db = SessionLocal()
    try:
        r = verificar_cobertura_normativa_st(db, "XT", "99998888", _REF)
        assert r == "sem_regra"
    finally:
        db.close()


def test_cobertura_st_expirada_sem_substituto_retorna_bloqueio():
    db = SessionLocal()
    try:
        db.query(TabelaMVA).filter(TabelaMVA.estado == "XT", TabelaMVA.ncm == "33334444").delete()
        db.commit()
        db.add(TabelaMVA(
            estado="XT", ncm="33334444", mva=30.0, aliquota_interna=0.18,
            vigencia_inicio=date(2020, 1, 1), vigencia_fim=date(2025, 12, 31),
            nivel_confianca_fonte="oficial", fonte_legal="Teste",
        ))
        db.commit()
        r = verificar_cobertura_normativa_st(db, "XT", "33334444", _REF)
        assert r == "expirada_sem_substituto"
    finally:
        db.query(TabelaMVA).filter(TabelaMVA.estado == "XT", TabelaMVA.ncm == "33334444").delete()
        db.commit()
        db.close()


def test_resolver_base_calculo_st_bloqueia_cobertura_expirada_sem_substituto():
    db = SessionLocal()
    try:
        db.query(TabelaMVA).filter(TabelaMVA.estado == "XT", TabelaMVA.ncm == "55556666").delete()
        db.commit()
        db.add(TabelaMVA(
            estado="XT", ncm="55556666", mva=30.0, aliquota_interna=0.18,
            vigencia_inicio=date(2020, 1, 1), vigencia_fim=date(2025, 12, 31),
            nivel_confianca_fonte="oficial", fonte_legal="Teste",
        ))
        db.commit()
        r = resolver_base_calculo_st(db, "XT", "55556666", valor_produto=100.0, data_referencia=_REF)
        assert r["metodo"] == "bloqueado_cobertura_expirada"
        assert r["base_calculo"] is None
        assert r["aliquota_interna"] is None
        assert "expirou sem substituto" in r["aviso"]
    finally:
        db.query(TabelaMVA).filter(TabelaMVA.estado == "XT", TabelaMVA.ncm == "55556666").delete()
        db.commit()
        db.close()


def test_resolver_base_calculo_st_nao_bloqueia_quando_ha_sucessora_vigente():
    db = SessionLocal()
    try:
        db.query(TabelaMVA).filter(TabelaMVA.estado == "XT", TabelaMVA.ncm == "77778888").delete()
        db.commit()
        db.add(TabelaMVA(
            estado="XT", ncm="77778888", mva=30.0, aliquota_interna=0.18,
            vigencia_inicio=date(2020, 1, 1), vigencia_fim=date(2025, 12, 31),
            nivel_confianca_fonte="oficial", fonte_legal="Teste antiga",
        ))
        db.add(TabelaMVA(
            estado="XT", ncm="77778888", mva=35.0, aliquota_interna=0.18,
            vigencia_inicio=date(2026, 1, 1), vigencia_fim=None,
            nivel_confianca_fonte="oficial", fonte_legal="Teste sucessora",
        ))
        db.commit()
        r = resolver_base_calculo_st(db, "XT", "77778888", valor_produto=100.0, data_referencia=_REF)
        assert r["metodo"] != "bloqueado_cobertura_expirada"
        assert r["base_calculo"] is not None
    finally:
        db.query(TabelaMVA).filter(TabelaMVA.estado == "XT", TabelaMVA.ncm == "77778888").delete()
        db.commit()
        db.close()


def test_resolver_base_calculo_st_pmpf_vigente_tem_prioridade_sobre_mva_expirada():
    db = SessionLocal()
    try:
        db.query(TabelaPMPF).filter(TabelaPMPF.estado == "XT", TabelaPMPF.ncm == "22021000").delete()
        db.query(TabelaMVA).filter(TabelaMVA.estado == "XT", TabelaMVA.ncm == "22021000").delete()
        db.commit()
        db.add(TabelaMVA(
            estado="XT", ncm="22021000", mva=30.0, aliquota_interna=0.18,
            vigencia_inicio=date(2020, 1, 1), vigencia_fim=date(2025, 12, 31),
            nivel_confianca_fonte="oficial", fonte_legal="MVA expirada",
        ))
        db.commit()
        _add(db, "MARCA-Y", None, 9.0)
        db.commit()
        r = resolver_base_calculo_st(db, "XT", "22021000", valor_produto=100.0, marca="MARCA-Y", data_referencia=_REF)
        assert r["metodo"] == "pmpf"
        assert r["base_calculo"] == 9.0
    finally:
        db.query(TabelaPMPF).filter(TabelaPMPF.estado == "XT", TabelaPMPF.ncm == "22021000").delete()
        db.query(TabelaMVA).filter(TabelaMVA.estado == "XT", TabelaMVA.ncm == "22021000").delete()
        db.commit()
        db.close()
