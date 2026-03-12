from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas.assistente_schema import AssistenteResponse, PerguntaRequest
from app.security import get_usuario_atual
from app.services.assistente_service import responder_pergunta

assistente_router = APIRouter(
    tags=["Assistente Fiscal"]
)


@assistente_router.post("/perguntar", response_model=AssistenteResponse)
def perguntar(
    body: PerguntaRequest,
    usuario_atual: models.User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    """
    Recebe perguntas do usuário. Base do Assistente Fiscal da plataforma.
    Arquitetura: identificar_contribuinte → MEI/CPF (imposto_service) ou
    Empresa (verificar pagamento → preview ou insights_engine + motor fiscal).
    """
    resultado = responder_pergunta(
        pergunta=body.pergunta,
        usuario=usuario_atual,
        db=db,
    )
    return AssistenteResponse(
        resposta=resultado["resposta"],
        analysis_type=resultado.get("analysis_type"),
        requires_payment=resultado.get("requires_payment", False),
        preview=resultado.get("preview"),
    )
