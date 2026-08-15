"""
Testes ADR-015 B14.3G — canário de pré-execução do fallback LLM operacional.

Cobrem contrato, fronteira da missão, precedência, bloqueios, contexto,
resultado universal, elegibilidade determinística, drift do legado,
segurança, ausência de chamada LLM e integridade estrutural.

Nenhum teste contacta rede, provider, router, BudgetGuard, BD, ORM,
filesystem do repositório, scheduler, registry ou executor.
"""

from __future__ import annotations

import ast
import inspect
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import get_args
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from tests.canonical_source_hash import canonical_source_sha256

import app.agents.adapters.agent_erro_operacional_llm_fallback as adapter_module
import app.agents.engines.agent_erro_operacional_llm_fallback as engine_module
from app.agents.adapters.agent_erro_operacional_llm_fallback import (
    execute_agent_erro_operacional_llm_fallback_mission,
)
from app.agents.contracts.agent_erro_operacional import (
    MAPA_SENTINELAS_PARA_CODIGOS,
    NOMES_SENTINELAS_CANONICOS,
    PERFIS_DIAGNOSTICOS_CANONICOS,
    SCHEMA_DRIFT_REPRESENTACAO_LEGADA,
    OperationalEventSnapshot,
    OperationalGlobalEventSnapshot,
    OperationalTenantEventSnapshot,
)
from app.agents.contracts.agent_erro_operacional_llm_fallback import (
    AGENT_VERSION_INCOMPATIBLE,
    AGENT_VERSION_INCOMPATIBLE_MESSAGE,
    AG_OPERATIONAL_LLM_FALLBACK_BUDGET_NOT_AUTHORIZED,
    AG_OPERATIONAL_LLM_FALLBACK_BUDGET_NOT_AUTHORIZED_MESSAGE,
    AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR,
    AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR_MESSAGE,
    AG_OPERATIONAL_LLM_FALLBACK_NOT_ELIGIBLE,
    AG_OPERATIONAL_LLM_FALLBACK_NOT_ELIGIBLE_MESSAGE,
    AG_OPERATIONAL_LLM_FALLBACK_REAL_CALL_NOT_ENABLED,
    AG_OPERATIONAL_LLM_FALLBACK_REAL_CALL_NOT_ENABLED_MESSAGE,
    EXECUTION_MODE_NOT_AUTHORIZED,
    EXECUTION_MODE_NOT_AUTHORIZED_MESSAGE,
    PERMITE_CHAMADA_REAL_V1,
    AgentErroOperacionalLLMFallbackPreExecutionError,
    AgentErroOperacionalLLMFallbackPreExecutionErrorCode,
    AgentErroOperacionalLLMFallbackResultSafetyError,
    AgentErroOperacionalLLMFallbackResultValidationError,
    OperationalLLMFallbackContext,
    OperationalLLMFallbackLegacyDriftError,
    OperationalLLMFallbackOutput,
    OperationalLLMFallbackPayload,
)
from app.agents.contracts.canonical import (
    build_context_hash,
    build_mission_idempotency_key,
)
from app.agents.contracts.mission import AgentMission
from app.agents.contracts.shared import BudgetPolicy
from app.agents.engines.agent_erro_operacional_llm_fallback import (
    OperationalLLMFallbackUnexpectedExecutionError,
    _reconstruir_contexto_legado,
    _reconstruir_evento_legado,
    _validar_superficie_legada,
    executar_agent_erro_operacional_llm_fallback_engine,
)


ROOT = Path(__file__).resolve().parents[1]

B14_3G_CONTRACT_PATH = (
    "app/agents/contracts/agent_erro_operacional_llm_fallback.py"
)
B14_3G_ENGINE_PATH = (
    "app/agents/engines/agent_erro_operacional_llm_fallback.py"
)
B14_3G_ADAPTER_PATH = (
    "app/agents/adapters/agent_erro_operacional_llm_fallback.py"
)

B14_3F_CONTRACT_PATH = "app/agents/contracts/agent_erro_operacional.py"
B14_3F_ENGINE_PATH = "app/agents/engines/agent_erro_operacional.py"
B14_3F_ADAPTER_PATH = "app/agents/adapters/agent_erro_operacional.py"
B14_3F_TEST_PATH = "tests/test_agent_erro_operacional_mission_adapter.py"
LEGACY_PATH = "app/agents/agent_erro_operacional.py"

B14_3G_CONTRACT_SHA256 = (
    "67C352789300607FB52619A2E8C97519414D70C95083DCC812D0BF46E1DDFA86"
)
B14_3G_ENGINE_SHA256 = (
    "9C590EF9C72AF10D8B1098E21EDE16D43B78F25C247C4E74DE59B452D2A8BD90"
)
B14_3G_ADAPTER_SHA256 = (
    "13A135BF499DA7AE150855648DAE6997D15A9C89D26E25F1035133C66196E301"
)

B14_3F_CONTRACT_SHA256 = (
    "7A418199963284D1A8EDC475DD80DACA8ECFF1A3A8101297DEF9A094392F8503"
)
B14_3F_ENGINE_SHA256 = (
    "60F4103407CB946134564E45D3F63F97BC86D6A161656470E17452BFA4542891"
)
B14_3F_ADAPTER_SHA256 = (
    "065AE4853339336B01390A03E2B728F6B9683C40E6BBADFB93FBEBC394A4D9FF"
)
B14_3F_TEST_SHA256 = (
    "2E15CA9C6220B83E6D811E0E24E303CFA270197B01886BE268B6D3D512A6EAF3"
)
LEGACY_SHA256 = (
    "B104441EBC8CADB5E17352B5413F2DAD3D334937C421180E74484C1CDA60A790"
)

ENGINE_MODULE = (
    "app.agents.engines.agent_erro_operacional_llm_fallback"
)
LEGACY_MODULE = "app.agents.agent_erro_operacional"

GENERIC_PREEXECUTION_MESSAGE = (
    "A missão de diagnóstico operacional recebida não é "
    "compatível com este agente."
)
CONTEXT_INVALID_MESSAGE = (
    "Não foi possível validar o contexto do evento operacional recebido."
)

EXPECTED_PREEXECUTION_CODES = {
    "MISSION_TARGET_MISMATCH",
    "MISSION_TYPE_UNSUPPORTED",
    "CONTEXT_SCHEMA_UNSUPPORTED",
    "CONTEXT_VERSION_UNSUPPORTED",
    "OUTPUT_SCHEMA_UNSUPPORTED",
    "OUTPUT_VERSION_UNSUPPORTED",
    "MISSION_SCOPE_UNSUPPORTED",
    "MISSION_TENANT_REQUIRED",
    "MISSION_TENANT_UNSUPPORTED",
    "MISSION_ACTOR_UNSUPPORTED",
    "MISSION_ENTITY_UNSUPPORTED",
    "MISSION_REQUESTED_BY_UNSUPPORTED",
    "MISSION_AUTHORITY_UNSUPPORTED",
    "MISSION_ORIGIN_UNSUPPORTED",
    "MISSION_BUDGET_UNSUPPORTED",
    "MISSION_SOURCES_UNSUPPORTED",
    "MISSION_ENVELOPE_UNSUPPORTED",
    "MISSION_PRIORITY_UNSUPPORTED",
    "MISSION_REFERENCE_AT_REQUIRED",
    "MISSION_TEMPORALITY_UNSUPPORTED",
    "AG_OPERATIONAL_LLM_FALLBACK_CONTEXT_INVALID",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _global_snapshot(
    *,
    event_id: UUID | None = None,
    occurred_at: datetime | None = None,
    tipo: str = "evento_operacional_desconhecido",
    origem: str = "pytest_b14_3g",
    mensagem: str = "Evento operacional sem correspondência conhecida.",
    endpoint: str | None = None,
    status_http: int | None = None,
    contexto_indicadores: tuple[str, ...] = (),
) -> OperationalGlobalEventSnapshot:
    return OperationalGlobalEventSnapshot(
        event_id=event_id or uuid4(),
        occurred_at=occurred_at or _now(),
        scope="global",
        tenant_id=None,
        tipo=tipo,
        origem=origem,
        mensagem=mensagem,
        endpoint=endpoint,
        status_http=status_http,
        contexto_indicadores=contexto_indicadores,
    )


def _tenant_snapshot(
    *,
    tenant_id: int = 73,
    event_id: UUID | None = None,
    occurred_at: datetime | None = None,
    tipo: str = "evento_operacional_desconhecido",
    origem: str = "pytest_b14_3g",
    mensagem: str = "Evento tenant sem correspondência conhecida.",
    endpoint: str | None = None,
    status_http: int | None = None,
    contexto_indicadores: tuple[str, ...] = (),
) -> OperationalTenantEventSnapshot:
    return OperationalTenantEventSnapshot(
        event_id=event_id or uuid4(),
        occurred_at=occurred_at or _now(),
        scope="tenant",
        tenant_id=tenant_id,
        tipo=tipo,
        origem=origem,
        mensagem=mensagem,
        endpoint=endpoint,
        status_http=status_http,
        contexto_indicadores=contexto_indicadores,
    )


def _budget_allow_llm() -> BudgetPolicy:
    return BudgetPolicy(
        allow_llm=True,
        allowed_providers=["deepseek"],
        max_calls=1,
        max_input_chars=1000,
        max_output_tokens=256,
        max_cost=Decimal("0.10"),
        currency="BRL",
        on_unavailable="human_review",
    )


def _mission(
    *,
    snapshot: (
        OperationalGlobalEventSnapshot
        | OperationalTenantEventSnapshot
        | None
    ) = None,
    execution_mode: str = "sombra",
    agent_version_required: str | None = "1.0",
    budget_policy: BudgetPolicy | None = None,
    actor_id: int = 1,
) -> AgentMission:
    snapshot = snapshot or _global_snapshot()
    context = snapshot.model_dump(mode="python")
    mission_type = "diagnosticar_evento_operacional_llm_fallback"
    target_agent = "agent_erro_operacional"

    return AgentMission(
        mission_id=uuid4(),
        correlation_id=uuid4(),
        mission_type=mission_type,
        target_agent=target_agent,
        context_schema="agent_erro_operacional_llm_fallback.context",
        context_version="1.0",
        output_schema="agent_erro_operacional_llm_fallback.result",
        output_version="1.0",
        scope=snapshot.scope,
        tenant_id=snapshot.tenant_id,
        actor_id=actor_id,
        entity_type=None,
        entity_id=None,
        source_event_id=snapshot.event_id,
        schedule_slot=None,
        source_request_id=None,
        parent_mission_id=None,
        requested_by="user",
        context=context,
        context_hash=build_context_hash(context),
        authority_level="leitura",
        execution_mode=execution_mode,
        ratification_id=None,
        authorized_by=None,
        authorization_role=None,
        idempotency_key=build_mission_idempotency_key(
            mission_type=mission_type,
            target_agent=target_agent,
            scope=snapshot.scope,
            tenant_id=snapshot.tenant_id,
            entity_type=None,
            entity_id=None,
            source_event_id=snapshot.event_id,
            schedule_slot=None,
            source_request_id=None,
            idempotency_reference_at=None,
        ),
        agent_version_required=agent_version_required,
        priority="alta",
        created_at=snapshot.occurred_at,
        deadline=None,
        reference_at=snapshot.occurred_at,
        idempotency_reference_at=None,
        budget_policy=budget_policy or BudgetPolicy(),
        sources=[],
    )


def _install_fake_engine(
    monkeypatch: pytest.MonkeyPatch,
    *,
    eligible: bool | None = None,
    error: BaseException | None = None,
) -> dict[str, object]:
    calls: dict[str, object] = {
        "count": 0,
        "context": None,
    }
    fake_module = types.ModuleType(ENGINE_MODULE)

    def controlled_engine(context: object) -> bool:
        calls["count"] = int(calls["count"]) + 1
        calls["context"] = context

        if error is not None:
            raise error

        assert eligible is not None
        return eligible

    fake_module.executar_agent_erro_operacional_llm_fallback_engine = (
        controlled_engine
    )
    monkeypatch.setitem(sys.modules, ENGINE_MODULE, fake_module)
    return calls


def _canonical_fake_legacy(
    *,
    outcomes: dict[str, object | BaseException | None] | None = None,
) -> SimpleNamespace:
    outcomes = outcomes or {}
    sentinels: list[object] = []

    for name in NOMES_SENTINELAS_CANONICOS:
        configured = outcomes.get(name)

        def sentinel(
            _: object,
            configured: object | BaseException | None = configured,
        ) -> object | None:
            if isinstance(configured, BaseException):
                raise configured
            return configured

        sentinel.__name__ = name
        sentinels.append(sentinel)

    return SimpleNamespace(
        _SENTINELAS=sentinels,
        _PADROES_APRENDIDOS=[],
    )


def _install_fake_legacy(
    monkeypatch: pytest.MonkeyPatch,
    legacy: object,
) -> None:
    import app.agents as agents_package

    monkeypatch.setitem(sys.modules, LEGACY_MODULE, legacy)
    monkeypatch.setattr(
        agents_package,
        "agent_erro_operacional",
        legacy,
        raising=False,
    )


def _assert_common_result(
    result: object,
    mission: AgentMission,
) -> None:
    assert result.contract_version == "1.0"
    assert result.attempt == 1
    assert result.agent_id == "agent_erro_operacional"
    assert result.agent_version == "1.0"
    assert result.mission_type == mission.mission_type
    assert result.mission_id == mission.mission_id
    assert result.correlation_id == mission.correlation_id
    assert result.scope == mission.scope
    assert result.tenant_id == mission.tenant_id
    assert result.mode == mission.execution_mode
    assert result.started_at.utcoffset() == timedelta(0)
    assert result.finished_at.utcoffset() == timedelta(0)
    assert result.finished_at >= result.started_at
    assert result.duration_ms >= 0
    assert (
        result.finished_at - result.started_at
        == timedelta(milliseconds=result.duration_ms)
    )
    assert result.evidence == []
    assert result.actions_proposed == []
    assert result.actions_executed == []
    assert result.requires_human_review is True
    assert (
        result.payload_schema
        == "agent_erro_operacional_llm_fallback.result"
    )
    assert result.payload_version == "1.0"
    assert result.payload == {}
    assert result.llm_used is False
    assert result.provider is None
    assert result.tokens_used is None
    assert result.cost_estimated is None
    assert result.cost_actual is None
    assert result.currency is None
    assert result.retryable is False


def _assert_preexecution(
    exc: AgentErroOperacionalLLMFallbackPreExecutionError,
    *,
    code: str,
    message: str = GENERIC_PREEXECUTION_MESSAGE,
) -> None:
    assert exc.code == code
    assert exc.public_message == message
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _tree(relative_path: str) -> ast.AST:
    return ast.parse(_source(relative_path))


def _imported_modules(relative_path: str) -> set[str]:
    modules: set[str] = set()

    for node in ast.walk(_tree(relative_path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    return modules


def _called_names(relative_path: str) -> set[str]:
    names: set[str] = set()

    for node in ast.walk(_tree(relative_path)):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)

    return names


# ---------------------------------------------------------------------------
# Identidade do contrato e autoridade permanente
# ---------------------------------------------------------------------------


def test_context_is_direct_alias_to_b14_3f_snapshot_union() -> None:
    assert OperationalLLMFallbackContext is OperationalEventSnapshot


def test_real_call_gate_is_permanently_false() -> None:
    assert PERMITE_CHAMADA_REAL_V1 is False
    assert type(PERMITE_CHAMADA_REAL_V1) is bool


@pytest.mark.parametrize(
    "model",
    [
        OperationalLLMFallbackOutput,
        OperationalLLMFallbackPayload,
        OperationalGlobalEventSnapshot,
        OperationalTenantEventSnapshot,
        AgentMission,
    ],
)
def test_no_model_exposes_permite_chamada_real_field(model: type) -> None:
    assert "permite_chamada_real" not in model.model_fields


def test_preexecution_code_union_is_exact_and_has_21_items() -> None:
    codes = set(get_args(AgentErroOperacionalLLMFallbackPreExecutionErrorCode))

    assert codes == EXPECTED_PREEXECUTION_CODES
    assert len(codes) == 21


def test_budget_unsupported_is_structural_only() -> None:
    codes = set(get_args(AgentErroOperacionalLLMFallbackPreExecutionErrorCode))

    assert "MISSION_BUDGET_UNSUPPORTED" in codes
    assert isinstance(_mission().budget_policy, BudgetPolicy)
    assert isinstance(
        _mission(budget_policy=_budget_allow_llm()).budget_policy,
        BudgetPolicy,
    )


# ---------------------------------------------------------------------------
# Contratos do output reservado e payload futuro
# ---------------------------------------------------------------------------


def test_output_accepts_each_content_field_individually() -> None:
    for field in (
        "hipotese_operacional",
        "informacao_adicional_necessaria",
        "recomendacao_de_investigacao",
    ):
        model = OperationalLLMFallbackOutput(**{field: "Conteúdo válido."})
        assert getattr(model, field) == "Conteúdo válido."


def test_payload_sets_authority_flags_deterministically() -> None:
    event_id = uuid4()
    payload = OperationalLLMFallbackPayload(
        event_id=event_id,
        hipotese_operacional="Hipótese controlada.",
    )

    assert payload.event_id == event_id
    assert payload.publication_allowed is False
    assert payload.automation_allowed is False
    assert payload.requires_human_review is True


@pytest.mark.parametrize(
    "model",
    [OperationalLLMFallbackOutput, OperationalLLMFallbackPayload],
)
def test_content_models_reject_all_fields_absent(model: type) -> None:
    kwargs = {"event_id": uuid4()} if model is OperationalLLMFallbackPayload else {}

    with pytest.raises(ValidationError):
        model(**kwargs)


@pytest.mark.parametrize("value", ["", " ", "\n", "  \n  "])
def test_content_rejects_empty_or_blank_text(value: str) -> None:
    with pytest.raises(ValidationError):
        OperationalLLMFallbackOutput(hipotese_operacional=value)


@pytest.mark.parametrize("value", ["a\rb", "a\tb", "a\x00b", "a\x1fb"])
def test_content_rejects_unicode_control_characters(value: str) -> None:
    with pytest.raises(ValidationError):
        OperationalLLMFallbackOutput(hipotese_operacional=value)


def test_content_allows_newline() -> None:
    output = OperationalLLMFallbackOutput(
        hipotese_operacional="Linha 1\nLinha 2"
    )
    assert output.hipotese_operacional == "Linha 1\nLinha 2"


def test_content_accepts_exact_500_character_field() -> None:
    output = OperationalLLMFallbackOutput(hipotese_operacional="a" * 500)
    assert len(output.hipotese_operacional or "") == 500


def test_content_rejects_501_character_field() -> None:
    with pytest.raises(ValidationError):
        OperationalLLMFallbackOutput(hipotese_operacional="a" * 501)


def test_content_accepts_exact_1200_character_aggregate() -> None:
    output = OperationalLLMFallbackOutput(
        hipotese_operacional="a" * 500,
        informacao_adicional_necessaria="b" * 500,
        recomendacao_de_investigacao="c" * 200,
    )
    assert sum(
        len(value)
        for value in (
            output.hipotese_operacional,
            output.informacao_adicional_necessaria,
            output.recomendacao_de_investigacao,
        )
        if value is not None
    ) == 1200


def test_content_rejects_1201_character_aggregate() -> None:
    with pytest.raises(ValidationError):
        OperationalLLMFallbackOutput(
            hipotese_operacional="a" * 500,
            informacao_adicional_necessaria="b" * 500,
            recomendacao_de_investigacao="c" * 201,
        )


def test_content_rejects_non_string_values() -> None:
    with pytest.raises(ValidationError):
        OperationalLLMFallbackOutput(hipotese_operacional=123)


def test_output_and_payload_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        OperationalLLMFallbackOutput(
            hipotese_operacional="Válida.",
            extra="proibido",
        )

    with pytest.raises(ValidationError):
        OperationalLLMFallbackPayload(
            event_id=uuid4(),
            hipotese_operacional="Válida.",
            provider="proibido",
        )


def test_output_and_payload_are_frozen() -> None:
    output = OperationalLLMFallbackOutput(
        hipotese_operacional="Válida."
    )
    payload = OperationalLLMFallbackPayload(
        event_id=uuid4(),
        hipotese_operacional="Válida.",
    )

    with pytest.raises(ValidationError):
        setattr(output, "hipotese_operacional", "Alterada")

    with pytest.raises(ValidationError):
        setattr(payload, "publication_allowed", True)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("publication_allowed", True),
        ("automation_allowed", True),
        ("requires_human_review", False),
    ],
)
def test_payload_rejects_authority_tampering(field: str, value: object) -> None:
    data = {
        "event_id": uuid4(),
        "hipotese_operacional": "Válida.",
        field: value,
    }

    with pytest.raises(ValidationError):
        OperationalLLMFallbackPayload.model_validate(data)


# ---------------------------------------------------------------------------
# Códigos e mensagens operacionais
# ---------------------------------------------------------------------------


def test_operational_codes_and_messages_are_exact() -> None:
    assert AGENT_VERSION_INCOMPATIBLE == "AGENT_VERSION_INCOMPATIBLE"
    assert AGENT_VERSION_INCOMPATIBLE_MESSAGE == (
        "A versão requerida pela missão não é compatível com o agente "
        "de fallback LLM operacional."
    )
    assert EXECUTION_MODE_NOT_AUTHORIZED == "EXECUTION_MODE_NOT_AUTHORIZED"
    assert EXECUTION_MODE_NOT_AUTHORIZED_MESSAGE == (
        "O modo de execução solicitado não está autorizado para o agente "
        "de fallback LLM operacional."
    )
    assert AG_OPERATIONAL_LLM_FALLBACK_NOT_ELIGIBLE == (
        "AG_OPERATIONAL_LLM_FALLBACK_NOT_ELIGIBLE"
    )
    assert AG_OPERATIONAL_LLM_FALLBACK_NOT_ELIGIBLE_MESSAGE == (
        "O evento foi reconhecido por uma sentinela determinística; "
        "o fallback LLM não é aplicável."
    )
    assert AG_OPERATIONAL_LLM_FALLBACK_BUDGET_NOT_AUTHORIZED == (
        "AG_OPERATIONAL_LLM_FALLBACK_BUDGET_NOT_AUTHORIZED"
    )
    assert AG_OPERATIONAL_LLM_FALLBACK_BUDGET_NOT_AUTHORIZED_MESSAGE == (
        "A missão não está autorizada a utilizar LLM."
    )
    assert AG_OPERATIONAL_LLM_FALLBACK_REAL_CALL_NOT_ENABLED == (
        "AG_OPERATIONAL_LLM_FALLBACK_REAL_CALL_NOT_ENABLED"
    )
    assert AG_OPERATIONAL_LLM_FALLBACK_REAL_CALL_NOT_ENABLED_MESSAGE == (
        "A chamada real a um provedor LLM não está activada nesta "
        "versão do agente."
    )
    assert AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR == (
        "AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR"
    )
    assert AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR_MESSAGE == (
        "Não foi possível concluir a verificação de elegibilidade "
        "para o fallback LLM operacional."
    )


def test_legacy_drift_error_is_exact_and_opaque() -> None:
    exc = OperationalLLMFallbackLegacyDriftError()

    assert exc.code == "AG_OPERATIONAL_LLM_FALLBACK_LEGACY_DRIFT"
    assert exc.public_message == (
        "O motor de fallback LLM detectou uma divergência "
        "no legado protegido."
    )
    assert exc.args == (exc.code,)


def test_postconstruction_errors_are_namespaced() -> None:
    validation = AgentErroOperacionalLLMFallbackResultValidationError()
    safety = AgentErroOperacionalLLMFallbackResultSafetyError()

    assert validation.code == (
        "AG_OPERATIONAL_LLM_FALLBACK_RESULT_VALIDATION_FAILED"
    )
    assert safety.code == (
        "AG_OPERATIONAL_LLM_FALLBACK_RESULT_SANITIZATION_FAILED"
    )


# ---------------------------------------------------------------------------
# Fronteira da missão
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("update", "code"),
    [
        ({"target_agent": "outro_agente"}, "MISSION_TARGET_MISMATCH"),
        ({"mission_type": "outra_missao"}, "MISSION_TYPE_UNSUPPORTED"),
        ({"context_schema": "outro.context"}, "CONTEXT_SCHEMA_UNSUPPORTED"),
        ({"context_version": "9.0"}, "CONTEXT_VERSION_UNSUPPORTED"),
        ({"output_schema": "outro.result"}, "OUTPUT_SCHEMA_UNSUPPORTED"),
        ({"output_version": "9.0"}, "OUTPUT_VERSION_UNSUPPORTED"),
        ({"scope": "utilizador"}, "MISSION_SCOPE_UNSUPPORTED"),
        ({"scope": "tenant", "tenant_id": None}, "MISSION_TENANT_REQUIRED"),
        ({"scope": "global", "tenant_id": 1}, "MISSION_TENANT_UNSUPPORTED"),
        ({"scope": "tenant", "tenant_id": True}, "MISSION_TENANT_UNSUPPORTED"),
        ({"actor_id": None}, "MISSION_ACTOR_UNSUPPORTED"),
        ({"actor_id": True}, "MISSION_ACTOR_UNSUPPORTED"),
        ({"actor_id": "1"}, "MISSION_ACTOR_UNSUPPORTED"),
        ({"actor_id": 1.0}, "MISSION_ACTOR_UNSUPPORTED"),
        ({"actor_id": 0}, "MISSION_ACTOR_UNSUPPORTED"),
        ({"actor_id": -1}, "MISSION_ACTOR_UNSUPPORTED"),
        ({"entity_type": "evento"}, "MISSION_ENTITY_UNSUPPORTED"),
        ({"entity_id": 7}, "MISSION_ENTITY_UNSUPPORTED"),
        ({"requested_by": "system"}, "MISSION_REQUESTED_BY_UNSUPPORTED"),
        ({"authority_level": "proposta"}, "MISSION_AUTHORITY_UNSUPPORTED"),
        ({"source_event_id": None}, "MISSION_ORIGIN_UNSUPPORTED"),
        ({"source_event_id": "não-uuid"}, "MISSION_ORIGIN_UNSUPPORTED"),
        ({"source_request_id": "request"}, "MISSION_ORIGIN_UNSUPPORTED"),
        ({"schedule_slot": "slot"}, "MISSION_ORIGIN_UNSUPPORTED"),
        ({"sources": [object()]}, "MISSION_SOURCES_UNSUPPORTED"),
        ({"parent_mission_id": uuid4()}, "MISSION_ENVELOPE_UNSUPPORTED"),
        ({"deadline": _now()}, "MISSION_ENVELOPE_UNSUPPORTED"),
        ({"idempotency_reference_at": _now()}, "MISSION_ENVELOPE_UNSUPPORTED"),
        ({"ratification_id": "rat"}, "MISSION_ENVELOPE_UNSUPPORTED"),
        ({"authorized_by": "admin"}, "MISSION_ENVELOPE_UNSUPPORTED"),
        ({"authorization_role": "admin"}, "MISSION_ENVELOPE_UNSUPPORTED"),
        ({"priority": "normal"}, "MISSION_PRIORITY_UNSUPPORTED"),
        ({"reference_at": None}, "MISSION_REFERENCE_AT_REQUIRED"),
        (
            {"created_at": datetime.now(timezone(timedelta(hours=-3)))},
            "MISSION_TEMPORALITY_UNSUPPORTED",
        ),
        (
            {"reference_at": datetime.now(timezone(timedelta(hours=-3)))},
            "MISSION_TEMPORALITY_UNSUPPORTED",
        ),
    ],
)
async def test_frontier_rejects_unsupported_missions(
    update: dict[str, object],
    code: str,
) -> None:
    mission = _mission().model_copy(update=update)

    with pytest.raises(
        AgentErroOperacionalLLMFallbackPreExecutionError
    ) as exc_info:
        await execute_agent_erro_operacional_llm_fallback_mission(mission)

    _assert_preexecution(exc_info.value, code=code)


@pytest.mark.asyncio
async def test_frontier_error_does_not_leak_rejected_value() -> None:
    secret = "SECRET-TARGET-B14-3G-99531"
    mission = _mission().model_copy(update={"target_agent": secret})

    with pytest.raises(
        AgentErroOperacionalLLMFallbackPreExecutionError
    ) as exc_info:
        await execute_agent_erro_operacional_llm_fallback_mission(mission)

    assert secret not in exc_info.value.public_message
    _assert_preexecution(exc_info.value, code="MISSION_TARGET_MISMATCH")


# ---------------------------------------------------------------------------
# Precedência congelada e bloqueios anteriores ao motor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_version_block_precedes_mode_context_and_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mission = _mission(
        execution_mode="activo",
        agent_version_required="9.9",
    ).model_copy(update={"context": {"segredo": "não analisar"}})
    context_mock = patch.object(
        adapter_module,
        "_validar_contexto",
        side_effect=AssertionError("contexto não deve ser analisado"),
    )
    calls = _install_fake_engine(
        monkeypatch,
        error=AssertionError("motor não deve ser chamado"),
    )

    with context_mock as mocked:
        result = await execute_agent_erro_operacional_llm_fallback_mission(
            mission
        )

    assert mocked.call_count == 0
    assert calls["count"] == 0
    assert result.status == "bloqueado"
    assert len(result.alerts) == 1
    assert result.alerts[0].code == AGENT_VERSION_INCOMPATIBLE
    assert result.alerts[0].message == AGENT_VERSION_INCOMPATIBLE_MESSAGE
    assert result.error_code is None
    assert result.error_message is None
    _assert_common_result(result, mission)


@pytest.mark.asyncio
async def test_active_mode_block_precedes_context_and_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mission = _mission(execution_mode="activo").model_copy(
        update={"context": {"segredo": "não analisar"}}
    )
    context_mock = patch.object(
        adapter_module,
        "_validar_contexto",
        side_effect=AssertionError("contexto não deve ser analisado"),
    )
    calls = _install_fake_engine(
        monkeypatch,
        error=AssertionError("motor não deve ser chamado"),
    )

    with context_mock as mocked:
        result = await execute_agent_erro_operacional_llm_fallback_mission(
            mission
        )

    assert mocked.call_count == 0
    assert calls["count"] == 0
    assert result.status == "bloqueado"
    assert len(result.alerts) == 1
    assert result.alerts[0].code == EXECUTION_MODE_NOT_AUTHORIZED
    assert result.alerts[0].message == EXECUTION_MODE_NOT_AUTHORIZED_MESSAGE
    _assert_common_result(result, mission)


# ---------------------------------------------------------------------------
# Coerência missão–snapshot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "event_id",
        "reference_at",
        "scope",
        "tenant_id",
        "created_before_event",
    ],
)
async def test_context_coherence_failures_are_typed(mutation: str) -> None:
    snapshot = _global_snapshot()
    mission = _mission(snapshot=snapshot)

    if mutation == "event_id":
        context = dict(mission.context)
        context["event_id"] = uuid4()
        mission = mission.model_copy(update={"context": context})
    elif mutation == "reference_at":
        mission = mission.model_copy(
            update={
                "reference_at": snapshot.occurred_at + timedelta(seconds=1)
            }
        )
    elif mutation == "scope":
        context = dict(mission.context)
        context["scope"] = "tenant"
        context["tenant_id"] = 19
        mission = mission.model_copy(update={"context": context})
    elif mutation == "tenant_id":
        tenant_snapshot = _tenant_snapshot(tenant_id=31)
        mission = _mission(snapshot=tenant_snapshot)
        context = dict(mission.context)
        context["tenant_id"] = 32
        mission = mission.model_copy(update={"context": context})
    elif mutation == "created_before_event":
        mission = mission.model_copy(
            update={
                "created_at": snapshot.occurred_at - timedelta(microseconds=1)
            }
        )
    else:
        raise AssertionError("mutação desconhecida")

    with pytest.raises(
        AgentErroOperacionalLLMFallbackPreExecutionError
    ) as exc_info:
        await execute_agent_erro_operacional_llm_fallback_mission(mission)

    _assert_preexecution(
        exc_info.value,
        code="AG_OPERATIONAL_LLM_FALLBACK_CONTEXT_INVALID",
        message=CONTEXT_INVALID_MESSAGE,
    )


@pytest.mark.asyncio
async def test_raw_context_must_be_a_dict() -> None:
    mission = _mission().model_copy(update={"context": object()})

    with pytest.raises(
        AgentErroOperacionalLLMFallbackPreExecutionError
    ) as exc_info:
        await execute_agent_erro_operacional_llm_fallback_mission(mission)

    _assert_preexecution(
        exc_info.value,
        code="AG_OPERATIONAL_LLM_FALLBACK_CONTEXT_INVALID",
        message=CONTEXT_INVALID_MESSAGE,
    )


@pytest.mark.asyncio
async def test_invalid_context_does_not_leak_sensitive_input() -> None:
    secret = "password=SEGREDO-OPERACIONAL-B14-3G-781"
    mission = _mission().model_copy(
        update={"context": {**_mission().context, "mensagem": secret}}
    )

    with pytest.raises(
        AgentErroOperacionalLLMFallbackPreExecutionError
    ) as exc_info:
        await execute_agent_erro_operacional_llm_fallback_mission(mission)

    assert secret not in exc_info.value.public_message
    _assert_preexecution(
        exc_info.value,
        code="AG_OPERATIONAL_LLM_FALLBACK_CONTEXT_INVALID",
        message=CONTEXT_INVALID_MESSAGE,
    )


@pytest.mark.asyncio
async def test_tenant_context_reaches_engine_as_exact_snapshot_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _tenant_snapshot(tenant_id=714)
    mission = _mission(snapshot=snapshot)
    calls = _install_fake_engine(monkeypatch, eligible=False)

    result = await execute_agent_erro_operacional_llm_fallback_mission(mission)

    assert calls["count"] == 1
    assert type(calls["context"]) is OperationalTenantEventSnapshot
    assert calls["context"].tenant_id == 714
    assert result.scope == "tenant"
    assert result.tenant_id == 714


# ---------------------------------------------------------------------------
# Matriz universal de resultados e precedência terminal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recognized_event_is_not_eligible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mission = _mission(budget_policy=_budget_allow_llm())
    calls = _install_fake_engine(monkeypatch, eligible=False)

    result = await execute_agent_erro_operacional_llm_fallback_mission(mission)

    assert calls["count"] == 1
    assert result.status == "bloqueado"
    assert len(result.alerts) == 1
    assert result.alerts[0].code == AG_OPERATIONAL_LLM_FALLBACK_NOT_ELIGIBLE
    assert (
        result.alerts[0].message
        == AG_OPERATIONAL_LLM_FALLBACK_NOT_ELIGIBLE_MESSAGE
    )
    assert result.error_code is None
    assert result.error_message is None
    _assert_common_result(result, mission)


@pytest.mark.asyncio
async def test_allow_llm_false_is_budget_block_not_frontier_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mission = _mission(budget_policy=BudgetPolicy())
    calls = _install_fake_engine(monkeypatch, eligible=True)

    result = await execute_agent_erro_operacional_llm_fallback_mission(mission)

    assert calls["count"] == 1
    assert result.status == "bloqueado"
    assert len(result.alerts) == 1
    assert result.alerts[0].code == (
        AG_OPERATIONAL_LLM_FALLBACK_BUDGET_NOT_AUTHORIZED
    )
    assert result.alerts[0].message == (
        AG_OPERATIONAL_LLM_FALLBACK_BUDGET_NOT_AUTHORIZED_MESSAGE
    )
    _assert_common_result(result, mission)


@pytest.mark.asyncio
async def test_allow_llm_true_reaches_permanent_real_call_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mission = _mission(budget_policy=_budget_allow_llm())
    calls = _install_fake_engine(monkeypatch, eligible=True)

    result = await execute_agent_erro_operacional_llm_fallback_mission(mission)

    assert calls["count"] == 1
    assert result.status == "bloqueado"
    assert len(result.alerts) == 1
    assert result.alerts[0].code == (
        AG_OPERATIONAL_LLM_FALLBACK_REAL_CALL_NOT_ENABLED
    )
    assert result.alerts[0].message == (
        AG_OPERATIONAL_LLM_FALLBACK_REAL_CALL_NOT_ENABLED_MESSAGE
    )
    _assert_common_result(result, mission)


@pytest.mark.asyncio
async def test_legacy_drift_maps_to_exact_public_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mission = _mission()
    calls = _install_fake_engine(
        monkeypatch,
        error=OperationalLLMFallbackLegacyDriftError(),
    )

    result = await execute_agent_erro_operacional_llm_fallback_mission(mission)

    assert calls["count"] == 1
    assert result.status == "erro"
    assert result.alerts == []
    assert result.error_code == "AG_OPERATIONAL_LLM_FALLBACK_LEGACY_DRIFT"
    assert result.error_message == (
        "O motor de fallback LLM detectou uma divergência "
        "no legado protegido."
    )
    _assert_common_result(result, mission)


@pytest.mark.asyncio
async def test_unexpected_engine_error_is_fixed_and_does_not_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = (
        "password=segredo; SELECT * FROM privada; "
        "C:\\dev\\saas-fiscal-demo\\interno_b14_3g.py"
    )
    mission = _mission()
    calls = _install_fake_engine(monkeypatch, error=RuntimeError(secret))

    result = await execute_agent_erro_operacional_llm_fallback_mission(mission)
    rendered = result.model_dump_json()

    assert calls["count"] == 1
    assert result.status == "erro"
    assert result.alerts == []
    assert result.error_code == AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR
    assert result.error_message == (
        AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR_MESSAGE
    )
    assert secret not in rendered
    assert "password=segredo" not in rendered
    assert "SELECT * FROM privada" not in rendered
    assert "interno_b14_3g.py" not in rendered
    assert "RuntimeError" not in rendered
    assert "Traceback" not in rendered
    _assert_common_result(result, mission)


@pytest.mark.asyncio
async def test_no_reachable_v1_result_has_success_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenarios = [
        (_mission(agent_version_required="9.9"), None),
        (_mission(execution_mode="activo"), None),
        (_mission(budget_policy=_budget_allow_llm()), False),
        (_mission(), True),
        (_mission(budget_policy=_budget_allow_llm()), True),
    ]

    for mission, eligible in scenarios:
        if eligible is not None:
            _install_fake_engine(monkeypatch, eligible=eligible)
        result = await execute_agent_erro_operacional_llm_fallback_mission(
            mission
        )
        assert result.status != "sucesso"


@pytest.mark.asyncio
async def test_cross_validation_failure_is_typed() -> None:
    mission = _mission(agent_version_required="9.9")

    with patch.object(
        adapter_module,
        "validate_result_against_mission",
        side_effect=ValueError("interno"),
    ):
        with pytest.raises(
            AgentErroOperacionalLLMFallbackResultValidationError
        ) as exc_info:
            await execute_agent_erro_operacional_llm_fallback_mission(mission)

    assert exc_info.value.code == (
        "AG_OPERATIONAL_LLM_FALLBACK_RESULT_VALIDATION_FAILED"
    )
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


@pytest.mark.asyncio
async def test_result_sanitization_failure_is_typed() -> None:
    mission = _mission(agent_version_required="9.9")

    with patch.object(
        adapter_module,
        "assert_result_sanitized",
        side_effect=ValueError("interno"),
    ):
        with pytest.raises(
            AgentErroOperacionalLLMFallbackResultSafetyError
        ) as exc_info:
            await execute_agent_erro_operacional_llm_fallback_mission(mission)

    assert exc_info.value.code == (
        "AG_OPERATIONAL_LLM_FALLBACK_RESULT_SANITIZATION_FAILED"
    )
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


# ---------------------------------------------------------------------------
# Motor determinístico de elegibilidade
# ---------------------------------------------------------------------------


def test_real_engine_returns_true_for_unknown_event() -> None:
    assert executar_agent_erro_operacional_llm_fallback_engine(
        _global_snapshot()
    ) is True


def test_real_engine_returns_false_for_known_sentinel() -> None:
    snapshot = _global_snapshot(
        tipo="erro_operacional",
        origem="frontend",
        mensagem="Falha ao aceitar termos da empresa",
        endpoint="/empresas/42",
        status_http=403,
    )

    assert executar_agent_erro_operacional_llm_fallback_engine(snapshot) is False


def test_engine_rejects_untyped_direct_context() -> None:
    with pytest.raises(
        AgentErroOperacionalLLMFallbackPreExecutionError
    ) as exc_info:
        executar_agent_erro_operacional_llm_fallback_engine({})

    _assert_preexecution(
        exc_info.value,
        code="AG_OPERATIONAL_LLM_FALLBACK_CONTEXT_INVALID",
        message=CONTEXT_INVALID_MESSAGE,
    )


def test_reconstructed_legacy_context_uses_exact_key_and_values() -> None:
    snapshot = _global_snapshot(
        mensagem="Falha de esquema detectada.",
        contexto_indicadores=(
            "UNDEFINED_COLUMN",
            "COLUMN_DOES_NOT_EXIST",
        ),
    )

    legacy_context = _reconstruir_contexto_legado(snapshot)

    assert set(legacy_context.keys()) == {"schema_drift_indicators"}
    assert legacy_context["schema_drift_indicators"] == (
        "undefinedcolumn",
        "column tabela.coluna does not exist",
    )


def test_reconstructed_legacy_context_is_empty_without_indicators() -> None:
    assert _reconstruir_contexto_legado(_global_snapshot()) == {}


def test_reconstructed_legacy_event_is_minimal() -> None:
    snapshot = _global_snapshot(
        endpoint="/upload-xml",
        status_http=500,
        contexto_indicadores=("UNDEFINED_COLUMN",),
    )

    event = _reconstruir_evento_legado(snapshot)

    assert event.tipo == snapshot.tipo
    assert event.origem == snapshot.origem
    assert event.mensagem == snapshot.mensagem
    assert event.endpoint == snapshot.endpoint
    assert event.status_http == snapshot.status_http
    assert event.ambiente == "local"
    assert event.commit_sha is None
    assert event.ficheiro_provavel is None
    assert set(event.contexto.keys()) == {"schema_drift_indicators"}


def test_first_matching_sentinel_stops_iteration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    first_name = NOMES_SENTINELAS_CANONICOS[0]
    outcomes: dict[str, object | BaseException | None] = {
        first_name: object(),
    }
    legacy = _canonical_fake_legacy(outcomes=outcomes)

    for sentinel in legacy._SENTINELAS:
        original = sentinel
        name = original.__name__

        def tracked(
            event: object,
            original: object = original,
            name: str = name,
        ) -> object | None:
            calls.append(name)
            return original(event)

        tracked.__name__ = name
        index = legacy._SENTINELAS.index(sentinel)
        legacy._SENTINELAS[index] = tracked

    _install_fake_legacy(monkeypatch, legacy)

    result = executar_agent_erro_operacional_llm_fallback_engine(
        _global_snapshot()
    )

    assert result is False
    assert calls == [first_name]


def test_all_nine_sentinels_run_in_canonical_order_when_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    legacy = _canonical_fake_legacy()

    for index, sentinel in enumerate(list(legacy._SENTINELAS)):
        name = sentinel.__name__

        def tracked(_: object, name: str = name) -> None:
            calls.append(name)
            return None

        tracked.__name__ = name
        legacy._SENTINELAS[index] = tracked

    _install_fake_legacy(monkeypatch, legacy)

    result = executar_agent_erro_operacional_llm_fallback_engine(
        _global_snapshot()
    )

    assert result is True
    assert tuple(calls) == NOMES_SENTINELAS_CANONICOS
    assert len(calls) == 9


def test_unexpected_sentinel_error_is_opaque(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "SECRET-SENTINEL-INTERNAL-B14-3G"
    legacy = _canonical_fake_legacy(
        outcomes={
            NOMES_SENTINELAS_CANONICOS[0]: RuntimeError(secret),
        }
    )
    _install_fake_legacy(monkeypatch, legacy)

    with pytest.raises(
        OperationalLLMFallbackUnexpectedExecutionError
    ) as exc_info:
        executar_agent_erro_operacional_llm_fallback_engine(
            _global_snapshot()
        )

    rendered = str(exc_info.value) + repr(exc_info.value)
    assert exc_info.value.args == ("execution_error",)
    assert secret not in rendered
    assert "RuntimeError" not in rendered


# ---------------------------------------------------------------------------
# Guardas da superfície legada
# ---------------------------------------------------------------------------


def test_canonical_legacy_surface_is_accepted() -> None:
    sentinels = _validar_superficie_legada(_canonical_fake_legacy())

    assert isinstance(sentinels, tuple)
    assert len(sentinels) == 9
    assert tuple(item.__name__ for item in sentinels) == (
        NOMES_SENTINELAS_CANONICOS
    )


@pytest.mark.parametrize(
    "legacy",
    [
        SimpleNamespace(_PADROES_APRENDIDOS=[]),
        SimpleNamespace(_SENTINELAS=1, _PADROES_APRENDIDOS=[]),
        SimpleNamespace(_SENTINELAS=[], _PADROES_APRENDIDOS=[]),
        SimpleNamespace(_SENTINELAS=[None] * 9, _PADROES_APRENDIDOS=[]),
        SimpleNamespace(
            _SENTINELAS=list(reversed(_canonical_fake_legacy()._SENTINELAS)),
            _PADROES_APRENDIDOS=[],
        ),
        SimpleNamespace(_SENTINELAS=_canonical_fake_legacy()._SENTINELAS),
        SimpleNamespace(
            _SENTINELAS=_canonical_fake_legacy()._SENTINELAS,
            _PADROES_APRENDIDOS=[{"tipo": "proibido"}],
        ),
    ],
)
def test_legacy_surface_drift_is_rejected(legacy: SimpleNamespace) -> None:
    with pytest.raises(OperationalLLMFallbackLegacyDriftError):
        _validar_superficie_legada(legacy)


def test_callability_is_checked_before_name_access() -> None:
    class NameTrap:
        def __getattribute__(self, name: str) -> object:
            if name == "__name__":
                raise AssertionError("__name__ não devia ser lido")
            return object.__getattribute__(self, name)

    legacy = _canonical_fake_legacy()
    legacy._SENTINELAS[0] = NameTrap()

    with pytest.raises(OperationalLLMFallbackLegacyDriftError):
        _validar_superficie_legada(legacy)


def test_sentinel_map_name_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    altered = dict(MAPA_SENTINELAS_PARA_CODIGOS)
    altered.pop(NOMES_SENTINELAS_CANONICOS[-1])
    monkeypatch.setattr(engine_module, "MAPA_SENTINELAS_PARA_CODIGOS", altered)

    with pytest.raises(OperationalLLMFallbackLegacyDriftError):
        _validar_superficie_legada(_canonical_fake_legacy())


def test_duplicate_mapped_code_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    altered = dict(MAPA_SENTINELAS_PARA_CODIGOS)
    names = NOMES_SENTINELAS_CANONICOS
    altered[names[1]] = altered[names[0]]
    monkeypatch.setattr(engine_module, "MAPA_SENTINELAS_PARA_CODIGOS", altered)

    with pytest.raises(OperationalLLMFallbackLegacyDriftError):
        _validar_superficie_legada(_canonical_fake_legacy())


def test_profile_key_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    altered = dict(PERFIS_DIAGNOSTICOS_CANONICOS)
    altered.pop(next(iter(altered)))
    monkeypatch.setattr(engine_module, "PERFIS_DIAGNOSTICOS_CANONICOS", altered)

    with pytest.raises(OperationalLLMFallbackLegacyDriftError):
        _validar_superficie_legada(_canonical_fake_legacy())


def test_schema_drift_mapping_is_used_read_only() -> None:
    before = dict(SCHEMA_DRIFT_REPRESENTACAO_LEGADA)

    _reconstruir_contexto_legado(
        _global_snapshot(contexto_indicadores=("UNDEFINED_COLUMN",))
    )

    assert dict(SCHEMA_DRIFT_REPRESENTACAO_LEGADA) == before


# ---------------------------------------------------------------------------
# Integridade estrutural, hashes e proibições
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("relative_path", "expected_hash"),
    [
        (B14_3G_CONTRACT_PATH, B14_3G_CONTRACT_SHA256),
        (B14_3G_ENGINE_PATH, B14_3G_ENGINE_SHA256),
        (B14_3G_ADAPTER_PATH, B14_3G_ADAPTER_SHA256),
        (B14_3F_CONTRACT_PATH, B14_3F_CONTRACT_SHA256),
        (B14_3F_ENGINE_PATH, B14_3F_ENGINE_SHA256),
        (B14_3F_ADAPTER_PATH, B14_3F_ADAPTER_SHA256),
        (B14_3F_TEST_PATH, B14_3F_TEST_SHA256),
        (LEGACY_PATH, LEGACY_SHA256),
    ],
)
def test_protected_hashes_are_exact(
    relative_path: str,
    expected_hash: str,
) -> None:
    digest = canonical_source_sha256(ROOT / relative_path)

    assert digest == expected_hash


@pytest.mark.parametrize(
    "relative_path",
    [
        B14_3G_CONTRACT_PATH,
        B14_3G_ENGINE_PATH,
        B14_3G_ADAPTER_PATH,
    ],
)
def test_new_layers_are_utf8_without_bom_and_lf_only(
    relative_path: str,
) -> None:
    raw = (ROOT / relative_path).read_bytes()

    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    raw.decode("utf-8")


def test_contract_has_no_forbidden_imports() -> None:
    forbidden = {
        "sqlalchemy",
        "app.database",
        "app.models",
        "httpx",
        "requests",
        "aiohttp",
        "openai",
        "anthropic",
        "os",
        "pathlib",
        "subprocess",
        "app.services",
        "app.agents.adapters",
        "app.agents.engines",
        "app.agents.agent_erro_operacional",
        "app.agents.agent_registry",
        "app.agents.agent_executor",
        "app.agents.agent_scheduler",
    }

    for module in _imported_modules(B14_3G_CONTRACT_PATH):
        assert not any(
            module == item or module.startswith(f"{item}.")
            for item in forbidden
        ), f"contrato importa módulo proibido: {module}"


@pytest.mark.parametrize(
    "relative_path",
    [B14_3G_ADAPTER_PATH, B14_3G_ENGINE_PATH],
)
def test_adapter_and_engine_have_no_infrastructure_or_llm_imports(
    relative_path: str,
) -> None:
    forbidden = {
        "sqlalchemy",
        "app.database",
        "app.models",
        "httpx",
        "requests",
        "aiohttp",
        "openai",
        "anthropic",
        "os",
        "pathlib",
        "subprocess",
        "app.services",
        "app.services.llm_router",
        "app.services.llm_budget_guard",
        "app.services.llm_providers",
    }

    for module in _imported_modules(relative_path):
        assert not any(
            module == item or module.startswith(f"{item}.")
            for item in forbidden
        ), f"{relative_path} importa módulo proibido: {module}"


def test_adapter_does_not_import_legacy_or_b14_3f_engine() -> None:
    modules = _imported_modules(B14_3G_ADAPTER_PATH)

    assert LEGACY_MODULE not in modules
    assert "app.agents.engines.agent_erro_operacional" not in modules


def test_engine_imports_legacy_only_inside_main_after_context_validation() -> None:
    tree = _tree(B14_3G_ENGINE_PATH)
    legacy_imports = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Import)
            and any(alias.name == LEGACY_MODULE for alias in node.names)
        )
    ]

    assert len(legacy_imports) == 1
    legacy_import = legacy_imports[0]
    function = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.FunctionDef)
            and node.name
            == "executar_agent_erro_operacional_llm_fallback_engine"
        )
    )
    validation_calls = [
        node
        for node in ast.walk(function)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_validar_contexto_tipado"
        )
    ]

    assert legacy_import in list(ast.walk(function))
    assert len(validation_calls) == 1
    assert validation_calls[0].lineno < legacy_import.lineno


def test_adapter_imports_engine_only_after_context_validation() -> None:
    tree = _tree(B14_3G_ADAPTER_PATH)
    function = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.AsyncFunctionDef)
            and node.name
            == "execute_agent_erro_operacional_llm_fallback_mission"
        )
    )
    engine_imports = [
        node
        for node in ast.walk(function)
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == ENGINE_MODULE
        )
    ]
    context_calls = [
        node
        for node in ast.walk(function)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_validar_contexto"
        )
    ]

    assert len(engine_imports) == 1
    assert len(context_calls) == 1
    assert context_calls[0].lineno < engine_imports[0].lineno


def test_clean_process_adapter_import_loads_no_engine_or_legacy() -> None:
    code = (
        "import sys;"
        "from app.agents.adapters.agent_erro_operacional_llm_fallback "
        "import execute_agent_erro_operacional_llm_fallback_mission;"
        "print("
        "'app.agents.engines.agent_erro_operacional_llm_fallback' "
        "in sys.modules,"
        "'app.agents.agent_erro_operacional' in sys.modules"
        ")"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "False False"


@pytest.mark.parametrize(
    "relative_path",
    [B14_3G_ADAPTER_PATH, B14_3G_ENGINE_PATH],
)
def test_layers_have_no_persistence_calls(relative_path: str) -> None:
    forbidden_calls = {
        "open",
        "write",
        "write_text",
        "write_bytes",
        "add",
        "add_all",
        "delete",
        "flush",
        "commit",
        "bulk_save_objects",
        "bulk_insert_mappings",
        "bulk_update_mappings",
    }

    assert _called_names(relative_path).isdisjoint(forbidden_calls)


def test_engine_references_no_prohibited_execution_paths() -> None:
    prohibited = {
        "run",
        "_tentar_padrao_aprendido",
        "budget_verificar",
        "completar",
        "LLMRouter",
        "LLMBudgetGuard",
    }

    assert _called_names(B14_3G_ENGINE_PATH).isdisjoint(prohibited)


def test_adapter_references_no_real_llm_execution_paths() -> None:
    prohibited = {
        "completar",
        "verificar",
        "LLMRouter",
        "LLMBudgetGuard",
        "DeepSeekProvider",
        "MockProvider",
    }

    assert _called_names(B14_3G_ADAPTER_PATH).isdisjoint(prohibited)


def test_no_exception_is_stringified() -> None:
    for relative_path in (B14_3G_ADAPTER_PATH, B14_3G_ENGINE_PATH):
        tree = _tree(relative_path)

        for handler in (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ExceptHandler) and node.name
        ):
            for node in ast.walk(handler):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Name) and node.func.id in {
                    "str",
                    "repr",
                }:
                    assert not any(
                        isinstance(argument, ast.Name)
                        and argument.id == handler.name
                        for argument in node.args
                    )


def test_adapter_has_no_success_literal_or_future_payload_reference() -> None:
    source = _source(B14_3G_ADAPTER_PATH)

    assert 'status="sucesso"' not in source
    assert "OperationalLLMFallbackPayload" not in source
    assert "provider=\"mock\"" not in source


def test_engine_and_adapter_do_not_read_environment() -> None:
    for relative_path in (B14_3G_ADAPTER_PATH, B14_3G_ENGINE_PATH):
        tree = _tree(relative_path)

        assert "os" not in _imported_modules(relative_path)
        assert not any(
            isinstance(node, ast.Attribute)
            and node.attr in {"environ", "getenv"}
            for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, ast.Name)
            and node.id in {"environ", "getenv"}
            for node in ast.walk(tree)
        )


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/agents/agent_executor.py",
        "app/agents/agent_scheduler.py",
    ],
)
def test_runtime_does_not_reference_b14_3g_adapter(
    relative_path: str,
) -> None:
    source = _source(relative_path)

    assert (
        "execute_agent_erro_operacional_llm_fallback_mission"
        not in source
    )
    assert (
        B14_3G_ADAPTER_PATH.replace("/", ".").removesuffix(".py")
        not in source
    )


def test_no_reader_was_created() -> None:
    assert not (
        ROOT
        / "app"
        / "agents"
        / "readers"
        / "agent_erro_operacional_llm_fallback.py"
    ).exists()


def test_no_init_py_was_connected_to_b14_3g() -> None:
    marker = "agent_erro_operacional_llm_fallback"

    for init_path in (
        "app/agents/contracts/__init__.py",
        "app/agents/engines/__init__.py",
        "app/agents/adapters/__init__.py",
    ):
        assert marker not in _source(init_path)


def test_adapter_is_async_and_engine_is_sync() -> None:
    assert inspect.iscoroutinefunction(
        execute_agent_erro_operacional_llm_fallback_mission
    )
    assert not inspect.iscoroutinefunction(
        executar_agent_erro_operacional_llm_fallback_engine
    )


def test_only_four_b14_3g_implementation_files_are_declared() -> None:
    expected = {
        B14_3G_CONTRACT_PATH,
        B14_3G_ENGINE_PATH,
        B14_3G_ADAPTER_PATH,
        "tests/test_agent_erro_operacional_llm_fallback_mission_adapter.py",
    }
    discovered = {
        path.relative_to(ROOT).as_posix()
        for base in (
            ROOT / "app" / "agents" / "contracts",
            ROOT / "app" / "agents" / "engines",
            ROOT / "app" / "agents" / "adapters",
            ROOT / "tests",
        )
        for path in base.glob("*agent_erro_operacional_llm_fallback*.py")
    }

    assert discovered == expected
