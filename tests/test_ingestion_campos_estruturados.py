"""
Teste de integração mínimo: pipeline do router → campos_estruturados.

Segue o padrão de test_document_audit.py (criar_evidencia + normalizar),
sem fixture HTTP nova — valida coerência entre evidência V1 e serialização CT-DOC-001.
"""

import hashlib

from app.services.document_ingestion.audit import criar_evidencia
from app.services.document_ingestion.classifier import TipoDocumento
from app.services.document_ingestion.confidence import DecisaoProcessamento
from app.services.document_ingestion.normalizer import normalizar
from app.services.document_ingestion.serializacao import (
    _CAMPOS_VOCABULARIO,
    serializar_campos_estruturados,
)

CONTEUDO = b"documento fiscal de teste"
SCORE = 95.0
DECISAO = DecisaoProcessamento.AUTO_PROCESSAR


def _doc_normalizado():
    return normalizar(
        "CNPJ 12.345.678/0001-90 CFOP 5102 Valor Total R$ 1.000,00",
        SCORE,
    )


def test_pipeline_router_produz_campos_estruturados_coerentes_com_evidencia():
    doc_norm = _doc_normalizado()
    evidencia = criar_evidencia(
        conteudo_original=CONTEUDO,
        tipo=TipoDocumento.PDF_DIGITAL,
        score_confianca=SCORE,
        decisao=DECISAO,
        documento_normalizado=doc_norm,
    )
    campos = serializar_campos_estruturados(doc_norm)

    assert len(campos) == 13
    assert set(campos.keys()) == set(_CAMPOS_VOCABULARIO)

    extraidos_por_valor = [
        nome for nome in _CAMPOS_VOCABULARIO if campos[nome]["valor"] is not None
    ]
    assert set(evidencia.campos_extraidos) == set(extraidos_por_valor)
    assert "cnpj_emitente" in evidencia.campos_extraidos
    assert campos["cnpj_emitente"]["confianca"] > 0.0
    assert campos["cnpj_emitente"]["origem"] is not None

    assert hashlib.sha256(CONTEUDO).hexdigest() == evidencia.documento_hash
