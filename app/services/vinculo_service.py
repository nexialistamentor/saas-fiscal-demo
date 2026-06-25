"""
VinculoService — domínio de autorização soberana contador↔empresa

ADR-004 / DT-CONTADOR-01: o vínculo deve preceder o acesso.

Responsabilidades:
  - Validar vínculo activo (não expirado, não revogado)
  - Enforçar INV-VINCULO-01: documento.empresa_id == vinculo.empresa_id
  - Enforçar INV-VINCULO-02: uma atribuição activa por (documento, escopo_chave)
  - Enforçar INV-VINCULO-05: atribuição não-manual exige policy_version
  - Criar HomologacaoAtribuicao com status=aceite no fluxo /assumir

Nota sobre status:
  O acto de assumir já é aceitação. Logo HomologacaoAtribuicao nasce com
  status="aceite" e aceite_em preenchido. HomologacaoDocumental só deve
  ser criada após HomologacaoAtribuicao com status=aceite (ADR-004).

Fluxo esperado no router /assumir (DT-CONTADOR-01):
  1. vinculo_service.validar_vinculo_e_aceitar_atribuicao(...)
  2. homologacao_service.criar_fila_homologacao(..., vinculo_id=atribuicao.vinculo_id)
"""

import re
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ContadorEmpresaVinculo,
    DocumentoIngerido,
    HomologacaoAtribuicao,
    PerfilContador,
)

# ---------------------------------------------------------------------------
# Constantes de domínio
# ---------------------------------------------------------------------------

_COMPLEXIDADES_VALIDAS = {"baixa", "media", "alta"}
_MODOS_VALIDOS = {"manual", "recomendado", "automatico"}
_RE_ESCOPO_CHAVE = re.compile(r'^[a-z0-9_.:-]+$')

# ---------------------------------------------------------------------------
# Excepções de domínio
# ---------------------------------------------------------------------------

class VinculoError(Exception):
    def __init__(self, mensagem: str = "Erro no vínculo contador↔empresa"):
        self.mensagem = mensagem
        super().__init__(mensagem)


class VinculoInexistenteError(VinculoError):
    def __init__(self, contador_id: int, empresa_id: int, escopo_chave: str):
        super().__init__(
            f"Não existe vínculo activo para contador={contador_id}, "
            f"empresa={empresa_id}, escopo={escopo_chave}"
        )


class VinculoIncoerenciaEmpresaError(VinculoError):
    """INV-VINCULO-01: empresa_id do documento diverge do vínculo."""
    def __init__(self, documento_empresa_id, vinculo_empresa_id):
        super().__init__(
            f"INV-VINCULO-01: documento.empresa_id={documento_empresa_id} "
            f"diverge de vinculo.empresa_id={vinculo_empresa_id}"
        )


class AtribuicaoActivaExisteError(VinculoError):
    """INV-VINCULO-02: já existe atribuição activa para este documento/escopo."""
    def __init__(self, documento_id: int, escopo_chave: str):
        super().__init__(
            f"INV-VINCULO-02: documento {documento_id} já tem atribuição "
            f"activa para escopo={escopo_chave}"
        )


# ---------------------------------------------------------------------------
# Validações de domínio (fronteira do serviço)
# ---------------------------------------------------------------------------

def _validar_escopo_chave(escopo_chave: str) -> None:
    if not escopo_chave or not escopo_chave.strip():
        raise VinculoError("escopo_chave não pode ser vazio")
    if escopo_chave != escopo_chave.lower():
        raise VinculoError(
            f"escopo_chave deve ser lowercase: '{escopo_chave}'"
        )
    if not _RE_ESCOPO_CHAVE.match(escopo_chave):
        raise VinculoError(
            f"escopo_chave formato inválido (apenas a-z, 0-9, _.:-): '{escopo_chave}'"
        )


def _validar_complexidade(complexidade: str) -> None:
    if complexidade not in _COMPLEXIDADES_VALIDAS:
        raise VinculoError(
            f"complexidade inválida: '{complexidade}' — "
            f"valores aceites: {sorted(_COMPLEXIDADES_VALIDAS)}"
        )


def _validar_modo_atribuicao(modo_atribuicao: str) -> None:
    if modo_atribuicao not in _MODOS_VALIDOS:
        raise VinculoError(
            f"modo_atribuicao inválido: '{modo_atribuicao}' — "
            f"valores aceites: {sorted(_MODOS_VALIDOS)}"
        )


def _validar_policy_version(modo_atribuicao: str, policy_version: str | None) -> None:
    """INV-VINCULO-05: atribuição não-manual exige policy_version não vazia."""
    if modo_atribuicao != "manual":
        if not policy_version or not policy_version.strip():
            raise VinculoError(
                f"INV-VINCULO-05: modo_atribuicao='{modo_atribuicao}' "
                "exige policy_version não vazia"
            )


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

def validar_vinculo(
    db: Session,
    contador_id: int,
    empresa_id: int,
    escopo_chave: str,
) -> ContadorEmpresaVinculo:
    """
    Verifica vínculo activo para (contador, empresa, escopo_chave).
    Bloqueia vínculo expirado ou com revogado_em preenchido.
    """
    agora = datetime.utcnow()

    vinculo = db.query(ContadorEmpresaVinculo).filter(
        ContadorEmpresaVinculo.contador_id == contador_id,
        ContadorEmpresaVinculo.empresa_id == empresa_id,
        ContadorEmpresaVinculo.escopo_chave == escopo_chave,
        ContadorEmpresaVinculo.status == "activo",
        ContadorEmpresaVinculo.revogado_em.is_(None),
    ).first()

    if not vinculo:
        raise VinculoInexistenteError(contador_id, empresa_id, escopo_chave)

    # Validade temporal — vínculo expirado não dá acesso
    if vinculo.validade is not None and vinculo.validade < agora:
        raise VinculoError(
            f"Vínculo {vinculo.id} expirou em {vinculo.validade.isoformat()}"
        )

    return vinculo


def validar_vinculo_e_aceitar_atribuicao(
    db: Session,
    documento: DocumentoIngerido,
    perfil: PerfilContador,
    escopo_chave: str,
    complexidade: str = "baixa",
    modo_atribuicao: str = "manual",
    policy_version: str | None = None,
    regra_matching_id: str | None = None,
) -> HomologacaoAtribuicao:
    """
    Valida vínculo e cria HomologacaoAtribuicao com status=aceite.

    O acto de assumir já é aceitação — HomologacaoAtribuicao nasce aceite
    para que HomologacaoDocumental possa ser criada a seguir.

    Enforça:
      INV-VINCULO-01: documento.empresa_id == vinculo.empresa_id
      INV-VINCULO-02: sem atribuição activa duplicada
      INV-VINCULO-05: não-manual exige policy_version
    """
    # Validações de domínio na fronteira do serviço
    _validar_escopo_chave(escopo_chave)
    _validar_complexidade(complexidade)
    _validar_modo_atribuicao(modo_atribuicao)
    _validar_policy_version(modo_atribuicao, policy_version)

    if documento.empresa_id is None:
        raise VinculoError(
            f"Documento {documento.id} não tem empresa_id — "
            "não é possível verificar vínculo"
        )

    # INV-VINCULO-01: validar vínculo para empresa do documento
    vinculo = validar_vinculo(
        db=db,
        contador_id=perfil.id,
        empresa_id=documento.empresa_id,
        escopo_chave=escopo_chave,
    )

    # INV-VINCULO-01: defesa em profundidade
    if vinculo.empresa_id != documento.empresa_id:
        raise VinculoIncoerenciaEmpresaError(documento.empresa_id, vinculo.empresa_id)

    # INV-VINCULO-02: sem atribuição activa duplicada
    atribuicao_existente = db.query(HomologacaoAtribuicao).filter(
        HomologacaoAtribuicao.documento_ingerido_id == documento.id,
        HomologacaoAtribuicao.escopo_chave == escopo_chave,
        HomologacaoAtribuicao.status.in_(["atribuida", "aceite"]),
    ).first()

    if atribuicao_existente:
        raise AtribuicaoActivaExisteError(documento.id, escopo_chave)

    agora = datetime.utcnow()

    atribuicao = HomologacaoAtribuicao(
        documento_ingerido_id=documento.id,
        empresa_id=documento.empresa_id,
        contador_id=perfil.id,
        vinculo_id=vinculo.id,
        escopo_chave=escopo_chave,
        # assumir = aceitar: HomologacaoDocumental só pode nascer após aceite
        status="aceite",
        aceite_em=agora,
        complexidade=complexidade,
        modo_atribuicao=modo_atribuicao,
        policy_version=policy_version,
        regra_matching_id=regra_matching_id,
        atribuido_em=agora,
        auditoria={
            "criado_por": "router_assumir",
            "vinculo_origem": vinculo.origem,
            "aceite_em": agora.isoformat(),
        },
    )
    db.add(atribuicao)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AtribuicaoActivaExisteError(documento.id, escopo_chave) from exc
    return atribuicao


def _serializar_vinculo_visao_empresa(vinculo: ContadorEmpresaVinculo) -> dict:
    """Visão informacional para o titular da empresa — sem dados de auditoria admin."""
    perfil = vinculo.contador
    return {
        "vinculo_id": vinculo.id,
        "escopo_chave": vinculo.escopo_chave,
        "status": vinculo.status,
        "criado_em": vinculo.criado_em.isoformat() if vinculo.criado_em else None,
        "contador": {
            "crc": perfil.crc if perfil else None,
            "uf_crc": perfil.uf_crc if perfil else None,
            "status_regulatorio": perfil.status if perfil else None,
        },
    }


def listar_vinculos_visao_empresa(db: Session, empresa_id: int) -> list[dict]:
    """Lista vínculos contador↔empresa visíveis ao titular da empresa."""
    vinculos = (
        db.query(ContadorEmpresaVinculo)
        .filter(ContadorEmpresaVinculo.empresa_id == empresa_id)
        .order_by(ContadorEmpresaVinculo.criado_em.desc())
        .all()
    )
    return [_serializar_vinculo_visao_empresa(v) for v in vinculos]
