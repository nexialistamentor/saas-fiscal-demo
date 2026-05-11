"""
Testes da auditoria documental soberana.
"""

import hashlib
from datetime import datetime

from app.services.document_ingestion.audit import (
    VERSAO_PIPELINE,
    EvidenciaDocumental,
    _hash_documento,
    criar_evidencia,
)
from app.services.document_ingestion.classifier import TipoDocumento
from app.services.document_ingestion.confidence import DecisaoProcessamento
from app.services.document_ingestion.normalizer import (
    DocumentoFiscalNormalizado,
    normalizar,
)


CONTEUDO = b"documento fiscal de teste"
SCORE = 95.0
DECISAO = DecisaoProcessamento.AUTO_PROCESSAR


def _doc_normalizado() -> DocumentoFiscalNormalizado:
    return normalizar(
        "CNPJ 12.345.678/0001-90 CFOP 5102 Valor Total R$ 1.000,00",
        SCORE,
    )


# ---------------------------------------------------------------------------
# Hash
# ---------------------------------------------------------------------------
def test_hash_sha256_correcto():
    esperado = hashlib.sha256(CONTEUDO).hexdigest()
    assert _hash_documento(CONTEUDO) == esperado


def test_hash_deterministico():
    assert _hash_documento(CONTEUDO) == _hash_documento(CONTEUDO)


def test_hash_diferente_para_conteudos_diferentes():
    assert _hash_documento(b"doc_a") != _hash_documento(b"doc_b")


def test_hash_muda_quando_conteudo_muda_um_byte():
    """Imutabilidade logica: qualquer alteracao no conteudo gera hash diferente."""
    original = b"documento fiscal original"
    alterado = b"documento fiscal origimal"  # um byte diferente
    assert _hash_documento(original) != _hash_documento(alterado)


# ---------------------------------------------------------------------------
# EvidenciaDocumental
# ---------------------------------------------------------------------------
def test_cria_evidencia_retorna_tipo_correcto():
    ev = criar_evidencia(
        conteudo_original=CONTEUDO,
        tipo=TipoDocumento.PDF_DIGITAL,
        score_confianca=SCORE,
        decisao=DECISAO,
        documento_normalizado=_doc_normalizado(),
    )
    assert isinstance(ev, EvidenciaDocumental)


def test_evidencia_hash_preenchido():
    ev = criar_evidencia(
        conteudo_original=CONTEUDO,
        tipo=TipoDocumento.PDF_DIGITAL,
        score_confianca=SCORE,
        decisao=DECISAO,
        documento_normalizado=_doc_normalizado(),
    )
    assert ev.documento_hash == hashlib.sha256(CONTEUDO).hexdigest()


def test_evidencia_timestamp_recente():
    antes = datetime.utcnow()
    ev = criar_evidencia(
        conteudo_original=CONTEUDO,
        tipo=TipoDocumento.PDF_DIGITAL,
        score_confianca=SCORE,
        decisao=DECISAO,
        documento_normalizado=_doc_normalizado(),
    )
    depois = datetime.utcnow()
    assert antes <= ev.timestamp <= depois


def test_timestamp_e_momento_geracao_nao_documento():
    """
    timestamp = momento da geracao da evidencia.

    Nao representa: data emissao, data OCR, data homologacao, data persistencia.
    Essas serao entidades separadas em V2.
    """
    ev = criar_evidencia(
        conteudo_original=CONTEUDO,
        tipo=TipoDocumento.PDF_DIGITAL,
        score_confianca=SCORE,
        decisao=DECISAO,
        documento_normalizado=_doc_normalizado(),
    )
    assert isinstance(ev.timestamp, datetime)
    assert ev.timestamp.year >= 2026


def test_evidencia_versao_pipeline():
    ev = criar_evidencia(
        conteudo_original=CONTEUDO,
        tipo=TipoDocumento.PDF_DIGITAL,
        score_confianca=SCORE,
        decisao=DECISAO,
        documento_normalizado=_doc_normalizado(),
    )
    assert ev.versao_pipeline == VERSAO_PIPELINE


def test_evidencia_validado_humano_false_por_defeito():
    ev = criar_evidencia(
        conteudo_original=CONTEUDO,
        tipo=TipoDocumento.PDF_DIGITAL,
        score_confianca=SCORE,
        decisao=DECISAO,
        documento_normalizado=_doc_normalizado(),
    )
    assert ev.validado_humano is False
    assert ev.validado_por is None


def test_evidencia_campos_extraidos():
    ev = criar_evidencia(
        conteudo_original=CONTEUDO,
        tipo=TipoDocumento.PDF_DIGITAL,
        score_confianca=SCORE,
        decisao=DECISAO,
        documento_normalizado=_doc_normalizado(),
    )
    assert "cnpj_emitente" in ev.campos_extraidos
    assert "cfop" in ev.campos_extraidos


def test_evidencia_tamanho_bytes():
    ev = criar_evidencia(
        conteudo_original=CONTEUDO,
        tipo=TipoDocumento.PDF_DIGITAL,
        score_confianca=SCORE,
        decisao=DECISAO,
        documento_normalizado=_doc_normalizado(),
    )
    assert ev.tamanho_bytes == len(CONTEUDO)


def test_evidencia_nome_ficheiro_opcional():
    ev = criar_evidencia(
        conteudo_original=CONTEUDO,
        tipo=TipoDocumento.PDF_DIGITAL,
        score_confianca=SCORE,
        decisao=DECISAO,
        documento_normalizado=_doc_normalizado(),
        nome_ficheiro="fatura_maio.pdf",
    )
    assert ev.nome_ficheiro == "fatura_maio.pdf"


def test_evidencia_sem_nome_ficheiro():
    ev = criar_evidencia(
        conteudo_original=CONTEUDO,
        tipo=TipoDocumento.PDF_DIGITAL,
        score_confianca=SCORE,
        decisao=DECISAO,
        documento_normalizado=_doc_normalizado(),
    )
    assert ev.nome_ficheiro is None


def test_dois_documentos_iguais_mesmo_hash():
    ev1 = criar_evidencia(
        conteudo_original=CONTEUDO,
        tipo=TipoDocumento.PDF_DIGITAL,
        score_confianca=SCORE,
        decisao=DECISAO,
        documento_normalizado=_doc_normalizado(),
    )
    ev2 = criar_evidencia(
        conteudo_original=CONTEUDO,
        tipo=TipoDocumento.PDF_DIGITAL,
        score_confianca=SCORE,
        decisao=DECISAO,
        documento_normalizado=_doc_normalizado(),
    )
    assert ev1.documento_hash == ev2.documento_hash
