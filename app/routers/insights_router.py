from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.rate_limit import limiter
from app.security import tenant_empresa
from app.services.insights_engine import InsightEngine

router = APIRouter()


@router.post("/insights/{empresa_id}")
@limiter.limit("10/minute")
def obter_insights(
    request: Request,
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    engine = InsightEngine(db)
    return engine.gerar_insights_empresa(empresa.id)
