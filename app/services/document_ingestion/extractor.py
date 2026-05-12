"""
Extractor documental soberano.

Responsabilidade única: dado um documento classificado, extrair
o texto bruto. Não interpreta — só extrai.

Princípio: extracção determinística antes de qualquer inteligência.
"""

import io
from dataclasses import dataclass

import pdfplumber

from app.services.document_ingestion.classifier import TipoDocumento


@dataclass
class ResultadoExtracao:
    texto: str
    paginas_extraidas: int
    paginas_total: int
    requer_ocr: bool
    erro: str | None = None


def extrair(conteudo: bytes, tipo: TipoDocumento) -> ResultadoExtracao:
    """
    Extrai texto bruto de um documento já classificado.
    PDF_SCAN e IMAGE usam OCR (Tesseract); requer_ocr=True no resultado.
    """
    if tipo == TipoDocumento.PDF_DIGITAL or tipo == TipoDocumento.DANFE:
        return _extrair_pdf_texto(conteudo)

    if tipo == TipoDocumento.PDF_SCAN:
        return _extrair_ocr(conteudo, _contar_paginas_pdf(conteudo))

    if tipo == TipoDocumento.IMAGE:
        return _extrair_ocr(conteudo, 1)

    return ResultadoExtracao(
        texto="",
        paginas_extraidas=0,
        paginas_total=0,
        requer_ocr=False,
        erro=f"Tipo não suportado para extracção: {tipo}",
    )


def _extrair_pdf_texto(conteudo: bytes) -> ResultadoExtracao:
    """Extrai texto de PDF digital via pdfplumber."""
    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            paginas_total = len(pdf.pages)
            textos = []
            paginas_extraidas = 0

            for page in pdf.pages:
                texto = page.extract_text() or ""
                if texto.strip():
                    textos.append(texto)
                    paginas_extraidas += 1

            return ResultadoExtracao(
                texto="\n".join(textos),
                paginas_extraidas=paginas_extraidas,
                paginas_total=paginas_total,
                requer_ocr=False,
            )

    except Exception as exc:
        return ResultadoExtracao(
            texto="",
            paginas_extraidas=0,
            paginas_total=0,
            requer_ocr=False,
            erro=f"Erro na extracção PDF: {exc}",
        )


def _contar_paginas_pdf(conteudo: bytes) -> int:
    """Conta páginas de PDF sem extrair texto."""
    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            return len(pdf.pages)
    except Exception:
        return 0


def _extrair_ocr(conteudo: bytes, paginas_total: int) -> ResultadoExtracao:
    """
    Extrai texto via OCR (Tesseract) — import lazy para não quebrar ambientes sem binário.
    Usado para PDF_SCAN e IMAGE.
    Língua: português + inglês (por+eng).
    """
    try:
        import pytesseract  # lazy — só importa quando OCR é necessário
        from PIL import Image as PILImage
    except ImportError:
        return ResultadoExtracao(
            texto="",
            paginas_extraidas=0,
            paginas_total=paginas_total,
            requer_ocr=True,
            erro="pytesseract não disponível neste ambiente",
        )

    try:
        import pdf2image  # lazy — converte PDF scan para imagens

        imagens = pdf2image.convert_from_bytes(conteudo, dpi=300)
    except ImportError:
        # PDF scan sem pdf2image — tenta tratar como imagem directa
        imagens = None
    except Exception:
        imagens = None

    # Se não é PDF scan, trata como imagem directa
    if imagens is None:
        try:
            import io as _io

            img = PILImage.open(_io.BytesIO(conteudo))
            imagens = [img]
        except Exception as exc:
            return ResultadoExtracao(
                texto="",
                paginas_extraidas=0,
                paginas_total=paginas_total,
                requer_ocr=True,
                erro=f"Erro ao abrir imagem: {exc}",
            )

    textos = []
    paginas_extraidas = 0
    for img in imagens:
        try:
            texto = pytesseract.image_to_string(img, lang="por+eng")
            if texto.strip():
                textos.append(texto)
                paginas_extraidas += 1
        except Exception:
            continue

    return ResultadoExtracao(
        texto="\n".join(textos),
        paginas_extraidas=paginas_extraidas,
        paginas_total=paginas_total,
        requer_ocr=True,
    )
