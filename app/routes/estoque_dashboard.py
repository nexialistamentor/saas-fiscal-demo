from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.security import tenant_empresa

router = APIRouter()


@router.get("/divergencias")
def ver_divergencias(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.AuditoriaEstoque)
        .filter(models.AuditoriaEstoque.empresa_id == empresa.id)
        .order_by(models.AuditoriaEstoque.created_at.desc())
        .limit(100)
        .all()
    )

    return [
        {
            "id": r.id,
            "empresa_id": r.empresa_id,
            "ncm": r.ncm,
            "estoque_fiscal": r.estoque_fiscal,
            "estoque_erp": r.estoque_erp,
            "diferenca": r.diferenca,
            "risco_desvio": r.risco_desvio,
            "created_at": str(r.created_at) if r.created_at else None,
        }
        for r in rows
    ]
