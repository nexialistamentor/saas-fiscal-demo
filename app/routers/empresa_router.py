from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Empresa
from app.security import get_usuario_atual, tenant_empresa
from app.services.vinculo_service import listar_vinculos_visao_empresa

router = APIRouter(prefix="/empresas", tags=["empresas"])


@router.get("/")
def listar_empresas(
    db: Session = Depends(get_db),
    usuario_atual=Depends(get_usuario_atual),
):
    """Lista apenas empresas do usuário logado (multi-tenant)."""
    empresas = db.query(Empresa).filter(Empresa.user_id == usuario_atual.id).all()
    return empresas


@router.get("/{empresa_id}/contador-vinculado")
def obter_contador_vinculado(
    empresa: Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    """B10-EMPRESA-01: titular da empresa consulta contador(es) vinculado(s)."""
    return {
        "empresa_id": empresa.id,
        "vinculos": listar_vinculos_visao_empresa(db, empresa.id),
    }
