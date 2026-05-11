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
    Para PDF_SCAN e IMAGE, sinaliza requer_ocr=True — OCR é responsabilidade do caller.
    """
    if tipo == TipoDocumento.PDF_DIGITAL or tipo == TipoDocumento.DANFE:
        return _extrair_pdf_texto(conteudo)

    if tipo == TipoDocumento.PDF_SCAN:
        return ResultadoExtracao(
            texto="",
            paginas_extraidas=0,
            paginas_total=_contar_paginas_pdf(conteudo),
            requer_ocr=True,
        )

    if tipo == TipoDocumento.IMAGE:
        return ResultadoExtracao(
            texto="",
            paginas_extraidas=0,
            paginas_total=1,
            requer_ocr=True,
        )

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
