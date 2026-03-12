from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Empresa
from app.security import get_usuario_atual

router = APIRouter(prefix="/empresas", tags=["empresas"])


@router.get("/")
def listar_empresas(
    db: Session = Depends(get_db),
    usuario_atual=Depends(get_usuario_atual),
):
    """Lista apenas empresas do usuário logado (multi-tenant)."""
    empresas = db.query(Empresa).filter(Empresa.user_id == usuario_atual.id).all()
    return empresas
