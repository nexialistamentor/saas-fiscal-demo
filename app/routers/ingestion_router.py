"""
Router de ingestão documental (pipeline soberano).

Monta classificação → extracção → confiança → normalização → evidência → persistência.
"""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DocumentoIngerido, Empresa, User
from app.rate_limit import limiter
from app.security import get_usuario_atual
from app.services.document_ingestion.audit import criar_evidencia
from app.services.document_ingestion.classifier import TipoDocumento, classificar
from app.services.document_ingestion.confidence import calcular
from app.services.document_ingestion.extractor import extrair
from app.services.document_ingestion.normalizer import normalizar
from app.services.document_ingestion.serializacao import serializar_campos_estruturados

router = APIRouter(prefix="/ingestao", tags=["ingestao"])

_MIME_ACEITES = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/tiff",
    }
)


@router.post("/documentos")
@limiter.limit("30/minute")
async def ingerir_documento(
    request: Request,
    file: UploadFile = File(...),
    empresa_id: int | None = None,
    db: Session = Depends(get_db),
    usuario_atual: User = Depends(get_usuario_atual),
):
    # 1. MIME como heurística inicial — bytes validados pelo classifier
    if file.content_type and file.content_type not in _MIME_ACEITES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Tipo não suportado: {file.content_type}. "
                "Aceites: PDF, JPEG, PNG, TIFF"
            ),
        )

    conteudo = await file.read()
    if not conteudo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ficheiro vazio.",
        )

    res_cls = classificar(conteudo, nome_ficheiro=file.filename or "")
    if res_cls.tipo == TipoDocumento.UNKNOWN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=res_cls.motivo_rejeicao or "Documento não reconhecido.",
        )

    res_ext = extrair(conteudo, res_cls.tipo)
    if res_ext.erro:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=res_ext.erro,
        )

    res_conf = calcular(res_ext.texto, requer_ocr=res_ext.requer_ocr)
    doc_norm = normalizar(res_ext.texto, res_conf.score)

    evidencia = criar_evidencia(
        conteudo_original=conteudo,
        tipo=res_cls.tipo,
        score_confianca=res_conf.score,
        decisao=res_conf.decisao,
        documento_normalizado=doc_norm,
        requereu_ocr=res_ext.requer_ocr,
        motivos=res_conf.motivos,
        nome_ficheiro=file.filename,
    )

    # 7a. Deduplicação soberana — SHA-256 como verdade
    documento_existente = (
        db.query(DocumentoIngerido)
        .filter(DocumentoIngerido.conteudo_sha256 == evidencia.documento_hash)
        .first()
    )
    if documento_existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "erro": "Documento já ingerido anteriormente.",
                "id": documento_existente.id,
                "documento_hash": documento_existente.conteudo_sha256,
                "evidencia_em": documento_existente.evidencia_em.isoformat(),
            },
        )

    empresa_fk = None
    if empresa_id is not None:
        emp = (
            db.query(Empresa)
            .filter(Empresa.id == empresa_id, Empresa.user_id == usuario_atual.id)
            .first()
        )
        if not emp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa não encontrada.",
            )
        empresa_fk = emp.id

    # 7b. Persistir — V1 síncrono. V2: service layer transacional com fila/OCR/ledger.
    registo = DocumentoIngerido(
        user_id=usuario_atual.id,
        empresa_id=empresa_fk,
        conteudo_sha256=evidencia.documento_hash,
        evidencia_em=evidencia.timestamp,
        versao_pipeline=evidencia.versao_pipeline,
        tipo_documento=evidencia.tipo_documento.value,
        score_confianca=evidencia.score_confianca,
        decisao=evidencia.decisao.value,
        requereu_ocr=evidencia.requereu_ocr,
        campos_extraidos=evidencia.campos_extraidos,
        campos_estruturados=serializar_campos_estruturados(doc_norm),
        campos_nao_extraidos=evidencia.campos_nao_extraidos,
        motivos=evidencia.motivos,
        validado_humano=evidencia.validado_humano,
        validado_por=evidencia.validado_por,
        validado_em=evidencia.validado_em,
        nome_ficheiro=evidencia.nome_ficheiro,
        tamanho_bytes=evidencia.tamanho_bytes,
    )
    db.add(registo)
    db.commit()
    db.refresh(registo)

    return {
        "id": registo.id,
        "documento_hash": registo.conteudo_sha256,
        "decisao": registo.decisao,
        "score_confianca": registo.score_confianca,
    }
