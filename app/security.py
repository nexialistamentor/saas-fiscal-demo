from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = "SUA_CHAVE_SUPER_SECRETA_AQUI"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_senha(senha: str):
    return pwd_context.hash(senha)


def verificar_senha(senha_plana, senha_hash):
    return pwd_context.verify(senha_plana, senha_hash)


def criar_token(dados: dict):
    dados_copia = dados.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    dados_copia.update({"exp": expire})
    token = jwt.encode(dados_copia, SECRET_KEY, algorithm=ALGORITHM)
    return token


def verificar_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from app.database import get_db
from app import models
from sqlalchemy.orm import Session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")





def get_usuario_atual(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = verificar_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token inválido")

    email = payload.get("sub")
    usuario = db.query(models.User).filter(models.User.email == email).first()

    if usuario is None:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")

    return usuario