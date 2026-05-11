"""
Auditoria documental soberana.

Responsabilidade única: construir evidência auditável do processamento
de um documento. Sem persistência — sem side effects.

Princípio: a evidência existe antes da persistência.
O que persistir e onde é responsabilidade do router/service layer.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from app.services.document_ingestion.classifier import TipoDocumento
from app.services.document_ingestion.confidence import DecisaoProcessamento
from app.services.document_ingestion.normalizer import DocumentoFiscalNormalizado

# Versão do pipeline — incrementar a cada alteração arquitectural relevante
VERSAO_PIPELINE = "1.0.0"


@dataclass
class EvidenciaDocumental:
    # Identidade do documento
    documento_hash: str  # SHA-256 dos bytes originais
    timestamp: datetime
    versao_pipeline: str

    # Classificação
    tipo_documento: TipoDocumento

    # Confiança e decisão
    score_confianca: float
    decisao: DecisaoProcessamento
    requereu_ocr: bool

    # Campos extraídos
    campos_extraidos: list[str]
    campos_nao_extraidos: list[str]

    # Estado humano
    validado_humano: bool = False
    validado_por: str | None = None  # CRC do contador — V2
    validado_em: datetime | None = None

    # Motivos da decisão
    motivos: list[str] = field(default_factory=list)

    # Metadata
    nome_ficheiro: str | None = None
    tamanho_bytes: int = 0


def criar_evidencia(
    conteudo_original: bytes,
    tipo: TipoDocumento,
    score_confianca: float,
    decisao: DecisaoProcessamento,
    documento_normalizado: DocumentoFiscalNormalizado,
    requereu_ocr: bool = False,
    motivos: list[str] | None = None,
    nome_ficheiro: str | None = None,
) -> EvidenciaDocumental:
    """
    Constrói evidência auditável do processamento documental.
    Não persiste — devolve objecto para o caller persistir.
    """
    return EvidenciaDocumental(
        documento_hash=_hash_documento(conteudo_original),
        timestamp=datetime.utcnow(),
        versao_pipeline=VERSAO_PIPELINE,
        tipo_documento=tipo,
        score_confianca=score_confianca,
        decisao=decisao,
        requereu_ocr=requereu_ocr,
        campos_extraidos=_campos_extraidos(documento_normalizado),
        campos_nao_extraidos=documento_normalizado.campos_nao_extraidos,
        validado_humano=False,
        motivos=motivos or [],
        nome_ficheiro=nome_ficheiro,
        tamanho_bytes=len(conteudo_original),
    )


def _hash_documento(conteudo: bytes) -> str:
    """SHA-256 dos bytes originais — rastreabilidade forte."""
    return hashlib.sha256(conteudo).hexdigest()


def _campos_extraidos(doc: DocumentoFiscalNormalizado) -> list[str]:
    """Lista campos que foram extraídos com sucesso."""
    campos = [
        "cnpj_emitente",
        "cnpj_destinatario",
        "cpf_destinatario",
        "chave_acesso",
        "cfop",
        "ncm",
        "valor_total",
        "base_calculo",
        "aliquota_icms",
        "valor_icms",
        "aliquota_pis",
        "aliquota_cofins",
        "data_emissao",
    ]
    return [c for c in campos if getattr(doc, c) is not None]
