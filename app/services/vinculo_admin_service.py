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
    """INV-VINCULO-03: já existe vínculo activo para (contador, empresa, escopo_chave)."""
    def __init__(self, contador_id: int, empresa_id: int, escopo_chave: str):
        super().__init__(
            f"INV-VINCULO-03: já existe vínculo activo para "
            f"contador={contador_id}, empresa={empresa_id}, escopo={escopo_chave}. "
            "Revogar ou expirar o vínculo existente antes de criar novo."
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

    vinculo = ContadorEmpresaVinculo(
        contador_id=perfil.id,
        empresa_id=empresa_id,
        escopo_chave=escopo_chave,
        escopo=escopo_detalhe,
        origem="admin",
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
