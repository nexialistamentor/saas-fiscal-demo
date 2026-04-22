import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas.user_schema import UserCreate, UserResponse, UserSession
from app.security import hash_senha, verificar_senha, criar_token, get_usuario_atual
from app.seed_data import ensure_planos
from app.rate_limit import limiter, login_throttle

router = APIRouter(prefix="/auth", tags=["Auth"])


def _consulta_liberada_no_registro() -> bool:
    v = os.environ.get("LIBERAR_CONSULTA_REGISTRO", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    url = os.environ.get("DATABASE_URL", "")
    return "sqlite" in url


@router.post("/register", response_model=UserResponse)
@limiter.limit("3/minute")
def register_user(request: Request, user: UserCreate, db: Session = Depends(get_db)) -> UserResponse:

    existing_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    ensure_planos(db)

    plano_basico = db.query(models.Plano).filter(
        models.Plano.nome == "Basico"
    ).first()

    if not plano_basico:
        raise HTTPException(status_code=500, detail="Falha ao garantir planos no banco")

    hashed = hash_senha(user.password)

    new_user = models.User(
        email=user.email,
        hashed_password=hashed,
        plano_id=plano_basico.id,
        consulta_paga=_consulta_liberada_no_registro(),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    empresa_id = None

    if user.tipo_usuario == "cpf":
        if user.documento:
            new_user.cpf = user.documento.strip()
            db.commit()
            db.refresh(new_user)
    else:
        regime = "mei" if user.tipo_usuario == "mei" else "simples"
        emp = models.Empresa(
            razao_social=user.nome.strip() if user.nome else None,
            regime_tributario=regime,
            cnpj=user.documento.strip() if user.documento else None,
            user_id=new_user.id,
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)
        empresa_id = emp.id

    return UserResponse(id=new_user.id, email=new_user.email, empresa_id=empresa_id, role=new_user.role)


@router.post("/login")
@limiter.limit("5/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> dict[str, str]:

    email = form_data.username

    if login_throttle.esta_bloqueado(email):
        restante = login_throttle.tempo_restante(email)
        raise HTTPException(
            status_code=429,
            detail=f"Conta temporariamente bloqueada. Tente novamente em {restante}s.",
            headers={"Retry-After": str(restante)},
        )

    usuario = db.query(models.User).filter(
        models.User.email == email,
    ).first()

    if not usuario:
        login_throttle.registrar_falha(email)
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    if not verificar_senha(form_data.password, usuario.hashed_password):
        login_throttle.registrar_falha(email)
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    login_throttle.limpar(email)
    token = criar_token({"sub": usuario.email})

    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserSession)
def me(usuario_atual: models.User = Depends(get_usuario_atual)) -> UserSession:
    return usuario_atual