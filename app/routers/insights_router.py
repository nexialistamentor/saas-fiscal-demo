from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.insights_engine import InsightEngine

router = APIRouter()


@router.get("/insights/{empresa_id}")
def obter_insights(empresa_id: int, db: Session = Depends(get_db)):
    engine = InsightEngine(db)
    return engine.gerar_insights_empresa(empresa_id)
