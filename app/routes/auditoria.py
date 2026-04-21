from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app import models
from app.agents.agent_estoque import salvar_auditoria
from app.database import get_db
from app.rate_limit import limiter
from app.security import tenant_empresa

router = APIRouter()


@router.post("/auditar")
@limiter.limit("10/minute")
def auditar_estoque(
    request: Request,
    empresa: models.Empresa = Depends(tenant_empresa),
):
    salvar_auditoria(empresa_id=empresa.id)
    return {"status": "auditoria executada", "empresa_id": empresa.id}
