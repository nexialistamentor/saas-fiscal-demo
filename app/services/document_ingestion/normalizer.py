"""
Normalizador documental soberano.

Responsabilidade única: dado texto extraído, estruturar campos fiscais
em schema tipado para consumo pelo motor fiscal.

NÃO interpreta regras fiscais — só extrai, limpa e estrutura.
Interpretação fiscal pertence ao motor_fiscal.

AVISO ARQUITECTURAL V1:
    confiança por campo usa score global do confidence.py.
    V2: score individual por campo via OCR word-level confidence.
    V3: validação cruzada entre campos (CNPJ × chave de acesso × valor).
"""

import re
from dataclasses import dataclass, field


@dataclass
class CampoNormalizado:
    valor: str | None
    confianca: float  # 0.0 – 100.0 herdada do score global V1
    origem: str  # "regex", "ocr", "manual"
    validado_humano: bool = False


@dataclass
class DocumentoFiscalNormalizado:
    # Identificação
    cnpj_emitente: CampoNormalizado | None = None
    cnpj_destinatario: CampoNormalizado | None = None
    cpf_destinatario: CampoNormalizado | None = None
    chave_acesso: CampoNormalizado | None = None

    # Classificação fiscal
    cfop: CampoNormalizado | None = None
    ncm: CampoNormalizado | None = None

    # Valores
    valor_total: CampoNormalizado | None = None
    base_calculo: CampoNormalizado | None = None
    aliquota_icms: CampoNormalizado | None = None
    valor_icms: CampoNormalizado | None = None
    aliquota_pis: CampoNormalizado | None = None
    aliquota_cofins: CampoNormalizado | None = None

    # Datas
    data_emissao: CampoNormalizado | None = None

    # Meta
    campos_nao_extraidos: list[str] = field(default_factory=list)
    texto_original_len: int = 0


# ---------------------------------------------------------------------------
# Regex soberanos — compilados uma vez
# ---------------------------------------------------------------------------
_RE_CNPJ = re.compile(r"\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\/\s]?\d{4}[-\s]?\d{2}")
_RE_CPF = re.compile(r"\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[-\s]?\d{2}")
_RE_CHAVE = re.compile(r"\d{44}")
_RE_CFOP = re.compile(r"\b[1-9]\d{3}\b")
_RE_NCM = re.compile(r"\b\d{8}\b")
# Exige símbolo monetário para não confundir CNPJ (12.345.678/...) com valor.
_RE_VALOR = re.compile(
    r"(?i)(?:R\s*\$|\$)\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)"
)
_RE_DATA = re.compile(r"\b(\d{2}[\/\-]\d{2}[\/\-]\d{4})\b")
_RE_ALIQ = re.compile(r"(\d{1,2}(?:,\d{1,2})?)\s*%")


def normalizar(texto: str, score_confianca: float) -> DocumentoFiscalNormalizado:
    """
    Normaliza texto extraído para schema fiscal tipado.
    score_confianca: score global do confidence.py (V1).
    """
    doc = DocumentoFiscalNormalizado(texto_original_len=len(texto))
    nao_extraidos = []

    def campo(valor: str | None, nome: str) -> CampoNormalizado | None:
        if valor is None:
            nao_extraidos.append(nome)
            return None
        return CampoNormalizado(
            valor=_limpar(valor),
            confianca=score_confianca,
            origem="regex",
        )

    # CNPJ — primeiro match = emitente, segundo = destinatário
    cnpjs = _RE_CNPJ.findall(texto)
    doc.cnpj_emitente = campo(cnpjs[0] if len(cnpjs) > 0 else None, "cnpj_emitente")
    doc.cnpj_destinatario = campo(cnpjs[1] if len(cnpjs) > 1 else None, "cnpj_destinatario")

    # CPF (só se não há CNPJ destinatário)
    if doc.cnpj_destinatario is None:
        cpfs = _RE_CPF.findall(texto)
        doc.cpf_destinatario = campo(cpfs[0] if cpfs else None, "cpf_destinatario")

    # Chave de acesso NF-e (44 dígitos)
    chaves = _RE_CHAVE.findall(texto)
    doc.chave_acesso = campo(chaves[0] if chaves else None, "chave_acesso")

    # CFOP
    cfops = _RE_CFOP.findall(texto)
    doc.cfop = campo(cfops[0] if cfops else None, "cfop")

    # NCM (8 dígitos — exclui chave de acesso)
    ncms = [m for m in _RE_NCM.findall(texto) if len(m) == 8]
    doc.ncm = campo(ncms[0] if ncms else None, "ncm")

    # Valores monetários
    valores = _RE_VALOR.findall(texto)
    doc.valor_total = campo(valores[0] if len(valores) > 0 else None, "valor_total")
    doc.base_calculo = campo(valores[1] if len(valores) > 1 else None, "base_calculo")

    # Alíquotas
    aliquotas = _RE_ALIQ.findall(texto)
    doc.aliquota_icms = campo(aliquotas[0] if len(aliquotas) > 0 else None, "aliquota_icms")
    doc.aliquota_pis = campo(aliquotas[1] if len(aliquotas) > 1 else None, "aliquota_pis")
    doc.aliquota_cofins = campo(aliquotas[2] if len(aliquotas) > 2 else None, "aliquota_cofins")

    # Data de emissão
    datas = _RE_DATA.findall(texto)
    doc.data_emissao = campo(datas[0] if datas else None, "data_emissao")

    doc.campos_nao_extraidos = nao_extraidos
    return doc


def _limpar(valor: str) -> str:
    """Remove espaços duplos e strip."""
    return re.sub(r"\s+", " ", valor).strip()
