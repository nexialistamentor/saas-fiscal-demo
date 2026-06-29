"""
AgentErroOperacional — B13-OPS-03.

Arquitectura: motor-first, LLM-last.

Sequência obrigatória:
1. Sentinelas determinísticas (zero tokens, zero custo).
2. Padrões aprendidos locais (zero tokens).
3. LLMRouter — só se modo_llm="fallback" e nenhuma camada anterior reconheceu.

Não escreve na BD.
Não entra no AgentRegistry nem AgentExecutor (ainda).
Não cria endpoint público.
Não usa modo_llm="always".
"""
from __future__ import annotations

from typing import Literal

from app.schemas.evento_operacional import EventoOperacional
from app.schemas.llm_schema import AgentOutputSchema, LLMRequest


# ---------------------------------------------------------------------------
# Camada 1 — Sentinelas determinísticas
# Cada sentinela recebe o evento e devolve AgentOutputSchema ou None.
# ---------------------------------------------------------------------------

def _sentinela_race_condition_termos(evento: EventoOperacional) -> AgentOutputSchema | None:
    """B13-P0-06 — dashboard disparou antes do gate de termos."""
    if (
        evento.status_http == 403
        and evento.endpoint is not None
        and "/empresas" in evento.endpoint
        and "termos" in evento.mensagem.lower()
    ):
        return AgentOutputSchema(
            classificacao="P0",
            causa_provavel=(
                "Race condition: setUsuario() foi chamado antes de verificar "
                "has-accepted-terms. O dashboard disparou /empresas/ sem gate de termos."
            ),
            evidencias=[
                f"HTTP 403 em {evento.endpoint}",
                f"Mensagem: {evento.mensagem}",
                f"Origem: {evento.origem}",
            ],
            ficheiros_provaveis=["frontend-dashboard/src/App.jsx"],
            teste_recomendado=(
                "Login com termos=false não deve chamar /empresas/. "
                "Verificar que has-accepted-terms é consultado antes de setUsuario()."
            ),
            patch_sugerido_texto=(
                "Mover verificação de has-accepted-terms para antes de setUsuario() em App.jsx."
            ),
            risco_patch="baixo",
            informacao_em_falta=[],
        )
    return None


def _sentinela_cta_login_contexto_perdido(evento: EventoOperacional) -> AgentOutputSchema | None:
    """B13-P0-07 — CTA 'Fazer login aqui' não preserva email do registo."""
    if evento.tipo == "cta_login_contexto_perdido" or (
        "fazer login" in evento.mensagem.lower()
        or "cta login" in evento.mensagem.lower()
        or ("email" in evento.mensagem.lower() and "registo" in evento.mensagem.lower())
    ):
        return AgentOutputSchema(
            classificacao="P0",
            causa_provavel=(
                "onClick do CTA 'Fazer login aqui' só executa setMostrarRegisto(false), "
                "sem chamar setEmail(emailRegisto). Email preenchido no registo perde-se."
            ),
            evidencias=[
                f"Origem: {evento.origem}",
                f"Mensagem: {evento.mensagem}",
            ],
            ficheiros_provaveis=["frontend-dashboard/src/App.jsx"],
            teste_recomendado=(
                "Preencher email no registo → clicar 'Fazer login aqui' → "
                "verificar que o campo email no login está preenchido."
            ),
            patch_sugerido_texto=(
                "onClick={() => { setEmail(emailRegisto); setMostrarRegisto(false) }}"
            ),
            risco_patch="baixo",
            informacao_em_falta=[],
        )
    return None


def _sentinela_vercel_env_vazia(evento: EventoOperacional) -> AgentOutputSchema | None:
    """Vercel VITE_API_URL vazia → frontend aponta para string vazia."""
    if (
        "vite_api_url" in evento.mensagem.lower()
        or "variável de ambiente" in evento.mensagem.lower()
        and "vercel" in evento.mensagem.lower()
    ):
        return AgentOutputSchema(
            classificacao="P0",
            causa_provavel="VITE_API_URL não definida nas variáveis de ambiente do Vercel.",
            evidencias=[f"Mensagem: {evento.mensagem}"],
            ficheiros_provaveis=["vercel.json", ".env.example"],
            teste_recomendado="Verificar VITE_API_URL nas env vars do Vercel dashboard.",
            patch_sugerido_texto="Preencher VITE_API_URL com URL de produção do Railway.",
            risco_patch="baixo",
            informacao_em_falta=[],
        )
    return None


def _sentinela_cnae_saas_errado(evento: EventoOperacional) -> AgentOutputSchema | None:
    """CNAE software → 5811 (edição de livros) em vez de 62xx."""
    if (
        "cnae" in evento.mensagem.lower()
        and ("5811" in evento.mensagem or "livro" in evento.mensagem.lower())
    ):
        return AgentOutputSchema(
            classificacao="P0",
            causa_provavel=(
                "Motor CNAE retornou 5811 (edição de livros) para actividade SaaS/software. "
                "Keywords do utilizador estão a bater em CNAE errado."
            ),
            evidencias=[f"Mensagem: {evento.mensagem}"],
            ficheiros_provaveis=[
                "app/services/cnae_engine.py",
                "data/cnae/cnae_keywords.json",
            ],
            teste_recomendado=(
                "Pesquisar 'software' no motor CNAE e verificar que resultado é 62xx."
            ),
            patch_sugerido_texto="Adicionar lista curada 62xx + gatilho tech em cnae_keywords.json.",
            risco_patch="medio",
            informacao_em_falta=[],
        )
    return None


def _sentinela_mei_limite_excedido(evento: EventoOperacional) -> AgentOutputSchema | None:
    """MEI + faturamento > limite anual sem bloqueio."""
    if (
        "mei" in evento.mensagem.lower()
        and any(t in evento.mensagem for t in ["500", "inelegível", "limite"])
    ):
        return AgentOutputSchema(
            classificacao="P0",
            causa_provavel=(
                "Simulação MEI com faturamento acima do limite anual não gerou alerta de inelegibilidade."
            ),
            evidencias=[f"Mensagem: {evento.mensagem}"],
            ficheiros_provaveis=[
                "app/routers/formalizacao_router.py",
                "app/services/tax_engines/mei_constants.py",
            ],
            teste_recomendado=(
                "Simular MEI com faturamento=500000 e verificar que resposta inclui alerta de inelegibilidade."
            ),
            patch_sugerido_texto=(
                "Adicionar validação explícita com MEI_LIMITE_ANUAL_FATURAMENTO no router."
            ),
            risco_patch="medio",
            informacao_em_falta=[],
        )
    return None


def _sentinela_faturamento_zero(evento: EventoOperacional) -> AgentOutputSchema | None:
    """Faturamento zero → 422 técnico em vez de resposta soberana."""
    if (
        evento.status_http == 422
        and "faturamento" in evento.mensagem.lower()
        and ("zero" in evento.mensagem.lower() or "0" in evento.mensagem)
    ):
        return AgentOutputSchema(
            classificacao="P0",
            causa_provavel=(
                "Validator gt=0 em SimularEmpresaRequest rejeita faturamento=0 com 422 técnico "
                "em vez de resposta soberana."
            ),
            evidencias=[
                f"HTTP 422 em {evento.endpoint}",
                f"Mensagem: {evento.mensagem}",
            ],
            ficheiros_provaveis=["app/routers/formalizacao_router.py"],
            teste_recomendado="POST /simular-empresa com faturamento=0 deve retornar resposta soberana, não 422.",
            patch_sugerido_texto="Mudar validator gt=0 para ge=0 e tratar faturamento=0 com resposta informativa.",
            risco_patch="baixo",
            informacao_em_falta=[],
        )
    return None


# Registo de sentinelas — ordem importa (mais específica primeiro)
_SENTINELAS = [
    _sentinela_race_condition_termos,
    _sentinela_cta_login_contexto_perdido,
    _sentinela_vercel_env_vazia,
    _sentinela_cnae_saas_errado,
    _sentinela_mei_limite_excedido,
    _sentinela_faturamento_zero,
]


# ---------------------------------------------------------------------------
# Camada 2 — Padrões aprendidos locais
# Estrutura preparada para receber padrões após aprovação Miguel/GPT.
# Começa vazia — será populada via B13-OPS-03.x.
# ---------------------------------------------------------------------------

_PADROES_APRENDIDOS: list[dict] = []


def _tentar_padrao_aprendido(evento: EventoOperacional) -> AgentOutputSchema | None:
    """Tenta match em padrões previamente aprovados e internalizados."""
    for padrao in _PADROES_APRENDIDOS:
        if (
            padrao.get("tipo") == evento.tipo
            and padrao.get("status_http") == evento.status_http
            and padrao.get("endpoint") in (evento.endpoint or "")
        ):
            return AgentOutputSchema(**padrao["output"])
    return None


# ---------------------------------------------------------------------------
# Agente principal
# ---------------------------------------------------------------------------

class AgentErroOperacional:
    """
    Motor de reconhecimento operacional.
    motor-first, LLM-last.
    """
    name = "agent_erro_operacional"
    permissions = ["read_eventos_operacionais"]

    async def run(
        self,
        evento: EventoOperacional,
        modo_llm: Literal["never", "fallback"] = "fallback",
    ) -> AgentOutputSchema:

        # Camada 1 — sentinelas determinísticas
        for sentinela in _SENTINELAS:
            resultado = sentinela(evento)
            if resultado is not None:
                return resultado

        # Camada 2 — padrões aprendidos
        resultado = _tentar_padrao_aprendido(evento)
        if resultado is not None:
            return resultado

        # Camada 3 — LLMRouter (só em fallback)
        if modo_llm == "fallback":
            from app.services.llm_router import completar

            request = LLMRequest(
                tarefa="diagnostico_erro",
                contexto={
                    "tipo": evento.tipo,
                    "origem": evento.origem,
                    "mensagem": evento.mensagem,
                    "endpoint": evento.endpoint,
                    "status_http": evento.status_http,
                    "ambiente": evento.ambiente,
                },
                provider="mock",  # dry-run por defeito; mudar para "deepseek" quando real
            )
            resposta = completar(request)
            if resposta.erro:
                return AgentOutputSchema(
                    classificacao="P2",
                    causa_provavel="LLMRouter retornou erro — análise incompleta.",
                    evidencias=[resposta.erro],
                    ficheiros_provaveis=[],
                    teste_recomendado=None,
                    patch_sugerido_texto=None,
                    risco_patch=None,
                    informacao_em_falta=["Rever evento e tentar novamente."],
                )
            # Se output do LLM não tiver classificacao válida, usa P2 seguro
            output = resposta.output
            if output.get("classificacao") not in ("P0", "P1", "P2", "dry_run"):
                output["classificacao"] = "P2"
            # Garantir campos obrigatórios de lista
            for campo in ("evidencias", "ficheiros_provaveis", "informacao_em_falta"):
                if not isinstance(output.get(campo), list):
                    output[campo] = []
            return AgentOutputSchema(**output)

        # modo_llm="never" e nenhuma camada reconheceu
        return AgentOutputSchema(
            classificacao="P2",
            causa_provavel="Evento não reconhecido por nenhuma sentinela ou padrão aprendido.",
            evidencias=[evento.mensagem],
            ficheiros_provaveis=[evento.ficheiro_provavel] if evento.ficheiro_provavel else [],
            teste_recomendado=None,
            patch_sugerido_texto=None,
            risco_patch=None,
            informacao_em_falta=[
                "Tipo de evento desconhecido. Analisar manualmente e criar sentinela se confirmado."
            ],
        )


agent_erro_operacional = AgentErroOperacional()
