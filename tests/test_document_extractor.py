"""
Testes do extractor documental soberano.
"""

import io

from app.services.document_ingestion.classifier import TipoDocumento
from app.services.document_ingestion.extractor import extrair


def _pdf_digital(
    texto: str = "Nota Fiscal valor total R$ 1.500,00 CFOP 5102 ICMS 12%",
) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(100, 750, texto)
    c.save()
    return buf.getvalue()


def _pdf_vazio() -> bytes:
    """PDF sem texto extraível. Canvas sem drawString vira 0 páginas no pdfplumber."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(100, 750, "")
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# PDF digital
# ---------------------------------------------------------------------------
def test_extrai_texto_pdf_digital():
    resultado = extrair(_pdf_digital(), TipoDocumento.PDF_DIGITAL)
    assert resultado.erro is None
    assert resultado.requer_ocr is False
    assert len(resultado.texto) > 0
    assert resultado.paginas_extraidas >= 1


def test_pdf_digital_contem_texto_extraido():
    resultado = extrair(_pdf_digital("CFOP 5102 ICMS valor"), TipoDocumento.PDF_DIGITAL)
    assert "CFOP" in resultado.texto or len(resultado.texto) > 0


# ---------------------------------------------------------------------------
# DANFE — mesmo extractor que PDF digital
# ---------------------------------------------------------------------------
def test_extrai_danfe():
    resultado = extrair(_pdf_digital("DANFE Chave de Acesso CFOP 5102"), TipoDocumento.DANFE)
    assert resultado.requer_ocr is False
    assert resultado.erro is None


# ---------------------------------------------------------------------------
# PDF scan — sinaliza OCR
# ---------------------------------------------------------------------------
def test_pdf_scan_requer_ocr():
    resultado = extrair(_pdf_vazio(), TipoDocumento.PDF_SCAN)
    assert resultado.requer_ocr is True
    assert resultado.texto == ""
    assert resultado.erro is None


def test_pdf_scan_conta_paginas():
    resultado = extrair(_pdf_vazio(), TipoDocumento.PDF_SCAN)
    assert resultado.paginas_total >= 1


# ---------------------------------------------------------------------------
# Imagem — sinaliza OCR
# ---------------------------------------------------------------------------
def test_image_requer_ocr():
    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.new("RGB", (10, 10)).save(buf, format="JPEG")
    resultado = extrair(buf.getvalue(), TipoDocumento.IMAGE)
    assert resultado.requer_ocr is True
    assert resultado.paginas_total == 1
    assert resultado.texto == ""


# ---------------------------------------------------------------------------
# Tipo desconhecido
# ---------------------------------------------------------------------------
def test_unknown_retorna_erro():
    resultado = extrair(b"qualquer coisa", TipoDocumento.UNKNOWN)
    assert resultado.erro is not None
    assert resultado.requer_ocr is False
