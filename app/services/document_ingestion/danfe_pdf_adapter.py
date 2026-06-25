"""
app/services/document_ingestion/danfe_pdf_adapter.py

B5-03a — Adaptador DANFE PDF para EvidenciaFiscalComparavel.

Responsabilidade única:
  - extrair_evidencia_danfe_pdf(bytes) → extrai texto via extractor e delega
  - extrair_evidencia_danfe_texto(str) → parser puro de texto DANFE (testável sem PDF)

Diferenças críticas DANFE PDF vs XML:
  - Chave fragmentada: "3526 0504 8312 ... 4607" (11 grupos × 4, separados por \s+)
  - Chave pode aparecer contínua (44 dígitos) — suporte a ambas
  - CNPJ formatado: "04.831.230/0001-53"
  - Protocolo (15 dígitos) seguido de " - dd/mm/yyyy"
  - Valor total: linha seguinte a "VALOR TOTAL DA NOTA", último valor monetário
  - Modelo derivado da chave (posição 20–21): "55" (NF-e) | "65" (NFC-e)

Fora de escopo:
  - Não toca em normalizer.py nem xml_service.py
  - Não persiste nada
  - Não chama motor fiscal
  - Não faz OCR (danfe4.jpg é B5-04)
"""

import re
from decimal import Decimal, InvalidOperation

from app.services.document_ingestion.evidencia_comparavel import EvidenciaFiscalComparavel
from app.services.document_ingestion.extractor import extrair
from app.services.document_ingestion.classifier import TipoDocumento

# ---------------------------------------------------------------------------
# Regex calibradas contra danfe3.pdf (texto real)
# ---------------------------------------------------------------------------

# Chave fragmentada: 11 grupos de 4 dígitos separados por \s+
_RE_CHAVE_FRAGMENTADA = re.compile(r"(\d{4}(?:\s+\d{4}){10})")
# Chave contínua: 44 dígitos seguidos (fallback)
_RE_CHAVE_CONTINUA = re.compile(r"\b(\d{44})\b")

# CNPJ formatado: XX.XXX.XXX/XXXX-XX
_RE_CNPJ_FORMATADO = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")

# Número da NF: "Nº. 78875" ou variantes
_RE_NUMERO_NF = re.compile(r"N[ºo°]\.?\s*(\d{1,15})", re.IGNORECASE)

# Série: "SÉRIE: 1" ou "SERIE: 1"
_RE_SERIE = re.compile(r"S[ÉE]RIE[:\s]+(\d{1,3})", re.IGNORECASE)

# Protocolo: exactamente 15 dígitos seguidos de " - " e data dd/mm/yyyy
_RE_PROTOCOLO = re.compile(r"\b(\d{15})\s*[-–]\s*\d{2}/\d{2}/\d{4}")

# Valores monetários BR: "5.503,72" ou "1.000,00" ou "0,00"
_RE_VALOR_BR = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}")


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def extrair_evidencia_danfe_pdf(conteudo: bytes) -> EvidenciaFiscalComparavel:
    """
    Extrai EvidenciaFiscalComparavel de bytes de DANFE PDF.
    Extrai texto via extractor existente e delega para extrair_evidencia_danfe_texto.
    """
    resultado_extracao = extrair(conteudo, TipoDocumento.DANFE)
    if resultado_extracao.erro:
        return EvidenciaFiscalComparavel(
            origem="danfe_pdf",
            chave_nfe=None, cnpj_emitente=None, cnpj_destinatario=None,
            numero_nota=None, serie=None, valor_total=None,
            modelo=None, protocolo=None, uf_emit=None, uf_dest=None,
            erro=f"Erro na extracção do PDF: {resultado_extracao.erro}",
        )
    return extrair_evidencia_danfe_texto(resultado_extracao.texto)


def extrair_evidencia_danfe_texto(texto: str) -> EvidenciaFiscalComparavel:
    """
    Parser puro de texto DANFE → EvidenciaFiscalComparavel.
    Testável sem PDF real (CI-safe).
    """
    chave_nfe    = _extrair_chave(texto)
    cnpjs        = _RE_CNPJ_FORMATADO.findall(texto)
    cnpj_emit    = _limpar_cnpj(cnpjs[0]) if len(cnpjs) > 0 else None
    cnpj_dest    = _limpar_cnpj(cnpjs[1]) if len(cnpjs) > 1 else None
    numero_nota  = _extrair_numero_nf(texto)
    serie        = _extrair_serie(texto)
    protocolo    = _extrair_protocolo(texto)
    valor_total  = _extrair_valor_total(texto)
    modelo       = _derivar_modelo(chave_nfe)

    return EvidenciaFiscalComparavel(
        origem="danfe_pdf",
        chave_nfe=chave_nfe,
        cnpj_emitente=cnpj_emit,
        cnpj_destinatario=cnpj_dest,
        numero_nota=numero_nota,
        serie=serie,
        valor_total=valor_total,
        modelo=modelo,
        protocolo=protocolo,
        uf_emit=None,   # UF não extraída nesta versão — chave é o campo soberano
        uf_dest=None,
        erro=None,
    )


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------


def _extrair_chave(texto: str) -> str | None:
    """Extrai chave fragmentada (grupos de 4) ou contínua (44 dígitos)."""
    m = _RE_CHAVE_FRAGMENTADA.search(texto)
    if m:
        chave = re.sub(r"\s+", "", m.group(1))
        if len(chave) == 44:
            return chave
    m = _RE_CHAVE_CONTINUA.search(texto)
    return m.group(1) if m else None


def _limpar_cnpj(cnpj_formatado: str) -> str:
    """Remove pontuação de CNPJ formatado → 14 dígitos."""
    return re.sub(r"\D", "", cnpj_formatado)


def _extrair_numero_nf(texto: str) -> str | None:
    m = _RE_NUMERO_NF.search(texto)
    return m.group(1) if m else None


def _extrair_serie(texto: str) -> str | None:
    m = _RE_SERIE.search(texto)
    return m.group(1) if m else None


def _extrair_protocolo(texto: str) -> str | None:
    m = _RE_PROTOCOLO.search(texto)
    return m.group(1) if m else None


def _extrair_valor_total(texto: str) -> Decimal | None:
    """
    Localiza linha "VALOR TOTAL DA NOTA" e lê o último valor monetário
    da linha seguinte. Evita capturar 0,00 intermediários.
    """
    linhas = texto.splitlines()
    for i, linha in enumerate(linhas):
        if "VALOR TOTAL DA NOTA" in linha.upper() and i + 1 < len(linhas):
            valores = _RE_VALOR_BR.findall(linhas[i + 1])
            if valores:
                return _parse_valor_br(valores[-1])
    return None


def _parse_valor_br(valor: str) -> Decimal | None:
    """Converte "5.503,72" → Decimal("5503.72")."""
    try:
        return Decimal(valor.replace(".", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _derivar_modelo(chave_nfe: str | None) -> str | None:
    """
    Deriva modelo da chave NF-e (posição 20–21).
    "55" = NF-e, "65" = NFC-e.
    """
    if chave_nfe and len(chave_nfe) == 44:
        return chave_nfe[20:22]
    return None
