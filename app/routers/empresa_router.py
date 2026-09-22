from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Empresa
from app.security import get_usuario_atual, tenant_empresa
from app.services.vinculo_service import listar_vinculos_visao_empresa

router = APIRouter(prefix="/empresas", tags=["empresas"])


class EmpresaCnpjUpdate(BaseModel):
    cnpj: str

    @field_validator("cnpj")
    @classmethod
    def validar_cnpj(cls, value: str) -> str:
        digits = "".join(c for c in value if c.isdigit())
        if len(digits) != 14:
            raise ValueError("CNPJ deve ter 14 dígitos")
        return digits


@router.get("/")
def listar_empresas(
    db: Session = Depends(get_db),
    usuario_atual=Depends(get_usuario_atual),
):
    """Lista apenas empresas do usuário logado (multi-tenant)."""
    empresas = db.query(Empresa).filter(Empresa.user_id == usuario_atual.id).all()
    return empresas


@router.patch("/{empresa_id}/cnpj")
def completar_cnpj_mei(
    body: EmpresaCnpjUpdate,
    empresa: Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    if empresa.regime_tributario != "mei":
        raise HTTPException(
            status_code=422,
            detail="CNPJ por este fluxo é permitido apenas para MEI",
        )

    if empresa.cnpj:
        raise HTTPException(
            status_code=409,
            detail="Empresa já possui CNPJ cadastrado",
        )

    conflito = (
        db.query(Empresa)
        .filter(
            Empresa.cnpj == body.cnpj,
            Empresa.id != empresa.id,
        )
        .first()
    )
    if conflito is not None:
        raise HTTPException(
            status_code=409,
            detail="CNPJ já vinculado a outra empresa",
        )

    empresa.cnpj = body.cnpj
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="CNPJ j? vinculado a outra empresa",
        ) from None

    db.refresh(empresa)

    return {
        "empresa_id": empresa.id,
        "cnpj": empresa.cnpj,
    }


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
