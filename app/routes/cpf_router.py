from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.security import get_usuario_atual
from app.services.cpf_dashboard_service import CPFDashboardService
from app.models import TIPOS_RENDIMENTO

router = APIRouter(prefix="/cpf", tags=["CPF"])


class CPFRequest(BaseModel):
    faturamento_mensal: float
    despesas: float = 0


class RendimentoConfirmado(BaseModel):
    tipo_rendimento: str
    descricao: str | None = None
    valor: float | None = Field(default=None, ge=0)
    ano_referencia: int | None = Field(default=None, ge=2000, le=2100)
    mes_referencia: int | None = Field(default=None, ge=1, le=12)
    fonte_pagadora: str | None = None
    confianca_extracao: str = "manual"
    campos_corrigidos: dict | None = None


@router.post("/dashboard")
def dashboard_cpf(dados: CPFRequest):
    service = CPFDashboardService()
    return service.calcular_resumo(
        faturamento_mensal=dados.faturamento_mensal,
        despesas=dados.despesas
    )


@router.post("/documentos/upload")
async def upload_documento_rendimento(
    file: UploadFile = File(...),
    usuario_atual: models.User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    conteudo = await file.read()
    if len(conteudo) == 0:
        raise HTTPException(status_code=400, detail="Ficheiro vazio.")
    return {
        "arquivo_nome": file.filename,
        "tamanho": len(conteudo),
        "instrucao": "Confirme os campos extraídos e submeta em /cpf/documentos/confirmar"
    }


@router.post("/documentos/confirmar")
def confirmar_documento_rendimento(
    dados: RendimentoConfirmado,
    usuario_atual: models.User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    if dados.tipo_rendimento not in TIPOS_RENDIMENTO:
        raise HTTPException(
            status_code=422,
            detail=f"tipo_rendimento inválido. Valores aceites: {TIPOS_RENDIMENTO}"
        )
    doc = models.DocumentoRendimento(
        user_id=usuario_atual.id,
        tipo_rendimento=dados.tipo_rendimento,
        descricao=dados.descricao,
        valor=dados.valor,
        ano_referencia=dados.ano_referencia,
        mes_referencia=dados.mes_referencia,
        fonte_pagadora=dados.fonte_pagadora,
        confianca_extracao=dados.confianca_extracao,
        campos_corrigidos=dados.campos_corrigidos,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "status": "persistido"}
