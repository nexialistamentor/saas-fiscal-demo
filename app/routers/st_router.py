from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_usuario_atual
from app.services.st_service import STAnalyzer
from app import models

router = APIRouter(prefix="/analise-st", tags=["Analise ST"])


@router.get("/{empresa_id}")
def analisar_st(
    empresa_id: int,
    db: Session = Depends(get_db),
):
    empresa = (
        db.query(models.Empresa)
        .filter(models.Empresa.id == empresa_id)
        .first()
    )

    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    analyzer = STAnalyzer()
    resultado = analyzer.calcular_restituicao(db, empresa_id)

    return resultado


@router.get("/resumo/{empresa_id}")
def resumo_st(
    empresa_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    empresa = (
        db.query(models.Empresa)
        .filter(models.Empresa.id == empresa_id)
        .first()
    )

    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    if empresa.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=403, detail="Acesso negado a esta empresa")

    analyzer = STAnalyzer()
    resultado = analyzer.calcular_restituicao(db, empresa_id)

    return resultado


@router.get("/ncm/{empresa_id}")
def analise_st_ncm(
    empresa_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    empresa = (
        db.query(models.Empresa)
        .filter(models.Empresa.id == empresa_id)
        .first()
    )
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    if empresa.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=403, detail="Acesso negado a esta empresa")
    analyzer = STAnalyzer()
    return analyzer.analise_por_ncm(db, empresa_id)


@router.get("/periodo/{empresa_id}")
def analise_st_periodo(
    empresa_id: int,
    data_inicio: date = Query(..., description="Data início do período"),
    data_fim: date = Query(..., description="Data fim do período"),
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    empresa = (
        db.query(models.Empresa)
        .filter(models.Empresa.id == empresa_id)
        .first()
    )
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    if empresa.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=403, detail="Acesso negado a esta empresa")
    return STAnalyzer().analise_por_periodo(db, empresa_id, data_inicio, data_fim)
