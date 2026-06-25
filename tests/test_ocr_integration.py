"""
Testes de integração OCR — requerem Tesseract instalado no sistema.

Executar apenas quando OCR_INTEGRATION=1:
    $env:OCR_INTEGRATION = "1"; python -m pytest tests\test_ocr_integration.py -v -m integration

Nunca correm na suite principal (pytest -q).
"""

import io
import os

import pytest

# Marca global — todos os testes neste ficheiro são integration
pytestmark = pytest.mark.integration


def _ocr_disponivel() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


skip_sem_ocr = pytest.mark.skipif(
    not _ocr_disponivel() or os.getenv("OCR_INTEGRATION") != "1",
    reason="Tesseract não disponível ou OCR_INTEGRATION != 1",
)


def _pdf_scan_bytes() -> bytes:
    """PDF com texto renderizado como imagem (simula scan)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(100, 750, "CNPJ 12.345.678/0001-90 CFOP 5102 Valor Total R$ 1.500,00")
    c.save()
    return buf.getvalue()


def _jpeg_fiscal() -> bytes:
    """Imagem PNG com texto fiscal legivel para OCR (fonte TrueType, imagem grande)."""
    from PIL import Image as PILImage, ImageDraw, ImageFont

    img = PILImage.new("RGB", (1400, 350), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 36)
        except Exception:
            font = ImageFont.load_default()
    draw.text((100, 120), "CNPJ 12.345.678/0001-90 CFOP 5102", fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@skip_sem_ocr
def test_ocr_imagem_extrai_texto():
    from app.services.document_ingestion.extractor import _extrair_ocr

    resultado = _extrair_ocr(_jpeg_fiscal(), paginas_total=1)
    assert resultado.requer_ocr is True
    assert resultado.erro is None
    assert len(resultado.texto) > 0


@skip_sem_ocr
def test_ocr_imagem_detecta_cnpj():
    from app.services.document_ingestion.extractor import _extrair_ocr

    resultado = _extrair_ocr(_jpeg_fiscal(), paginas_total=1)
    assert "CNPJ" in resultado.texto or "cnpj" in resultado.texto.lower()


@skip_sem_ocr
def test_ocr_confianca_apos_extracao():
    """Pipeline completo: OCR → confidence → score real."""
    from app.services.document_ingestion.confidence import calcular
    from app.services.document_ingestion.extractor import _extrair_ocr

    resultado = _extrair_ocr(_jpeg_fiscal(), paginas_total=1)
    if resultado.texto:
        confianca = calcular(resultado.texto, requer_ocr=True)
        assert 0.0 <= confianca.score <= 100.0


@skip_sem_ocr
def test_ocr_score_penalizado_vs_digital():
    """OCR deve ter score inferior ao mesmo texto extraído digitalmente."""
    from app.services.document_ingestion.confidence import calcular

    texto = "CNPJ 12.345.678/0001-90 CFOP 5102 valor total R$ 1.500,00"
    score_digital = calcular(texto, requer_ocr=False).score
    score_ocr = calcular(texto, requer_ocr=True).score
    assert score_ocr < score_digital
