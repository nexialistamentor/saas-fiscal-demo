"""
EventoOperacional — contrato de entrada para AgentErroOperacional.

REGRAS DE SEGURANÇA:
- Nunca incluir: CPF, CNPJ, email, token, XML fiscal bruto, payload real.
- contexto deve conter apenas dados operacionais anonimizados.
"""
from typing import Optional

from pydantic import BaseModel, Field


class EventoOperacional(BaseModel):
    tipo: str
    origem: str
    mensagem: str
    endpoint: Optional[str] = None
    status_http: Optional[int] = None
    ambiente: str = "local"
    commit_sha: Optional[str] = None
    ficheiro_provavel: Optional[str] = None
    contexto: dict = Field(default_factory=dict)
