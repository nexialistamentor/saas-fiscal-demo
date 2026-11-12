"""Fase 1/PA: teste read-only da regra real restaurada em test.db.

Nao cria seed, nao insere nem reescreve valores e nao usa mock de norma.
"""
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import sqlite3

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.services.jurisdicao_normativa_service import selecionar_norma_por_jurisdicao
from app.services.fiscal_utils import resolver_aliquota_e_mva


_DB = Path(__file__).resolve().parents[1] / "test.db"
_NCM_PA = "22021000"
_DATA = date(2024, 1, 1)


@pytest.fixture(scope="module")
def db():
    assert _DB.is_file(), "Dado não encontrado: test.db local exigido pela missão"
    # URI de SQLite somente leitura: nunca gerar ou modificar o banco real.
    def _abrir_somente_leitura():
        return sqlite3.connect(f"{_DB.as_uri()}?mode=ro", uri=True)

    engine = create_engine("sqlite://", creator=_abrir_somente_leitura, poolclass=NullPool)
    try:
        with Session(engine) as sessao:
            yield sessao
    finally:
        engine.dispose()


def test_pa_regra_real_cadastrada_sem_fonte_identificada(db):
    reg = db.connection().exec_driver_sql(
        "SELECT estado, ncm, mva, aliquota_interna, vigencia_inicio, "
        "vigencia_fim, nivel_confianca_fonte, fonte_legal, url_fonte "
        "FROM tabela_mva WHERE estado = ? AND ncm = ?",
        ("PA", _NCM_PA),
    ).all()
    assert len(reg) == 1
    row = reg[0]
    assert (row.estado, row.ncm, row.mva, row.aliquota_interna) == (
        "PA", "22021000", 40.0, 0.18,
    )
    assert row.vigencia_inicio == "2024-01-01"
    assert row.vigencia_fim is None
    assert row.nivel_confianca_fonte == "oficial"
    assert row.fonte_legal is None and row.url_fonte is None


def test_pa_encontrada_mas_autoridade_nao_comprovada(db):
    resposta = selecionar_norma_por_jurisdicao(
        db=db, empresa=SimpleNamespace(uf="PA", municipio=None),
        ncm=_NCM_PA, data_referencia=_DATA,
    )
    assert resposta["regra_cadastrada"] is True
    assert resposta["estado"] == "REGRA_CADASTRADA_AUTORIDADE_NAO_COMPROVADA"
    assert resposta["autoridade_normativa_verificada"] is False
    assert resposta["calculo_autorizado"] is False
    assert resposta["norma_resolvida"] is None
    assert resposta["motivo"] == "fonte_legal_ausente"
    assert resposta["aviso"] == "cobertura normativa não comprovada"
    assert resposta["scope"] == {
        "jurisdiction": "BR-PA", "sphere": "estadual",
        "territory": {"uf": "PA", "municipio": None},
        "source_id": None, "use": "icms_st_mva",
    }
    assert resposta["domain"] == "ICMS_ST_MVA"
    assert resposta["policy_version"] is None and resposta["policy_hash"] is None
    assert resposta["declared_material_applicability"] == {
        "kind": "vigencia_regra_cadastrada", "from": "2024-01-01", "until": None,
    }


def test_resolvedor_existente_permanece_fail_closed_para_pa(db):
    resultado = resolver_aliquota_e_mva(db, "PA", _NCM_PA, data_referencia=_DATA)
    assert resultado["calculo_autorizado"] is False
    assert resultado["bloqueio_normativo"] is True
    assert resultado["motivo_bloqueio"] == "fonte_normativa_invalida"


def test_uf_sem_regra_nao_recebe_norma_de_pa(db):
    # A outra UF e usada somente como controlo negativo, sem seed nem norma.
    assert db.connection().exec_driver_sql(
        "SELECT count(*) FROM tabela_mva WHERE estado = ? AND ncm = ?",
        ("SP", _NCM_PA),
    ).scalar_one() == 0
    resposta = selecionar_norma_por_jurisdicao(
        db=db, empresa=SimpleNamespace(uf="SP", municipio=None),
        ncm=_NCM_PA, data_referencia=_DATA,
    )
    assert resposta["estado"] == "COBERTURA_NORMATIVA_NAO_COMPROVADA"
    assert resposta["regra_cadastrada"] is False
    assert resposta["autoridade_normativa_verificada"] is False
    assert resposta["calculo_autorizado"] is False
    assert resposta["norma_resolvida"] is None
    assert resposta["registro_mva_id"] is None
    assert resposta["scope"]["jurisdiction"] == "BR-SP"
    assert resposta["scope"]["source_id"] is None
    assert resposta["aviso"] == "cobertura normativa não comprovada"


def test_pa_fora_da_vigencia_nao_e_promovida(db):
    resposta = selecionar_norma_por_jurisdicao(
        db=db, empresa=SimpleNamespace(uf="PA"),
        ncm=_NCM_PA, data_referencia=date(2023, 12, 31),
    )
    assert resposta["regra_cadastrada"] is False
    assert resposta["autoridade_normativa_verificada"] is False
    assert resposta["norma_resolvida"] is None


def test_chave_sem_data_explicitamente_bloqueada(db):
    resposta = selecionar_norma_por_jurisdicao(
        db=db, empresa=SimpleNamespace(uf="PA"),
        ncm=_NCM_PA, data_referencia=None,
    )
    assert resposta["estado"] == "COBERTURA_NORMATIVA_NAO_COMPROVADA"
    assert resposta["calculo_autorizado"] is False
    assert resposta["norma_resolvida"] is None
