from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import tenant_empresa
from app.services.st_service import STAnalyzer
from app import models

router = APIRouter(prefix="/analise-st", tags=["Analise ST"])


@router.get("/{empresa_id}")
def analisar_st(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    analyzer = STAnalyzer()
    return analyzer.calcular_restituicao(db, empresa.id)


@router.get("/resumo/{empresa_id}")
def resumo_st(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    analyzer = STAnalyzer()
    return analyzer.calcular_restituicao(db, empresa.id)


@router.get("/ncm/{empresa_id}")
def analise_st_ncm(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return STAnalyzer().analise_por_ncm(db, empresa.id)


@router.get("/periodo/{empresa_id}")
def analise_st_periodo(
    data_inicio: date = Query(..., description="Data início do período"),
    data_fim: date = Query(..., description="Data fim do período"),
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return STAnalyzer().analise_por_periodo(db, empresa.id, data_inicio, data_fim)
