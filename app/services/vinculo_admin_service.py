"""
VinculoAdminService — criação administrada de vínculo contador↔empresa

DT-VINCULO-ADMIN-01: processo soberano para Admin criar ContadorEmpresaVinculo.

Responsabilidades:
  - Validar que admin_user.role == "admin" (defesa em profundidade)
  - Validar que o contador existe e está aprovado
  - Validar que a empresa existe
  - Validar escopo_chave: formato + lista de escopos V1 admissíveis
  - Validar validade futura (vínculo não nasce já expirado)
  - Enforçar INV-VINCULO-03: sem duplicado activo
  - Criar ContadorEmpresaVinculo com origem="admin" e trilha de auditoria

Este service não cria vínculos com origem="cliente" ou origem="sistema".
Esses fluxos são entregáveis futuros.

Princípio: vínculo não nasce do contador. Nasce de acto administrativo auditável.
"""

import re
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import (
    ContadorEmpresaVinculo,
    Empresa,
    PerfilContador,
    User,
)

# ---------------------------------------------------------------------------
# Constantes de domínio
# ---------------------------------------------------------------------------

_RE_ESCOPO_CHAVE = re.compile(r'^[a-z0-9_.:-]+$')

# Escopos admissíveis no piloto V1 — lista fechada
ESCOPOS_PILOTO_V1 = frozenset({
    "homologacao_documental",
    "parecer_tecnico",
    "analise_xml",
})


# ---------------------------------------------------------------------------
# Excepções de domínio
# ---------------------------------------------------------------------------

class VinculoAdminError(Exception):
    def __init__(self, mensagem: str):
        self.mensagem = mensagem
        super().__init__(mensagem)


class ContadorNaoEncontradoError(VinculoAdminError):
    def __init__(self, contador_user_id: int):
        super().__init__(
            f"PerfilContador não encontrado para user_id={contador_user_id}"
        )


class ContadorNaoAprovadoParaVinculoError(VinculoAdminError):
    def __init__(self, status: str):
        super().__init__(
            f"Contador não está aprovado — status actual: {status}"
        )


class EmpresaNaoEncontradaError(VinculoAdminError):
    def __init__(self, empresa_id: int):
        super().__init__(
            f"Empresa não encontrada: empresa_id={empresa_id}"
        )


class VinculoDuplicadoActivoError(VinculoAdminError):
    """INV-VINCULO-03: já existe vínculo activo ou suspenso para (contador, empresa, escopo_chave).
    suspenso = ainda institucionalmente pendente.
    revogado/expirado = encerrado, pode criar novo.
    """
    def __init__(self, contador_id: int, empresa_id: int, escopo_chave: str):
        super().__init__(
            f"INV-VINCULO-03: já existe vínculo activo ou suspenso para "
            f"contador={contador_id}, empresa={empresa_id}, escopo={escopo_chave}. "
            "Revogar ou expirar o vínculo existente antes de criar novo."
        )


class VinculoNaoEncontradoError(VinculoAdminError):
    def __init__(self, vinculo_id: int):
        super().__init__(f"Vínculo não encontrado: vinculo_id={vinculo_id}")


class VinculoTransicaoInvalidaError(VinculoAdminError):
    """Transição de status não permitida."""
    def __init__(self, status_actual: str, status_destino: str):
        super().__init__(
            f"Transição inválida: {status_actual} → {status_destino}. "
            f"Vínculo com status='{status_actual}' não pode ser alterado para '{status_destino}'."
        )


# ---------------------------------------------------------------------------
# Validações de domínio
# ---------------------------------------------------------------------------

def _validar_escopo_chave(escopo_chave: str) -> None:
    if not escopo_chave or not escopo_chave.strip():
        raise VinculoAdminError("escopo_chave não pode ser vazio")
    if escopo_chave != escopo_chave.lower():
        raise VinculoAdminError(
            f"escopo_chave deve ser lowercase: '{escopo_chave}'"
        )
    if not _RE_ESCOPO_CHAVE.match(escopo_chave):
        raise VinculoAdminError(
            f"escopo_chave formato inválido (apenas a-z, 0-9, _.:-): '{escopo_chave}'"
        )
    # Lista fechada de escopos V1 admissíveis
    if escopo_chave not in ESCOPOS_PILOTO_V1:
        raise VinculoAdminError(
            f"escopo_chave não permitido no piloto V1: '{escopo_chave}'. "
            f"Escopos admissíveis: {sorted(ESCOPOS_PILOTO_V1)}"
        )


# ---------------------------------------------------------------------------
# Função pública
# ---------------------------------------------------------------------------

def criar_vinculo_contador_empresa(
    db: Session,
    admin_user: User,
    contador_user_id: int,
    empresa_id: int,
    escopo_chave: str,
    validade: datetime | None = None,
    policy_version: str | None = None,
    escopo_detalhe: dict | None = None,
    origem_cliente: str = "plataforma_directa",
) -> ContadorEmpresaVinculo:
    """
    Cria ContadorEmpresaVinculo com origem="admin".

    Args:
      admin_user:        User autenticado com role=admin (validado pelo router E pelo service)
      contador_user_id:  user_id do contador (não o perfil_id)
      empresa_id:        ID da empresa a vincular
      escopo_chave:      Chave canónica lowercase, lista fechada V1
      validade:          Data de expiração futura (None = permanente até revogação)
      policy_version:    Versão de política (opcional para origem=admin)
      escopo_detalhe:    JSONB opcional com detalhes do escopo

    Enforça:
      - admin_user.role == "admin" (defesa em profundidade)
      - Contador existe e status=aprovado
      - Empresa existe
      - Escopo_chave válido e na lista V1
      - Validade futura se definida
      - INV-VINCULO-03: sem duplicado activo
    """
    # Defesa em profundidade — router já valida, service confirma
    if getattr(admin_user, "role", None) != "admin":
        raise VinculoAdminError(
            "Apenas admin pode criar vínculo contador↔empresa"
        )

    _validar_escopo_chave(escopo_chave)

    # Validade deve ser futura
    if validade is not None and validade <= datetime.utcnow():
        raise VinculoAdminError(
            "validade deve ser uma data futura — vínculo não pode nascer já expirado"
        )

    # Validar contador
    perfil = db.query(PerfilContador).filter(
        PerfilContador.user_id == contador_user_id,
    ).first()
    if not perfil:
        raise ContadorNaoEncontradoError(contador_user_id)
    if perfil.status != "aprovado":
        raise ContadorNaoAprovadoParaVinculoError(perfil.status)

    # Validar empresa
    empresa = db.query(Empresa).filter(
        Empresa.id == empresa_id,
    ).first()
    if not empresa:
        raise EmpresaNaoEncontradaError(empresa_id)

    # INV-VINCULO-03: sem duplicado activo ou suspenso
    # suspenso = ainda institucionalmente pendente; revogado/expirado = encerrado
    existente = db.query(ContadorEmpresaVinculo).filter(
        ContadorEmpresaVinculo.contador_id == perfil.id,
        ContadorEmpresaVinculo.empresa_id == empresa_id,
        ContadorEmpresaVinculo.escopo_chave == escopo_chave,
        ContadorEmpresaVinculo.status.in_(["activo", "suspenso"]),
    ).first()
    if existente:
        raise VinculoDuplicadoActivoError(perfil.id, empresa_id, escopo_chave)

    # INV-CARTEIRA-06: origem_cliente obrigatório — nunca usar "legado" em código novo
    _ORIGENS_CLIENTE_VALIDAS = frozenset({
        "contador_parceiro", "plataforma_directa", "empresa_directa", "legado"
    })
    if origem_cliente not in _ORIGENS_CLIENTE_VALIDAS:
        raise VinculoAdminError(
            f"origem_cliente inválido: '{origem_cliente}'. "
            f"Válidos: {sorted(_ORIGENS_CLIENTE_VALIDAS)}"
        )

    vinculo = ContadorEmpresaVinculo(
        contador_id=perfil.id,
        empresa_id=empresa_id,
        escopo_chave=escopo_chave,
        escopo=escopo_detalhe,
        origem="admin",
        origem_cliente=origem_cliente,
        status="activo",
        criado_por_user_id=admin_user.id,
        criado_por_email=admin_user.email,
        criado_em=datetime.utcnow(),
        validade=validade,
        policy_version=policy_version,
    )
    db.add(vinculo)
    db.flush()
    return vinculo


def _serializar_vinculo(v: ContadorEmpresaVinculo) -> dict:
    """Serialização operacional — inclui dados de contador e empresa via ORM."""
    perfil = v.contador
    user_contador = perfil.user if perfil else None
    empresa = v.empresa
    return {
        "vinculo_id": v.id,
        "contador_id": v.contador_id,
        "contador_user_id": perfil.user_id if perfil else None,
        "contador_crc": perfil.crc if perfil else None,
        "contador_email": user_contador.email if user_contador else None,
        "empresa_id": v.empresa_id,
        "empresa_razao_social": empresa.razao_social if empresa else None,
        "escopo_chave": v.escopo_chave,
        "status": v.status,
        "origem": v.origem,
        "criado_por_user_id": v.criado_por_user_id,
        "criado_por_email": v.criado_por_email,
        "criado_em": v.criado_em.isoformat() if v.criado_em else None,
        "validade": v.validade.isoformat() if v.validade else None,
        "policy_version": v.policy_version,
        "revogado_em": v.revogado_em.isoformat() if v.revogado_em else None,
        "revogado_por_user_id": v.revogado_por_user_id,
    }


STATUS_VINCULO_VALIDOS = frozenset({
    "activo",
    "suspenso",
    "revogado",
    "expirado",
})


def listar_vinculos(
    db: Session,
    admin_user: User,
    status: str | None = None,
    empresa_id: int | None = None,
    contador_user_id: int | None = None,
    escopo_chave: str | None = None,
) -> list[dict]:
    """
    Lista ContadorEmpresaVinculo com filtros opcionais.
    Devolve dados operacionais ricos (contador, empresa, auditoria).
    Valida filtros para evitar lista vazia silenciosa por erro humano.
    """
    if getattr(admin_user, "role", None) != "admin":
        raise VinculoAdminError("Apenas admin pode listar vínculos")

    if status is not None and status not in STATUS_VINCULO_VALIDOS:
        raise VinculoAdminError(
            f"status inválido: '{status}'. Válidos: {sorted(STATUS_VINCULO_VALIDOS)}"
        )
    if escopo_chave is not None:
        _validar_escopo_chave(escopo_chave)

    query = db.query(ContadorEmpresaVinculo)

    if status is not None:
        query = query.filter(ContadorEmpresaVinculo.status == status)
    if empresa_id is not None:
        query = query.filter(ContadorEmpresaVinculo.empresa_id == empresa_id)
    if escopo_chave is not None:
        query = query.filter(ContadorEmpresaVinculo.escopo_chave == escopo_chave)
    if contador_user_id is not None:
        # Filtrar por user_id do contador via join com PerfilContador
        query = query.join(
            PerfilContador,
            ContadorEmpresaVinculo.contador_id == PerfilContador.id
        ).filter(PerfilContador.user_id == contador_user_id)

    vinculos = query.order_by(ContadorEmpresaVinculo.criado_em.desc()).all()
    return [_serializar_vinculo(v) for v in vinculos]


def suspender_vinculo(
    db: Session,
    admin_user: User,
    vinculo_id: int,
) -> ContadorEmpresaVinculo:
    """
    Suspende vínculo activo.
    Permitido: activo → suspenso
    Bloqueado: suspenso/revogado/expirado → suspenso
    """
    if getattr(admin_user, "role", None) != "admin":
        raise VinculoAdminError("Apenas admin pode suspender vínculo")

    vinculo = db.query(ContadorEmpresaVinculo).filter(
        ContadorEmpresaVinculo.id == vinculo_id
    ).first()
    if not vinculo:
        raise VinculoNaoEncontradoError(vinculo_id)

    if vinculo.status != "activo":
        raise VinculoTransicaoInvalidaError(vinculo.status, "suspenso")

    vinculo.status = "suspenso"
    db.flush()
    return vinculo


def revogar_vinculo(
    db: Session,
    admin_user: User,
    vinculo_id: int,
) -> ContadorEmpresaVinculo:
    """
    Revoga vínculo activo ou suspenso.
    Permitido: activo/suspenso → revogado
    Bloqueado: revogado/expirado → revogado
    Preenche revogado_em e revogado_por_user_id.
    """
    if getattr(admin_user, "role", None) != "admin":
        raise VinculoAdminError("Apenas admin pode revogar vínculo")

    vinculo = db.query(ContadorEmpresaVinculo).filter(
        ContadorEmpresaVinculo.id == vinculo_id
    ).first()
    if not vinculo:
        raise VinculoNaoEncontradoError(vinculo_id)

    if vinculo.status not in ("activo", "suspenso"):
        raise VinculoTransicaoInvalidaError(vinculo.status, "revogado")

    vinculo.status = "revogado"
    vinculo.revogado_em = datetime.utcnow()
    vinculo.revogado_por_user_id = admin_user.id
    db.flush()
    return vinculo
