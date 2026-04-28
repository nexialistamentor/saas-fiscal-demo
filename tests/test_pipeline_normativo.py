"""Testes do pipeline normativo L2 (importar_regras / verificar_divergencias)."""

from datetime import date

from app.database import SessionLocal
from app.models import TabelaMVA
from app.services.pipeline_normativo import RegraNormativa, importar_regras, verificar_divergencias

EST = "P2"
NCM_NOVO = "12345678"
NCM_OFICIAL = "87654321"
NCM_DIV = "11223344"


def _cleanup_p2(db):
    db.query(TabelaMVA).filter(TabelaMVA.estado == EST).delete()
    db.commit()


def _regra(
    ncm: str,
    mva: float,
    *,
    vigencia_inicio: date = date(2020, 1, 1),
    nivel: str = "convenio_base",
) -> RegraNormativa:
    return RegraNormativa(
        estado=EST,
        ncm=ncm,
        mva=mva,
        aliquota_interna=0.18,
        vigencia_inicio=vigencia_inicio,
        vigencia_fim=None,
        fonte_legal="pytest fixture pipeline_normativo",
        url_fonte="http://pytest.local/regra",
        nivel_confianca=nivel,  # type: ignore[arg-type]
        importado_por="pytest",
    )


def test_importar_novo_insere_na_bd():
    db = SessionLocal()
    try:
        _cleanup_p2(db)
        r = _regra(NCM_NOVO, 15.5)
        res = importar_regras(db, [r], dry_run=False)
        assert res.inseridos == 1
        assert res.atualizados == 0
        assert res.ignorados == 0
        assert res.erros == []
        row = (
            db.query(TabelaMVA)
            .filter(TabelaMVA.estado == EST, TabelaMVA.ncm == NCM_NOVO)
            .first()
        )
        assert row is not None
        assert row.mva == 15.5
        assert row.nivel_confianca_fonte == "convenio_base"
    finally:
        _cleanup_p2(db)
        db.close()


def test_nao_sobrescreve_oficial():
    db = SessionLocal()
    try:
        _cleanup_p2(db)
        db.add(
            TabelaMVA(
                estado=EST,
                ncm=NCM_OFICIAL,
                mva=99.0,
                aliquota_interna=0.17,
                vigencia_inicio=date(2019, 1, 1),
                vigencia_fim=None,
                nivel_confianca_fonte="oficial",
                fonte_legal="SEFAZ",
            )
        )
        db.commit()
        r = _regra(NCM_OFICIAL, 50.0, vigencia_inicio=date(2019, 1, 1))
        res = importar_regras(db, [r], dry_run=False)
        assert res.ignorados == 1
        assert res.atualizados == 0
        assert res.inseridos == 0
        row = (
            db.query(TabelaMVA)
            .filter(TabelaMVA.estado == EST, TabelaMVA.ncm == NCM_OFICIAL)
            .first()
        )
        assert row is not None
        assert row.mva == 99.0
    finally:
        _cleanup_p2(db)
        db.close()


def test_dry_run_nao_grava():
    db = SessionLocal()
    try:
        _cleanup_p2(db)
        r = _regra(NCM_NOVO, 20.0)
        res = importar_regras(db, [r], dry_run=True)
        assert res.inseridos == 1
        assert res.erros == []
        row = (
            db.query(TabelaMVA)
            .filter(TabelaMVA.estado == EST, TabelaMVA.ncm == NCM_NOVO)
            .first()
        )
        assert row is None
    finally:
        _cleanup_p2(db)
        db.close()


def test_verificar_divergencias_mva():
    db = SessionLocal()
    try:
        _cleanup_p2(db)
        db.add(
            TabelaMVA(
                estado=EST,
                ncm=NCM_DIV,
                mva=10.0,
                aliquota_interna=0.18,
                vigencia_inicio=date(2018, 10, 16),
                vigencia_fim=None,
                nivel_confianca_fonte="convenio_base",
                fonte_legal="CSV",
            )
        )
        db.commit()
        r = _regra(NCM_DIV, 25.0, vigencia_inicio=date(2018, 10, 16))
        divs = verificar_divergencias(db, [r])
        assert len(divs) == 1
        assert divs[0]["tipo"] == "MVA_DIVERGENTE"
        assert divs[0]["mva_esperado"] == 25.0
        assert divs[0]["mva_bd"] == 10.0
    finally:
        _cleanup_p2(db)
        db.close()
