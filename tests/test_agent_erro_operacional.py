"""
Testes B13-OPS-03 — AgentErroOperacional.

Critério principal: motor-first, LLM-last.
Eventos conhecidos (B13) → sentinela local, zero tokens.
Eventos desconhecidos → LLMRouter mock em fallback.
"""
import pytest
from unittest.mock import patch

from app.schemas.evento_operacional import EventoOperacional
from app.schemas.llm_schema import AgentOutputSchema
from app.agents.agent_erro_operacional import AgentErroOperacional

agent = AgentErroOperacional()


# --- fixtures B13 ---

EVENTO_P006 = EventoOperacional(
    tipo="race_condition_frontend",
    origem="validarSessao",
    mensagem="Termos de Uso não aceites",
    endpoint="/empresas/",
    status_http=403,
)

EVENTO_P007 = EventoOperacional(
    tipo="cta_login_contexto_perdido",
    origem="App.jsx",
    mensagem="CTA login não preserva email do registo",
    endpoint=None,
    status_http=None,
)

EVENTO_CNAE = EventoOperacional(
    tipo="cnae_errado",
    origem="formalizacao_router",
    mensagem="CNAE retornou 5811 livros para actividade software SaaS",
    endpoint="/formalizacao/recomendar-cnae",
    status_http=200,
)

EVENTO_MEI = EventoOperacional(
    tipo="mei_inelegivel_sem_alerta",
    origem="formalizacao_router",
    mensagem="MEI com faturamento 500000 sem bloqueio de inelegibilidade",
    endpoint="/formalizacao/simular-empresa",
    status_http=200,
)

EVENTO_FATURAMENTO_ZERO = EventoOperacional(
    tipo="validacao_tecnica",
    origem="formalizacao_router",
    mensagem="faturamento zero retornou 422 técnico",
    endpoint="/formalizacao/simular-empresa",
    status_http=422,
)

EVENTO_DESCONHECIDO = EventoOperacional(
    tipo="erro_desconhecido",
    origem="servico_x",
    mensagem="timeout inesperado em operação interna",
)




# --- testes sentinela _sentinela_upload_xml_500 (B13-PILOT0-001) ---



EVENTO_UPLOAD_500 = EventoOperacional(

    tipo="HTTP_500_ENDPOINT",

    origem="smoke_pilot0_flow",

    mensagem="POST /upload-xml devolveu 500 com body vazio apos auth completo em producao.",

    endpoint="/upload-xml",

    status_http=500,

    ambiente="production",

    commit_sha="ceb8cfb",

)



EVENTO_UPLOAD_500_PREFIXO = EventoOperacional(

    tipo="HTTP_500_ENDPOINT",

    origem="middleware",

    mensagem="500 em rota fiscal/upload-xml",

    endpoint="/fiscal/upload-xml",

    status_http=500,

)



EVENTO_UPLOAD_422 = EventoOperacional(

    tipo="HTTP_422_ENDPOINT",

    origem="smoke",

    mensagem="POST /upload-xml devolveu 422 — validacao fiscal",

    endpoint="/upload-xml",

    status_http=422,

)



EVENTO_OUTRO_500 = EventoOperacional(

    tipo="HTTP_500_ENDPOINT",

    origem="servico_x",

    mensagem="500 em endpoint diferente",

    endpoint="/fiscal/calcular",

    status_http=500,

)





@pytest.mark.asyncio

async def test_upload_xml_500_classificado_p0_sem_llm():

    """B13-PILOT0-001: sentinela detecta 500 em /upload-xml sem chamar LLMRouter."""

    with patch("app.services.llm_router.completar") as mock_llm:

        resultado = await agent.run(EVENTO_UPLOAD_500)

        mock_llm.assert_not_called()

    assert resultado.classificacao == "P0"





@pytest.mark.asyncio

async def test_upload_xml_500_ficheiros_provaveis():

    """Sentinela aponta para ficheiros correctos."""

    resultado = await agent.run(EVENTO_UPLOAD_500, modo_llm="never")

    assert any("main.py" in f for f in resultado.ficheiros_provaveis)

    assert any("registro_analise_service" in f for f in resultado.ficheiros_provaveis)





@pytest.mark.asyncio

async def test_upload_xml_500_teste_recomendado_presente():

    """Sentinela devolve teste_recomendado nao nulo."""

    resultado = await agent.run(EVENTO_UPLOAD_500, modo_llm="never")

    assert resultado.teste_recomendado is not None

    assert len(resultado.teste_recomendado) > 0





@pytest.mark.asyncio

async def test_upload_xml_500_informacao_em_falta():

    """Sentinela devolve informacao_em_falta com stack trace e corpos de servico."""

    resultado = await agent.run(EVENTO_UPLOAD_500, modo_llm="never")

    assert isinstance(resultado.informacao_em_falta, list)

    assert len(resultado.informacao_em_falta) > 0

    textos = " ".join(resultado.informacao_em_falta).lower()

    assert "stack" in textos or "executar_analise" in textos or "ler_xml" in textos





@pytest.mark.asyncio

async def test_upload_xml_500_prefixo_diferente_tambem_classificado():

    """Sentinela activa para /fiscal/upload-xml (prefixo diferente)."""

    with patch("app.services.llm_router.completar") as mock_llm:

        resultado = await agent.run(EVENTO_UPLOAD_500_PREFIXO)

        mock_llm.assert_not_called()

    assert resultado.classificacao == "P0"





@pytest.mark.asyncio

async def test_upload_xml_422_nao_activa_sentinela():

    """Sentinela nao activa para 422 — so para 500."""

    with patch("app.services.llm_router.completar") as mock_llm:

        mock_llm.return_value = type("R", (), {

            "erro": None,

            "output": {

                "classificacao": "P2",

                "causa_provavel": "mock",

                "evidencias": [],

                "ficheiros_provaveis": [],

                "informacao_em_falta": [],

            }

        })()

        resultado = await agent.run(EVENTO_UPLOAD_422, modo_llm="fallback")

    assert resultado.classificacao != "P0" or "upload-xml" not in (EVENTO_UPLOAD_422.endpoint or "")





@pytest.mark.asyncio

async def test_outro_500_nao_activa_sentinela_upload():

    """Sentinela upload nao activa para 500 em endpoint diferente."""

    with patch("app.services.llm_router.completar") as mock_llm:

        mock_llm.return_value = type("R", (), {

            "erro": None,

            "output": {

                "classificacao": "P2",

                "causa_provavel": "mock",

                "evidencias": [],

                "ficheiros_provaveis": [],

                "informacao_em_falta": [],

            }

        })()

        resultado = await agent.run(EVENTO_OUTRO_500, modo_llm="fallback")

    assert resultado.classificacao == "P2"





# --- testes sentinelas (zero tokens) ---

@pytest.mark.asyncio
async def test_b13_p006_classificado_p0_sem_llm():
    """B13-P0-06: sentinela detecta race condition sem chamar LLMRouter."""
    with patch("app.services.llm_router.completar") as mock_llm:
        resultado = await agent.run(EVENTO_P006)
        mock_llm.assert_not_called()

    assert resultado.classificacao == "P0"
    assert "App.jsx" in " ".join(resultado.ficheiros_provaveis)
    assert "termos" in resultado.teste_recomendado.lower() or "empresas" in resultado.teste_recomendado.lower()


@pytest.mark.asyncio
async def test_b13_p007_classificado_p0_sem_llm():
    """B13-P0-07: sentinela detecta CTA login sem chamar LLMRouter."""
    with patch("app.services.llm_router.completar") as mock_llm:
        resultado = await agent.run(EVENTO_P007)
        mock_llm.assert_not_called()

    assert resultado.classificacao == "P0"
    assert "App.jsx" in " ".join(resultado.ficheiros_provaveis)


@pytest.mark.asyncio
async def test_cnae_saas_errado_p0_sem_llm():
    with patch("app.services.llm_router.completar") as mock_llm:
        resultado = await agent.run(EVENTO_CNAE)
        mock_llm.assert_not_called()

    assert resultado.classificacao == "P0"
    assert any("cnae" in f.lower() for f in resultado.ficheiros_provaveis)


@pytest.mark.asyncio
async def test_mei_limite_excedido_p0_sem_llm():
    with patch("app.services.llm_router.completar") as mock_llm:
        resultado = await agent.run(EVENTO_MEI)
        mock_llm.assert_not_called()

    assert resultado.classificacao == "P0"


@pytest.mark.asyncio
async def test_faturamento_zero_p0_sem_llm():
    with patch("app.services.llm_router.completar") as mock_llm:
        resultado = await agent.run(EVENTO_FATURAMENTO_ZERO)
        mock_llm.assert_not_called()

    assert resultado.classificacao == "P0"


@pytest.mark.asyncio
async def test_sentinela_tempo_normativo_ausente_classifica_p0():
    evento = EventoOperacional(
        tipo="calculo_sem_tempo_normativo",
        mensagem="TEMPO_NORMATIVO_AUSENTE: Simples Nacional sem ano_referencia",
        origem="imposto_router",
        endpoint="/imposto/simples-nacional",
    )
    with patch("app.services.llm_router.completar") as mock_llm:
        resultado = await agent.run(evento, modo_llm="never")
        mock_llm.assert_not_called()

    assert resultado.classificacao == "P0"


# --- testes modo_llm ---

@pytest.mark.asyncio
async def test_evento_desconhecido_never_nao_chama_llm():
    """modo_llm=never: evento desconhecido não chama LLMRouter."""
    with patch("app.services.llm_router.completar") as mock_llm:
        resultado = await agent.run(EVENTO_DESCONHECIDO, modo_llm="never")
        mock_llm.assert_not_called()

    assert resultado.classificacao == "P2"
    assert len(resultado.informacao_em_falta) > 0


@pytest.mark.asyncio
async def test_evento_desconhecido_fallback_chama_llm(monkeypatch):
    """modo_llm=fallback: evento desconhecido chama LLMRouter mock."""
    from app.schemas.llm_schema import LLMResponse

    monkeypatch.setenv("LLM_ALLOW_REAL_CALLS", "true")

    mock_resposta = LLMResponse(
        provider="mock",
        modelo="mock-v1",
        output={
            "classificacao": "P2",
            "causa_provavel": "mock",
            "evidencias": [],
            "ficheiros_provaveis": [],
            "teste_recomendado": None,
            "patch_sugerido_texto": None,
            "risco_patch": "baixo",
            "informacao_em_falta": [],
        },
        dry_run=True,
    )
    with patch("app.services.llm_router.completar", return_value=mock_resposta) as mock_llm:
        resultado = await agent.run(EVENTO_DESCONHECIDO, modo_llm="fallback")
        mock_llm.assert_called_once()

    assert isinstance(resultado, AgentOutputSchema)


# --- output valida contra schema ---

@pytest.mark.asyncio
async def test_output_valida_contra_agent_output_schema():
    resultado = await agent.run(EVENTO_P006)
    assert isinstance(resultado, AgentOutputSchema)
    assert resultado.classificacao in ("P0", "P1", "P2", "dry_run")


# --- agente não escreve na BD ---

@pytest.mark.asyncio
async def test_agente_nao_escreve_bd():
    """Agente não importa SessionLocal nem AlertaFiscal."""
    import app.agents.agent_erro_operacional as modulo

    assert not hasattr(modulo, "SessionLocal")
    assert not hasattr(modulo, "AlertaFiscal")
