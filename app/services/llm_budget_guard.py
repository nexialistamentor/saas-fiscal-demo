"""
LLMBudgetGuard — B13-OPS-04.

Travão financeiro soberano antes de qualquer chamada LLM real.

AVISO: contador em memória — apenas para fase dry-run/testes.
Não é controlo financeiro L3 definitivo.
Antes de uso real em produção: persistir contadores em Redis ou Postgres.
Em Railway/Vercel, memória pode resetar em deploy, restart ou múltiplos workers.

Sequência de verificação (ordem é lei):
1. LLM_ALLOW_REAL_CALLS=false → bloqueia sempre (travão absoluto)
2. input_chars > LLM_MAX_INPUT_CHARS → bloqueia
3. max_output_tokens > LLM_MAX_OUTPUT_TOKENS → bloqueia
4. motivo ausente e LLM_REQUIRE_REASON=true → bloqueia
5. LLM_BUDGET_ENABLED=true + diário excedido → bloqueia
6. LLM_BUDGET_ENABLED=true + mensal excedido → bloqueia
7. Tudo OK → permite + devolve limites restantes
"""
import os
from app.schemas.llm_usage_schema import BudgetCheckRequest, BudgetCheckResult

# Contadores em memória — resetam com restart do processo
_contador_diario: int = 0
_contador_mensal: int = 0


def _reset_contadores() -> None:
    """Apenas para testes — nunca chamar em produção."""
    global _contador_diario, _contador_mensal
    _contador_diario = 0
    _contador_mensal = 0


def _incrementar() -> None:
    global _contador_diario, _contador_mensal
    _contador_diario += 1
    _contador_mensal += 1


def verificar(request: BudgetCheckRequest) -> BudgetCheckResult:
    """
    Verifica se a chamada LLM é permitida pela política de orçamento.
    Deve ser chamado apenas para eventos desconhecidos em modo_llm=fallback.
    Eventos conhecidos por sentinela nunca devem passar aqui.
    """
    allow_real = os.getenv("LLM_ALLOW_REAL_CALLS", "false").lower() == "true"
    budget_enabled = os.getenv("LLM_BUDGET_ENABLED", "true").lower() == "true"
    daily_max = int(os.getenv("LLM_DAILY_MAX_CALLS", "20"))
    monthly_max = int(os.getenv("LLM_MONTHLY_MAX_CALLS", "300"))
    max_input_chars = int(os.getenv("LLM_MAX_INPUT_CHARS", "12000"))
    require_reason = os.getenv("LLM_REQUIRE_REASON", "true").lower() == "true"

    estimativa_tokens = request.input_chars // 4

    # 1. Travão absoluto
    if not allow_real:
        return BudgetCheckResult(
            permitido=False,
            motivo="LLM_ALLOW_REAL_CALLS=false — travão absoluto activo",
            estimativa_tokens_input=estimativa_tokens,
        )

    # 2. Input demasiado grande
    if request.input_chars > max_input_chars:
        return BudgetCheckResult(
            permitido=False,
            motivo=f"input_chars={request.input_chars} excede LLM_MAX_INPUT_CHARS={max_input_chars}",
            estimativa_tokens_input=estimativa_tokens,
        )

    # 3. Output demasiado grande
    max_output_tokens_env = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1024"))
    if request.max_output_tokens > max_output_tokens_env:
        return BudgetCheckResult(
            permitido=False,
            motivo=f"max_output_tokens={request.max_output_tokens} excede LLM_MAX_OUTPUT_TOKENS={max_output_tokens_env}",
            estimativa_tokens_input=estimativa_tokens,
            max_output_tokens=max_output_tokens_env,
        )

    # 4. Motivo obrigatório
    if require_reason and not request.motivo:
        return BudgetCheckResult(
            permitido=False,
            motivo="LLM_REQUIRE_REASON=true — motivo operacional obrigatório",
            estimativa_tokens_input=estimativa_tokens,
        )

    # 5. Orçamento diário
    if budget_enabled and _contador_diario >= daily_max:
        return BudgetCheckResult(
            permitido=False,
            motivo=f"Orçamento diário excedido ({_contador_diario}/{daily_max})",
            daily_remaining=0,
            monthly_remaining=max(0, monthly_max - _contador_mensal),
            estimativa_tokens_input=estimativa_tokens,
        )

    # 6. Orçamento mensal
    if budget_enabled and _contador_mensal >= monthly_max:
        return BudgetCheckResult(
            permitido=False,
            motivo=f"Orçamento mensal excedido ({_contador_mensal}/{monthly_max})",
            daily_remaining=max(0, daily_max - _contador_diario),
            monthly_remaining=0,
            estimativa_tokens_input=estimativa_tokens,
        )

    # 7. Permitido — incrementa e devolve limites
    _incrementar()
    return BudgetCheckResult(
        permitido=True,
        motivo="evento_desconhecido_sem_sentinela",
        daily_remaining=daily_max - _contador_diario,
        monthly_remaining=monthly_max - _contador_mensal,
        max_output_tokens=request.max_output_tokens,
        estimativa_tokens_input=estimativa_tokens,
    )
