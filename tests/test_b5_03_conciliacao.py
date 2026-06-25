"""
tests/test_b5_03_conciliacao.py

B5-03 — Conciliação DANFE PDF ↔ XML NF-e.

Cobertura:
  P1  danfe3.pdf ↔ danfe2.nexialista → conciliado (amostras reais)
  P2  chave igual → conciliado
  P3  sem chave + 3 críticos coincidem → conciliado
  P4  valor diverge + chave coincide → conciliado + alerta
  P5  danfe3.pdf: chave/número/série/protocolo/valor correctos (amostra real)
  P6  texto DANFE sintético → todos os campos extraídos (CI-safe)
  N1  chave diverge → divergente
  N2  CNPJ emitente diverge sem chave → divergente
  N3  campos críticos todos ausentes → inconclusivo
  N4  bytes inválidos no adapter → erro preenchido
  N5  sem chave + apenas 2 críticos → inconclusivo (não conciliado)
"""
from decimal import Decimal
from pathlib import Path
import pytest

from app.services.document_ingestion.evidencia_comparavel import EvidenciaFiscalComparavel
from app.services.document_ingestion.xml_fiscal_adapter import extrair_evidencia_xml_fiscal
from app.services.document_ingestion.danfe_pdf_adapter import (
    extrair_evidencia_danfe_pdf,
    extrair_evidencia_danfe_texto,
)
from app.services.document_ingestion.conciliacao_danfe_xml import conciliar

XMLS_DIR = Path("app/xmls_testes")
DANFE2 = XMLS_DIR / "danfe2.nexialista"
DANFE3 = XMLS_DIR / "danfe3.pdf"

# ---------------------------------------------------------------------------
# Constantes sintéticas (sem dados reais)
# ---------------------------------------------------------------------------
_CHAVE  = "35260699999999000191550010000000011000000010"
_CNPJ_E = "99999999000191"
_CNPJ_D = "88888888000188"
_NPROT  = "135260099999999"   # 15 dígitos


def _ev_xml(**kw) -> EvidenciaFiscalComparavel:
    defaults = dict(
        origem="xml_fiscal", chave_nfe=_CHAVE,
        cnpj_emitente=_CNPJ_E, cnpj_destinatario=_CNPJ_D,
        numero_nota="1", serie="1", valor_total=Decimal("1000.00"),
        modelo="55", protocolo=_NPROT, uf_emit="SP", uf_dest="PA",
    )
    return EvidenciaFiscalComparavel(**{**defaults, **kw})


def _ev_danfe(**kw) -> EvidenciaFiscalComparavel:
    defaults = dict(
        origem="danfe_pdf", chave_nfe=_CHAVE,
        cnpj_emitente=_CNPJ_E, cnpj_destinatario=_CNPJ_D,
        numero_nota="1", serie="1", valor_total=Decimal("1000.00"),
        modelo="55", protocolo=_NPROT, uf_emit=None, uf_dest=None,
    )
    return EvidenciaFiscalComparavel(**{**defaults, **kw})


# Texto DANFE sintético CI-safe (estrutura real, dados fictícios)
_TEXTO_DANFE_SINTETICO = f"""RECEBEMOS DE EMPRESA SINTETICA EMITENTE LTDA
NF-e
Nº. 1
SÉRIE: 1
CHAVE DE ACESSO
3526 0699 9999 9900 0191 5500 1000 0000 0110 0000 0010
PROTOCOLO DE AUTORIZAÇÃO DE USO
{_NPROT} - 01/06/2026 10:00:00
CNPJ / CPF DO EMITENTE
99.999.999/0001-91
DESTINATÁRIO/REMETENTE
EMPRESA SINTETICA DESTINATARIA LTDA 88.888.888/0001-88
VALOR DO FRETE VALOR DO SEGURO DESCONTO OUTRAS DESPESAS ACESSÓRIAS VALOR TOTAL DO I.P.I VALOR TOTAL DA NOTA
0,00 0,00 0,00 0,00 0,00 1.000,00
"""

# ---------------------------------------------------------------------------
# Testes com amostras reais
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (DANFE2.exists() and DANFE3.exists()),
    reason="amostras reais ausentes — validação local",
)
def test_p1_conciliacao_real_yamaguchi():
    """P1 — danfe3.pdf ↔ danfe2.nexialista → conciliado (caso Yamaguchi)."""
    ev_xml   = extrair_evidencia_xml_fiscal(DANFE2.read_bytes())
    ev_danfe = extrair_evidencia_danfe_pdf(DANFE3.read_bytes())

    assert ev_xml.erro is None,   f"Erro XML: {ev_xml.erro}"
    assert ev_danfe.erro is None, f"Erro DANFE: {ev_danfe.erro}"

    resultado = conciliar(ev_xml, ev_danfe)
    assert resultado.status == "conciliado", (
        f"Status: {resultado.status}\n"
        f"Conciliados: {resultado.campos_conciliados}\n"
        f"Divergências: {resultado.divergencias}\n"
        f"Faltantes: {resultado.faltantes}"
    )
    assert "chave_nfe" in resultado.campos_conciliados


@pytest.mark.skipif(not DANFE3.exists(), reason="amostra real ausente")
def test_p5_danfe_pdf_campos_reais():
    """P5 — danfe3.pdf: campos correctos extraídos da amostra real."""
    ev = extrair_evidencia_danfe_pdf(DANFE3.read_bytes())
    assert ev.erro is None
    assert ev.chave_nfe is not None and len(ev.chave_nfe) == 44
    assert ev.chave_nfe.isdigit()
    assert ev.numero_nota == "78875"
    assert ev.serie == "1"
    assert ev.protocolo == "135261800334789"
    assert ev.valor_total == Decimal("5503.72")
    assert ev.modelo == "55"   # derivado da chave (posição 20–21)


# ---------------------------------------------------------------------------
# Testes sintéticos (CI-safe)
# ---------------------------------------------------------------------------


def test_p2_chave_igual_conciliado():
    """P2 — chave igual → conciliado."""
    r = conciliar(_ev_xml(), _ev_danfe())
    assert r.status == "conciliado"
    assert "chave_nfe" in r.campos_conciliados


def test_p3_sem_chave_tres_criticos_conciliado():
    """P3 — sem chave + CNPJ+número+série coincidem → conciliado."""
    r = conciliar(
        _ev_xml(chave_nfe=None),
        _ev_danfe(chave_nfe=None),
    )
    assert r.status == "conciliado"


def test_p4_valor_diverge_chave_coincide_alerta():
    """P4 — valor diverge mas chave coincide → conciliado + alerta."""
    r = conciliar(
        _ev_xml(valor_total=Decimal("1000.00")),
        _ev_danfe(valor_total=Decimal("999.00")),
    )
    assert r.status == "conciliado"
    assert any("valor_total" in a for a in r.alertas)


def test_p6_texto_danfe_sintetico_ci_safe():
    """P6 — texto DANFE sintético → todos os campos extraídos (CI-safe)."""
    ev = extrair_evidencia_danfe_texto(_TEXTO_DANFE_SINTETICO)
    assert ev.erro is None
    assert ev.chave_nfe == "35260699999999000191550010000000011000000010"
    assert ev.cnpj_emitente == "99999999000191"
    assert ev.cnpj_destinatario == "88888888000188"
    assert ev.numero_nota == "1"
    assert ev.serie == "1"
    assert ev.protocolo == _NPROT
    assert ev.valor_total == Decimal("1000.00")
    assert ev.modelo == "55"


def test_n1_chave_diverge():
    """N1 — chave diverge → divergente."""
    r = conciliar(_ev_xml(chave_nfe="3" * 44), _ev_danfe(chave_nfe="4" * 44))
    assert r.status == "divergente"


def test_n2_cnpj_diverge_sem_chave():
    """N2 — CNPJ diverge sem chave → divergente."""
    r = conciliar(
        _ev_xml(chave_nfe=None, cnpj_emitente="99999999000191"),
        _ev_danfe(chave_nfe=None, cnpj_emitente="11111111000111"),
    )
    assert r.status == "divergente"


def test_n3_campos_criticos_ausentes_inconclusivo():
    """N3 — campos críticos ausentes → inconclusivo."""
    r = conciliar(
        _ev_xml(chave_nfe=None, cnpj_emitente=None, numero_nota=None, serie=None),
        _ev_danfe(chave_nfe=None, cnpj_emitente=None, numero_nota=None, serie=None),
    )
    assert r.status == "inconclusivo"


def test_n4_bytes_invalidos_erro_preenchido():
    """N4 — bytes inválidos → erro preenchido, não excepção."""
    ev = extrair_evidencia_danfe_pdf(b"\x00\x01\x02 nao e pdf")
    assert ev.erro is not None


def test_n5_sem_chave_dois_criticos_inconclusivo():
    """N5 — sem chave + apenas 2 de 3 críticos → inconclusivo (não conciliado)."""
    r = conciliar(
        _ev_xml(chave_nfe=None, serie=None),
        _ev_danfe(chave_nfe=None, serie=None),
    )
    assert r.status == "inconclusivo"
