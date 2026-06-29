"""
LLM Usage Schema — contrato de governança de custo LLM.
"""
from pydantic import BaseModel
from typing import Optional


class BudgetCheckRequest(BaseModel):
    provider: str = "deepseek"
    tarefa: str
    motivo: Optional[str] = None
    input_chars: int = 0
    max_output_tokens: int = 1024


class BudgetCheckResult(BaseModel):
    permitido: bool
    motivo: str
    daily_remaining: Optional[int] = None
    monthly_remaining: Optional[int] = None
    max_output_tokens: Optional[int] = None
    estimativa_tokens_input: Optional[int] = None
