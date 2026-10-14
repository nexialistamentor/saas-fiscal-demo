"""AUD2.2A: UNKNOWN não se torna OBSERVED por números, hash ou backfill.

Sem schema futuro: histórico é inserido diretamente no modelo atual, sem
evidência original; observado percorre parser/writer do contrato AUD2.1.
Uma implementação futura deve estabelecer essa evidência no caminho real.
LEGACY_CONTRACT_CONFLICT: PASSO 26 exige ST derivado nas chaves observadas.
Não altera esse script nem o contrato AUD2.1.
"""
from datetime import date
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models
from app.services.detector_creditos_service import detectar_creditos
from app.services.tax_report_eligibility import projetar_tax_report_eligibility


# Reutiliza somente fixtures/helpers já ratificados. Nenhum teste anterior
# é executado ou modificado por este carregamento, nem se impõe nome de coluna.
_path = Path(__file__).with_name("test_credito_st_origem_fiscal_contract_red.py")
_spec = importlib.util.spec_from_file_location("_aud21_fixture_helpers", _path)
_aud21 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_aud21)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    models.DocumentoFiscal.__table__.create(engine)
    models.ItemFiscal.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _historico_desconhecido(db, *, hash_original=None):
    # Não inventa provenance, não dispõe dos bytes originais. Números iguais
    # aos do observado AUD2.1 não estabelecem a origem destes campos.
    documento = models.DocumentoFiscal(
        empresa_id=21, usuario_id=11, data_emissao=date(2026, 1, 15),
        uf_emit="PA", uf_dest="PA", tipo="entrada", mva_utilizada=40,
        conteudo_sha256=hash_original,
    )
    db.add(documento)
    db.flush()
    item = models.ItemFiscal(
        documento_id=documento.id, ncm="10019010", cfop="1102",
        quantidade=1, valor_produto=100, base_st=140, valor_st=7.20,
    )
    db.add(item)
    db.commit()
    return item.id


@pytest.mark.parametrize("hash_original", [None, "a" * 64],
                         ids=["sem-hash", "hash-presente"])
def test_historico_st_sem_origem_comprovada_nao_pode_gerar_credito_comercial(
    db, monkeypatch, hash_original,
):
    _aud21._norma(monkeypatch)
    _historico_desconhecido(db, hash_original=hash_original)
    assert detectar_creditos(db, 21) == [], "UNKNOWN_ORIGIN não autoriza ST pago"


def test_hash_sozinho_nao_prova_origem_dos_campos_st(db, monkeypatch):
    _aud21._norma(monkeypatch)
    _historico_desconhecido(db, hash_original="a" * 64)
    assert projetar_tax_report_eligibility(_aud21._resultado(db)) == {"eligible": False}


def test_avaliacao_nao_apaga_nem_reescreve_historico(db, monkeypatch):
    _aud21._norma(monkeypatch)
    item_id = _historico_desconhecido(db, hash_original="a" * 64)
    detectar_creditos(db, 21)
    db.flush()
    db.expire_all()
    item = db.get(models.ItemFiscal, item_id)
    assert item is not None
    assert (item.base_st, item.valor_st) == (140, 7.20)
    doc = db.get(models.DocumentoFiscal, item.documento_id)
    assert doc.conteudo_sha256 == "a" * 64


def test_novo_xml_observado_pode_participar_com_norma_autorizada(db, monkeypatch):
    _aud21._norma(monkeypatch)
    extraido, item = _aud21._persistir(db, monkeypatch, st=(140, 7.20))
    assert extraido["base_st"] == "140" and extraido["valor_st"] == "7.2"
    assert projetar_tax_report_eligibility(_aud21._resultado(db)) == {"eligible": True}
    assert detectar_creditos(db, 21)[0]["credito_estimado"] == pytest.approx(5.80)


def test_novo_xml_sem_st_nao_adquire_autoridade_por_enriquecimento(db, monkeypatch):
    _aud21._norma(monkeypatch)
    extraido, item = _aud21._persistir(db, monkeypatch)
    assert extraido["base_st"] is None and extraido["valor_st"] is None
    # Não exige remover estimativas analíticas ou escolher onde armazená-las.
    assert projetar_tax_report_eligibility(_aud21._resultado(db)) == {"eligible": False}


def test_reupload_observado_nao_reclassifica_historico_desconhecido(db, monkeypatch):
    _aud21._norma(monkeypatch)
    historico_id = _historico_desconhecido(db, hash_original="a" * 64)
    _aud21._persistir(db, monkeypatch, st=(140, 7.20))
    # Só o novo item com bytes observados pode contribuir. Não soma o histórico
    # numericamente idêntico nem exige backfill, UPDATE ou DELETE.
    creditos = detectar_creditos(db, 21)
    assert sum(c["credito_estimado"] for c in creditos) == pytest.approx(5.80)
    assert projetar_tax_report_eligibility(_aud21._resultado(db)) == {"eligible": True}
    db.expire_all()
    historico = db.get(models.ItemFiscal, historico_id)
    assert (historico.base_st, historico.valor_st) == (140, 7.20)
