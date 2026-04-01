import os
import uuid
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = os.environ.get("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY não definida no ambiente")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_senha(senha: str):
    return pwd_context.hash(senha)


def verificar_senha(senha_plana, senha_hash):
    return pwd_context.verify(senha_plana, senha_hash)


def criar_token(dados: dict):
    dados_copia = dados.copy()
    agora = datetime.utcnow()
    expire = agora + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    dados_copia.update({
        "exp": expire,
        "iat": agora,
        "jti": str(uuid.uuid4())
    })

    token = jwt.encode(dados_copia, SECRET_KEY, algorithm=ALGORITHM)
    return token


def verificar_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Validação mínima de integridade do token
        if "jti" not in payload or "iat" not in payload:
            return None

        return payload
    except JWTError:
        return None
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from app.database import get_db
from app import models
from sqlalchemy.orm import Session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")





def get_usuario_atual(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = verificar_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token inválido")

    email = payload.get("sub")
    usuario = db.query(models.User).filter(models.User.email == email).first()

    if usuario is None:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")

    return usuario


def require_role(*roles_permitidos: str):
    """Factory de dependência FastAPI que restringe acesso por role."""
    def _check(usuario: models.User = Depends(get_usuario_atual)):
        if usuario.role not in roles_permitidos:
            raise HTTPException(
                status_code=403,
                detail=f"Acesso restrito a: {', '.join(roles_permitidos)}"
            )
        return usuario
    return _check


def verificar_acesso_relatorio(relatorio: "models.RelatorioAnalise", usuario: "models.User", db: Session) -> None:
    """
    Multi-tenant: garante que o relatório pertence ao usuário (via user_id ou empresa).
    Levanta 403 se não tiver acesso.
    """
    if relatorio.user_id == usuario.id:
        return
    if relatorio.empresa_id:
        verificar_empresa_do_usuario(relatorio.empresa_id, usuario, db)
        return
    raise HTTPException(status_code=403, detail="Acesso negado ao relatório")


def verificar_empresa_do_usuario(empresa_id: int | None, usuario: "models.User", db: Session) -> "models.Empresa":
    """
    Multi-tenant: garante que a empresa pertence ao usuário logado.
    Levanta 403 se a empresa não for do usuário.
    Retorna a Empresa se válida.
    """
    if empresa_id is None:
        raise HTTPException(status_code=403, detail="Recurso sem empresa associada")
    empresa = db.query(models.Empresa).filter(
        models.Empresa.id == empresa_id,
        models.Empresa.user_id == usuario.id
    ).first()
    if not empresa:
        raise HTTPException(
            status_code=403,
            detail="Acesso negado: empresa não pertence ao usuário"
        )
    return empresa