"""
Testes LLMRouter — sem chamada real à API.
Chamada real: DEEPSEEK_INTEGRATION=1 (futuramente, separado).
"""
import pytest
from app.schemas.llm_schema import LLMRequest
from app.services.llm_router import completar
from app.services.llm_providers.mock_provider import MockProvider
from app.services.llm_providers.deepseek_provider import DeepSeekProvider


CONTEXTO_MOCK = {
    "tipo": "race_condition_frontend",
    "endpoint": "/empresas/",
    "status_http": 403,
    "mensagem": "Termos de Uso não aceites",
}


def test_router_usa_mock_por_defeito(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    req = LLMRequest(tarefa="diagnostico_erro", contexto=CONTEXTO_MOCK)
    resp = completar(req)
    assert resp.provider == "mock"
    assert resp.dry_run is True
    assert isinstance(resp.output, dict)
    assert "classificacao" in resp.output


def test_mock_provider_output_estruturado():
    p = MockProvider()
    r = p.completar(tarefa="diagnostico_erro", contexto=CONTEXTO_MOCK)
    campos = ["classificacao", "causa_provavel", "evidencias",
              "ficheiros_provaveis", "teste_recomendado",
              "patch_sugerido_texto", "risco_patch", "informacao_em_falta"]
    for campo in campos:
        assert campo in r["output"], f"Campo ausente: {campo}"


def test_deepseek_dry_run_por_defeito(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_DRY_RUN", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    p = DeepSeekProvider()
    r = p.completar(tarefa="diagnostico_erro", contexto=CONTEXTO_MOCK)
    assert r["dry_run"] is True
    assert r["modelo"] == "deepseek-v4-flash"


def test_deepseek_bloqueia_campo_proibido(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_DRY_RUN", "true")
    p = DeepSeekProvider()
    with pytest.raises(ValueError, match="campo proibido"):
        p.completar(tarefa="diagnostico_erro", contexto={"cpf": "123.456.789-00"})


def test_deepseek_bloqueia_campo_proibido_aninhado(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_DRY_RUN", "true")
    p = DeepSeekProvider()
    with pytest.raises(ValueError, match="campo proibido"):
        p.completar(
            tarefa="diagnostico_erro",
            contexto={"usuario": {"cpf": "123.456.789-00"}},
        )


def test_deepseek_bloqueia_chave_parcial(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_DRY_RUN", "true")
    p = DeepSeekProvider()
    with pytest.raises(ValueError, match="campo proibido"):
        p.completar(
            tarefa="diagnostico_erro",
            contexto={"cpf_cliente": "123.456.789-00"},
        )


def test_router_deepseek_dry_run(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_DRY_RUN", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    req = LLMRequest(tarefa="diagnostico_erro", contexto=CONTEXTO_MOCK, provider="deepseek")
    resp = completar(req)
    assert resp.provider == "deepseek"
    assert resp.dry_run is True
    assert resp.modelo == "deepseek-v4-flash"


def test_router_resolve_provider_via_ambiente(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_DRY_RUN", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    # request sem provider — deve usar o ambiente
    req = LLMRequest(tarefa="diagnostico_erro", contexto=CONTEXTO_MOCK)
    resp = completar(req)
    assert resp.provider == "deepseek"
    assert resp.dry_run is True


def test_llm_request_defaults():
    req = LLMRequest(tarefa="analise_cnae", contexto={"cnae": "6201-5/01"})
    assert req.provider is None
    assert req.max_tokens == 1024
    assert req.temperatura == 0.2


def test_deepseek_bloqueia_cpf_em_valor(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_DRY_RUN", "true")
    p = DeepSeekProvider()
    with pytest.raises(ValueError, match="CPF"):
        p.completar(
            tarefa="diagnostico_erro",
            contexto={"mensagem": "erro do utilizador com CPF 123.456.789-00"},
        )


def test_deepseek_bloqueia_email_em_valor(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_DRY_RUN", "true")
    p = DeepSeekProvider()
    with pytest.raises(ValueError, match="email"):
        p.completar(
            tarefa="diagnostico_erro",
            contexto={"mensagem": "utilizador joao@email.com falhou"},
        )


def test_deepseek_bloqueia_xml_nfe_em_valor(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_DRY_RUN", "true")
    p = DeepSeekProvider()
    with pytest.raises(ValueError, match="XML NFe"):
        p.completar(
            tarefa="diagnostico_erro",
            contexto={"body": "<NFe xmlns='http://www.portalfiscal.inf.br/nfe'>..."},
        )


def test_deepseek_bloqueia_jwt_em_valor(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_DRY_RUN", "true")
    p = DeepSeekProvider()
    with pytest.raises(ValueError, match="JWT"):
        p.completar(
            tarefa="diagnostico_erro",
            contexto={"auth": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.abc123"},
        )


# --- B13-OPS-02.2 — validação AgentOutputSchema ---

from app.schemas.llm_schema import AgentOutputSchema
from pydantic import ValidationError

OUTPUT_VALIDO = {
    "classificacao": "P0",
    "causa_provavel": "race condition no frontend",
    "evidencias": ["log linha 42"],
    "ficheiros_provaveis": ["App.jsx"],
    "teste_recomendado": "teste manual T3",
    "patch_sugerido_texto": None,
    "risco_patch": "baixo",
    "informacao_em_falta": [],
}


def test_agent_output_schema_valido():
    schema = AgentOutputSchema(**OUTPUT_VALIDO)
    assert schema.classificacao == "P0"
    assert isinstance(schema.evidencias, list)


def test_agent_output_schema_sem_classificacao():
    dados = {k: v for k, v in OUTPUT_VALIDO.items() if k != "classificacao"}
    with pytest.raises(ValidationError):
        AgentOutputSchema(**dados)


def test_agent_output_schema_classificacao_invalida():
    dados = {**OUTPUT_VALIDO, "classificacao": "urgente"}
    with pytest.raises(ValidationError):
        AgentOutputSchema(**dados)


def test_agent_output_schema_evidencias_tipo_errado():
    dados = {**OUTPUT_VALIDO, "evidencias": "nao sou uma lista"}
    with pytest.raises(ValidationError):
        AgentOutputSchema(**dados)


def test_agent_output_schema_campo_extra_proibido():
    dados = {**OUTPUT_VALIDO, "decisao_fiscal": "aprovar MEI"}
    with pytest.raises(ValidationError):
        AgentOutputSchema(**dados)


def test_mock_provider_output_valida_contra_agent_schema():
    p = MockProvider()
    r = p.completar(tarefa="diagnostico_erro", contexto=CONTEXTO_MOCK)
    # mock devolve classificacao="P2" — deve passar no schema
    schema = AgentOutputSchema(**r["output"])
    assert schema.classificacao == "P2"
