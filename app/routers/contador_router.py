"""
Router do contador parceiro — domínio regulatório soberano.
Fluxo DT-CONTADOR-01 (vínculo soberano):
    documento pendente (fila_homologacao)
    → validar vínculo activo contador↔empresa
    → criar HomologacaoAtribuicao (aceite)
    → criar HomologacaoDocumental (pendente)
    → contador decide (aprovado/rejeitado + parecer)
Princípio: contador assina — não opera o motor fiscal.
ADR-004: sem vínculo activo, /assumir devolve 403.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DocumentoIngerido, PerfilContador, User
from app.security import get_usuario_atual
from app.services.homologacao_service import (
    ContadorNaoAprovadoError,
    HomologacaoError,
    HomologacaoJaExisteError,
    HomologacaoNaoPendenteError,
    HomologacaoSemAtribuicaoSoberanaError,
    criar_fila_homologacao,
    obter_homologacoes_pendentes,
    registar_decisao,
)
from app.services.vinculo_service import (
    AtribuicaoActivaExisteError,
    VinculoError,
    validar_vinculo_e_aceitar_atribuicao,
)

router = APIRouter(prefix="/contador", tags=["contador"])

# ---------------------------------------------------------------------------
# Schemas de entrada
# ---------------------------------------------------------------------------
class AssumirHomologacaoRequest(BaseModel):
    tipo_decisao: str = "homologacao_documental"

class DecisaoRequest(BaseModel):
    status_decisao: str   # aprovado | rejeitado
    parecer_texto: str

# ---------------------------------------------------------------------------
# Dependency — valida que o utilizador é contador aprovado
# ---------------------------------------------------------------------------
def _get_perfil_contador(
    usuario: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
) -> PerfilContador:
    if usuario.role != "contador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a contadores parceiros",
        )
    perfil = db.query(PerfilContador).filter(
        PerfilContador.user_id == usuario.id,
        PerfilContador.status == "aprovado",
    ).first()
    if not perfil:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Perfil de contador não encontrado ou não aprovado",
        )
    return perfil

# ---------------------------------------------------------------------------
# Dependency — valida que o utilizador é contador (qualquer status de perfil)
# ---------------------------------------------------------------------------
def _get_usuario_contador(
    usuario: User = Depends(get_usuario_atual),
) -> User:
    """Acesso informacional: role=contador obrigatório, status de perfil irrelevante."""
    if usuario.role != "contador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a contadores parceiros",
        )
    return usuario

@router.get("/perfil")
def consultar_proprio_perfil(
    usuario: User = Depends(_get_usuario_contador),
    db: Session = Depends(get_db),
):
    """Contador consulta o próprio estado regulatório. Não exige status=aprovado."""
    perfil = db.query(PerfilContador).filter(
        PerfilContador.user_id == usuario.id
    ).first()
    if not perfil:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PerfilContador não encontrado para este utilizador.",
        )
    return {
        "perfil_id": perfil.id,
        "crc": perfil.crc,
        "uf_crc": perfil.uf_crc,
        "status": perfil.status,
        "aprovado_em": perfil.aprovado_em.isoformat() if perfil.aprovado_em else None,
        "aprovado_por": perfil.aprovado_por,
        "criado_em": perfil.criado_em.isoformat() if perfil.criado_em else None,
    }

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/homologacoes/pendentes")
def listar_pendentes(
    perfil: PerfilContador = Depends(_get_perfil_contador),
    db: Session = Depends(get_db),
):
    """Lista homologações pendentes atribuídas a este contador."""
    homologacoes = obter_homologacoes_pendentes(db, perfil.id)
    return [
        {
            "id": h.id,
            "documento_ingerido_id": h.documento_ingerido_id,
            "tipo_decisao": h.tipo_decisao,
            "versao_parecer": h.versao_parecer,
            "criado_em": h.criado_em.isoformat() if h.criado_em else None,
        }
        for h in homologacoes
    ]


@router.post("/homologacoes/{documento_id}/assumir", status_code=status.HTTP_201_CREATED)
def assumir_homologacao(
    documento_id: int,
    body: AssumirHomologacaoRequest,
    perfil: PerfilContador = Depends(_get_perfil_contador),
    db: Session = Depends(get_db),
):
    """
    Contador assume documento da fila de homologação.
    DT-CONTADOR-01: exige vínculo activo contador↔empresa (ADR-004).
    Piloto manual: escopo_chave=homologacao_documental, modo=manual.
    """
    # Carregar e validar documento
    documento = db.query(DocumentoIngerido).filter(
        DocumentoIngerido.id == documento_id,
    ).first()
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento não encontrado",
        )
    if documento.decisao != "fila_homologacao":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Documento não está em fila de homologação — decisão actual: {documento.decisao}",
        )

    # Piloto DT-CONTADOR-01: só aceita homologacao_documental
    if body.tipo_decisao != "homologacao_documental":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="DT-CONTADOR-01 piloto aceita apenas tipo_decisao='homologacao_documental'",
        )
    escopo_chave = body.tipo_decisao  # escopo_chave == tipo_decisao — sem divergência

    # DT-CONTADOR-01: validar vínculo e criar atribuição aceite
    try:
        validar_vinculo_e_aceitar_atribuicao(
            db=db,
            documento=documento,
            perfil=perfil,
            escopo_chave=escopo_chave,
            complexidade="baixa",
            modo_atribuicao="manual",
        )
    except AtribuicaoActivaExisteError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.mensagem)
    except VinculoError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.mensagem)

    # Criar HomologacaoDocumental (só alcançado após atribuição aceite)
    try:
        homologacao = criar_fila_homologacao(
            db=db,
            documento_ingerido_id=documento_id,
            contador_id=perfil.id,
            tipo_decisao=escopo_chave,
        )
        db.commit()
        db.refresh(homologacao)
    except HomologacaoJaExisteError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.mensagem)
    except ContadorNaoAprovadoError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.mensagem)

    return {
        "id": homologacao.id,
        "documento_ingerido_id": homologacao.documento_ingerido_id,
        "contador_id": homologacao.contador_id,
        "status": homologacao.status,
        "tipo_decisao": homologacao.tipo_decisao,
        "criado_em": homologacao.criado_em.isoformat() if homologacao.criado_em else None,
    }


@router.post("/homologacoes/{homologacao_id}/decidir")
def decidir_homologacao(
    homologacao_id: int,
    body: DecisaoRequest,
    perfil: PerfilContador = Depends(_get_perfil_contador),
    db: Session = Depends(get_db),
):
    """
    Contador regista parecer e decisão sobre homologação assumida.
    Gera assinatura lógica V1 (SHA-256 não repúdio básico).
    """
    if not body.parecer_texto or not body.parecer_texto.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Parecer não pode estar vazio",
        )
    try:
        homologacao = registar_decisao(
            db=db,
            homologacao_id=homologacao_id,
            status_decisao=body.status_decisao,
            parecer_texto=body.parecer_texto,
            contador_id=perfil.id,
        )
        db.commit()
        db.refresh(homologacao)
    except HomologacaoSemAtribuicaoSoberanaError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.mensagem)
    except HomologacaoNaoPendenteError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.mensagem)
    except HomologacaoError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.mensagem)

    return {
        "id": homologacao.id,
        "status": homologacao.status,
        "parecer_texto": homologacao.parecer_texto,
        "assinatura_logica": homologacao.assinatura_logica,
        "decidido_em": homologacao.decidido_em.isoformat() if homologacao.decidido_em else None,
        "versao_parecer": homologacao.versao_parecer,
    }
