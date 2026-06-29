"""
LLM Schema — contrato soberano para o LLMRouter.

REGRAS DE SANITIZAÇÃO (obrigatórias antes de qualquer chamada LLM):
- Nunca enviar: CPF, CNPJ, email completo, token, XML fiscal bruto, documentos reais.
- contexto deve conter apenas dados operacionais anonimizados.
- Violação = bloqueio imediato no provider.
"""
from pydantic import BaseModel
from typing import Optional


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
