"""
Testes B14.3F — migração L3 do AgentErroOperacional.

Cobrem contrato, fronteira da missão, bloqueios, coerência temporal,
resultado universal, motor determinístico, drift do legado, sanitização
e integridade estrutural. Nenhum teste escreve em BD, filesystem do
repositório, registry, scheduler, executor, router ou endpoint.
"""

from __future__ import annotations

import ast
import inspect
import json
import operator
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from tests.canonical_source_hash import canonical_source_sha256

import app.agents.adapters.agent_erro_operacional as adapter_module
import app.agents.engines.agent_erro_operacional as engine_module
from app.agents.adapters.agent_erro_operacional import (
    execute_agent_erro_operacional_mission,
)
from app.agents.contracts.agent_erro_operacional import (
    INFO_LEGADO_EXACTA,
    MAPA_CODIGOS_PARA_INFO_EM_FALTA,
    MAPA_SENTINELAS_PARA_CODIGOS,
    MENSAGENS_VITE_API_URL_PERMITIDAS,
    NOMES_SENTINELAS_CANONICOS,
    ORDEM_INFO_EM_FALTA,
    ORDEM_SCHEMA_DRIFT_INDICADORES,
    PERFIS_DIAGNOSTICOS_CANONICOS,
    SCHEMA_DRIFT_REPRESENTACAO_LEGADA,
    AgentErroDiagnosisPreExecutionError,
    AgentErroDiagnosisResultSafetyError,
    AgentErroDiagnosisResultValidationError,
    OperationalDiagnosisInternal,
    OperationalDiagnosisPayload,
    OperationalGlobalEventSnapshot,
    OperationalLegacyDriftError,
    OperationalTenantEventSnapshot,
)
from app.agents.contracts.mission import (
    AgentMission,
    build_context_hash,
    build_mission_idempotency_key,
)
from app.agents.contracts.shared import BudgetPolicy
from app.agents.engines.agent_erro_operacional import (
    _reconstruir_evento_legado,
    _validar_superficie_legada,
    construir_payload_diagnostico_operacional,
    executar_agent_erro_operacional_engine,
    projectar_resultado_operacional,
    validate_operational_diagnosis_payload_against_context,
)


ROOT = Path(__file__).resolve().parents[1]

CONTRACT_PATH = "app/agents/contracts/agent_erro_operacional.py"
ENGINE_PATH = "app/agents/engines/agent_erro_operacional.py"
ADAPTER_PATH = "app/agents/adapters/agent_erro_operacional.py"
LEGACY_PATH = "app/agents/agent_erro_operacional.py"

CONTRACT_SHA256 = (
    "7A418199963284D1A8EDC475DD80DACA8ECFF1A3A8101297DEF9A094392F8503"
)
ENGINE_SHA256 = (
    "60F4103407CB946134564E45D3F63F97BC86D6A161656470E17452BFA4542891"
)
ADAPTER_SHA256 = (
    "065AE4853339336B01390A03E2B728F6B9683C40E6BBADFB93FBEBC394A4D9FF"
)
LEGACY_SHA256 = (
    "B104441EBC8CADB5E17352B5413F2DAD3D334937C421180E74484C1CDA60A790"
)

ENGINE_MODULE = "app.agents.engines.agent_erro_operacional"
LEGACY_MODULE = "app.agents.agent_erro_operacional"

GENERIC_PREEXECUTION_MESSAGE = (
    "A missão de diagnóstico operacional recebida não é "
    "compatível com este agente."
)
CONTEXT_INVALID_MESSAGE = (
    "Não foi possível validar o contexto do evento operacional recebido."
)
EXECUTION_ERROR_CODE = "AG_OPERATIONAL_DIAGNOSIS_EXECUTION_ERROR"
EXECUTION_ERROR_MESSAGE = (
    "Não foi possível concluir o diagnóstico do evento operacional."
)
LEGACY_DRIFT_CODE = "AG_OPERATIONAL_DIAGNOSIS_LEGACY_DRIFT"
LEGACY_DRIFT_MESSAGE = (
    "O motor de diagnóstico detectou uma divergência no legado protegido."
)

LEGACY_INFO_BY_CODE = {
    "DATABASE_COLUMNS_STATE_REQUIRED":
        "colunas reais de tabela em producao",
    "ALEMBIC_VERSION_REQUIRED":
        "valor actual de alembic_version em producao",
    "RAILWAY_STACK_TRACE_REQUIRED":
        "stack trace Railway",
    "EXECUTAR_ANALISE_XML_SOURCE_REQUIRED":
        "corpo de executar_analise_xml",
    "LER_XML_UNICO_SOURCE_REQUIRED":
        "corpo de ler_xml_unico",
    "SMOKE_XML_REQUIRED":
        "XML completo usado no smoke",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _global_snapshot(
    *,
    event_id: UUID | None = None,
    occurred_at: datetime | None = None,
    tipo: str = "evento_operacional_desconhecido",
    origem: str = "pytest_b14_3f",
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
    tenant_id: int = 71,
    event_id: UUID | None = None,
    occurred_at: datetime | None = None,
    tipo: str = "evento_operacional_desconhecido",
    origem: str = "pytest_b14_3f",
    mensagem: str = "Evento operacional tenant sem correspondência conhecida.",
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


def _mission(
    *,
    snapshot: (
        OperationalGlobalEventSnapshot
        | OperationalTenantEventSnapshot
        | None
    ) = None,
    execution_mode: str = "sombra",
    agent_version_required: str | None = "1.0",
) -> AgentMission:
    snapshot = snapshot or _global_snapshot()
    context = snapshot.model_dump(mode="python")

    return AgentMission(
        mission_id=uuid4(),
        correlation_id=uuid4(),
        mission_type="diagnosticar_evento_operacional",
        target_agent="agent_erro_operacional",
        context_schema="agent_erro_operacional.context",
        context_version="1.0",
        output_schema="agent_erro_operacional.result",
        output_version="1.0",
        scope=snapshot.scope,
        tenant_id=snapshot.tenant_id,
        actor_id=None,
        entity_type=None,
        entity_id=None,
        source_event_id=snapshot.event_id,
        schedule_slot=None,
        source_request_id=None,
        parent_mission_id=None,
        requested_by="system",
        context=context,
        context_hash=build_context_hash(context),
        authority_level="leitura",
        execution_mode=execution_mode,
        ratification_id=None,
        authorized_by=None,
        authorization_role=None,
        idempotency_key=build_mission_idempotency_key(
            mission_type="diagnosticar_evento_operacional",
            target_agent="agent_erro_operacional",
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
        budget_policy=BudgetPolicy(),
        sources=[],
    )


def _nonrecognized_payload(
    event_id: UUID,
) -> OperationalDiagnosisPayload:
    return OperationalDiagnosisPayload(
        event_id=event_id,
        reconhecido=False,
        camada_reconhecimento="nao_reconhecido",
        diagnostico_codigo=None,
        classificacao=None,
        risco_patch=None,
        tem_causa_provavel=False,
        tem_evidencias=False,
        tem_teste_recomendado=False,
        tem_patch_sugerido=False,
        informacao_em_falta=(),
        publication_allowed=False,
        automation_allowed=False,
        requires_human_review=True,
    )


def _recognized_payload(
    event_id: UUID,
    code: str = "RACE_CONDITION_TERMOS",
) -> OperationalDiagnosisPayload:
    profile = PERFIS_DIAGNOSTICOS_CANONICOS[code]

    return OperationalDiagnosisPayload(
        event_id=event_id,
        reconhecido=True,
        camada_reconhecimento="sentinela",
        diagnostico_codigo=code,
        classificacao=profile.classificacao,
        risco_patch=profile.risco_patch,
        tem_causa_provavel=profile.tem_causa_provavel,
        tem_evidencias=profile.tem_evidencias,
        tem_teste_recomendado=profile.tem_teste_recomendado,
        tem_patch_sugerido=profile.tem_patch_sugerido,
        informacao_em_falta=profile.informacao_em_falta,
        publication_allowed=False,
        automation_allowed=False,
        requires_human_review=True,
    )


def _install_fake_engine(
    monkeypatch: pytest.MonkeyPatch,
    *,
    payload: OperationalDiagnosisPayload | None = None,
    error: BaseException | None = None,
) -> dict[str, object]:
    calls: dict[str, object] = {
        "count": 0,
        "context": None,
    }
    fake_module = types.ModuleType(ENGINE_MODULE)

    def controlled_engine(context: object) -> object:
        calls["count"] = int(calls["count"]) + 1
        calls["context"] = context

        if error is not None:
            raise error

        assert payload is not None
        return payload

    fake_module.executar_agent_erro_operacional_engine = controlled_engine
    monkeypatch.setitem(sys.modules, ENGINE_MODULE, fake_module)
    return calls


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
    assert result.payload_schema == "agent_erro_operacional.result"
    assert result.payload_version == "1.0"
    assert result.llm_used is False
    assert result.provider is None
    assert result.tokens_used is None
    assert result.cost_estimated is None
    assert result.cost_actual is None
    assert result.currency is None
    assert result.retryable is False


def _assert_preexecution(
    exc: AgentErroDiagnosisPreExecutionError,
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


def _legacy_result_for(code: str) -> SimpleNamespace:
    profile = PERFIS_DIAGNOSTICOS_CANONICOS[code]

    return SimpleNamespace(
        classificacao=profile.classificacao,
        risco_patch=profile.risco_patch,
        causa_provavel="Causa canónica presente.",
        evidencias=["Evidência canónica presente."],
        teste_recomendado="Teste canónico presente.",
        patch_sugerido_texto="Patch canónico presente.",
        informacao_em_falta=[
            LEGACY_INFO_BY_CODE[item]
            for item in profile.informacao_em_falta
        ],
    )


def _canonical_fake_legacy() -> SimpleNamespace:
    sentinels = []

    for name in NOMES_SENTINELAS_CANONICOS:
        def sentinel(_: object = None) -> None:
            return None

        sentinel.__name__ = name
        sentinels.append(sentinel)

    return SimpleNamespace(
        _SENTINELAS=sentinels,
        _PADROES_APRENDIDOS=[],
    )


# ---------------------------------------------------------------------------
# Contrato dos snapshots
# ---------------------------------------------------------------------------


def test_global_snapshot_nominal_is_frozen_and_closed() -> None:
    snapshot = _global_snapshot()

    assert snapshot.scope == "global"
    assert snapshot.tenant_id is None
    assert snapshot.contexto_indicadores == ()

    with pytest.raises(ValidationError):
        setattr(snapshot, "mensagem", "alterada")

    data = snapshot.model_dump(mode="python")
    data["campo_extra"] = "proibido"

    with pytest.raises(ValidationError):
        OperationalGlobalEventSnapshot.model_validate(data)


def test_tenant_snapshot_requires_strict_positive_tenant() -> None:
    snapshot = _tenant_snapshot(tenant_id=91)

    assert snapshot.scope == "tenant"
    assert snapshot.tenant_id == 91

    for bad_value in (True, False, "91", 91.0, 0, -1):
        data = snapshot.model_dump(mode="python")
        data["tenant_id"] = bad_value

        with pytest.raises(ValidationError):
            OperationalTenantEventSnapshot.model_validate(data)


@pytest.mark.parametrize(
    "message",
    MENSAGENS_VITE_API_URL_PERMITIDAS,
)
def test_exact_vite_messages_are_allowed(message: str) -> None:
    snapshot = _global_snapshot(mensagem=message)
    assert snapshot.mensagem == message


@pytest.mark.parametrize(
    "message",
    [
        "vite_api_url não definida no Vercel",
        "VITE_API_URL não definida no Vercel.",
        "prefixo VITE_API_URL não definida no Vercel",
        "VITE_API_URL=https://api.example",
        "VITE_API_URL: segredo",
        "API_KEY=segredo",
        "password=segredo",
        "Authorization Bearer segredo",
        "cookie de sessão",
        "SELECT * FROM tabela",
        "insert into tabela values (1)",
        "update tabela set campo=1",
        "delete from tabela",
        "drop table tabela",
        "create table tabela(id int)",
        "alter table tabela add column x int",
        "truncate table tabela",
        "merge into tabela t",
        "grant select on tabela to user",
        "revoke select on tabela from user",
        "execute procedimento",
        "call procedimento()",
        "copy tabela from arquivo",
        "information_schema.columns",
        '{"token": "segredo"}',
        '["corpo", "http"]',
        "<?xml version='1.0'?><NFe/>",
        "Traceback (most recent call last):",
    ],
)
def test_sensitive_messages_are_rejected(message: str) -> None:
    with pytest.raises(ValidationError):
        _global_snapshot(mensagem=message)


@pytest.mark.parametrize(
    "message",
    [
        "Actualização disponível para o sistema.",
        "Copy concluído pelo operador.",
        "Call recebido pela equipa.",
        "Dados from origem externa foram removidos.",
        "Join operacional concluído.",
        "Where aplicável foi documentado.",
    ],
)
def test_isolated_sql_words_do_not_create_false_positive(
    message: str,
) -> None:
    snapshot = _global_snapshot(mensagem=message)
    assert snapshot.mensagem == message


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.test/upload",
        "/../../segredo",
        "/upload?token=segredo",
        "/upload#fragmento",
        "upload-sem-barra",
        "",
    ],
)
def test_endpoint_rejects_non_template_values(endpoint: str) -> None:
    with pytest.raises(ValidationError):
        _global_snapshot(endpoint=endpoint)


@pytest.mark.parametrize(
    "status",
    [True, False, "500", 500.0, 99, 600],
)
def test_status_http_is_strict_and_bounded(status: object) -> None:
    with pytest.raises(ValidationError):
        _global_snapshot(status_http=status)


def test_context_indicators_accept_only_canonical_order() -> None:
    snapshot = _global_snapshot(
        contexto_indicadores=ORDEM_SCHEMA_DRIFT_INDICADORES
    )

    assert (
        snapshot.contexto_indicadores
        == ORDEM_SCHEMA_DRIFT_INDICADORES
    )


@pytest.mark.parametrize(
    "indicators",
    [
        (
            "COLUMN_DOES_NOT_EXIST",
            "UNDEFINED_COLUMN",
        ),
        (
            "UNDEFINED_COLUMN",
            "UNDEFINED_COLUMN",
        ),
        (
            "UNDEFINED_COLUMN",
            "COLUMN_DOES_NOT_EXIST",
            "RELATORIOS_ANALISE_FINGERPRINT_MISSING",
            "UNDEFINED_COLUMN",
        ),
        ("OUTRO_INDICADOR",),
    ],
)
def test_context_indicators_reject_invalid_sequences(
    indicators: tuple[str, ...],
) -> None:
    with pytest.raises(ValidationError):
        _global_snapshot(contexto_indicadores=indicators)


def test_snapshot_rejects_non_utc_datetime() -> None:
    non_utc = datetime.now(
        timezone(timedelta(hours=-3))
    )

    with pytest.raises(ValidationError):
        _global_snapshot(occurred_at=non_utc)


# ---------------------------------------------------------------------------
# Contrato do payload
# ---------------------------------------------------------------------------


def test_nonrecognized_payload_is_exact() -> None:
    event_id = uuid4()
    payload = _nonrecognized_payload(event_id)

    assert payload.event_id == event_id
    assert payload.reconhecido is False
    assert payload.camada_reconhecimento == "nao_reconhecido"
    assert payload.diagnostico_codigo is None
    assert payload.classificacao is None
    assert payload.risco_patch is None
    assert payload.tem_causa_provavel is False
    assert payload.tem_evidencias is False
    assert payload.tem_teste_recomendado is False
    assert payload.tem_patch_sugerido is False
    assert payload.informacao_em_falta == ()
    assert payload.publication_allowed is False
    assert payload.automation_allowed is False
    assert payload.requires_human_review is True


@pytest.mark.parametrize(
    "code",
    tuple(PERFIS_DIAGNOSTICOS_CANONICOS.keys()),
)
def test_recognized_payload_matches_every_canonical_profile(
    code: str,
) -> None:
    payload = _recognized_payload(uuid4(), code)
    profile = PERFIS_DIAGNOSTICOS_CANONICOS[code]

    assert payload.reconhecido is True
    assert payload.camada_reconhecimento == "sentinela"
    assert payload.classificacao == profile.classificacao
    assert payload.risco_patch == profile.risco_patch
    assert payload.informacao_em_falta == profile.informacao_em_falta


def test_payload_forbids_extra_and_is_frozen() -> None:
    payload = _nonrecognized_payload(uuid4())
    data = payload.model_dump(mode="python")
    data["mensagem_original"] = "não pode sair"

    with pytest.raises(ValidationError):
        OperationalDiagnosisPayload.model_validate(data)

    with pytest.raises(ValidationError):
        setattr(payload, "publication_allowed", True)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reconhecido", 1),
        ("tem_causa_provavel", 0),
        ("tem_evidencias", "false"),
        ("tem_teste_recomendado", None),
        ("tem_patch_sugerido", []),
        ("publication_allowed", True),
        ("automation_allowed", True),
        ("requires_human_review", False),
    ],
)
def test_payload_rejects_noncanonical_flags(
    field: str,
    value: object,
) -> None:
    data = _nonrecognized_payload(
        uuid4()
    ).model_dump(mode="python")
    data[field] = value

    with pytest.raises(ValidationError):
        OperationalDiagnosisPayload.model_validate(data)


def test_payload_rejects_recognition_layer_mismatch() -> None:
    data = _recognized_payload(
        uuid4()
    ).model_dump(mode="python")
    data["camada_reconhecimento"] = "nao_reconhecido"

    with pytest.raises(ValidationError):
        OperationalDiagnosisPayload.model_validate(data)


def test_payload_rejects_profile_tampering() -> None:
    data = _recognized_payload(
        uuid4(),
        "RACE_CONDITION_TERMOS",
    ).model_dump(mode="python")
    data["risco_patch"] = "alto"

    with pytest.raises(ValidationError):
        OperationalDiagnosisPayload.model_validate(data)


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
        ({"actor_id": "actor"}, "MISSION_ACTOR_UNSUPPORTED"),
        ({"entity_type": "evento"}, "MISSION_ENTITY_UNSUPPORTED"),
        ({"entity_id": 7}, "MISSION_ENTITY_UNSUPPORTED"),
        ({"requested_by": "admin"}, "MISSION_REQUESTED_BY_UNSUPPORTED"),
        ({"authority_level": "proposta"}, "MISSION_AUTHORITY_UNSUPPORTED"),
        ({"source_event_id": None}, "MISSION_ORIGIN_UNSUPPORTED"),
        ({"source_event_id": "não-uuid"}, "MISSION_ORIGIN_UNSUPPORTED"),
        ({"source_request_id": "request"}, "MISSION_ORIGIN_UNSUPPORTED"),
        ({"schedule_slot": "slot"}, "MISSION_ORIGIN_UNSUPPORTED"),
        (
            {
                "budget_policy": BudgetPolicy(
                    allow_llm=True,
                    allowed_providers=["local_model"],
                    max_calls=1,
                    max_input_chars=1,
                    max_output_tokens=1,
                )
            },
            "MISSION_BUDGET_UNSUPPORTED",
        ),
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
            {
                "created_at": datetime.now(
                    timezone(timedelta(hours=-3))
                )
            },
            "MISSION_TEMPORALITY_UNSUPPORTED",
        ),
        (
            {
                "reference_at": datetime.now(
                    timezone(timedelta(hours=-3))
                )
            },
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
        AgentErroDiagnosisPreExecutionError
    ) as exc_info:
        await execute_agent_erro_operacional_mission(mission)

    _assert_preexecution(exc_info.value, code=code)


@pytest.mark.asyncio
async def test_frontier_error_does_not_leak_rejected_value() -> None:
    secret = "SECRET-TARGET-99531"
    mission = _mission().model_copy(
        update={"target_agent": secret}
    )

    with pytest.raises(
        AgentErroDiagnosisPreExecutionError
    ) as exc_info:
        await execute_agent_erro_operacional_mission(mission)

    assert secret not in exc_info.value.public_message
    _assert_preexecution(
        exc_info.value,
        code="MISSION_TARGET_MISMATCH",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    ["sombra", "dry_run"],
)
async def test_supported_modes_execute_successfully_with_fake_engine(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    snapshot = _global_snapshot()
    mission = _mission(
        snapshot=snapshot,
        execution_mode=mode,
    )
    payload = _nonrecognized_payload(snapshot.event_id)
    calls = _install_fake_engine(
        monkeypatch,
        payload=payload,
    )

    result = await execute_agent_erro_operacional_mission(mission)

    assert calls["count"] == 1
    assert isinstance(
        calls["context"],
        OperationalGlobalEventSnapshot,
    )
    assert result.status == "sucesso"
    assert result.alerts == []
    assert result.error_code is None
    assert result.error_message is None
    assert result.payload["event_id"] == snapshot.event_id
    assert result.payload["reconhecido"] is False
    _assert_common_result(result, mission)


@pytest.mark.asyncio
async def test_tenant_success_preserves_tenant_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _tenant_snapshot(tenant_id=714)
    mission = _mission(snapshot=snapshot)
    calls = _install_fake_engine(
        monkeypatch,
        payload=_recognized_payload(
            snapshot.event_id,
            "FATURAMENTO_ZERO",
        ),
    )

    result = await execute_agent_erro_operacional_mission(mission)

    assert calls["count"] == 1
    assert isinstance(
        calls["context"],
        OperationalTenantEventSnapshot,
    )
    assert result.status == "sucesso"
    assert result.scope == "tenant"
    assert result.tenant_id == 714
    assert result.payload["reconhecido"] is True
    _assert_common_result(result, mission)


@pytest.mark.asyncio
async def test_version_block_precedes_mode_and_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mission = _mission(
        execution_mode="activo",
        agent_version_required="9.9",
    )
    mission = mission.model_copy(
        update={"context": {"segredo": "não analisar"}}
    )
    context_mock = patch.object(
        adapter_module,
        "_validar_contexto",
        side_effect=AssertionError("contexto não deve ser analisado"),
    )
    engine_calls = _install_fake_engine(
        monkeypatch,
        error=AssertionError("motor não deve ser chamado"),
    )

    with context_mock as mocked:
        result = await execute_agent_erro_operacional_mission(mission)

    assert mocked.call_count == 0
    assert engine_calls["count"] == 0
    assert result.status == "bloqueado"
    assert result.payload == {}
    assert result.error_code is None
    assert result.error_message is None
    assert len(result.alerts) == 1
    assert result.alerts[0].code == "AGENT_VERSION_INCOMPATIBLE"
    assert result.alerts[0].severity == "alto"
    assert (
        result.alerts[0].message
        == "Versão do agente incompatível com a missão."
    )
    _assert_common_result(result, mission)


@pytest.mark.asyncio
async def test_active_mode_block_precedes_context_and_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mission = _mission(execution_mode="activo")
    mission = mission.model_copy(
        update={"context": {"segredo": "não analisar"}}
    )
    context_mock = patch.object(
        adapter_module,
        "_validar_contexto",
        side_effect=AssertionError("contexto não deve ser analisado"),
    )
    engine_calls = _install_fake_engine(
        monkeypatch,
        error=AssertionError("motor não deve ser chamado"),
    )

    with context_mock as mocked:
        result = await execute_agent_erro_operacional_mission(mission)

    assert mocked.call_count == 0
    assert engine_calls["count"] == 0
    assert result.status == "bloqueado"
    assert result.payload == {}
    assert len(result.alerts) == 1
    assert result.alerts[0].code == "EXECUTION_MODE_NOT_AUTHORIZED"
    assert result.alerts[0].severity == "alto"
    assert (
        result.alerts[0].message
        == "Modo activo não autorizado neste canário."
    )
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
async def test_context_coherence_failures_are_typed(
    mutation: str,
) -> None:
    snapshot = _global_snapshot()
    mission = _mission(snapshot=snapshot)

    if mutation == "event_id":
        context = dict(mission.context)
        context["event_id"] = uuid4()
        mission = mission.model_copy(update={"context": context})
    elif mutation == "reference_at":
        mission = mission.model_copy(
            update={
                "reference_at":
                    snapshot.occurred_at + timedelta(seconds=1)
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
                "created_at":
                    snapshot.occurred_at - timedelta(microseconds=1)
            }
        )
    else:
        raise AssertionError("mutação desconhecida")

    with pytest.raises(
        AgentErroDiagnosisPreExecutionError
    ) as exc_info:
        await execute_agent_erro_operacional_mission(mission)

    _assert_preexecution(
        exc_info.value,
        code="AG_OPERATIONAL_DIAGNOSIS_CONTEXT_INVALID",
        message=CONTEXT_INVALID_MESSAGE,
    )


@pytest.mark.asyncio
async def test_raw_context_must_be_a_dict() -> None:
    mission = _mission().model_copy(
        update={"context": object()}
    )

    with pytest.raises(
        AgentErroDiagnosisPreExecutionError
    ) as exc_info:
        await execute_agent_erro_operacional_mission(mission)

    _assert_preexecution(
        exc_info.value,
        code="AG_OPERATIONAL_DIAGNOSIS_CONTEXT_INVALID",
        message=CONTEXT_INVALID_MESSAGE,
    )


@pytest.mark.asyncio
async def test_invalid_context_does_not_leak_sensitive_input() -> None:
    secret = "password=SEGREDO-OPERACIONAL-781"
    mission = _mission().model_copy(
        update={
            "context": {
                **_mission().context,
                "mensagem": secret,
            }
        }
    )

    with pytest.raises(
        AgentErroDiagnosisPreExecutionError
    ) as exc_info:
        await execute_agent_erro_operacional_mission(mission)

    assert secret not in exc_info.value.public_message
    _assert_preexecution(
        exc_info.value,
        code="AG_OPERATIONAL_DIAGNOSIS_CONTEXT_INVALID",
        message=CONTEXT_INVALID_MESSAGE,
    )


# ---------------------------------------------------------------------------
# Resultado universal e erros públicos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_drift_maps_to_exact_public_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mission = _mission()
    calls = _install_fake_engine(
        monkeypatch,
        error=OperationalLegacyDriftError(),
    )

    result = await execute_agent_erro_operacional_mission(mission)

    assert calls["count"] == 1
    assert result.status == "erro"
    assert result.payload == {}
    assert result.alerts == []
    assert result.error_code == LEGACY_DRIFT_CODE
    assert result.error_message == LEGACY_DRIFT_MESSAGE
    _assert_common_result(result, mission)


@pytest.mark.asyncio
async def test_unexpected_error_is_fixed_and_does_not_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = (
        "password=segredo; SELECT * FROM privada; "
        "C:\\dev\\saas-fiscal-demo\\interno.py"
    )
    mission = _mission()
    calls = _install_fake_engine(
        monkeypatch,
        error=RuntimeError(secret),
    )

    result = await execute_agent_erro_operacional_mission(mission)
    rendered = result.model_dump_json()

    assert calls["count"] == 1
    assert result.status == "erro"
    assert result.payload == {}
    assert result.alerts == []
    assert result.error_code == EXECUTION_ERROR_CODE
    assert result.error_message == EXECUTION_ERROR_MESSAGE
    assert secret not in rendered
    assert "password=segredo" not in rendered
    assert "SELECT * FROM privada" not in rendered
    assert "interno.py" not in rendered
    assert "RuntimeError" not in rendered
    assert "Traceback" not in rendered
    _assert_common_result(result, mission)


@pytest.mark.asyncio
async def test_cross_validation_failure_is_typed() -> None:
    mission = _mission(agent_version_required="9.9")

    with patch.object(
        adapter_module,
        "validate_result_against_mission",
        side_effect=ValueError("interno"),
    ):
        with pytest.raises(
            AgentErroDiagnosisResultValidationError
        ) as exc_info:
            await execute_agent_erro_operacional_mission(mission)

    assert (
        exc_info.value.code
        == "RESULT_MISSION_VALIDATION_FAILED"
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
            AgentErroDiagnosisResultSafetyError
        ) as exc_info:
            await execute_agent_erro_operacional_mission(mission)

    assert exc_info.value.code == "RESULT_SANITIZATION_FAILED"
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


# ---------------------------------------------------------------------------
# Motor determinístico e nove sentinelas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    (
        "snapshot_kwargs",
        "expected_code",
        "expected_risk",
        "expected_missing",
    ),
    [
        (
            {
                "mensagem": "termos pendentes",
                "endpoint": "/empresas/{empresa_id}",
                "status_http": 403,
            },
            "RACE_CONDITION_TERMOS",
            "baixo",
            (),
        ),
        (
            {
                "tipo": "cta_login_contexto_perdido",
                "mensagem": "Contexto do botão perdido.",
            },
            "CTA_LOGIN_CONTEXTO_PERDIDO",
            "baixo",
            (),
        ),
        (
            {
                "mensagem": "VITE_API_URL não definida no Vercel",
            },
            "VERCEL_ENV_VAZIA",
            "baixo",
            (),
        ),
        (
            {
                "mensagem": "CNAE 5811 para actividade SaaS.",
            },
            "CNAE_SAAS_ERRADO",
            "medio",
            (),
        ),
        (
            {
                "mensagem": "MEI acima do limite 500.",
            },
            "MEI_LIMITE_EXCEDIDO",
            "medio",
            (),
        ),
        (
            {
                "mensagem": "faturamento zero rejeitado",
                "status_http": 422,
            },
            "FATURAMENTO_ZERO",
            "baixo",
            (),
        ),
        (
            {
                "tipo": "tempo_normativo_ausente",
                "mensagem": "Referência temporal ausente.",
            },
            "TEMPO_NORMATIVO_AUSENTE",
            "medio",
            (),
        ),
        (
            {
                "mensagem": "Falha de esquema detectada.",
                "contexto_indicadores": ("UNDEFINED_COLUMN",),
            },
            "SCHEMA_DRIFT_UNDEFINED_COLUMN",
            "medio",
            (
                "DATABASE_COLUMNS_STATE_REQUIRED",
                "ALEMBIC_VERSION_REQUIRED",
            ),
        ),
        (
            {
                "mensagem": "Falha operacional no upload.",
                "endpoint": "/upload-xml",
                "status_http": 500,
            },
            "UPLOAD_XML_500",
            "baixo",
            (
                "RAILWAY_STACK_TRACE_REQUIRED",
                "EXECUTAR_ANALISE_XML_SOURCE_REQUIRED",
                "LER_XML_UNICO_SOURCE_REQUIRED",
                "SMOKE_XML_REQUIRED",
            ),
        ),
    ],
)
def test_each_legacy_sentinel_maps_to_canonical_payload(
    snapshot_kwargs: dict[str, object],
    expected_code: str,
    expected_risk: str,
    expected_missing: tuple[str, ...],
) -> None:
    snapshot = _global_snapshot(**snapshot_kwargs)
    payload = executar_agent_erro_operacional_engine(snapshot)

    assert payload.event_id == snapshot.event_id
    assert payload.reconhecido is True
    assert payload.camada_reconhecimento == "sentinela"
    assert payload.diagnostico_codigo == expected_code
    assert payload.classificacao == "P0"
    assert payload.risco_patch == expected_risk
    assert payload.tem_causa_provavel is True
    assert payload.tem_evidencias is True
    assert payload.tem_teste_recomendado is True
    assert payload.tem_patch_sugerido is True
    assert payload.informacao_em_falta == expected_missing
    assert payload.publication_allowed is False
    assert payload.automation_allowed is False
    assert payload.requires_human_review is True


def test_first_matching_sentinel_wins_in_canonical_order() -> None:
    snapshot = _global_snapshot(
        tipo="cta_login_contexto_perdido",
        mensagem="CNAE 5811 com contexto perdido.",
    )

    payload = executar_agent_erro_operacional_engine(snapshot)

    assert (
        payload.diagnostico_codigo
        == "CTA_LOGIN_CONTEXTO_PERDIDO"
    )


def test_unknown_event_is_successful_nonrecognition() -> None:
    snapshot = _global_snapshot()

    payload = executar_agent_erro_operacional_engine(snapshot)

    assert payload == _nonrecognized_payload(snapshot.event_id)


def test_engine_does_not_call_run_patterns_budget_or_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.agents.agent_erro_operacional as legacy

    def forbidden(*_: object, **__: object) -> object:
        raise AssertionError("caminho proibido executado")

    monkeypatch.setattr(
        legacy,
        "_tentar_padrao_aprendido",
        forbidden,
    )
    monkeypatch.setattr(
        legacy.AgentErroOperacional,
        "run",
        forbidden,
    )
    monkeypatch.setattr(
        legacy,
        "budget_verificar",
        forbidden,
    )

    payload = executar_agent_erro_operacional_engine(
        _global_snapshot()
    )

    assert payload.reconhecido is False


def test_reconstructed_legacy_event_is_minimal() -> None:
    snapshot = _global_snapshot(
        mensagem="Falha de esquema detectada.",
        contexto_indicadores=(
            "UNDEFINED_COLUMN",
            "COLUMN_DOES_NOT_EXIST",
        ),
    )

    event = _reconstruir_evento_legado(snapshot)

    assert event.tipo == snapshot.tipo
    assert event.origem == snapshot.origem
    assert event.mensagem == snapshot.mensagem
    assert event.endpoint is None
    assert event.status_http is None
    assert event.ambiente == "local"
    assert event.commit_sha is None
    assert event.ficheiro_provavel is None
    assert set(event.contexto.keys()) == {
        "schema_drift_indicators"
    }
    assert event.contexto["schema_drift_indicators"] == (
        "undefinedcolumn",
        "column tabela.coluna does not exist",
    )


@pytest.mark.parametrize(
    "code",
    tuple(PERFIS_DIAGNOSTICOS_CANONICOS.keys()),
)
def test_projection_accepts_exact_canonical_legacy_result(
    code: str,
) -> None:
    projection = projectar_resultado_operacional(
        diagnostico_codigo=code,
        legacy_result=_legacy_result_for(code),
    )
    profile = PERFIS_DIAGNOSTICOS_CANONICOS[code]

    assert projection.diagnostico_codigo == code
    assert projection.classificacao == profile.classificacao
    assert projection.risco_patch == profile.risco_patch
    assert projection.tem_causa_provavel is True
    assert projection.tem_evidencias is True
    assert projection.tem_teste_recomendado is True
    assert projection.tem_patch_sugerido is True
    assert projection.informacao_em_falta == profile.informacao_em_falta


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("classificacao", "P1"),
        ("risco_patch", "alto"),
        ("causa_provavel", "   "),
        ("evidencias", []),
        ("evidencias", [""]),
        ("teste_recomendado", None),
        ("patch_sugerido_texto", "   "),
        ("informacao_em_falta", "texto"),
        ("informacao_em_falta", ["valor não canónico"]),
    ],
)
def test_projection_rejects_legacy_drift(
    field: str,
    value: object,
) -> None:
    legacy_result = _legacy_result_for("RACE_CONDITION_TERMOS")
    setattr(legacy_result, field, value)

    with pytest.raises(OperationalLegacyDriftError):
        projectar_resultado_operacional(
            diagnostico_codigo="RACE_CONDITION_TERMOS",
            legacy_result=legacy_result,
        )


def test_projection_contains_no_raw_legacy_text() -> None:
    secret = "RAW-LEGACY-SECRET-41236"
    legacy_result = _legacy_result_for("RACE_CONDITION_TERMOS")
    legacy_result.causa_provavel = secret
    legacy_result.evidencias = [secret]
    legacy_result.teste_recomendado = secret
    legacy_result.patch_sugerido_texto = secret

    projection = projectar_resultado_operacional(
        diagnostico_codigo="RACE_CONDITION_TERMOS",
        legacy_result=legacy_result,
    )
    rendered = json.dumps(
        projection.model_dump(mode="json"),
        ensure_ascii=False,
    )

    assert secret not in rendered


def test_payload_builder_exposes_only_public_projection() -> None:
    context = _global_snapshot()
    projection = OperationalDiagnosisInternal(
        diagnostico_codigo=None,
        classificacao=None,
        risco_patch=None,
        tem_causa_provavel=False,
        tem_evidencias=False,
        tem_teste_recomendado=False,
        tem_patch_sugerido=False,
        informacao_em_falta=(),
    )

    payload = construir_payload_diagnostico_operacional(
        context=context,
        projection=projection,
    )
    keys = set(payload.model_dump(mode="python").keys())

    assert keys == {
        "event_id",
        "reconhecido",
        "camada_reconhecimento",
        "diagnostico_codigo",
        "classificacao",
        "risco_patch",
        "tem_causa_provavel",
        "tem_evidencias",
        "tem_teste_recomendado",
        "tem_patch_sugerido",
        "informacao_em_falta",
        "publication_allowed",
        "automation_allowed",
        "requires_human_review",
    }


def test_independent_validation_detects_simultaneous_tampering() -> None:
    context = _global_snapshot()
    projection = projectar_resultado_operacional(
        diagnostico_codigo="RACE_CONDITION_TERMOS",
        legacy_result=_legacy_result_for("RACE_CONDITION_TERMOS"),
    )
    payload = construir_payload_diagnostico_operacional(
        context=context,
        projection=projection,
    )

    altered_projection = projection.model_copy(
        update={"risco_patch": "alto"}
    )
    altered_payload = payload.model_copy(
        update={"risco_patch": "alto"}
    )

    with pytest.raises(OperationalLegacyDriftError):
        validate_operational_diagnosis_payload_against_context(
            context=context,
            projection=altered_projection,
            payload=altered_payload,
        )


def test_independent_validation_detects_event_id_tampering() -> None:
    context = _global_snapshot()
    projection = OperationalDiagnosisInternal(
        diagnostico_codigo=None,
        classificacao=None,
        risco_patch=None,
        tem_causa_provavel=False,
        tem_evidencias=False,
        tem_teste_recomendado=False,
        tem_patch_sugerido=False,
        informacao_em_falta=(),
    )
    payload = construir_payload_diagnostico_operacional(
        context=context,
        projection=projection,
    ).model_copy(update={"event_id": uuid4()})

    with pytest.raises(OperationalLegacyDriftError):
        validate_operational_diagnosis_payload_against_context(
            context=context,
            projection=projection,
            payload=payload,
        )


# ---------------------------------------------------------------------------
# Guardas da superfície legada
# ---------------------------------------------------------------------------


def test_canonical_legacy_surface_is_accepted() -> None:
    legacy = _canonical_fake_legacy()
    sentinels = _validar_superficie_legada(legacy)

    assert isinstance(sentinels, tuple)
    assert tuple(item.__name__ for item in sentinels) == (
        NOMES_SENTINELAS_CANONICOS
    )


@pytest.mark.parametrize(
    "legacy",
    [
        SimpleNamespace(_PADROES_APRENDIDOS=[]),
        SimpleNamespace(
            _SENTINELAS=1,
            _PADROES_APRENDIDOS=[],
        ),
        SimpleNamespace(
            _SENTINELAS=[],
            _PADROES_APRENDIDOS=[],
        ),
        SimpleNamespace(
            _SENTINELAS=[None] * 9,
            _PADROES_APRENDIDOS=[],
        ),
        SimpleNamespace(
            _SENTINELAS=list(
                reversed(
                    _canonical_fake_legacy()._SENTINELAS
                )
            ),
            _PADROES_APRENDIDOS=[],
        ),
        SimpleNamespace(
            _SENTINELAS=_canonical_fake_legacy()._SENTINELAS,
        ),
        SimpleNamespace(
            _SENTINELAS=_canonical_fake_legacy()._SENTINELAS,
            _PADROES_APRENDIDOS=[{"tipo": "proibido"}],
        ),
    ],
)
def test_legacy_surface_drift_is_rejected(
    legacy: SimpleNamespace,
) -> None:
    with pytest.raises(OperationalLegacyDriftError):
        _validar_superficie_legada(legacy)


def test_callability_is_checked_before_name_access() -> None:
    class NameTrap:
        def __getattribute__(self, name: str) -> object:
            if name == "__name__":
                raise AssertionError("__name__ não devia ser lido")
            return object.__getattribute__(self, name)

    legacy = _canonical_fake_legacy()
    legacy._SENTINELAS[0] = NameTrap()

    with pytest.raises(OperationalLegacyDriftError):
        _validar_superficie_legada(legacy)


def test_sentinel_map_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    altered = dict(MAPA_SENTINELAS_PARA_CODIGOS)
    altered.pop(NOMES_SENTINELAS_CANONICOS[-1])
    monkeypatch.setattr(
        engine_module,
        "MAPA_SENTINELAS_PARA_CODIGOS",
        altered,
    )

    with pytest.raises(OperationalLegacyDriftError):
        _validar_superficie_legada(_canonical_fake_legacy())


def test_profile_key_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    altered = dict(PERFIS_DIAGNOSTICOS_CANONICOS)
    altered.pop("UPLOAD_XML_500")
    monkeypatch.setattr(
        engine_module,
        "PERFIS_DIAGNOSTICOS_CANONICOS",
        altered,
    )

    with pytest.raises(OperationalLegacyDriftError):
        _validar_superficie_legada(_canonical_fake_legacy())


# ---------------------------------------------------------------------------
# Integridade estrutural e escopo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("relative_path", "expected_hash"),
    [
        (CONTRACT_PATH, CONTRACT_SHA256),
        (ENGINE_PATH, ENGINE_SHA256),
        (ADAPTER_PATH, ADAPTER_SHA256),
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
        CONTRACT_PATH,
        ENGINE_PATH,
        ADAPTER_PATH,
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

    for module in _imported_modules(CONTRACT_PATH):
        assert not any(
            module == item
            or module.startswith(f"{item}.")
            for item in forbidden
        ), f"contrato importa módulo proibido: {module}"


@pytest.mark.parametrize(
    "relative_path",
    [
        ADAPTER_PATH,
        ENGINE_PATH,
    ],
)
def test_adapter_and_engine_have_no_infrastructure_imports(
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
    }

    for module in _imported_modules(relative_path):
        assert not any(
            module == item
            or module.startswith(f"{item}.")
            for item in forbidden
        ), f"{relative_path} importa módulo proibido: {module}"


def test_adapter_does_not_import_legacy_agent() -> None:
    assert LEGACY_MODULE not in _imported_modules(ADAPTER_PATH)


def test_engine_imports_legacy_only_inside_main_function() -> None:
    tree = _tree(ENGINE_PATH)
    legacy_imports = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "app.agents"
            and any(
                alias.name == "agent_erro_operacional"
                for alias in node.names
            )
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
            == "executar_agent_erro_operacional_engine"
        )
    )
    assert legacy_import in list(ast.walk(function))

    validation_calls = [
        node
        for node in ast.walk(function)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_validar_contexto_tipado"
        )
    ]
    assert len(validation_calls) == 1
    assert validation_calls[0].lineno < legacy_import.lineno


def test_adapter_imports_engine_only_after_context_validation() -> None:
    tree = _tree(ADAPTER_PATH)
    function = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.AsyncFunctionDef)
            and node.name
            == "execute_agent_erro_operacional_mission"
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
        "from app.agents.adapters.agent_erro_operacional "
        "import execute_agent_erro_operacional_mission;"
        "print("
        "'app.agents.engines.agent_erro_operacional' in sys.modules,"
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
    [
        ADAPTER_PATH,
        ENGINE_PATH,
    ],
)
def test_layers_have_no_persistence_calls(
    relative_path: str,
) -> None:
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

    assert _called_names(relative_path).isdisjoint(
        forbidden_calls
    )


def test_engine_references_no_prohibited_execution_paths() -> None:
    prohibited = {
        "run",
        "_tentar_padrao_aprendido",
        "budget_verificar",
        "completar",
        "LLMRouter",
    }

    assert _called_names(ENGINE_PATH).isdisjoint(prohibited)


def test_no_exception_is_stringified() -> None:
    for relative_path in (ADAPTER_PATH, ENGINE_PATH):
        tree = _tree(relative_path)

        for handler in (
            node
            for node in ast.walk(tree)
            if (
                isinstance(node, ast.ExceptHandler)
                and node.name
            )
        ):
            for node in ast.walk(handler):
                if not isinstance(node, ast.Call):
                    continue
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "str"
                ):
                    assert not any(
                        isinstance(argument, ast.Name)
                        and argument.id == handler.name
                        for argument in node.args
                    )


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/agents/agent_executor.py",
        "app/agents/agent_scheduler.py",
    ],
)
def test_runtime_does_not_reference_b14_3f_adapter(
    relative_path: str,
) -> None:
    source = _source(relative_path)

    assert "execute_agent_erro_operacional_mission" not in source
    assert ADAPTER_PATH.replace("/", ".").removesuffix(".py") not in source


def test_no_reader_was_created() -> None:
    assert not (
        ROOT
        / "app"
        / "agents"
        / "readers"
        / "agent_erro_operacional.py"
    ).exists()


def test_no_init_py_was_connected_to_b14_3f() -> None:
    for init_path in (
        "app/agents/contracts/__init__.py",
        "app/agents/engines/__init__.py",
        "app/agents/adapters/__init__.py",
    ):
        assert "agent_erro_operacional" not in _source(init_path)


def test_legacy_agent_has_no_run_mission() -> None:
    names = {
        node.name
        for node in ast.walk(_tree(LEGACY_PATH))
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }

    assert "run_mission" not in names


def test_adapter_is_async_and_engine_is_sync() -> None:
    assert inspect.iscoroutinefunction(
        execute_agent_erro_operacional_mission
    )
    assert not inspect.iscoroutinefunction(
        executar_agent_erro_operacional_engine
    )


def test_canonical_collections_are_immutable() -> None:
    assert isinstance(NOMES_SENTINELAS_CANONICOS, tuple)
    assert isinstance(ORDEM_SCHEMA_DRIFT_INDICADORES, tuple)
    assert isinstance(ORDEM_INFO_EM_FALTA, tuple)
    assert isinstance(MAPA_SENTINELAS_PARA_CODIGOS, MappingProxyType)
    assert isinstance(PERFIS_DIAGNOSTICOS_CANONICOS, MappingProxyType)
    assert isinstance(MAPA_CODIGOS_PARA_INFO_EM_FALTA, MappingProxyType)
    assert isinstance(SCHEMA_DRIFT_REPRESENTACAO_LEGADA, MappingProxyType)
    assert isinstance(INFO_LEGADO_EXACTA, MappingProxyType)

    with pytest.raises(TypeError):
        operator.setitem(
            MAPA_SENTINELAS_PARA_CODIGOS,
            "NOVO",
            "UPLOAD_XML_500",
        )
