"""
LLM Schema — contrato soberano para o LLMRouter.

REGRAS DE SANITIZAÇÃO (obrigatórias antes de qualquer chamada LLM):
- Nunca enviar: CPF, CNPJ, email completo, token, XML fiscal bruto, documentos reais.
- contexto deve conter apenas dados operacionais anonimizados.
- Violação = bloqueio imediato no provider.
"""
from pydantic import BaseModel, ConfigDict
from typing import Literal, Optional


class LLMRequest(BaseModel):
    tarefa: str
    contexto: dict
    provider: Optional[str] = None
    max_tokens: int = 1024
    temperatura: float = 0.2


class LLMResponse(BaseModel):
    provider: str
    modelo: str
    output: dict
    dry_run: bool
    tokens_utilizados: Optional[int] = None
    latencia_ms: Optional[int] = None
    erro: Optional[str] = None


class AgentOutputSchema(BaseModel):
    """
    Contrato obrigatório de output para agentes L3.
    Todo output LLM é validado aqui antes de chegar ao agente.
    Campos extras são proibidos. classificacao deve ser Literal.
    """
    classificacao: Literal["P0", "P1", "P2", "dry_run"]
    causa_provavel: str
    evidencias: list[str]
    ficheiros_provaveis: list[str]
    teste_recomendado: Optional[str] = None
    patch_sugerido_texto: Optional[str] = None
    risco_patch: Optional[str] = None
    informacao_em_falta: list[str]

    model_config = ConfigDict(extra="forbid")
