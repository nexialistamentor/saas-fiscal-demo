"""
tests/test_consistency_audit_mission_adapter.py — ADR-012 B14.3D.

Provas contratuais do ConsistencyAuditAgent L3:
- MissionFactory e fronteira soberana do adapter;
- modos sombra/dry_run e bloqueios auditáveis;
- contrato e motor determinístico puro;
- validação independente payload-contexto;
- fail-closed perante resposta do TaxConsistencyEngine;
- ausência de BD, LLM, persistência e integração activa;
- preservação byte a byte do agente legado e do engine.
"""

from __future__ import annotations

import ast
import inspect
import json
import math
import operator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from tests.canonical_source_hash import canonical_source_sha256

from app.agents.adapters.consistency_audit import (
    execute_consistency_audit_mission,
)
from app.agents.contracts.consistency_audit import (
    ALERTAS_CONSISTENCY_CANONICOS,
    INDICE_ALERTA_CONSISTENCY,
    ORDEM_ALERTAS_CONSISTENCY,
    PARES_CANONICOS,
    ConsistencyAuditAlert,
    ConsistencyAuditContext,
    ConsistencyAuditPayload,
    ConsistencyAuditPreExecutionError,
    ConsistencyAuditResultSafetyError,
    ConsistencyAuditResultValidationError,
)
from app.agents.contracts.shared import BudgetPolicy
import app.agents.engines.consistency_audit as consistency_engine_module
from app.agents.engines.consistency_audit import (
    construir_payload_consistency_audit,
    validate_consistency_audit_payload_against_context,
)
from app.agents.mission_factory import create_agent_mission


ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc

TENANT_ID = 42
ACTOR_ID = 99
EMPRESA_ID = 7
DOCUMENTO_ID = 101

CREATED_AT = datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC)

LEGACY_AGENT_SHA256 = (
    "6752D0C3471F46B9486F23FA9D1A6CC0CE5509AA9296E04472D7BFDFFD9AE7D1"
)
LEGACY_ENGINE_SHA256 = (
    "EE426DB333DEE81948FADB2AFF1F6F3F901582F0D6E93FFFD08410328AB53D3F"
)

EXECUTION_ERROR_MESSAGE = (
    "Não foi possível concluir a auditoria de consistência fiscal."
)

# Sentinelas inequivocamente distintos — diferença > 0.01
_SENTINELA_XML   = 99_999.77
_SENTINELA_MOTOR = 88_888.66


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mission(
    *,
    context: dict | None = None,
    execution_mode: str = "sombra",
    requested_by: str = "user",
    agent_version_required: str | None = None,
    source_request_id: str = "req-consistency-001",
    reference_at: datetime | None = None,
    tenant_id: object = TENANT_ID,
    actor_id: object = ACTOR_ID,
    entity_id: object = DOCUMENTO_ID,
    entity_type: str = "documento_fiscal",
    **overrides,
):
    kwargs: dict = {
        "mission_type": "auditar_consistencia_fiscal",
        "target_agent": "consistency_audit_agent",
        "context": (
            context
            if context is not None
            else {
                "empresa_id": EMPRESA_ID,
                "documento_id": DOCUMENTO_ID,
                "icms_st_xml": 100.0,
                "icms_st_motor": 100.0,
            }
        ),
        "context_schema": "consistency_audit.context",
        "context_version": "1.0",
        "output_schema": "consistency_audit.result",
        "output_version": "1.0",
        "scope": "documento",
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "requested_by": requested_by,
        "authority_level": "leitura",
        "execution_mode": execution_mode,
        "source_request_id": source_request_id,
        "created_at": CREATED_AT,
        "reference_at": reference_at,
        "agent_version_required": agent_version_required,
        "budget_policy": BudgetPolicy(),
        "sources": [],
    }
    kwargs.update(overrides)
    return create_agent_mission(**kwargs)


def _ctx(
    *,
    empresa_id: int = EMPRESA_ID,
    documento_id: int = DOCUMENTO_ID,
    **kwargs,
) -> ConsistencyAuditContext:
    return ConsistencyAuditContext(
        empresa_id=empresa_id,
        documento_id=documento_id,
        **kwargs,
    )


def _assert_common_result(result) -> None:
    assert result.attempt == 1
    assert result.agent_id == "consistency_audit_agent"
    assert result.agent_version == "1.0"
    assert result.mission_type == "auditar_consistencia_fiscal"
    assert result.scope == "documento"
    assert result.tenant_id == TENANT_ID
    assert result.requires_human_review is True
    assert result.llm_used is False
    assert result.provider is None
    assert result.tokens_used is None
    assert result.cost_estimated is None
    assert result.cost_actual is None
    assert result.currency is None
    assert result.retryable is False
    assert result.evidence == []
    assert result.actions_proposed == []
    assert result.actions_executed == []
    assert result.payload_schema == "consistency_audit.result"
    assert result.payload_version == "1.0"
    assert result.started_at.utcoffset() == timedelta(0)
    assert result.finished_at.utcoffset() == timedelta(0)
    assert result.finished_at >= result.started_at
    assert type(result.duration_ms) is int
    assert result.duration_ms >= 0


_ENGINE_PATH = (
    "app.agents.engines.consistency_audit.TaxConsistencyEngine"
)


def _patch_engine(result: object):
    mock = MagicMock()
    mock.return_value.verificar_consistencia.return_value = result
    return patch(_ENGINE_PATH, mock)


# Missão com ICMS e MVA aplicáveis, valores iguais (sem divergência real)
def _mission_icms_mva(
    icms_xml: float = 1.0,
    icms_motor: float = 1.0,
    mva_xml: float = 2.0,
    mva_motor: float = 2.0,
) -> object:
    return _mission(context={
        "empresa_id": EMPRESA_ID,
        "documento_id": DOCUMENTO_ID,
        "icms_st_xml": icms_xml,
        "icms_st_motor": icms_motor,
        "mva_xml": mva_xml,
        "mva_motor": mva_motor,
    })


# ---------------------------------------------------------------------------
# 18.1 Fronteira da missão
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sombra", "dry_run"])
async def test_nominal_modes_succeed(mode: str) -> None:
    result = await execute_consistency_audit_mission(
        _mission(execution_mode=mode)
    )
    assert result.status == "sucesso"
    assert result.mode == mode
    assert result.error_code is None
    assert result.error_message is None
    assert result.alerts == []
    assert result.payload["dados_coerentes"] is True
    assert result.payload["publication_allowed"] is False
    _assert_common_result(result)


@pytest.mark.asyncio
async def test_actor_id_may_differ_from_tenant_id() -> None:
    result = await execute_consistency_audit_mission(
        _mission(tenant_id=TENANT_ID, actor_id=ACTOR_ID)
    )
    assert result.status == "sucesso"


@pytest.mark.asyncio
@pytest.mark.parametrize("requested_by", ["user", "system"])
async def test_requested_by_user_and_system_accepted(requested_by: str) -> None:
    result = await execute_consistency_audit_mission(
        _mission(requested_by=requested_by)
    )
    assert result.status == "sucesso"


@pytest.mark.asyncio
async def test_reference_at_none_accepted() -> None:
    result = await execute_consistency_audit_mission(
        _mission(reference_at=None)
    )
    assert result.status == "sucesso"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("target_agent",      "outro",        "MISSION_TARGET_MISMATCH"),
        ("mission_type",      "outro",        "MISSION_TYPE_UNSUPPORTED"),
        ("context_schema",    "outro",        "CONTEXT_SCHEMA_UNSUPPORTED"),
        ("context_version",   "9.0",          "CONTEXT_VERSION_UNSUPPORTED"),
        ("output_schema",     "outro",        "OUTPUT_SCHEMA_UNSUPPORTED"),
        ("output_version",    "9.0",          "OUTPUT_VERSION_UNSUPPORTED"),
        ("scope",             "tenant",       "MISSION_SCOPE_UNSUPPORTED"),
        ("tenant_id",         None,           "MISSION_TENANT_REQUIRED"),
        ("tenant_id",         True,           "MISSION_TENANT_UNSUPPORTED"),
        ("tenant_id",         0,              "MISSION_TENANT_UNSUPPORTED"),
        ("tenant_id",         -1,             "MISSION_TENANT_UNSUPPORTED"),
        ("tenant_id",         "42",           "MISSION_TENANT_UNSUPPORTED"),
        ("tenant_id",         42.0,           "MISSION_TENANT_UNSUPPORTED"),
        ("actor_id",          None,           "MISSION_ACTOR_UNSUPPORTED"),
        ("actor_id",          True,           "MISSION_ACTOR_UNSUPPORTED"),
        ("actor_id",          0,              "MISSION_ACTOR_UNSUPPORTED"),
        ("actor_id",          -1,             "MISSION_ACTOR_UNSUPPORTED"),
        ("actor_id",          "99",           "MISSION_ACTOR_UNSUPPORTED"),
        ("actor_id",          99.0,           "MISSION_ACTOR_UNSUPPORTED"),
        ("entity_type",       "empresa",      "MISSION_ENTITY_UNSUPPORTED"),
        ("entity_id",         None,           "MISSION_ENTITY_UNSUPPORTED"),
        ("entity_id",         True,           "MISSION_ENTITY_UNSUPPORTED"),
        ("entity_id",         0,              "MISSION_ENTITY_UNSUPPORTED"),
        ("entity_id",         -1,             "MISSION_ENTITY_UNSUPPORTED"),
        ("entity_id",         "101",          "MISSION_ENTITY_UNSUPPORTED"),
        ("entity_id",         101.0,          "MISSION_ENTITY_UNSUPPORTED"),
        ("requested_by",      "admin",        "MISSION_REQUESTED_BY_UNSUPPORTED"),
        ("authority_level",   "proposta",     "MISSION_AUTHORITY_UNSUPPORTED"),
        ("source_request_id", None,           "MISSION_ORIGIN_UNSUPPORTED"),
        ("source_request_id", 123,            "MISSION_ORIGIN_UNSUPPORTED"),
        ("source_request_id", "  ",           "MISSION_ORIGIN_UNSUPPORTED"),
    ],
)
async def test_mission_boundary_rejects_invalid_values(
    field: str,
    value: object,
    expected_code: str,
) -> None:
    mission = _mission().model_copy(update={field: value})
    with pytest.raises(ConsistencyAuditPreExecutionError) as exc_info:
        await execute_consistency_audit_mission(mission)
    assert exc_info.value.code == expected_code
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


@pytest.mark.asyncio
async def test_entity_id_must_match_context_documento_id() -> None:
    mission = _mission().model_copy(update={"entity_id": DOCUMENTO_ID + 1})
    with pytest.raises(ConsistencyAuditPreExecutionError) as exc_info:
        await execute_consistency_audit_mission(mission)
    assert exc_info.value.code == "MISSION_ENTITY_UNSUPPORTED"


@pytest.mark.asyncio
async def test_source_event_id_rejected() -> None:
    mission = _mission().model_copy(
        update={"source_event_id": _mission().mission_id}
    )
    with pytest.raises(ConsistencyAuditPreExecutionError) as exc_info:
        await execute_consistency_audit_mission(mission)
    assert exc_info.value.code == "MISSION_ORIGIN_UNSUPPORTED"


@pytest.mark.asyncio
async def test_schedule_slot_rejected() -> None:
    mission = _mission().model_copy(
        update={"schedule_slot": "2026-07-17T12:00:00Z"}
    )
    with pytest.raises(ConsistencyAuditPreExecutionError) as exc_info:
        await execute_consistency_audit_mission(mission)
    assert exc_info.value.code == "MISSION_ORIGIN_UNSUPPORTED"


@pytest.mark.asyncio
async def test_budget_must_be_default() -> None:
    mission = _mission().model_copy(
        update={"budget_policy": BudgetPolicy(
            allow_llm=True,
            allowed_providers=["local_model"],
            max_calls=1,
            max_input_chars=1,
            max_output_tokens=1,
        )}
    )
    with pytest.raises(ConsistencyAuditPreExecutionError) as exc_info:
        await execute_consistency_audit_mission(mission)
    assert exc_info.value.code == "MISSION_BUDGET_UNSUPPORTED"


@pytest.mark.asyncio
async def test_sources_must_be_empty() -> None:
    mission = _mission().model_copy(update={"sources": [object()]})
    with pytest.raises(ConsistencyAuditPreExecutionError) as exc_info:
        await execute_consistency_audit_mission(mission)
    assert exc_info.value.code == "MISSION_SOURCES_UNSUPPORTED"


@pytest.mark.asyncio
async def test_active_mode_blocked() -> None:
    result = await execute_consistency_audit_mission(
        _mission(execution_mode="activo")
    )
    assert result.status == "bloqueado"
    assert result.payload == {}
    assert result.error_code is None
    assert result.error_message is None
    assert len(result.alerts) == 1
    assert result.alerts[0].code == "EXECUTION_MODE_NOT_AUTHORIZED"
    _assert_common_result(result)


@pytest.mark.asyncio
async def test_incompatible_version_precedes_active_mode() -> None:
    result = await execute_consistency_audit_mission(
        _mission(execution_mode="activo", agent_version_required="9.0")
    )
    assert result.status == "bloqueado"
    assert result.alerts[0].code == "AGENT_VERSION_INCOMPATIBLE"


@pytest.mark.asyncio
@pytest.mark.parametrize("required", [None, "1.0"])
async def test_compatible_version_executes(required: str | None) -> None:
    result = await execute_consistency_audit_mission(
        _mission(agent_version_required=required)
    )
    assert result.status == "sucesso"


# ---------------------------------------------------------------------------
# 18.2 Contexto
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad_id",
    [True, False, "7", 7.0, 0, -1],
)
def test_context_rejects_invalid_empresa_id(bad_id: object) -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditContext(
            empresa_id=bad_id,
            documento_id=DOCUMENTO_ID,
            icms_st_xml=1.0,
            icms_st_motor=1.0,
        )


@pytest.mark.parametrize(
    "bad_id",
    [True, False, "101", 101.0, 0, -1],
)
def test_context_rejects_invalid_documento_id(bad_id: object) -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditContext(
            empresa_id=EMPRESA_ID,
            documento_id=bad_id,
            icms_st_xml=1.0,
            icms_st_motor=1.0,
        )


def test_context_frozen_forbids_attribute_assignment() -> None:
    ctx = _ctx(icms_st_xml=1.0, icms_st_motor=1.0)
    with pytest.raises(ValidationError):
        setattr(ctx, "empresa_id", 99)


def test_context_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditContext(
            empresa_id=EMPRESA_ID,
            documento_id=DOCUMENTO_ID,
            icms_st_xml=1.0,
            icms_st_motor=1.0,
            campo_extra=1,
        )


def test_context_requires_at_least_one_complete_pair() -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditContext(
            empresa_id=EMPRESA_ID,
            documento_id=DOCUMENTO_ID,
        )


def test_context_incomplete_pair_rejected() -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditContext(
            empresa_id=EMPRESA_ID,
            documento_id=DOCUMENTO_ID,
            icms_st_xml=1.0,
        )


def test_context_explicit_none_in_xml_rejected() -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditContext(
            empresa_id=EMPRESA_ID,
            documento_id=DOCUMENTO_ID,
            icms_st_xml=None,
            icms_st_motor=1.0,
        )


def test_context_explicit_none_in_motor_rejected() -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditContext(
            empresa_id=EMPRESA_ID,
            documento_id=DOCUMENTO_ID,
            icms_st_xml=1.0,
            icms_st_motor=None,
        )


def test_context_model_fields_set_distinguishes_absent_from_none() -> None:
    # Omitido: não aparece em model_fields_set
    ctx_absent = ConsistencyAuditContext.model_construct(
        empresa_id=EMPRESA_ID,
        documento_id=DOCUMENTO_ID,
        icms_st_xml=1.0,
        icms_st_motor=1.0,
    )
    assert "mva_xml" not in ctx_absent.model_fields_set

    # None explícito: aparece em model_fields_set
    ctx_none = ConsistencyAuditContext.model_construct(
        empresa_id=EMPRESA_ID,
        documento_id=DOCUMENTO_ID,
        icms_st_xml=1.0,
        icms_st_motor=1.0,
        mva_xml=None,
    )
    # model_construct ignora validators mas preenche model_fields_set
    # apenas com campos passados explicitamente
    assert "mva_xml" in ctx_none.model_fields_set


@pytest.mark.parametrize(
    "bad_value",
    [True, False, "1.0", b"1.0", Decimal("1.0")],
)
def test_context_rejects_non_numeric_pair_values(bad_value: object) -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditContext(
            empresa_id=EMPRESA_ID,
            documento_id=DOCUMENTO_ID,
            icms_st_xml=bad_value,
            icms_st_motor=1.0,
        )


@pytest.mark.parametrize(
    "bad_value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_context_rejects_non_finite_floats(bad_value: float) -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditContext(
            empresa_id=EMPRESA_ID,
            documento_id=DOCUMENTO_ID,
            icms_st_xml=bad_value,
            icms_st_motor=1.0,
        )


def test_context_rejects_integer_overflow() -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditContext(
            empresa_id=EMPRESA_ID,
            documento_id=DOCUMENTO_ID,
            icms_st_xml=10**1000,
            icms_st_motor=1.0,
        )


def test_context_accepts_zero_in_pair() -> None:
    ctx = _ctx(icms_st_xml=0, icms_st_motor=0)
    assert ctx.icms_st_xml == 0
    assert ctx.icms_st_motor == 0


def test_context_accepts_negative_finite_values() -> None:
    ctx = _ctx(icms_st_xml=-1.0, icms_st_motor=-2.0)
    assert ctx.icms_st_xml == -1.0


# ---------------------------------------------------------------------------
# 18.3 Tolerância exacta com math.nextafter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("par", ["icms_st", "mva", "base_st"])
def test_tolerance_below_does_not_diverge(par: str) -> None:
    delta = math.nextafter(0.01, 0.0)
    ctx = ConsistencyAuditContext(
        empresa_id=EMPRESA_ID,
        documento_id=DOCUMENTO_ID,
        **{f"{par}_xml": 0.0, f"{par}_motor": delta},
    )
    payload = construir_payload_consistency_audit(ctx)
    assert payload.dados_coerentes is True
    assert payload.alertas == ()


@pytest.mark.parametrize("par", ["icms_st", "mva", "base_st"])
def test_tolerance_exact_does_not_diverge(par: str) -> None:
    ctx = ConsistencyAuditContext(
        empresa_id=EMPRESA_ID,
        documento_id=DOCUMENTO_ID,
        **{f"{par}_xml": 0.0, f"{par}_motor": 0.01},
    )
    payload = construir_payload_consistency_audit(ctx)
    assert payload.dados_coerentes is True


@pytest.mark.parametrize("par", ["icms_st", "mva", "base_st"])
def test_tolerance_above_diverges(par: str) -> None:
    delta = math.nextafter(0.01, math.inf)
    ctx = ConsistencyAuditContext(
        empresa_id=EMPRESA_ID,
        documento_id=DOCUMENTO_ID,
        **{f"{par}_xml": 0.0, f"{par}_motor": delta},
    )
    payload = construir_payload_consistency_audit(ctx)
    assert payload.dados_coerentes is False
    assert len(payload.alertas) == 1


@pytest.mark.parametrize("par", ["icms_st", "mva", "base_st"])
def test_tolerance_symmetric_abs(par: str) -> None:
    delta = math.nextafter(0.01, math.inf)
    ctx_pos = ConsistencyAuditContext(
        empresa_id=EMPRESA_ID,
        documento_id=DOCUMENTO_ID,
        **{f"{par}_xml": 0.0, f"{par}_motor": delta},
    )
    ctx_neg = ConsistencyAuditContext(
        empresa_id=EMPRESA_ID,
        documento_id=DOCUMENTO_ID,
        **{f"{par}_xml": delta, f"{par}_motor": 0.0},
    )
    p1 = construir_payload_consistency_audit(ctx_pos)
    p2 = construir_payload_consistency_audit(ctx_neg)
    assert p1.dados_coerentes is False
    assert p2.dados_coerentes is False


# ---------------------------------------------------------------------------
# 18.4 Combinações de alertas
# ---------------------------------------------------------------------------

def test_single_icms_st_divergence() -> None:
    delta = math.nextafter(0.01, math.inf)
    ctx = _ctx(icms_st_xml=0.0, icms_st_motor=delta)
    payload = construir_payload_consistency_audit(ctx)
    assert tuple(a.codigo for a in payload.alertas) == ("ICMS_ST_DIVERGENTE",)


def test_single_mva_divergence() -> None:
    delta = math.nextafter(0.01, math.inf)
    ctx = _ctx(mva_xml=0.0, mva_motor=delta)
    payload = construir_payload_consistency_audit(ctx)
    assert tuple(a.codigo for a in payload.alertas) == ("MVA_DIVERGENTE",)


def test_single_base_st_divergence() -> None:
    delta = math.nextafter(0.01, math.inf)
    ctx = _ctx(base_st_xml=0.0, base_st_motor=delta)
    payload = construir_payload_consistency_audit(ctx)
    assert tuple(a.codigo for a in payload.alertas) == ("BASE_ST_DIVERGENTE",)


def test_two_divergences_canonical_order() -> None:
    delta = math.nextafter(0.01, math.inf)
    ctx = _ctx(
        icms_st_xml=0.0, icms_st_motor=delta,
        mva_xml=0.0, mva_motor=delta,
    )
    payload = construir_payload_consistency_audit(ctx)
    assert tuple(a.codigo for a in payload.alertas) == (
        "ICMS_ST_DIVERGENTE", "MVA_DIVERGENTE"
    )


def test_three_divergences_canonical_order() -> None:
    delta = math.nextafter(0.01, math.inf)
    ctx = _ctx(
        icms_st_xml=0.0, icms_st_motor=delta,
        mva_xml=0.0, mva_motor=delta,
        base_st_xml=0.0, base_st_motor=delta,
    )
    payload = construir_payload_consistency_audit(ctx)
    assert tuple(a.codigo for a in payload.alertas) == (
        "ICMS_ST_DIVERGENTE", "MVA_DIVERGENTE", "BASE_ST_DIVERGENTE"
    )
    assert payload.dados_coerentes is False
    assert payload.total_alertas == 3


def test_omitted_pair_produces_no_alert() -> None:
    ctx = _ctx(icms_st_xml=1.0, icms_st_motor=1.0)
    payload = construir_payload_consistency_audit(ctx)
    codigos = [a.codigo for a in payload.alertas]
    assert "MVA_DIVERGENTE" not in codigos
    assert "BASE_ST_DIVERGENTE" not in codigos


# ---------------------------------------------------------------------------
# 18.5 Fail-closed com patch do TaxConsistencyEngine
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failclosed_resultado_nao_mapping() -> None:
    with _patch_engine("string"):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"
    assert result.error_code == "AG_CONSISTENCY_AUDIT_EXECUTION_ERROR"


@pytest.mark.asyncio
async def test_failclosed_chave_extra_na_raiz() -> None:
    with _patch_engine({"consistente": True, "divergencias": [], "extra": 1}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_chave_ausente_na_raiz() -> None:
    with _patch_engine({"consistente": True}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_consistente_nao_bool_exacto() -> None:
    with _patch_engine({"consistente": 1, "divergencias": []}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_divergencias_nao_list_exacta() -> None:
    with _patch_engine({"consistente": True, "divergencias": ()}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_incoerencia_consistente_true_com_divergencias() -> None:
    div = {"tipo": "ICMS_ST_DIVERGENTE", "valor_xml": 100.0, "valor_motor": 100.0}
    with _patch_engine({"consistente": True, "divergencias": [div]}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_consistente_false_sem_divergencias() -> None:
    with _patch_engine({"consistente": False, "divergencias": []}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_item_nao_mapping() -> None:
    with _patch_engine({"consistente": False, "divergencias": ["string"]}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_tipo_ausente() -> None:
    with _patch_engine({"consistente": False, "divergencias": [
        {"valor_xml": 1.0, "valor_motor": 2.0}
    ]}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_tipo_nao_textual() -> None:
    with _patch_engine({"consistente": False, "divergencias": [
        {"tipo": 123, "valor_xml": 1.0, "valor_motor": 2.0}
    ]}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_codigo_desconhecido() -> None:
    with _patch_engine({"consistente": False, "divergencias": [
        {"tipo": "CODIGO_INVENTADO", "valor_xml": 1.0, "valor_motor": 2.0}
    ]}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_codigo_duplicado() -> None:
    div = {"tipo": "ICMS_ST_DIVERGENTE", "valor_xml": 100.0, "valor_motor": 100.0}
    with _patch_engine({"consistente": False, "divergencias": [div, div]}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.parametrize(
    "validator_name",
    ["_validar_resposta_protegida", "_inspecionar_resposta_independente"],
)
def test_failclosed_duplicado_detectado_antes_de_ordem(
    validator_name: str,
) -> None:
    """O terceiro ICMS é simultaneamente duplicado e fora de ordem."""
    context = _ctx(
        icms_st_xml=1.0,
        icms_st_motor=2.0,
        mva_xml=3.0,
        mva_motor=4.0,
    )
    pares_aplicaveis = getattr(
        consistency_engine_module,
        "_identificar_pares_aplicaveis",
    )(context)
    div_icms = {
        "tipo": "ICMS_ST_DIVERGENTE",
        "valor_xml": 1.0,
        "valor_motor": 2.0,
    }
    div_mva = {
        "tipo": "MVA_DIVERGENTE",
        "mva_xml": 3.0,
        "mva_motor": 4.0,
    }
    resultado = {
        "consistente": False,
        "divergencias": [div_icms, div_mva, div_icms],
    }
    validator = getattr(consistency_engine_module, validator_name)
    with pytest.raises(ValueError, match="duplicado"):
        validator(resultado, context, pares_aplicaveis)


@pytest.mark.asyncio
async def test_failclosed_ordem_errada() -> None:
    div_mva = {
        "tipo": "MVA_DIVERGENTE",
        "mva_xml": 3.0,
        "mva_motor": 4.0,
    }
    div_icms = {
        "tipo": "ICMS_ST_DIVERGENTE",
        "valor_xml": 1.0,
        "valor_motor": 2.0,
    }
    with _patch_engine({
        "consistente": False,
        "divergencias": [div_mva, div_icms],
    }):
        result = await execute_consistency_audit_mission(
            _mission_icms_mva(
                icms_xml=1.0,
                icms_motor=2.0,
                mva_xml=3.0,
                mva_motor=4.0,
            )
        )
    assert result.status == "erro"
    assert result.error_code == "AG_CONSISTENCY_AUDIT_EXECUTION_ERROR"


@pytest.mark.asyncio
async def test_failclosed_codigo_para_par_nao_aplicavel() -> None:
    div_mva = {"tipo": "MVA_DIVERGENTE", "mva_xml": 1.0, "mva_motor": 2.0}
    with _patch_engine({"consistente": False, "divergencias": [div_mva]}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_chaves_item_extras() -> None:
    div = {
        "tipo": "ICMS_ST_DIVERGENTE",
        "valor_xml": 100.0,
        "valor_motor": 100.0,
        "extra": "proibido",
    }
    with _patch_engine({"consistente": False, "divergencias": [div]}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_chave_bruta_obrigatoria_ausente() -> None:
    # ICMS_ST_DIVERGENTE exige valor_xml, valor_motor — omitir valor_motor
    div = {"tipo": "ICMS_ST_DIVERGENTE", "valor_xml": 100.0}
    with _patch_engine({"consistente": False, "divergencias": [div]}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_valor_bruto_tipo_divergente_do_contexto() -> None:
    # Contexto tem float; engine devolve int — tipo divergente
    div = {"tipo": "ICMS_ST_DIVERGENTE", "valor_xml": 100, "valor_motor": 100.0}
    with _patch_engine({"consistente": False, "divergencias": [div]}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_valor_bruto_diverge_do_contexto() -> None:
    # Contexto 100.0; engine devolve 99.0 — valor divergente
    div = {"tipo": "ICMS_ST_DIVERGENTE", "valor_xml": 99.0, "valor_motor": 100.0}
    with _patch_engine({"consistente": False, "divergencias": [div]}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_valor_bruto_nan() -> None:
    div = {"tipo": "ICMS_ST_DIVERGENTE", "valor_xml": float("nan"), "valor_motor": 100.0}
    with _patch_engine({"consistente": False, "divergencias": [div]}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


@pytest.mark.asyncio
async def test_failclosed_valor_bruto_infinito() -> None:
    div = {"tipo": "ICMS_ST_DIVERGENTE", "valor_xml": float("inf"), "valor_motor": 100.0}
    with _patch_engine({"consistente": False, "divergencias": [div]}):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"


# ---------------------------------------------------------------------------
# 18.6 Payload
# ---------------------------------------------------------------------------

def test_payload_strict_types() -> None:
    ctx = _ctx(icms_st_xml=1.0, icms_st_motor=1.0)
    payload = construir_payload_consistency_audit(ctx)
    assert type(payload.dados_coerentes) is bool
    assert type(payload.total_alertas) is int


def test_payload_rejects_non_strict_bool() -> None:
    base = {
        "analysis_type": "auditoria_consistencia_fiscal",
        "schema_type": "ConsistencyAuditPayload",
        "versao": "1.0",
        "empresa_id": EMPRESA_ID,
        "documento_id": DOCUMENTO_ID,
        "dados_coerentes": True,
        "total_alertas": 0,
        "alertas": (),
        "publication_allowed": False,
    }
    bad_bool = dict(base)
    bad_bool["dados_coerentes"] = 1
    with pytest.raises(ValidationError):
        ConsistencyAuditPayload.model_validate(bad_bool)


@pytest.mark.parametrize("bad_total", [True, "0", 0.0])
def test_payload_rejects_non_strict_total(bad_total: object) -> None:
    base = {
        "analysis_type": "auditoria_consistencia_fiscal",
        "schema_type": "ConsistencyAuditPayload",
        "versao": "1.0",
        "empresa_id": EMPRESA_ID,
        "documento_id": DOCUMENTO_ID,
        "dados_coerentes": True,
        "total_alertas": bad_total,
        "alertas": (),
        "publication_allowed": False,
    }
    with pytest.raises(ValidationError):
        ConsistencyAuditPayload.model_validate(base)


@pytest.mark.parametrize(
    "bad_id",
    [True, False, "7", 7.0, 0, -1],
)
def test_payload_rejects_invalid_empresa_id(bad_id: object) -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditPayload(
            empresa_id=bad_id,
            documento_id=DOCUMENTO_ID,
            dados_coerentes=True,
            total_alertas=0,
            alertas=(),
        )


@pytest.mark.parametrize(
    "bad_id",
    [True, False, "101", 101.0, 0, -1],
)
def test_payload_rejects_invalid_documento_id(bad_id: object) -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditPayload(
            empresa_id=EMPRESA_ID,
            documento_id=bad_id,
            dados_coerentes=True,
            total_alertas=0,
            alertas=(),
        )


def test_payload_rejects_negative_total() -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditPayload(
            empresa_id=EMPRESA_ID,
            documento_id=DOCUMENTO_ID,
            dados_coerentes=True,
            total_alertas=-1,
            alertas=(),
        )


def test_payload_rejects_total_mismatch() -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditPayload(
            empresa_id=EMPRESA_ID,
            documento_id=DOCUMENTO_ID,
            dados_coerentes=False,
            total_alertas=2,
            alertas=(),
        )


def test_payload_rejects_duplicate_codes() -> None:
    alert = ConsistencyAuditAlert(
        codigo="ICMS_ST_DIVERGENTE",
        severidade="alto",
        mensagem=ALERTAS_CONSISTENCY_CANONICOS["ICMS_ST_DIVERGENTE"][1],
    )
    with pytest.raises(ValidationError):
        ConsistencyAuditPayload(
            empresa_id=EMPRESA_ID,
            documento_id=DOCUMENTO_ID,
            dados_coerentes=False,
            total_alertas=2,
            alertas=(alert, alert),
        )


def test_payload_rejects_wrong_order() -> None:
    mva = ConsistencyAuditAlert(
        codigo="MVA_DIVERGENTE",
        severidade="alto",
        mensagem=ALERTAS_CONSISTENCY_CANONICOS["MVA_DIVERGENTE"][1],
    )
    icms = ConsistencyAuditAlert(
        codigo="ICMS_ST_DIVERGENTE",
        severidade="alto",
        mensagem=ALERTAS_CONSISTENCY_CANONICOS["ICMS_ST_DIVERGENTE"][1],
    )
    with pytest.raises(ValidationError):
        ConsistencyAuditPayload(
            empresa_id=EMPRESA_ID,
            documento_id=DOCUMENTO_ID,
            dados_coerentes=False,
            total_alertas=2,
            alertas=(mva, icms),
        )


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("analysis_type",     "outro"),
        ("schema_type",       "Outro"),
        ("versao",            "9.0"),
        ("empresa_id",        EMPRESA_ID + 1),
        ("documento_id",      DOCUMENTO_ID + 1),
        ("dados_coerentes",   False),
        ("total_alertas",     1),
        ("publication_allowed", True),
    ],
)
def test_payload_tampering_detected_by_validation(
    field: str,
    bad_value: object,
) -> None:
    ctx = _ctx(icms_st_xml=1.0, icms_st_motor=1.0)
    payload = construir_payload_consistency_audit(ctx)
    altered = payload.model_copy(update={field: bad_value})
    with pytest.raises(ValueError):
        validate_consistency_audit_payload_against_context(
            context=ctx,
            payload=altered,
        )


def test_payload_alert_severidade_tampering_detected() -> None:
    delta = math.nextafter(0.01, math.inf)
    ctx = _ctx(icms_st_xml=0.0, icms_st_motor=delta)
    payload = construir_payload_consistency_audit(ctx)
    # Tentar criar alerta com severidade errada mas mesmo código
    with pytest.raises(ValidationError):
        ConsistencyAuditAlert(
            codigo="ICMS_ST_DIVERGENTE",
            severidade="medio",  # errado — tabela exige "alto"
            mensagem=ALERTAS_CONSISTENCY_CANONICOS["ICMS_ST_DIVERGENTE"][1],
        )


def test_payload_alert_mensagem_tampering_detected() -> None:
    with pytest.raises(ValidationError):
        ConsistencyAuditAlert(
            codigo="ICMS_ST_DIVERGENTE",
            severidade="alto",
            mensagem="mensagem adulterada",
        )


def test_payload_alert_tampering_detected_by_independent_validation() -> None:
    delta = math.nextafter(0.01, math.inf)
    ctx = _ctx(icms_st_xml=0.0, icms_st_motor=delta)
    payload = construir_payload_consistency_audit(ctx)
    wrong_alert = ConsistencyAuditAlert(
        codigo="MVA_DIVERGENTE",
        severidade="alto",
        mensagem=ALERTAS_CONSISTENCY_CANONICOS["MVA_DIVERGENTE"][1],
    )
    altered = payload.model_copy(update={
        "alertas": (wrong_alert,),
        "total_alertas": 1,
    })
    with pytest.raises(ValueError):
        validate_consistency_audit_payload_against_context(
            context=ctx,
            payload=altered,
        )


# ---------------------------------------------------------------------------
# 18.7 Segurança
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fiscal_values_not_in_serialized_payload() -> None:
    mission = _mission(context={
        "empresa_id": EMPRESA_ID,
        "documento_id": DOCUMENTO_ID,
        "icms_st_xml": _SENTINELA_XML,
        "icms_st_motor": _SENTINELA_MOTOR,
    })
    result = await execute_consistency_audit_mission(mission)
    assert result.status == "sucesso"
    assert result.payload["dados_coerentes"] is False
    assert result.payload["total_alertas"] == 1
    assert len(result.payload["alertas"]) == 1
    rendered = json.dumps(result.payload, ensure_ascii=False, default=str)
    assert str(_SENTINELA_XML) not in rendered
    assert str(_SENTINELA_MOTOR) not in rendered
    diferenca = abs(_SENTINELA_XML - _SENTINELA_MOTOR)
    assert str(diferenca) not in rendered


def test_alert_messages_have_no_fiscal_values() -> None:
    # Garantir divergência real: diferença entre sentinelas >> 0.01
    assert abs(_SENTINELA_XML - _SENTINELA_MOTOR) > 0.01
    ctx = _ctx(
        icms_st_xml=_SENTINELA_XML,
        icms_st_motor=_SENTINELA_MOTOR,
    )
    payload = construir_payload_consistency_audit(ctx)
    # Confirmar que há alerta
    assert len(payload.alertas) == 1
    for alert in payload.alertas:
        assert str(_SENTINELA_XML) not in alert.mensagem
        assert str(_SENTINELA_MOTOR) not in alert.mensagem
        assert "%" not in alert.mensagem
        # Verificar também a diferença calculada
        diferenca = abs(_SENTINELA_XML - _SENTINELA_MOTOR)
        assert str(diferenca) not in alert.mensagem


@pytest.mark.asyncio
async def test_execution_error_does_not_leak_secret() -> None:
    secret = "segredo-interno-fiscal-42"
    with patch(
        "app.agents.adapters.consistency_audit.construir_payload_consistency_audit",
        side_effect=RuntimeError(secret),
    ):
        result = await execute_consistency_audit_mission(_mission())
    assert result.status == "erro"
    assert result.error_code == "AG_CONSISTENCY_AUDIT_EXECUTION_ERROR"
    assert result.error_message == EXECUTION_ERROR_MESSAGE
    assert secret not in result.error_message
    assert "RuntimeError" not in result.error_message
    assert "Traceback" not in result.error_message
    assert result.payload == {}
    _assert_common_result(result)


@pytest.mark.asyncio
async def test_result_alerts_empty_on_success() -> None:
    result = await execute_consistency_audit_mission(_mission())
    assert result.status == "sucesso"
    assert result.alerts == []


@pytest.mark.asyncio
async def test_cross_validation_failure_typed() -> None:
    with patch(
        "app.agents.adapters.consistency_audit.validate_result_against_mission",
        side_effect=ValueError("interno"),
    ):
        with pytest.raises(ConsistencyAuditResultValidationError) as exc_info:
            await execute_consistency_audit_mission(_mission())
    assert exc_info.value.code == "RESULT_MISSION_VALIDATION_FAILED"
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


@pytest.mark.asyncio
async def test_sanitization_failure_typed() -> None:
    with patch(
        "app.agents.adapters.consistency_audit.assert_result_sanitized",
        side_effect=ValueError("interno"),
    ):
        with pytest.raises(ConsistencyAuditResultSafetyError) as exc_info:
            await execute_consistency_audit_mission(_mission())
    assert exc_info.value.code == "RESULT_SANITIZATION_FAILED"
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


# ---------------------------------------------------------------------------
# 18.8 Integridade estrutural
# ---------------------------------------------------------------------------

def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _imported_modules(relative_path: str) -> set[str]:
    tree = ast.parse(_source(relative_path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_legacy_agent_hash() -> None:
    path = ROOT / "app" / "agents" / "consistency_audit_agent.py"
    digest = canonical_source_sha256(path)
    assert digest == LEGACY_AGENT_SHA256


def test_legacy_engine_hash() -> None:
    path = (
        ROOT / "app" / "services" / "tax_consistency"
        / "tax_consistency_engine.py"
    )
    digest = canonical_source_sha256(path)
    assert digest == LEGACY_ENGINE_SHA256


def test_legacy_agent_has_no_run_mission() -> None:
    path = ROOT / "app" / "agents" / "consistency_audit_agent.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "run_mission" not in names


def test_contract_has_no_forbidden_imports() -> None:
    forbidden = {
        "sqlalchemy",
        "app.database",
        "app.models",
        "httpx",
        "requests",
        "os",
        "pathlib",
        "subprocess",
        "app.agents.consistency_audit_agent",
        "app.agents.agent_executor",
        "app.agents.agent_scheduler",
        "app.services",
        "app.agents.adapters",
    }
    imported = _imported_modules(
        "app/agents/contracts/consistency_audit.py"
    )
    for module in imported:
        assert not any(
            module == item or module.startswith(f"{item}.")
            for item in forbidden
        ), f"contrato importa módulo proibido: {module}"


def test_adapter_does_not_import_tax_consistency_engine() -> None:
    imported = _imported_modules(
        "app/agents/adapters/consistency_audit.py"
    )
    for module in imported:
        assert "tax_consistency_engine" not in module, (
            f"adapter importa módulo proibido: {module}"
        )


def test_adapter_does_not_import_legacy_agent() -> None:
    imported = _imported_modules(
        "app/agents/adapters/consistency_audit.py"
    )
    for module in imported:
        assert "consistency_audit_agent" not in module or (
            "contracts" in module or "engines" in module
        ), f"adapter importa agente legado: {module}"


def test_adapter_does_not_reference_or_instantiate_legacy_agent() -> None:
    tree = ast.parse(_source("app/agents/adapters/consistency_audit.py"))
    referenced = {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }
    referenced.update(
        node.attr for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    )
    assert "ConsistencyAuditAgent" not in referenced


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/agents/adapters/consistency_audit.py",
        "app/agents/engines/consistency_audit.py",
    ],
)
def test_adapter_and_engine_have_no_forbidden_infrastructure_imports(
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
    }
    for module in _imported_modules(relative_path):
        assert not any(
            module == item or module.startswith(f"{item}.")
            for item in forbidden
        ), f"{relative_path} importa módulo proibido: {module}"


def test_only_engine_imports_tax_consistency_engine() -> None:
    engine_imports = _imported_modules(
        "app/agents/engines/consistency_audit.py"
    )
    assert any(
        "tax_consistency_engine" in m for m in engine_imports
    )


def test_engine_layers_have_no_persistence_calls() -> None:
    forbidden_calls = {
        "open", "write", "write_text", "write_bytes",
        "add_all", "delete", "flush", "commit",
        "bulk_save_objects", "bulk_insert_mappings",
        "bulk_update_mappings",
    }
    for relative_path in (
        "app/agents/engines/consistency_audit.py",
        "app/agents/adapters/consistency_audit.py",
    ):
        tree = ast.parse(_source(relative_path))
        used: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                used.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                used.add(node.func.attr)
        assert used.isdisjoint(forbidden_calls), (
            f"{relative_path} contém chamada proibida: "
            f"{used & forbidden_calls}"
        )


def test_no_exception_is_stringified_in_adapter_or_engine() -> None:
    for relative_path in (
        "app/agents/engines/consistency_audit.py",
        "app/agents/adapters/consistency_audit.py",
    ):
        tree = ast.parse(_source(relative_path))
        for handler in (
            node for node in ast.walk(tree)
            if isinstance(node, ast.ExceptHandler) and node.name
        ):
            for node in ast.walk(handler):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Name) or node.func.id != "str":
                    continue
                assert not any(
                    isinstance(argument, ast.Name)
                    and argument.id == handler.name
                    for argument in node.args
                ), f"{relative_path} expõe excepção por str()"


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/agents/agent_executor.py",
        "app/agents/agent_scheduler.py",
    ],
)
def test_runtime_components_do_not_reference_adapter(
    relative_path: str,
) -> None:
    source = _source(relative_path)
    assert "execute_consistency_audit_mission" not in source
    assert "app.agents.adapters.consistency_audit" not in source


def test_adapter_is_async() -> None:
    assert inspect.iscoroutinefunction(
        execute_consistency_audit_mission
    )


def test_engine_functions_are_synchronous() -> None:
    assert not inspect.iscoroutinefunction(
        construir_payload_consistency_audit
    )
    assert not inspect.iscoroutinefunction(
        validate_consistency_audit_payload_against_context
    )


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/agents/adapters/consistency_audit.py",
        "app/agents/engines/consistency_audit.py",
    ],
)
def test_adapter_and_engine_have_no_reader(relative_path: str) -> None:
    tree = ast.parse(_source(relative_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "reader" not in alias.name.casefold()
        elif isinstance(node, ast.ImportFrom):
            assert "reader" not in (node.module or "").casefold()
        elif isinstance(node, ast.Name):
            assert "reader" not in node.id.casefold()
        elif isinstance(node, ast.Attribute):
            assert "reader" not in node.attr.casefold()


def test_canonical_collections_are_immutable() -> None:
    assert isinstance(PARES_CANONICOS, tuple)
    assert isinstance(ORDEM_ALERTAS_CONSISTENCY, tuple)
    assert isinstance(INDICE_ALERTA_CONSISTENCY, MappingProxyType)
    assert isinstance(ALERTAS_CONSISTENCY_CANONICOS, MappingProxyType)
    with pytest.raises(TypeError):
        operator.setitem(ALERTAS_CONSISTENCY_CANONICOS, "NOVO", ("alto", "x"))


def test_no_init_py_altered_by_b14_3d() -> None:
    for init_path in (
        "app/agents/contracts/__init__.py",
        "app/agents/engines/__init__.py",
        "app/agents/adapters/__init__.py",
    ):
        source = _source(init_path)
        assert "consistency_audit" not in source, (
            f"{init_path} referencia B14.3D"
        )
