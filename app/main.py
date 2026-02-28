from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import engine, SessionLocal, get_db
from app import models
from app.xml_service import ler_xml_unico

from app.schemas.user_schema import (
    UserCreate,
    UserResponse,
)

from app.security import hash_senha, verificar_senha, criar_token, get_usuario_atual
import os

app = FastAPI()


@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)
# Cria tabelas automaticamente

# models.Base.metadata.create_all(bind=engine)

# ===============================
# CRIAR PLANO BASICO SE NÃO EXISTIR
# ===============================

from app.database import SessionLocal

# db = SessionLocal()

# plano_existente = db.query(models.Plano).filter(
#     models.Plano.nome == "Basico"
# ).first()

# if not plano_existente:
#     plano = models.Plano(
#         nome="Basico",
#         limite_cnpjs=3
#     )
#     db.add(plano)
#     db.commit()

# db.close()




# ===============================
# TESTE DE CONEXÃO COM BANCO
# ===============================

from sqlalchemy import text

@app.get("/teste-banco")
def teste_banco():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        return {
            "status": "Banco conectado",
            "resultado": result.scalar()
        }

@app.post("/register", response_model=UserResponse)
def register_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    # Verifica se email já existe
    existing_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if existing_user:
        return {"error": "Email já cadastrado"}

    # Cria usuário com senha criptografada
    hashed = hash_senha(user.password)

    plano_basico = db.query(models.Plano).filter(
        models.Plano.nome == "Basico"
    ).first()

    new_user = models.User(
        email=user.email,
        hashed_password=hashed,
        plano_id=plano_basico.id
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user
# ===============================
# UPLOAD E SALVAR XML
# ===============================

@app.post("/upload-xml")
async def upload_xml(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual)
):
    # Conta quantas empresas o usuário já tem
    total_empresas = db.query(models.Empresa).filter(
        models.Empresa.user_id == usuario_atual.id
    ).count()

    # Busca limite do plano
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

    caminho = os.path.join(pasta, "xml_temp.xml")

    conteudo = await file.read()

    with open(caminho, "wb") as f:
        f.write(conteudo)

    dados = ler_xml_unico(caminho)

    nova_empresa = models.Empresa(
        cnpj=dados.get("cnpj"),
        razao_social=dados.get("razao_social"),
        user_id=usuario_atual.id
    )

    db.add(nova_empresa)
    db.commit()

    return {"mensagem": "XML salvo no banco com sucesso"}
    




# ===============================
# LISTAR EMPRESAS
# ===============================

@app.get("/empresas")
def listar_empresas(db: Session = Depends(get_db)):
    empresas = db.query(models.Empresa).all()
    return empresas
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.security import verificar_senha, criar_token


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from fastapi.security import OAuth2PasswordRequestForm

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