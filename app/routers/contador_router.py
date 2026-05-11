"""
Router do contador parceiro — domínio regulatório soberano.

Fluxo pool aberto V1:
    documento pendente (fila_homologacao)
    → contador assume
    → contador decide (aprovado/rejeitado + parecer)

Princípio: contador assina — não opera o motor fiscal.
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
    criar_fila_homologacao,
    obter_homologacoes_pendentes,
    registar_decisao,
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
    Pool aberto V1: primeiro contador aprovado que assume fica responsável.
    """
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

    try:
        homologacao = criar_fila_homologacao(
            db=db,
            documento_ingerido_id=documento_id,
            contador_id=perfil.id,
            tipo_decisao=body.tipo_decisao,
        )
        db.commit()
        db.refresh(homologacao)
    except HomologacaoJaExisteError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.mensagem)
    except ContadorNaoAprovadoError as e:
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
