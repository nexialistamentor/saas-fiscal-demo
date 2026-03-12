from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DocumentoFiscal, Empresa
from app.security import get_usuario_atual

router = APIRouter(prefix="/documentos", tags=["documentos"])


@router.get("/")
def listar_documentos(
    db: Session = Depends(get_db),
    usuario_atual=Depends(get_usuario_atual),
):
    """Lista documentos fiscais apenas das empresas do usuário (multi-tenant)."""
    ids_empresas = [e.id for e in db.query(Empresa).filter(Empresa.user_id == usuario_atual.id).all()]
    docs = (
        db.query(DocumentoFiscal)
        .filter(DocumentoFiscal.empresa_id.in_(ids_empresas))
        .all()
    )
    return docs
