"""
LLMRouter — barramento soberano de análise para agentes.
Não é um chat genérico. Cada chamada tem tarefa + contexto estruturado.

Resolução de provider (por prioridade):
1. request.provider (se vier definido)
2. LLM_PROVIDER do ambiente
3. mock (fallback seguro)
"""
import os
from app.schemas.llm_schema import LLMRequest, LLMResponse
from app.services.llm_providers.mock_provider import MockProvider
from app.services.llm_providers.deepseek_provider import DeepSeekProvider

PROVIDERS = {
    "deepseek": DeepSeekProvider,
    "mock": MockProvider,
}


def get_provider(nome: str | None = None):
    nome_resolvido = (nome or os.getenv("LLM_PROVIDER", "mock")).lower()
    cls = PROVIDERS.get(nome_resolvido, MockProvider)
    return cls()


def completar(request: LLMRequest) -> LLMResponse:
    provider = get_provider(request.provider)
    resultado = provider.completar(
        tarefa=request.tarefa,
        contexto=request.contexto,
        max_tokens=request.max_tokens,
        temperatura=request.temperatura,
    )
    return LLMResponse(**resultado)
