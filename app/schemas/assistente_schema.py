from pydantic import BaseModel, Field


class PerguntaRequest(BaseModel):
    """Schema para perguntas enviadas ao Assistente Fiscal."""

    pergunta: str = Field(..., min_length=1, description="Pergunta do usuário sobre aspectos fiscais")


class AssistenteResponse(BaseModel):
    """Estrutura padrão das respostas do Assistente Fiscal.
    Garante compatibilidade entre frontend, assistente, relatórios e pagamento."""

    resposta: str
    analysis_type: str | None = None  # mei_tax | tax_planning | tax_recovery
    requires_payment: bool = False
    preview: dict | None = None
