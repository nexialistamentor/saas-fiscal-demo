import os
import uuid
import logging
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.token_revocation import revogacao_jti

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15

_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower().strip()

_secret = os.getenv("SECRET_KEY")

if _ENVIRONMENT == "production":
    if not _secret:
        raise RuntimeError(
            "SECRET_KEY não definida. "
            "A aplicação não pode iniciar em produção sem esta variável."
        )
else:
    if not _secret:
        _secret = "dev-insecure-placeholder-DO-NOT-USE-IN-PROD"
        logger.warning(
            "SECRET_KEY não definida — usando chave de desenvolvimento. "
            "NUNCA use isto em produção."
        )

SECRET_KEY: str = _secret
del _secret

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

        jti = payload.get("jti")
        if jti and revogacao_jti.esta_revogado(jti):
            return None

        return payload
    except JWTError:
        return None


def decodificar_token_acesso_valido(token: str) -> dict | None:
    """
    Assinatura e exp; não verifica revogação (necessário para /auth/logout idempotente).
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if "jti" not in payload or "iat" not in payload:
            return None
        return payload
    except JWTError:
        return None


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


def tenant_empresa(
    empresa_id: int,
    db: Session = Depends(get_db),
    usuario_atual: "models.User" = Depends(get_usuario_atual),
) -> "models.Empresa":
    """Dependência FastAPI estrutural: valida ownership de empresa_id antes do handler."""
    return verificar_empresa_do_usuario(empresa_id, usuario_atual, db)