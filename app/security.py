import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.token_revocation import revogacao_jti

logger = logging.getLogger(__name__)

# ─── Algoritmo ──────────────────────────────────────────────────────
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15

# ─── Chaves (multi‑key) ────────────────────────────────────────────
_SECRET_KEY_FALLBACK: str = os.getenv("SECRET_KEY", "dev-insecure-placeholder-DO-NOT-USE-IN-PROD")

_SECRET_KEYS: Dict[str, str] = {}
_raw_keys = os.getenv("SECRET_KEYS", "")
if _raw_keys:
    for pair in _raw_keys.split(","):
        pair = pair.strip()
        if "=" in pair:
            kid, secret = pair.split("=", 1)
            _SECRET_KEYS[kid.strip()] = secret.strip()

_ACTIVE_KID: Optional[str] = max(_SECRET_KEYS.keys()) if _SECRET_KEYS else None

_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower().strip()
if _ENVIRONMENT == "production":
    if not _SECRET_KEYS:
        raise RuntimeError(
            "SECRET_KEYS não definida. "
            "A aplicação não pode iniciar em produção sem pelo menos uma chave (formato kid=secret)."
        )
else:
    if not _SECRET_KEYS:
        logger.warning(
            "SECRET_KEYS não definida — usando apenas chave de fallback. "
            "NUNCA use isto em produção."
        )

# ─── Password hashing ───────────────────────────────────────────────
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha_plana, senha_hash)


# ─── JWT (multi‑key) ────────────────────────────────────────────────
def criar_token(dados: dict) -> str:
    dados_copia = dados.copy()
    agora = datetime.utcnow()
    expire = agora + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    dados_copia.update({
        "exp": expire,
        "iat": agora,
        "jti": str(uuid.uuid4())
    })
    if _ACTIVE_KID and _SECRET_KEYS:
        kid = _ACTIVE_KID
        secret = _SECRET_KEYS[kid]
        headers = {"kid": kid}
    else:
        secret = _SECRET_KEY_FALLBACK
        headers = {}
    return jwt.encode(dados_copia, secret, algorithm=ALGORITHM, headers=headers)


def _obter_secret_para_token(token: str) -> Optional[str]:
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        return None
    kid = unverified_header.get("kid")
    if kid and kid in _SECRET_KEYS:
        return _SECRET_KEYS[kid]
    return _SECRET_KEY_FALLBACK


def verificar_token(token: str) -> Optional[dict]:
    secret = _obter_secret_para_token(token)
    if not secret:
        return None
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        if "jti" not in payload or "iat" not in payload:
            return None
        jti = payload.get("jti")
        if jti and revogacao_jti.esta_revogado(jti):
            return None
        return payload
    except JWTError:
        return None


def decodificar_token_acesso_valido(token: str) -> Optional[dict]:
    secret = _obter_secret_para_token(token)
    if not secret:
        return None
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        if "jti" not in payload or "iat" not in payload:
            return None
        return payload
    except JWTError:
        return None


# ─── OAuth2 ─────────────────────────────────────────────────────────
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


# ─── Roles e multi‑tenant ────────────────────────────────────────────
def require_role(*roles_permitidos: str):
    def _check(usuario: models.User = Depends(get_usuario_atual)):
        if usuario.role not in roles_permitidos:
            raise HTTPException(
                status_code=403,
                detail=f"Acesso restrito a: {', '.join(roles_permitidos)}"
            )
        return usuario
    return _check


def verificar_acesso_relatorio(relatorio: "models.RelatorioAnalise", usuario: "models.User", db: Session) -> None:
    if relatorio.user_id == usuario.id:
        return
    if relatorio.empresa_id:
        verificar_empresa_do_usuario(relatorio.empresa_id, usuario, db)
        return
    raise HTTPException(status_code=403, detail="Acesso negado ao relatório")


def verificar_empresa_do_usuario(empresa_id: int | None, usuario: "models.User", db: Session) -> "models.Empresa":
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
    return verificar_empresa_do_usuario(empresa_id, usuario_atual, db)
