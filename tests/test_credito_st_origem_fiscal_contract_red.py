"""AUD2.1: origem autorizada é adicional ao gate normativo, sem impor schema.

Fixtures XML sintéticas não afirmam autenticidade SEFAZ. Os mesmos números
observados e derivados devem ter decisões diferentes pela origem, nunca por
heurística financeira. Usa parser, enriquecedor, writer e detector reais.
Somente lookup normativo/legado é controlado; não simula a decisão do detector.
"""
from datetime import date
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models, xml_service
from app.services import fiscal_utils
from app.services.detector_creditos_service import detectar_creditos
from app.services.insights_engine import InsightEngine
from app.services.resultado_empresarial_service import compor_resultado_empresarial
from app.services.resultado_provenance_service import (
    fingerprint_resultado_json, selar_resultado_nao_mei,
    verificar_resultado_persistido,
)
from app.services.tax_report_eligibility import projetar_tax_report_eligibility


def _xml(st=None):
    campos = "" if st is None else (
        f"<vBCST>{st[0]}</vBCST><vICMSST>{st[1]}</vICMSST>"
    )
    return f'''<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
      <infNFe><ide><nNF>1</nNF><tpNF>0</tpNF>
        <dhEmi>2026-01-15T12:00:00-03:00</dhEmi></ide>
      <emit><CNPJ>12345678000195</CNPJ><enderEmit><UF>PA</UF></enderEmit></emit>
      <dest><enderDest><UF>PA</UF></enderDest></dest>
      <det nItem="1"><prod><NCM>10019010</NCM><CFOP>1102</CFOP>
        <qCom>1</qCom><vProd>100</vProd></prod>
        <imposto><ICMS><ICMS10>{campos}</ICMS10></ICMS></imposto></det>
      <total><ICMSTot><vNF>100</vNF></ICMSTot></total>
      </infNFe></NFe>'''.encode()


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    # Não cria schema de produção nem executa migrations; duas tabelas efémeras.
    models.DocumentoFiscal.__table__.create(engine)
    models.ItemFiscal.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _norma(monkeypatch, *, aliquota=0.01, nivel="oficial", fonte="Norma fixture", inicio=date(2026, 1, 1)):
    monkeypatch.setattr(fiscal_utils, "uf_tem_dados_mva", lambda db, uf: True)
    monkeypatch.setattr(fiscal_utils, "buscar_mva", lambda *a, **kw: {
        "mva": 40.0, "aliquota_interna": aliquota,
        "fonte_legal": fonte, "nivel_confianca_fonte": nivel,
        "vigencia_inicio": inicio, "vigencia_fim": None,
    })


def _persistir(db, monkeypatch, *, st=None, mva=40.0):
    original = _xml(st)
    dados = xml_service.ler_xml_unico(xml_bytes=original)
    extraido = dict(dados["itens"][0])
    monkeypatch.setattr(xml_service, "carregar_mva", lambda *a, **kw: mva)
    xml_service.enriquecer_st_se_necessario(dados, {})
    documento = xml_service.persistir_documento_fiscal(
        db, SimpleNamespace(id=11), SimpleNamespace(id=21), dados,
        conteudo_sha256=hashlib.sha256(original).hexdigest(),
    )
    db.expire_all()
    item = db.scalar(select(models.ItemFiscal).where(
        models.ItemFiscal.documento_id == documento.id,
    ))
    return extraido, item


def _resultado(db):
    # Conversor real, sem reimplementar filtro ou fórmula financeira.
    creditos = InsightEngine._analisar_creditos(SimpleNamespace(db=db), 21)
    return compor_resultado_empresarial(21, {}, {
        "empresa_id": 21, "creditos_detectados": creditos,
    })


def test_st_observado_com_norma_autorizada_pode_gerar_credito(db, monkeypatch):
    _norma(monkeypatch)
    extraido, item = _persistir(db, monkeypatch, st=(140, 7.20))
    assert extraido["base_st"] == "140"
    assert extraido["valor_st"] == "7.2"
    assert (item.base_st, item.valor_st) == (140, 7.20)
    assert detectar_creditos(db, 21)[0]["credito_estimado"] == pytest.approx(5.80)
    assert projetar_tax_report_eligibility(_resultado(db)) == {"eligible": True}


def test_st_derivado_legado_nao_pode_gerar_credito_comercial(db, monkeypatch):
    _norma(monkeypatch)
    extraido, item = _persistir(db, monkeypatch)
    assert extraido["base_st"] is None and extraido["valor_st"] is None
    # Hoje resulta nos mesmos números do controlo observado. Não exigimos
    # manter derivados persistidos: a futura solução pode deixar de os gravar.
    assert detectar_creditos(db, 21) == [], "ST derivado foi tratado como ST pago observado"


def test_18_por_cento_fixo_nao_confere_autoridade_fiscal(db, monkeypatch):
    _norma(monkeypatch)
    _persistir(db, monkeypatch)
    assert projetar_tax_report_eligibility(_resultado(db)) == {"eligible": False}


def test_mva_json_decimal_nao_pode_autorizar_credito(db, monkeypatch):
    legado = json.loads((Path(__file__).resolve().parents[1] / "app/data/mva.json").read_text())
    assert legado["10019010"] == 0.40
    # Alíquota sintética aceita pelo gate atual; não afirma regra fiscal real.
    _norma(monkeypatch, aliquota=0.0001)
    extraido, item = _persistir(db, monkeypatch, mva=legado["10019010"])
    assert extraido["valor_st"] is None
    assert projetar_tax_report_eligibility(_resultado(db)) == {"eligible": False}


def test_snapshot_integro_nao_legitima_st_derivado(db, monkeypatch):
    _norma(monkeypatch)
    _persistir(db, monkeypatch)
    sealed = selar_resultado_nao_mei(_resultado(db), producer_id=(
        "app.services.resultado_empresarial_service.compor_resultado_empresarial"
    ))
    rel = SimpleNamespace(resultado_json=sealed,
        fingerprint=fingerprint_resultado_json(sealed), analysis_type="xml_analise")
    verificado = verificar_resultado_persistido(rel)
    assert verificado == _resultado(db)
    assert projetar_tax_report_eligibility(verificado) == {"eligible": False}


@pytest.mark.parametrize("norma", [
    {"nivel": "convenio_base_sem_aliquota"},
    {"fonte": ""},
    {"inicio": date(2027, 1, 1)},
], ids=["parcial", "sem-fonte", "fora-vigencia"])
def test_origem_observada_nao_dispensa_gate_normativo(db, monkeypatch, norma):
    _norma(monkeypatch, **norma)
    _persistir(db, monkeypatch, st=(140, 7.20))
    assert detectar_creditos(db, 21) == []
    assert projetar_tax_report_eligibility(_resultado(db)) == {"eligible": False}
