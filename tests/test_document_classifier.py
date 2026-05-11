"""
Testes do classificador documental soberano.

Confrontação de tipos, limites e edge cases.
"""

import io

from app.services.document_ingestion.classifier import (
    MAX_BYTES,
    TipoDocumento,
    classificar,
)


# ---------------------------------------------------------------------------
# Helpers para gerar bytes de teste
# ---------------------------------------------------------------------------
def _pdf_digital(texto: str | None = None) -> bytes:
    """Gera PDF digital mínimo com texto via reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    if texto is None:
        # >= MIN_CHARS_PDF_DIGITAL para não cair em pdf_scan
        texto = (
            "Nota Fiscal CFOP 5102 valor 1000,00 tomador "
            "documento fiscal eletrônico Brasil referência teste"
        )
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(100, 750, texto)
    c.save()
    return buf.getvalue()


def _pdf_vazio() -> bytes:
    """PDF sem texto (simula scan)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.save()
    return buf.getvalue()


def _pdf_danfe() -> bytes:
    """PDF com marcadores DANFE."""
    return _pdf_digital(
        "DANFE DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRÔNICA "
        "Chave de Acesso 1234 CFOP 5102"
    )


def _jpeg_bytes() -> bytes:
    """JPEG mínimo válido (magic bytes JPEG)."""
    from PIL import Image as PILImage

    buf = io.BytesIO()
    img = PILImage.new("RGB", (10, 10), color=(255, 255, 255))
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _png_bytes() -> bytes:
    """PNG mínimo válido."""
    from PIL import Image as PILImage

    buf = io.BytesIO()
    img = PILImage.new("RGB", (10, 10), color=(0, 0, 0))
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# PDF digital
# ---------------------------------------------------------------------------
def test_pdf_digital_classificado():
    resultado = classificar(_pdf_digital())
    assert resultado.tipo == TipoDocumento.PDF_DIGITAL
    assert resultado.tem_texto is True
    assert resultado.motivo_rejeicao is None


def test_pdf_digital_paginas():
    resultado = classificar(_pdf_digital())
    assert resultado.paginas >= 1


# ---------------------------------------------------------------------------
# PDF scan (sem texto)
# ---------------------------------------------------------------------------
def test_pdf_scan_classificado():
    resultado = classificar(_pdf_vazio())
    assert resultado.tipo == TipoDocumento.PDF_SCAN
    assert resultado.tem_texto is False


# ---------------------------------------------------------------------------
# DANFE
# ---------------------------------------------------------------------------
def test_danfe_detectado():
    resultado = classificar(_pdf_danfe())
    assert resultado.tipo == TipoDocumento.DANFE
    assert resultado.detectou_danfe is True


# ---------------------------------------------------------------------------
# Imagens
# ---------------------------------------------------------------------------
def test_jpeg_classificado():
    resultado = classificar(_jpeg_bytes())
    assert resultado.tipo == TipoDocumento.IMAGE
    assert resultado.tem_imagem is True


def test_png_classificado():
    resultado = classificar(_png_bytes())
    assert resultado.tipo == TipoDocumento.IMAGE
    assert resultado.tem_imagem is True


# ---------------------------------------------------------------------------
# Rejeições
# ---------------------------------------------------------------------------
def test_rejeita_formato_desconhecido():
    resultado = classificar(b"isto nao e pdf nem imagem")
    assert resultado.tipo == TipoDocumento.UNKNOWN
    assert resultado.motivo_rejeicao is not None


def test_rejeita_documento_grande_demais():
    conteudo_grande = b"%PDF" + b"x" * (MAX_BYTES + 1)
    resultado = classificar(conteudo_grande)
    assert resultado.tipo == TipoDocumento.UNKNOWN
    assert "limite" in resultado.motivo_rejeicao.lower()


def test_bytes_vazios_rejeitados():
    resultado = classificar(b"")
    assert resultado.tipo == TipoDocumento.UNKNOWN
