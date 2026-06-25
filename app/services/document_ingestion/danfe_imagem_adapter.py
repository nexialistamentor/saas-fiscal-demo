"""
app/services/document_ingestion/danfe_imagem_adapter.py

B5-04 — Adaptador DANFE imagem (JPG/PNG/TIFF) para EvidenciaFiscalComparavel.

Responsabilidade única:
  - Receber bytes de imagem classificada como TipoDocumento.IMAGE
  - Extrair texto via OCR (extractor.py — Tesseract)
  - Reconstruir chave NF-e por candidatos + validação de DV
  - Reutilizar extrair_evidencia_danfe_texto() do adapter PDF
  - Devolver EvidenciaFiscalComparavel com origem="danfe_imagem"

Princípio soberano:
  OCR introduz ruído. Uma chave de 44 dígitos sem DV válido não é evidência fiscal.
  Melhor chave_nfe=None do que chave errada canonizada.

Estratégia de reconstrução da chave:
  1. Procurar chave contínua de 44 dígitos (melhor caso)
  2. Procurar 11 grupos de 4 dígitos consecutivos
  3. Procurar após marcador "CHAVE DE ACESSO" no texto
  4. Para cada candidato, validar DV (módulo 11)
  5. Devolver apenas candidato com DV válido

Fora de escopo:
  - Não toca em normalizer.py, xml_service.py, banco, motor fiscal
  - Não reimplementa OCR — usa extractor.py
  - Conciliação perfeita imagem↔XML é B5-05 (OCR tem menor confiança)
"""

import re
from app.services.document_ingestion.evidencia_comparavel import EvidenciaFiscalComparavel
from app.services.document_ingestion.extractor import extrair
from app.services.document_ingestion.classifier import TipoDocumento
from app.services.document_ingestion.danfe_pdf_adapter import extrair_evidencia_danfe_texto

# Grupos de exactamente 4 dígitos
_RE_GRUPO_4 = re.compile(r"\b(\d{4})\b")
# Chave contínua de 44 dígitos
_RE_CHAVE_CONTINUA = re.compile(r"\b(\d{44})\b")
# Marcador de chave no DANFE
_RE_MARCADOR_CHAVE = re.compile(r"CHAVE\s+DE\s+ACESSO", re.IGNORECASE)


def extrair_evidencia_danfe_imagem(conteudo: bytes) -> EvidenciaFiscalComparavel:
    """
    Extrai EvidenciaFiscalComparavel de bytes de imagem DANFE (JPG/PNG/TIFF).
    Chave NF-e só é devolvida se passar validação de DV.
    """
    resultado_ocr = extrair(conteudo, TipoDocumento.IMAGE)

    if resultado_ocr.erro:
        return EvidenciaFiscalComparavel(
            origem="danfe_imagem",
            chave_nfe=None, cnpj_emitente=None, cnpj_destinatario=None,
            numero_nota=None, serie=None, valor_total=None,
            modelo=None, protocolo=None, uf_emit=None, uf_dest=None,
            erro=f"Erro no OCR da imagem: {resultado_ocr.erro}",
        )

    texto = resultado_ocr.texto
    chave_nfe = _extrair_chave_validada(texto)
    ev_base = extrair_evidencia_danfe_texto(texto)

    modelo = _derivar_modelo(chave_nfe if chave_nfe else ev_base.chave_nfe)

    return EvidenciaFiscalComparavel(
        origem="danfe_imagem",
        chave_nfe=chave_nfe,
        cnpj_emitente=ev_base.cnpj_emitente,
        cnpj_destinatario=ev_base.cnpj_destinatario,
        numero_nota=ev_base.numero_nota,
        serie=ev_base.serie,
        valor_total=ev_base.valor_total,
        modelo=modelo,
        protocolo=ev_base.protocolo,
        uf_emit=None,
        uf_dest=None,
        erro=None,
    )


# ---------------------------------------------------------------------------
# Validação de chave NF-e
# ---------------------------------------------------------------------------


def chave_nfe_valida(chave: str) -> bool:
    """
    Valida chave NF-e de 44 dígitos pelo dígito verificador (módulo 11).
    Retorna True se a chave é estruturalmente válida.
    """
    if not chave or len(chave) != 44 or not chave.isdigit():
        return False
    # Calcular DV dos primeiros 43 dígitos
    soma = sum(int(d) * ((i % 8) + 2) for i, d in enumerate(reversed(chave[:43])))
    resto = soma % 11
    dv_esperado = 0 if resto < 2 else 11 - resto
    return int(chave[43]) == dv_esperado


def _derivar_modelo(chave_nfe: str | None) -> str | None:
    """Deriva modelo da chave (posição 20–21): '55' (NF-e) | '65' (NFC-e)."""
    if chave_nfe and len(chave_nfe) == 44:
        return chave_nfe[20:22]
    return None


# ---------------------------------------------------------------------------
# Reconstrução de chave por candidatos + validação DV
# ---------------------------------------------------------------------------


def _extrair_chave_validada(texto: str) -> str | None:
    """
    Gera candidatos de chave por múltiplas estratégias e valida DV.
    Devolve apenas candidato com DV válido ou None.
    """
    candidatos = []

    # Estratégia 1: chave contínua de 44 dígitos
    for m in _RE_CHAVE_CONTINUA.finditer(texto):
        candidatos.append(m.group(1))

    # Estratégia 2: 11 grupos de 4 dígitos próximos (gap ≤ 50 chars)
    matches = list(_RE_GRUPO_4.finditer(texto))
    for i in range(len(matches) - 10):
        janela = matches[i:i + 11]
        valida = all(
            janela[j + 1].start() - janela[j].end() <= 50
            for j in range(len(janela) - 1)
        )
        if valida:
            candidatos.append("".join(m.group() for m in janela))

    # Estratégia 3: após marcador "CHAVE DE ACESSO"
    m_marcador = _RE_MARCADOR_CHAVE.search(texto)
    if m_marcador:
        texto_apos = texto[m_marcador.end():]
        # Tentar chave contínua após marcador
        m_cont = _RE_CHAVE_CONTINUA.search(texto_apos)
        if m_cont:
            candidatos.append(m_cont.group(1))
        # Tentar grupos de 4 após marcador
        grupos_apos = list(_RE_GRUPO_4.finditer(texto_apos))
        if len(grupos_apos) >= 11:
            candidatos.append("".join(m.group() for m in grupos_apos[:11]))

    # Validar cada candidato pelo DV
    for candidato in candidatos:
        if len(candidato) == 44 and chave_nfe_valida(candidato):
            return candidato

    return None
