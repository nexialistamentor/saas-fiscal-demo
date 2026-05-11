"""
Classificador documental soberano.

Responsabilidade única: receber bytes de um documento e determinar
o seu tipo antes de qualquer extracção.

Tipos suportados V1:
    pdf_digital  — PDF com texto extraível (pdfplumber)
    pdf_scan     — PDF de imagem sem texto (requer OCR)
    image        — JPEG/PNG/TIFF (requer OCR)
    danfe        — PDF com estrutura DANFE detectada
    unknown      — não reconhecido → rejeitar

Princípio: classificar antes de extrair — nunca extrair às cegas.
"""

import io
from enum import Enum
from dataclasses import dataclass

import pdfplumber


class TipoDocumento(str, Enum):
    PDF_DIGITAL = "pdf_digital"
    PDF_SCAN = "pdf_scan"
    IMAGE = "image"
    DANFE = "danfe"
    UNKNOWN = "unknown"


@dataclass
class ResultadoClassificacao:
    tipo: TipoDocumento
    paginas: int
    tem_texto: bool
    tem_imagem: bool
    detectou_danfe: bool
    motivo_rejeicao: str | None = None


# Marcadores estruturais de DANFE em PDF digital
_DANFE_MARKERS = [
    "DANFE",
    "DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRÔNICA",
    "Chave de Acesso",
    "CFOP",
]

# Tamanho máximo aceite: 20 MB
MAX_BYTES = 20 * 1024 * 1024

# Mínimo de caracteres para considerar PDF com texto real
MIN_CHARS_PDF_DIGITAL = 50


def classificar(conteudo: bytes, nome_ficheiro: str = "") -> ResultadoClassificacao:
    """
    Classifica documento a partir dos seus bytes.
    Não faz IO — recebe bytes, devolve classificação.
    """
    if len(conteudo) > MAX_BYTES:
        return ResultadoClassificacao(
            tipo=TipoDocumento.UNKNOWN,
            paginas=0,
            tem_texto=False,
            tem_imagem=False,
            detectou_danfe=False,
            motivo_rejeicao=f"Documento excede limite de {MAX_BYTES // (1024*1024)} MB",
        )

    # Detecta imagem por magic bytes
    if _is_image(conteudo):
        return ResultadoClassificacao(
            tipo=TipoDocumento.IMAGE,
            paginas=1,
            tem_texto=False,
            tem_imagem=True,
            detectou_danfe=False,
        )

    # Detecta PDF por magic bytes
    if not conteudo.startswith(b"%PDF"):
        return ResultadoClassificacao(
            tipo=TipoDocumento.UNKNOWN,
            paginas=0,
            tem_texto=False,
            tem_imagem=False,
            detectou_danfe=False,
            motivo_rejeicao="Formato não reconhecido — apenas PDF e imagens são aceites",
        )

    return _classificar_pdf(conteudo)


def _is_image(conteudo: bytes) -> bool:
    """Detecta imagem por magic bytes (JPEG, PNG, TIFF, BMP, WEBP)."""
    magic = {
        b"\xff\xd8\xff",  # JPEG
        b"\x89PNG",  # PNG
        b"II*\x00",  # TIFF little-endian
        b"MM\x00*",  # TIFF big-endian
        b"BM",  # BMP
        b"RIFF",  # WEBP (parcial)
    }
    return any(conteudo.startswith(m) for m in magic)


def _classificar_pdf(conteudo: bytes) -> ResultadoClassificacao:
    """Analisa PDF e determina subtipo."""
    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            paginas = len(pdf.pages)
            texto_total = ""
            tem_imagem = False

            for page in pdf.pages:
                texto = page.extract_text() or ""
                texto_total += texto
                if page.images:
                    tem_imagem = True

            tem_texto = len(texto_total.strip()) >= MIN_CHARS_PDF_DIGITAL
            detectou_danfe = _detectar_danfe(texto_total)

            if detectou_danfe:
                return ResultadoClassificacao(
                    tipo=TipoDocumento.DANFE,
                    paginas=paginas,
                    tem_texto=True,
                    tem_imagem=tem_imagem,
                    detectou_danfe=True,
                )

            if tem_texto:
                return ResultadoClassificacao(
                    tipo=TipoDocumento.PDF_DIGITAL,
                    paginas=paginas,
                    tem_texto=True,
                    tem_imagem=tem_imagem,
                    detectou_danfe=False,
                )

            # PDF sem texto → scan
            return ResultadoClassificacao(
                tipo=TipoDocumento.PDF_SCAN,
                paginas=paginas,
                tem_texto=False,
                tem_imagem=tem_imagem,
                detectou_danfe=False,
            )

    except Exception as exc:
        return ResultadoClassificacao(
            tipo=TipoDocumento.UNKNOWN,
            paginas=0,
            tem_texto=False,
            tem_imagem=False,
            detectou_danfe=False,
            motivo_rejeicao=f"Erro ao processar PDF: {exc}",
        )


def _detectar_danfe(texto: str) -> bool:
    """Detecta DANFE por marcadores estruturais no texto."""
    texto_upper = texto.upper()
    return sum(1 for m in _DANFE_MARKERS if m.upper() in texto_upper) >= 2
