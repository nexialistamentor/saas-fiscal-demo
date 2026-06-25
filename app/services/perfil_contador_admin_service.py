"""
Service: ciclo administrativo soberano de PerfilContador.

Responsabilidades:
  - criar_perfil_contador_pendente  → entrada na fila
  - listar_perfis_contador          → auditoria da fila
  - aprovar_perfil_contador         → acto administrativo auditável

Fora de escopo:
  - vínculo contador↔empresa (vinculo_admin_service)
  - suspensão/revogação de perfil (fase posterior)
  - auto-candidatura pública (ADR-005 §5)
"""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import PerfilContador, User

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

ESTADOS_VALIDOS = ("pendente", "aprovado", "suspenso")

# ---------------------------------------------------------------------------
# Excepções de domínio
# ---------------------------------------------------------------------------


class UserNaoEncontradoError(HTTPException):
    def __init__(self, email: str):
        super().__init__(status_code=404, detail=f"Utilizador não encontrado: {email}")


class PerfilContadorJaExisteError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=409,
            detail="Já existe um PerfilContador para este utilizador.",
        )


class CrcJaRegistadoError(HTTPException):
    def __init__(self, crc: str):
        super().__init__(status_code=409, detail=f"CRC já registado: {crc}")


class UfCrcInvalidoError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=422,
            detail="uf_crc inválido. Use sigla UF com 2 letras (ex: PA, SP).",
        )


class PerfilContadorNaoEncontradoError(HTTPException):
    def __init__(self, perfil_id: int):
        super().__init__(
            status_code=404,
            detail=f"PerfilContador não encontrado: id={perfil_id}",
        )


class TransicaoEstadoInvalidaError(HTTPException):
    def __init__(self, status_actual: str):
        super().__init__(
            status_code=422,
            detail=f"Transição inválida: perfil está '{status_actual}', não 'pendente'.",
        )


class StatusFiltroInvalidoError(HTTPException):
    def __init__(self, status: str):
        super().__init__(
            status_code=422,
            detail=f"Status inválido: '{status}'. Valores aceites: {ESTADOS_VALIDOS}",
        )


# ---------------------------------------------------------------------------
# Funções de serviço
# ---------------------------------------------------------------------------


def criar_perfil_contador_pendente(
    db: Session,
    admin_user: User,
    email: str,
    crc: str,
    uf_crc: str,
) -> PerfilContador:
    """
    Cria PerfilContador(status=pendente) para User existente.
    Na mesma transacção: promove User.role = "contador".

    Regras:
      - Normalização: email lower+strip, crc upper+strip, uf_crc upper+strip
      - uf_crc deve ter exactamente 2 letras → 422
      - User inexistente → 404
      - Perfil já existe para user_id → 409
      - CRC duplicado → 409
    """
    # 1. Normalização
    email = (email or "").strip().lower()
    crc = (crc or "").strip().upper()
    uf_crc = (uf_crc or "").strip().upper()

    # 2. Validar uf_crc
    if len(uf_crc) != 2 or not uf_crc.isalpha():
        raise UfCrcInvalidoError()

    # 3. Resolver User por email
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise UserNaoEncontradoError(email)

    # 4. Perfil duplicado por user_id
    existente = (
        db.query(PerfilContador).filter(PerfilContador.user_id == user.id).first()
    )
    if existente:
        raise PerfilContadorJaExisteError()

    # 5. CRC duplicado
    crc_existente = db.query(PerfilContador).filter(PerfilContador.crc == crc).first()
    if crc_existente:
        raise CrcJaRegistadoError(crc)

    # 6. Transacção única: role + perfil
    user.role = "contador"
    perfil = PerfilContador(
        user_id=user.id,
        crc=crc,
        uf_crc=uf_crc,
        status="pendente",
        aprovado_em=None,
        aprovado_por=None,
    )
    db.add(perfil)
    db.commit()
    db.refresh(perfil)
    return perfil


def listar_perfis_contador(
    db: Session,
    status: str = "pendente",
) -> list[dict]:
    """
    Lista PerfilContador com filtro por status.
    status inválido → 422 (não lista vazia silenciosa).
    """
    if status not in ESTADOS_VALIDOS:
        raise StatusFiltroInvalidoError(status)

    perfis = (
        db.query(PerfilContador, User)
        .join(User, PerfilContador.user_id == User.id)
        .filter(PerfilContador.status == status)
        .all()
    )

    return [
        {
            "perfil_id": p.id,
            "user_id": p.user_id,
            "email": u.email,
            "crc": p.crc,
            "uf_crc": p.uf_crc,
            "status": p.status,
            "criado_em": p.criado_em.isoformat() if p.criado_em else None,
            "aprovado_em": p.aprovado_em.isoformat() if p.aprovado_em else None,
            "aprovado_por": p.aprovado_por,
        }
        for p, u in perfis
    ]


def aprovar_perfil_contador(
    db: Session,
    admin_user: User,
    perfil_id: int,
) -> PerfilContador:
    """
    Transição soberana: pendente → aprovado.
    Preenche aprovado_em e aprovado_por (trilha auditável).

    Regras:
      - Perfil inexistente → 404
      - status != pendente → 422
      - Não cria vínculo
      - Não toca em origem_cliente
    """
    perfil = db.query(PerfilContador).filter(PerfilContador.id == perfil_id).first()
    if not perfil:
        raise PerfilContadorNaoEncontradoError(perfil_id)

    if perfil.status != "pendente":
        raise TransicaoEstadoInvalidaError(perfil.status)

    perfil.status = "aprovado"
    perfil.aprovado_em = datetime.utcnow()
    perfil.aprovado_por = admin_user.email

    db.commit()
    db.refresh(perfil)
    return perfil
