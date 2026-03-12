from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas.user_schema import UserCreate, UserResponse
from app.security import hash_senha, verificar_senha, criar_token, get_usuario_atual

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):

    existing_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    plano_basico = db.query(models.Plano).filter(
        models.Plano.nome == "Basico"
    ).first()

    if not plano_basico:
        raise HTTPException(status_code=400, detail="Plano Basico não existe")

    hashed = hash_senha(user.password)

    new_user = models.User(
        email=user.email,
        hashed_password=hashed,
        plano_id=plano_basico.id
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):

    usuario = db.query(models.User).filter(
        models.User.email == form_data.username
    ).first()

    if not usuario:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    if not verificar_senha(form_data.password, usuario.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    token = criar_token({"sub": usuario.email})

    return {"access_token": token, "token_type": "bearer"}