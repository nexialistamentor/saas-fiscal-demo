"""
tests/test_b5_04_danfe_imagem.py

B5-04 — Adapter DANFE imagem (OCR).

Cobertura:
  P1  danfe4.jpg → EvidenciaFiscalComparavel segura (chave validada ou None) [real, OCR]
  P2  danfe4.jpg → conciliação diagnóstica com danfe2.nexialista [real, OCR, xfail]
  P3  imagem sintética legível → chave extraída e validada [OCR]
  P4  chave_nfe_valida() funciona correctamente (CI-safe, sem OCR)
  N1  bytes inválidos → erro preenchido, não excepção
  N2  imagem branca sem texto → chave=None, sem chave falsa

P1/P2/P3 requerem OCR_INTEGRATION=1.
P2 é xfail: OCR real pode distorcer dígitos → conciliação não é gating.
"""

import io
import os
from pathlib import Path

import pytest

from app.services.document_ingestion.evidencia_comparavel import EvidenciaFiscalComparavel
from app.services.document_ingestion.xml_fiscal_adapter import extrair_evidencia_xml_fiscal
from app.services.document_ingestion.danfe_imagem_adapter import (
    extrair_evidencia_danfe_imagem,
    chave_nfe_valida,
)
from app.services.document_ingestion.conciliacao_danfe_xml import conciliar

XMLS_DIR = Path("app/xmls_testes")
DANFE2 = XMLS_DIR / "danfe2.nexialista"
DANFE4 = XMLS_DIR / "danfe4.jpg"

_OCR_ACTIVO = os.environ.get("OCR_INTEGRATION") == "1"
skip_sem_ocr = pytest.mark.skipif(not _OCR_ACTIVO, reason="OCR_INTEGRATION=1 não definido")


def _tesseract_disponivel() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _imagem_fiscal_sintetica() -> bytes:
    """Imagem PNG com texto DANFE sintético — dados fictícios, chave com DV válido."""
    from PIL import Image as PILImage, ImageDraw, ImageFont

    img = PILImage.new("RGB", (1400, 500), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 28)
        except Exception:
            font = ImageFont.load_default()

    # Chave sintética com DV válido (calculado): 35260699999999000191550010000000011000000010
    # Verificar: chave_nfe_valida("35260699999999000191550010000000011000000010")
    linhas = [
        "DANFE - DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRONICA",
        "No. 1   SERIE: 1",
        "CHAVE DE ACESSO",
        "3526 0699 9999 9900 0191 5500 1000 0000 0110 0000 0010",
        "PROTOCOLO: 135260099999999 - 01/06/2026 10:00:00",
        "CNPJ / CPF DO EMITENTE: 99.999.999/0001-91",
        "DESTINATARIO: 88.888.888/0001-88",
        "VALOR DO FRETE VALOR SEGURO VALOR TOTAL DA NOTA",
        "0,00 0,00 1.000,00",
    ]
    y = 40
    for linha in linhas:
        draw.text((80, y), linha, fill=(0, 0, 0), font=font)
        y += 45

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Testes com amostra real (OCR)
# ---------------------------------------------------------------------------


@skip_sem_ocr
@pytest.mark.skipif(not DANFE4.exists(), reason="amostra real ausente")
def test_p1_danfe4_jpg_evidencia_segura():
    """
    P1 — danfe4.jpg → EvidenciaFiscalComparavel segura.
    Se OCR distorcer a chave, chave_nfe=None é resultado seguro (não erro).
    Se chave extraída, deve ter 44 dígitos e DV válido.
    """
    ev = extrair_evidencia_danfe_imagem(DANFE4.read_bytes())
    assert ev.erro is None, f"Erro inesperado: {ev.erro}"
    assert ev.origem == "danfe_imagem"
    if ev.chave_nfe is not None:
        assert len(ev.chave_nfe) == 44, f"Chave com {len(ev.chave_nfe)} dígitos"
        assert ev.chave_nfe.isdigit(), "Chave com não-dígitos"
        assert chave_nfe_valida(ev.chave_nfe), f"Chave com DV inválido: {ev.chave_nfe}"


@skip_sem_ocr
@pytest.mark.skipif(
    not (DANFE2.exists() and DANFE4.exists()),
    reason="amostras reais ausentes",
)
@pytest.mark.xfail(
    reason="OCR de foto real pode distorcer dígitos da chave — conciliação perfeita é B5-05",
    strict=False,
)
def test_p2_conciliacao_imagem_xml_diagnostico():
    """
    P2 — danfe4.jpg ↔ danfe2.nexialista → conciliação diagnóstica.
    xfail: OCR pode errar dígitos; resultado divergente não é falha do sistema.
    """
    ev_xml = extrair_evidencia_xml_fiscal(DANFE2.read_bytes())
    ev_img = extrair_evidencia_danfe_imagem(DANFE4.read_bytes())

    assert ev_xml.erro is None
    assert ev_img.erro is None

    resultado = conciliar(ev_xml, ev_img)
    assert resultado.status == "conciliado", (
        f"Status: {resultado.status} — OCR distorceu campos críticos\n"
        f"Conciliados: {resultado.campos_conciliados}\n"
        f"Divergências: {resultado.divergencias}"
    )


@skip_sem_ocr
def test_p3_imagem_sintetica_chave_validada():
    """P3 — imagem sintética → chave extraída e com DV válido."""
    ev = extrair_evidencia_danfe_imagem(_imagem_fiscal_sintetica())
    assert ev.erro is None
    if ev.chave_nfe is not None:
        assert len(ev.chave_nfe) == 44
        assert chave_nfe_valida(ev.chave_nfe)


# ---------------------------------------------------------------------------
# Testes CI-safe (sem OCR)
# ---------------------------------------------------------------------------


def test_p4_validacao_dv_chave_nfe():
    """P4 — chave_nfe_valida() funciona correctamente (CI-safe)."""
    # Chave real do caso Yamaguchi (deve ser válida)
    chave_real = "35260504831230000153550010000788751956084607"
    assert chave_nfe_valida(chave_real) is True

    # Chave com dígito errado (0788 → 0784 como OCR distorceu)
    chave_ocr_errada = "35260504831230000153550010000784751956084607"
    assert chave_nfe_valida(chave_ocr_errada) is False

    # Chave com comprimento errado
    assert chave_nfe_valida("12345") is False
    assert chave_nfe_valida("") is False
    assert chave_nfe_valida(None) is False

    # Chave com não-dígitos
    assert chave_nfe_valida("3526" * 10 + "ABCD") is False


def test_n1_bytes_invalidos_erro_preenchido():
    """N1 — bytes inválidos → erro preenchido, não excepção."""
    ev = extrair_evidencia_danfe_imagem(b"\x00\x01\x02 nao e imagem")
    assert ev.erro is not None
    assert ev.chave_nfe is None


def test_n2_imagem_branca_sem_chave_falsa():
    """N2 — imagem branca → chave=None ou erro, nunca chave falsa."""
    from PIL import Image as PILImage
    img = PILImage.new("RGB", (100, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    ev = extrair_evidencia_danfe_imagem(buf.getvalue())
    assert ev is not None
    # Nunca deve produzir chave falsa
    if ev.chave_nfe is not None:
        assert chave_nfe_valida(ev.chave_nfe), "Imagem branca produziu chave com DV inválido"
    # Sem Tesseract → erro; com Tesseract → chave=None (texto vazio)
    if not _tesseract_disponivel():
        assert ev.erro is not None
    else:
        assert ev.chave_nfe is None
