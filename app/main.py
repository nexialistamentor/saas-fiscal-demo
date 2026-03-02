from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
import os

from app.database import engine, SessionLocal, get_db
from app import models
from app.routers.auth_router import router as auth_router
from app.xml_service import ler_xml_unico
from app.schemas.user_schema import UserCreate, UserResponse
from app.security import hash_senha, verificar_senha, criar_token, get_usuario_atual


app = FastAPI(title="API Fiscal SaaS", version="0.1.0")


app.include_router(auth_router)


@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"message": "API Fiscal SaaS ativa"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/teste-banco")
def teste_banco():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        return {
            "status": "Banco conectado",
            "resultado": result.scalar()
        }


@app.post("/register", response_model=UserResponse)
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


@app.post("/login")
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


@app.post("/upload-xml")
async def upload_xml(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual)
):

    total_empresas = db.query(models.Empresa).filter(
        models.Empresa.user_id == usuario_atual.id
    ).count()

    plano = db.query(models.Plano).filter(
        models.Plano.id == usuario_atual.plano_id
    ).first()

    if total_empresas >= plano.limite_cnpjs:
        raise HTTPException(
            status_code=403,
            detail="Limite de CNPJs atingido para seu plano"
        )

    pasta = "app/xmls_testes"
    os.makedirs(pasta, exist_ok=True)

    caminho = os.path.join(pasta, file.filename)

    conteudo = await file.read()

    with open(caminho, "wb") as f:
        f.write(conteudo)

    dados = ler_xml_unico(caminho)

    return dados


@app.post("/criar-planos")
def criar_planos(db: Session = Depends(get_db)):

    planos = [
        models.Plano(nome="Basico", limite_cnpjs=5),
        models.Plano(nome="Pro", limite_cnpjs=10),
        models.Plano(nome="Ilimitado", limite_cnpjs=999999),
    ]

    for plano in planos:
        db.add(plano)

    db.commit()

   return {"mensagem": "Planos criados com sucesso"}