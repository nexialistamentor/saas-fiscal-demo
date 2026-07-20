"""
tests/test_memorial_validator_mission_adapter.py - ADR-013 B14.3E.

Provas contratuais do MemorialValidatorAgent L3:
- fronteira soberana da missão;
- precedência dos bloqueios sobre o parsing do contexto;
- contrato e motor determinístico puro;
- validação independente payload-contexto;
- ausência de autoridade de publicação;
- preservação byte a byte do agente legado;
- ausência de BD, LLM, persistência e integração activa.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import operator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

import pytest
from pydantic import ValidationError

import app.agents.engines.memorial_validator as memorial_engine_module
from app.agents.adapters.memorial_validator import (
    execute_memorial_validator_mission,
)
from app.agents.contracts.memorial_validator import (
    ALERTAS_MEMORIAL_CANONICOS,
    INDICE_ALERTA_MEMORIAL,
    LIMIAR_ALERTAS_REVISAO,
    ORDEM_ALERTAS_MEMORIAL,
    MemorialEngineSnapshot,
    MemorialReferenciaSnapshot,
    MemorialRelatorioSnapshot,
    MemorialValidatorAlert,
    MemorialValidatorContext,
    MemorialValidatorPayload,
    MemorialValidatorPreExecutionError,
    MemorialValidatorResultSafetyError,
    MemorialValidatorResultValidationError,
)
from app.agents.contracts.shared import BudgetPolicy
from app.agents.engines.memorial_validator import (
    construir_payload_memorial,
    derivar_alertas_memorial,
    validate_memorial_validator_payload_against_context,
)
from app.agents.mission_factory import create_agent_mission


ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc

TENANT_ID = 42
ACTOR_ID = 99
EMPRESA_ID = 7
RELATORIO_ID = 101

CREATED_AT = datetime(
    2026,
    7,
    19,
    12,
    0,
    0,
    tzinfo=UTC,
)

LEGACY_AGENT_SHA256 = (
    "B8B5841BB5D3F85BE412421614D01212"
    "D967C298DE4F2437A39F31FA54A546A4"
)

EXECUTION_ERROR_MESSAGE = (
    "Não foi possível concluir a validação do memorial fiscal."
)


def _contexto_nominal() -> dict:
    return {
        "empresa_id": EMPRESA_ID,
        "relatorio_id": RELATORIO_ID,
        "relatorio": {
            "id": RELATORIO_ID,
            "empresa_id": EMPRESA_ID,
            "status": "concluido",
            "total_alertas": 0,
        },
        "engines": [
            {
                "engine_nome": "regime_engine",
            }
        ],
        "referencias_legais": [
            {
                "fundamento": "Fundamento normativo válido.",
            }
        ],
    }


def _mission(
    *,
    context: object | None = None,
    execution_mode: str = "sombra",
    requested_by: str = "user",
    agent_version_required: str | None = None,
    source_request_id: object = "req-memorial-001",
    reference_at: datetime | None = None,
    tenant_id: object = TENANT_ID,
    actor_id: object = ACTOR_ID,
    entity_id: object = RELATORIO_ID,
    entity_type: str = "relatorio_analise",
    **overrides,
):
    kwargs: dict = {
        "mission_type": "validar_memorial_fiscal",
        "target_agent": "memorial_validator_agent",
        "context": (
            context
            if context is not None
            else _contexto_nominal()
        ),
        "context_schema": "memorial_validator.context",
        "context_version": "1.0",
        "output_schema": "memorial_validator.result",
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
    **overrides,
) -> MemorialValidatorContext:
    context = _contexto_nominal()
    context.update(overrides)

    return MemorialValidatorContext.model_validate(context)


def _assert_common_result(result) -> None:
    assert result.attempt == 1
    assert result.agent_id == "memorial_validator_agent"
    assert result.agent_version == "1.0"
    assert result.mission_type == "validar_memorial_fiscal"
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
    assert result.payload_schema == "memorial_validator.result"
    assert result.payload_version == "1.0"
    assert result.started_at.utcoffset() == timedelta(0)
    assert result.finished_at.utcoffset() == timedelta(0)
    assert result.finished_at >= result.started_at
    assert type(result.duration_ms) is int
    assert result.duration_ms >= 0

# ---------------------------------------------------------------------------
# 18.1 Execução nominal e precedência dos bloqueios
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sombra", "dry_run"])
async def test_nominal_modes_succeed(mode: str) -> None:
    result = await execute_memorial_validator_mission(
        _mission(execution_mode=mode)
    )

    assert result.status == "sucesso"
    assert result.mode == mode
    assert result.error_code is None
    assert result.error_message is None
    assert result.alerts == []
    assert result.payload["diagnostico_consistente"] is True
    assert result.payload["total_alertas"] == 0
    assert result.payload["publication_allowed"] is False
    _assert_common_result(result)


@pytest.mark.asyncio
async def test_actor_id_may_differ_from_tenant_id() -> None:
    result = await execute_memorial_validator_mission(
        _mission(
            tenant_id=TENANT_ID,
            actor_id=ACTOR_ID,
        )
    )

    assert result.status == "sucesso"


@pytest.mark.asyncio
@pytest.mark.parametrize("requested_by", ["user", "system"])
async def test_requested_by_user_and_system_accepted(
    requested_by: str,
) -> None:
    result = await execute_memorial_validator_mission(
        _mission(requested_by=requested_by)
    )

    assert result.status == "sucesso"


@pytest.mark.asyncio
async def test_reference_at_none_accepted() -> None:
    result = await execute_memorial_validator_mission(
        _mission(reference_at=None)
    )

    assert result.status == "sucesso"


@pytest.mark.asyncio
async def test_active_mode_blocked() -> None:
    result = await execute_memorial_validator_mission(
        _mission(execution_mode="activo")
    )

    assert result.status == "bloqueado"
    assert result.payload == {}
    assert result.error_code is None
    assert result.error_message is None
    assert len(result.alerts) == 1
    assert (
        result.alerts[0].code
        == "EXECUTION_MODE_NOT_AUTHORIZED"
    )
    _assert_common_result(result)


@pytest.mark.asyncio
async def test_incompatible_version_precedes_active_mode() -> None:
    result = await execute_memorial_validator_mission(
        _mission(
            execution_mode="activo",
            agent_version_required="9.0",
        )
    )

    assert result.status == "bloqueado"
    assert len(result.alerts) == 1
    assert (
        result.alerts[0].code
        == "AGENT_VERSION_INCOMPATIBLE"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("required", [None, "1.0"])
async def test_compatible_version_executes(
    required: str | None,
) -> None:
    result = await execute_memorial_validator_mission(
        _mission(agent_version_required=required)
    )

    assert result.status == "sucesso"


@pytest.mark.asyncio
async def test_active_mode_does_not_parse_invalid_context() -> None:
    mission = _mission(
        execution_mode="activo"
    ).model_copy(
        update={
            "context": {
                "segredo_interno": object(),
            }
        }
    )

    result = await execute_memorial_validator_mission(mission)

    assert result.status == "bloqueado"
    assert (
        result.alerts[0].code
        == "EXECUTION_MODE_NOT_AUTHORIZED"
    )
    assert result.payload == {}


@pytest.mark.asyncio
async def test_incompatible_version_does_not_parse_invalid_context() -> None:
    mission = _mission(
        agent_version_required="9.0"
    ).model_copy(
        update={
            "context": {
                "segredo_interno": object(),
            }
        }
    )

    result = await execute_memorial_validator_mission(mission)

    assert result.status == "bloqueado"
    assert (
        result.alerts[0].code
        == "AGENT_VERSION_INCOMPATIBLE"
    )
    assert result.payload == {}

# ---------------------------------------------------------------------------
# 18.2 Fronteira soberana da missão
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        (
            "target_agent",
            "outro",
            "MISSION_TARGET_MISMATCH",
        ),
        (
            "mission_type",
            "outro",
            "MISSION_TYPE_UNSUPPORTED",
        ),
        (
            "context_schema",
            "outro",
            "CONTEXT_SCHEMA_UNSUPPORTED",
        ),
        (
            "context_version",
            "9.0",
            "CONTEXT_VERSION_UNSUPPORTED",
        ),
        (
            "output_schema",
            "outro",
            "OUTPUT_SCHEMA_UNSUPPORTED",
        ),
        (
            "output_version",
            "9.0",
            "OUTPUT_VERSION_UNSUPPORTED",
        ),
        (
            "scope",
            "tenant",
            "MISSION_SCOPE_UNSUPPORTED",
        ),
        (
            "tenant_id",
            None,
            "MISSION_TENANT_REQUIRED",
        ),
        (
            "tenant_id",
            True,
            "MISSION_TENANT_UNSUPPORTED",
        ),
        (
            "tenant_id",
            0,
            "MISSION_TENANT_UNSUPPORTED",
        ),
        (
            "tenant_id",
            -1,
            "MISSION_TENANT_UNSUPPORTED",
        ),
        (
            "tenant_id",
            "42",
            "MISSION_TENANT_UNSUPPORTED",
        ),
        (
            "tenant_id",
            42.0,
            "MISSION_TENANT_UNSUPPORTED",
        ),
        (
            "actor_id",
            None,
            "MISSION_ACTOR_UNSUPPORTED",
        ),
        (
            "actor_id",
            True,
            "MISSION_ACTOR_UNSUPPORTED",
        ),
        (
            "actor_id",
            0,
            "MISSION_ACTOR_UNSUPPORTED",
        ),
        (
            "actor_id",
            -1,
            "MISSION_ACTOR_UNSUPPORTED",
        ),
        (
            "actor_id",
            "99",
            "MISSION_ACTOR_UNSUPPORTED",
        ),
        (
            "actor_id",
            99.0,
            "MISSION_ACTOR_UNSUPPORTED",
        ),
        (
            "entity_type",
            "empresa",
            "MISSION_ENTITY_UNSUPPORTED",
        ),
        (
            "entity_id",
            None,
            "MISSION_ENTITY_UNSUPPORTED",
        ),
        (
            "entity_id",
            True,
            "MISSION_ENTITY_UNSUPPORTED",
        ),
        (
            "entity_id",
            0,
            "MISSION_ENTITY_UNSUPPORTED",
        ),
        (
            "entity_id",
            -1,
            "MISSION_ENTITY_UNSUPPORTED",
        ),
        (
            "entity_id",
            "101",
            "MISSION_ENTITY_UNSUPPORTED",
        ),
        (
            "entity_id",
            101.0,
            "MISSION_ENTITY_UNSUPPORTED",
        ),
        (
            "requested_by",
            "admin",
            "MISSION_REQUESTED_BY_UNSUPPORTED",
        ),
        (
            "authority_level",
            "proposta",
            "MISSION_AUTHORITY_UNSUPPORTED",
        ),
        (
            "source_request_id",
            None,
            "MISSION_ORIGIN_UNSUPPORTED",
        ),
        (
            "source_request_id",
            123,
            "MISSION_ORIGIN_UNSUPPORTED",
        ),
        (
            "source_request_id",
            "   ",
            "MISSION_ORIGIN_UNSUPPORTED",
        ),
    ],
)
async def test_mission_boundary_rejects_invalid_values(
    field: str,
    value: object,
    expected_code: str,
) -> None:
    mission = _mission().model_copy(
        update={
            field: value,
        }
    )

    with pytest.raises(
        MemorialValidatorPreExecutionError
    ) as exc_info:
        await execute_memorial_validator_mission(mission)

    assert exc_info.value.code == expected_code
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


@pytest.mark.asyncio
async def test_entity_id_must_match_context_relatorio_id() -> None:
    mission = _mission().model_copy(
        update={
            "entity_id": RELATORIO_ID + 1,
        }
    )

    with pytest.raises(
        MemorialValidatorPreExecutionError
    ) as exc_info:
        await execute_memorial_validator_mission(mission)

    assert (
        exc_info.value.code
        == "MISSION_ENTITY_UNSUPPORTED"
    )


@pytest.mark.asyncio
async def test_source_event_id_rejected() -> None:
    base = _mission()
    mission = base.model_copy(
        update={
            "source_event_id": base.mission_id,
        }
    )

    with pytest.raises(
        MemorialValidatorPreExecutionError
    ) as exc_info:
        await execute_memorial_validator_mission(mission)

    assert (
        exc_info.value.code
        == "MISSION_ORIGIN_UNSUPPORTED"
    )


@pytest.mark.asyncio
async def test_schedule_slot_rejected() -> None:
    mission = _mission().model_copy(
        update={
            "schedule_slot": "2026-07-19T12:00:00Z",
        }
    )

    with pytest.raises(
        MemorialValidatorPreExecutionError
    ) as exc_info:
        await execute_memorial_validator_mission(mission)

    assert (
        exc_info.value.code
        == "MISSION_ORIGIN_UNSUPPORTED"
    )


@pytest.mark.asyncio
async def test_budget_must_be_default() -> None:
    mission = _mission().model_copy(
        update={
            "budget_policy": BudgetPolicy(
                allow_llm=True,
                allowed_providers=["local_model"],
                max_calls=1,
                max_input_chars=1,
                max_output_tokens=1,
            ),
        }
    )

    with pytest.raises(
        MemorialValidatorPreExecutionError
    ) as exc_info:
        await execute_memorial_validator_mission(mission)

    assert (
        exc_info.value.code
        == "MISSION_BUDGET_UNSUPPORTED"
    )


@pytest.mark.asyncio
async def test_sources_must_be_empty() -> None:
    mission = _mission().model_copy(
        update={
            "sources": [object()],
        }
    )

    with pytest.raises(
        MemorialValidatorPreExecutionError
    ) as exc_info:
        await execute_memorial_validator_mission(mission)

    assert (
        exc_info.value.code
        == "MISSION_SOURCES_UNSUPPORTED"
    )

# ---------------------------------------------------------------------------
# 18.3 Contrato do contexto
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad_id",
    [True, False, "7", 7.0, 0, -1],
)
def test_context_rejects_invalid_empresa_id(
    bad_id: object,
) -> None:
    data = _contexto_nominal()
    data["empresa_id"] = bad_id

    with pytest.raises(ValidationError):
        MemorialValidatorContext.model_validate(data)


@pytest.mark.parametrize(
    "bad_id",
    [True, False, "101", 101.0, 0, -1],
)
def test_context_rejects_invalid_relatorio_id(
    bad_id: object,
) -> None:
    data = _contexto_nominal()
    data["relatorio_id"] = bad_id

    with pytest.raises(ValidationError):
        MemorialValidatorContext.model_validate(data)


def test_context_requires_engines_field() -> None:
    data = _contexto_nominal()
    data.pop("engines")

    with pytest.raises(ValidationError):
        MemorialValidatorContext.model_validate(data)


def test_context_requires_referencias_legais_field() -> None:
    data = _contexto_nominal()
    data.pop("referencias_legais")

    with pytest.raises(ValidationError):
        MemorialValidatorContext.model_validate(data)


def test_context_accepts_empty_required_collections() -> None:
    context = _ctx(
        engines=[],
        referencias_legais=[],
    )

    assert context.engines == ()
    assert context.referencias_legais == ()


def test_context_accepts_absent_relatorio() -> None:
    context = _ctx(relatorio=None)

    assert context.relatorio is None


def test_context_rejects_relatorio_id_mismatch() -> None:
    data = _contexto_nominal()
    data["relatorio"]["id"] = RELATORIO_ID + 1

    with pytest.raises(ValidationError):
        MemorialValidatorContext.model_validate(data)


def test_context_rejects_relatorio_empresa_mismatch() -> None:
    data = _contexto_nominal()
    data["relatorio"]["empresa_id"] = EMPRESA_ID + 1

    with pytest.raises(ValidationError):
        MemorialValidatorContext.model_validate(data)


@pytest.mark.parametrize(
    "bad_status",
    ["", "   ", 1, True, None],
)
def test_relatorio_rejects_invalid_status(
    bad_status: object,
) -> None:
    data = _contexto_nominal()
    data["relatorio"]["status"] = bad_status

    with pytest.raises(ValidationError):
        MemorialValidatorContext.model_validate(data)


@pytest.mark.parametrize(
    "bad_total",
    [True, False, "0", 0.0, -1],
)
def test_relatorio_rejects_invalid_total_alertas(
    bad_total: object,
) -> None:
    data = _contexto_nominal()
    data["relatorio"]["total_alertas"] = bad_total

    with pytest.raises(ValidationError):
        MemorialValidatorContext.model_validate(data)


@pytest.mark.parametrize(
    "bad_name",
    ["", "   ", 1, True, None],
)
def test_engine_rejects_invalid_name(
    bad_name: object,
) -> None:
    data = _contexto_nominal()
    data["engines"] = [
        {
            "engine_nome": bad_name,
        }
    ]

    with pytest.raises(ValidationError):
        MemorialValidatorContext.model_validate(data)


@pytest.mark.parametrize(
    "fundamento",
    [None, "", "   ", "Fundamento válido."],
)
def test_referencia_accepts_supported_fundamento_values(
    fundamento: str | None,
) -> None:
    data = _contexto_nominal()
    data["referencias_legais"] = [
        {
            "fundamento": fundamento,
        }
    ]

    context = MemorialValidatorContext.model_validate(data)

    assert (
        context.referencias_legais[0].fundamento
        == fundamento
    )


@pytest.mark.parametrize(
    "bad_fundamento",
    [1, True, b"texto", [], {}],
)
def test_referencia_rejects_non_string_fundamento(
    bad_fundamento: object,
) -> None:
    data = _contexto_nominal()
    data["referencias_legais"] = [
        {
            "fundamento": bad_fundamento,
        }
    ]

    with pytest.raises(ValidationError):
        MemorialValidatorContext.model_validate(data)


def test_context_forbids_extra_fields() -> None:
    data = _contexto_nominal()
    data["campo_extra"] = "proibido"

    with pytest.raises(ValidationError):
        MemorialValidatorContext.model_validate(data)


def test_context_is_frozen() -> None:
    context = _ctx()

    with pytest.raises(ValidationError):
        setattr(context, "empresa_id", EMPRESA_ID + 1)

# ---------------------------------------------------------------------------
# 18.4 Derivação determinística dos alertas
# ---------------------------------------------------------------------------

def _codigos(
    context: MemorialValidatorContext,
) -> tuple[str, ...]:
    return tuple(
        alerta.codigo
        for alerta in derivar_alertas_memorial(context)
    )


def test_nominal_context_has_no_alerts() -> None:
    context = _ctx()

    assert derivar_alertas_memorial(context) == ()


def test_absent_report_does_not_short_circuit_other_checks() -> None:
    context = _ctx(
        relatorio=None,
        engines=[],
        referencias_legais=[],
    )

    assert _codigos(context) == (
        "MEMORIAL_RELATORIO_AUSENTE",
        "MEMORIAL_ENGINES_VAZIOS",
        "MEMORIAL_REFERENCIAS_VAZIAS",
    )


def test_empty_engines_produces_canonical_alert() -> None:
    context = _ctx(engines=[])

    assert _codigos(context) == (
        "MEMORIAL_ENGINES_VAZIOS",
    )


def test_empty_references_produces_only_empty_alert() -> None:
    context = _ctx(referencias_legais=[])

    assert _codigos(context) == (
        "MEMORIAL_REFERENCIAS_VAZIAS",
    )


@pytest.mark.parametrize(
    "fundamento",
    [None, "", "   ", "\t\n"],
)
def test_incomplete_reference_produces_single_alert(
    fundamento: str | None,
) -> None:
    context = _ctx(
        referencias_legais=[
            {"fundamento": fundamento},
            {"fundamento": fundamento},
        ]
    )

    assert _codigos(context) == (
        "MEMORIAL_REFERENCIA_INCOMPLETA",
    )


def test_reference_with_surrounding_whitespace_is_complete() -> None:
    context = _ctx(
        referencias_legais=[
            {
                "fundamento": "  fundamento válido  ",
            }
        ]
    )

    assert _codigos(context) == ()


@pytest.mark.parametrize(
    "status",
    ["Erro", "ERRO", " erro", "erro "],
)
def test_status_check_is_exact(
    status: str,
) -> None:
    relatorio = _contexto_nominal()["relatorio"]
    relatorio["status"] = status
    context = _ctx(relatorio=relatorio)

    assert (
        "MEMORIAL_STATUS_ANALISE"
        not in _codigos(context)
    )


def test_exact_error_status_produces_alert() -> None:
    relatorio = _contexto_nominal()["relatorio"]
    relatorio["status"] = "erro"
    context = _ctx(relatorio=relatorio)

    assert _codigos(context) == (
        "MEMORIAL_STATUS_ANALISE",
    )


@pytest.mark.parametrize(
    "total_alertas",
    [0, 1, LIMIAR_ALERTAS_REVISAO],
)
def test_alert_threshold_is_exclusive(
    total_alertas: int,
) -> None:
    relatorio = _contexto_nominal()["relatorio"]
    relatorio["total_alertas"] = total_alertas
    context = _ctx(relatorio=relatorio)

    assert (
        "MEMORIAL_CONTAGEM_ALERTAS"
        not in _codigos(context)
    )


def test_alert_count_above_threshold_produces_alert() -> None:
    relatorio = _contexto_nominal()["relatorio"]
    relatorio["total_alertas"] = LIMIAR_ALERTAS_REVISAO + 1
    context = _ctx(relatorio=relatorio)

    assert _codigos(context) == (
        "MEMORIAL_CONTAGEM_ALERTAS",
    )


def test_all_six_alerts_follow_canonical_order() -> None:
    relatorio = _contexto_nominal()["relatorio"]
    relatorio["status"] = "erro"
    relatorio["total_alertas"] = LIMIAR_ALERTAS_REVISAO + 1

    context = _ctx(
        relatorio=relatorio,
        engines=[],
        referencias_legais=[
            {
                "fundamento": "   ",
            }
        ],
    )

    codigos = (
        "MEMORIAL_ENGINES_VAZIOS",
        "MEMORIAL_REFERENCIA_INCOMPLETA",
        "MEMORIAL_STATUS_ANALISE",
        "MEMORIAL_CONTAGEM_ALERTAS",
    )

    assert _codigos(context) == codigos


def test_canonical_alert_fields_are_exact() -> None:
    relatorio = _contexto_nominal()["relatorio"]
    relatorio["status"] = "erro"
    context = _ctx(relatorio=relatorio)

    alerta = derivar_alertas_memorial(context)[0]
    severidade, mensagem = ALERTAS_MEMORIAL_CANONICOS[
        "MEMORIAL_STATUS_ANALISE"
    ]

    assert alerta.severidade == severidade
    assert alerta.mensagem == mensagem

# ---------------------------------------------------------------------------
# 18.5 Payload e validação independente
# ---------------------------------------------------------------------------

def test_payload_nominal_fields() -> None:
    payload = construir_payload_memorial(_ctx())

    assert payload.analysis_type == "validacao_memorial_fiscal"
    assert payload.schema_type == "MemorialValidatorPayload"
    assert payload.versao == "1.0"
    assert payload.empresa_id == EMPRESA_ID
    assert payload.relatorio_id == RELATORIO_ID
    assert payload.diagnostico_consistente is True
    assert payload.total_alertas == 0
    assert payload.alertas == ()
    assert payload.publication_allowed is False


def test_payload_does_not_expose_legacy_authority_fields() -> None:
    rendered = construir_payload_memorial(
        _ctx()
    ).model_dump(mode="python")

    assert "pode_exportar" not in rendered
    assert "memorial_validado" not in rendered
    assert rendered["publication_allowed"] is False


@pytest.mark.parametrize(
    "bad_id",
    [True, False, "7", 7.0, 0, -1],
)
def test_payload_rejects_invalid_empresa_id(
    bad_id: object,
) -> None:
    with pytest.raises(ValidationError):
        MemorialValidatorPayload(
            empresa_id=bad_id,
            relatorio_id=RELATORIO_ID,
            diagnostico_consistente=True,
            total_alertas=0,
            alertas=(),
        )


@pytest.mark.parametrize(
    "bad_id",
    [True, False, "101", 101.0, 0, -1],
)
def test_payload_rejects_invalid_relatorio_id(
    bad_id: object,
) -> None:
    with pytest.raises(ValidationError):
        MemorialValidatorPayload(
            empresa_id=EMPRESA_ID,
            relatorio_id=bad_id,
            diagnostico_consistente=True,
            total_alertas=0,
            alertas=(),
        )


@pytest.mark.parametrize(
    "bad_bool",
    [1, 0, "true", None],
)
def test_payload_rejects_non_strict_diagnostico(
    bad_bool: object,
) -> None:
    with pytest.raises(ValidationError):
        MemorialValidatorPayload(
            empresa_id=EMPRESA_ID,
            relatorio_id=RELATORIO_ID,
            diagnostico_consistente=bad_bool,
            total_alertas=0,
            alertas=(),
        )


@pytest.mark.parametrize(
    "bad_total",
    [True, False, "0", 0.0, -1],
)
def test_payload_rejects_invalid_total_alertas(
    bad_total: object,
) -> None:
    with pytest.raises(ValidationError):
        MemorialValidatorPayload(
            empresa_id=EMPRESA_ID,
            relatorio_id=RELATORIO_ID,
            diagnostico_consistente=True,
            total_alertas=bad_total,
            alertas=(),
        )


def test_payload_rejects_total_mismatch() -> None:
    with pytest.raises(ValidationError):
        MemorialValidatorPayload(
            empresa_id=EMPRESA_ID,
            relatorio_id=RELATORIO_ID,
            diagnostico_consistente=False,
            total_alertas=2,
            alertas=(),
        )


def test_payload_rejects_diagnostico_mismatch() -> None:
    alerta = MemorialValidatorAlert(
        codigo="MEMORIAL_ENGINES_VAZIOS",
        severidade="alto",
        mensagem=ALERTAS_MEMORIAL_CANONICOS[
            "MEMORIAL_ENGINES_VAZIOS"
        ][1],
    )

    with pytest.raises(ValidationError):
        MemorialValidatorPayload(
            empresa_id=EMPRESA_ID,
            relatorio_id=RELATORIO_ID,
            diagnostico_consistente=True,
            total_alertas=1,
            alertas=(alerta,),
        )


def test_payload_rejects_duplicate_alert_codes() -> None:
    alerta = MemorialValidatorAlert(
        codigo="MEMORIAL_ENGINES_VAZIOS",
        severidade="alto",
        mensagem=ALERTAS_MEMORIAL_CANONICOS[
            "MEMORIAL_ENGINES_VAZIOS"
        ][1],
    )

    with pytest.raises(ValidationError):
        MemorialValidatorPayload(
            empresa_id=EMPRESA_ID,
            relatorio_id=RELATORIO_ID,
            diagnostico_consistente=False,
            total_alertas=2,
            alertas=(alerta, alerta),
        )


def test_payload_rejects_alerts_out_of_canonical_order() -> None:
    referencia = MemorialValidatorAlert(
        codigo="MEMORIAL_REFERENCIA_INCOMPLETA",
        severidade="medio",
        mensagem=ALERTAS_MEMORIAL_CANONICOS[
            "MEMORIAL_REFERENCIA_INCOMPLETA"
        ][1],
    )
    engines = MemorialValidatorAlert(
        codigo="MEMORIAL_ENGINES_VAZIOS",
        severidade="alto",
        mensagem=ALERTAS_MEMORIAL_CANONICOS[
            "MEMORIAL_ENGINES_VAZIOS"
        ][1],
    )

    with pytest.raises(ValidationError):
        MemorialValidatorPayload(
            empresa_id=EMPRESA_ID,
            relatorio_id=RELATORIO_ID,
            diagnostico_consistente=False,
            total_alertas=2,
            alertas=(referencia, engines),
        )


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("analysis_type", "outro"),
        ("schema_type", "OutroPayload"),
        ("versao", "9.0"),
        ("empresa_id", EMPRESA_ID + 1),
        ("relatorio_id", RELATORIO_ID + 1),
        ("diagnostico_consistente", False),
        ("total_alertas", 1),
        ("publication_allowed", True),
    ],
)
def test_independent_validation_detects_payload_tampering(
    field: str,
    bad_value: object,
) -> None:
    context = _ctx()
    payload = construir_payload_memorial(context)
    altered = payload.model_copy(
        update={
            field: bad_value,
        }
    )

    with pytest.raises(ValueError):
        validate_memorial_validator_payload_against_context(
            context=context,
            payload=altered,
        )


def test_independent_validation_detects_alert_tampering() -> None:
    context = _ctx(engines=[])
    payload = construir_payload_memorial(context)

    wrong_alert = MemorialValidatorAlert(
        codigo="MEMORIAL_REFERENCIAS_VAZIAS",
        severidade="alto",
        mensagem=ALERTAS_MEMORIAL_CANONICOS[
            "MEMORIAL_REFERENCIAS_VAZIAS"
        ][1],
    )

    altered = payload.model_copy(
        update={
            "alertas": (wrong_alert,),
            "total_alertas": 1,
            "diagnostico_consistente": False,
        }
    )

    with pytest.raises(ValueError):
        validate_memorial_validator_payload_against_context(
            context=context,
            payload=altered,
        )

# ---------------------------------------------------------------------------
# 18.6 Segurança e comportamento fail-closed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_context_raises_typed_preexecution_error() -> None:
    mission = _mission().model_copy(
        update={
            "context": {
                "empresa_id": EMPRESA_ID,
                "relatorio_id": RELATORIO_ID,
            }
        }
    )

    with pytest.raises(
        MemorialValidatorPreExecutionError
    ) as exc_info:
        await execute_memorial_validator_mission(mission)

    assert (
        exc_info.value.code
        == "AG_MEMORIAL_VALIDATOR_CONTEXT_INVALID"
    )
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


@pytest.mark.asyncio
async def test_execution_error_does_not_leak_secret() -> None:
    secret = "segredo-interno-memorial-42"

    with patch(
        "app.agents.adapters.memorial_validator."
        "construir_payload_memorial",
        side_effect=RuntimeError(secret),
    ):
        result = await execute_memorial_validator_mission(
            _mission()
        )

    assert result.status == "erro"
    assert (
        result.error_code
        == "AG_MEMORIAL_VALIDATOR_EXECUTION_ERROR"
    )
    assert result.error_message == EXECUTION_ERROR_MESSAGE
    assert secret not in result.error_message
    assert "RuntimeError" not in result.error_message
    assert "Traceback" not in result.error_message
    assert result.payload == {}
    assert result.alerts == []
    _assert_common_result(result)


@pytest.mark.asyncio
async def test_result_alerts_are_empty_on_success() -> None:
    result = await execute_memorial_validator_mission(
        _mission(
            context={
                **_contexto_nominal(),
                "engines": [],
            }
        )
    )

    assert result.status == "sucesso"
    assert result.alerts == []
    assert result.payload["total_alertas"] == 1
    assert (
        result.payload["alertas"][0]["codigo"]
        == "MEMORIAL_ENGINES_VAZIOS"
    )


@pytest.mark.asyncio
async def test_cross_validation_failure_is_typed() -> None:
    with patch(
        "app.agents.adapters.memorial_validator."
        "validate_result_against_mission",
        side_effect=ValueError("interno"),
    ):
        with pytest.raises(
            MemorialValidatorResultValidationError
        ) as exc_info:
            await execute_memorial_validator_mission(
                _mission()
            )

    assert (
        exc_info.value.code
        == "RESULT_MISSION_VALIDATION_FAILED"
    )
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


@pytest.mark.asyncio
async def test_sanitization_failure_is_typed() -> None:
    with patch(
        "app.agents.adapters.memorial_validator."
        "assert_result_sanitized",
        side_effect=ValueError("interno"),
    ):
        with pytest.raises(
            MemorialValidatorResultSafetyError
        ) as exc_info:
            await execute_memorial_validator_mission(
                _mission()
            )

    assert (
        exc_info.value.code
        == "RESULT_SANITIZATION_FAILED"
    )
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


@pytest.mark.asyncio
async def test_payload_does_not_expose_raw_memorial_content() -> None:
    engine_secret = "ENGINE-RAW-SECRET-83741"
    fundamento_secret = "FUNDAMENTO-RAW-SECRET-92652"

    mission = _mission(
        context={
            "empresa_id": EMPRESA_ID,
            "relatorio_id": RELATORIO_ID,
            "relatorio": {
                "id": RELATORIO_ID,
                "empresa_id": EMPRESA_ID,
                "status": "erro",
                "total_alertas": LIMIAR_ALERTAS_REVISAO + 1,
            },
            "engines": [
                {
                    "engine_nome": engine_secret,
                }
            ],
            "referencias_legais": [
                {
                    "fundamento": fundamento_secret,
                }
            ],
        }
    )

    result = await execute_memorial_validator_mission(
        mission
    )

    assert result.status == "sucesso"

    rendered = json.dumps(
        result.payload,
        ensure_ascii=False,
        default=str,
    )

    assert engine_secret not in rendered
    assert fundamento_secret not in rendered
    assert "pode_exportar" not in rendered
    assert "memorial_validado" not in rendered
    assert result.payload["publication_allowed"] is False


def test_alert_messages_contain_no_raw_values() -> None:
    relatorio = _contexto_nominal()["relatorio"]
    relatorio["status"] = "erro"
    relatorio["total_alertas"] = 987654

    context = _ctx(
        relatorio=relatorio,
        engines=[],
        referencias_legais=[
            {
                "fundamento": "   ",
            }
        ],
    )

    payload = construir_payload_memorial(context)
    rendered = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
    )

    assert "987654" not in rendered
    assert "   " not in rendered


# ---------------------------------------------------------------------------
# 18.7 Integridade estrutural
# ---------------------------------------------------------------------------

def _source(relative_path: str) -> str:
    return (
        ROOT / relative_path
    ).read_text(encoding="utf-8")


def _imported_modules(
    relative_path: str,
) -> set[str]:
    tree = ast.parse(_source(relative_path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(
                alias.name
                for alias in node.names
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
        ):
            modules.add(node.module)

    return modules


def test_legacy_agent_hash_is_preserved() -> None:
    path = (
        ROOT
        / "app"
        / "agents"
        / "memorial_validator_agent.py"
    )

    digest = hashlib.sha256(
        path.read_bytes()
    ).hexdigest().upper()

    assert digest == LEGACY_AGENT_SHA256


def test_legacy_agent_has_no_run_mission() -> None:
    path = (
        ROOT
        / "app"
        / "agents"
        / "memorial_validator_agent.py"
    )
    tree = ast.parse(
        path.read_text(encoding="utf-8")
    )

    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }

    assert "run_mission" not in names


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
        "app.agents.memorial_validator_agent",
        "app.agents.agent_registry",
        "app.agents.agent_executor",
        "app.agents.agent_scheduler",
    }

    imported = _imported_modules(
        "app/agents/contracts/memorial_validator.py"
    )

    for module in imported:
        assert not any(
            module == item
            or module.startswith(f"{item}.")
            for item in forbidden
        ), f"contrato importa módulo proibido: {module}"


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/agents/adapters/memorial_validator.py",
        "app/agents/engines/memorial_validator.py",
    ],
)
def test_adapter_and_engine_have_no_forbidden_imports(
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
    imported = _imported_modules(
        "app/agents/adapters/memorial_validator.py"
    )

    assert (
        "app.agents.memorial_validator_agent"
        not in imported
    )


def test_adapter_does_not_reference_legacy_class() -> None:
    tree = ast.parse(
        _source(
            "app/agents/adapters/memorial_validator.py"
        )
    )

    referenced = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }

    referenced.update(
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    )

    assert "MemorialValidatorAgent" not in referenced


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/agents/adapters/memorial_validator.py",
        "app/agents/engines/memorial_validator.py",
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


def test_no_exception_is_stringified() -> None:
    for relative_path in (
        "app/agents/adapters/memorial_validator.py",
        "app/agents/engines/memorial_validator.py",
    ):
        tree = ast.parse(_source(relative_path))

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
                    not isinstance(node.func, ast.Name)
                    or node.func.id != "str"
                ):
                    continue

                assert not any(
                    isinstance(argument, ast.Name)
                    and argument.id == handler.name
                    for argument in node.args
                )


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/agents/agent_registry.py",
        "app/agents/agent_executor.py",
        "app/agents/agent_scheduler.py",
    ],
)
def test_runtime_does_not_reference_adapter(
    relative_path: str,
) -> None:
    source = _source(relative_path)

    assert (
        "execute_memorial_validator_mission"
        not in source
    )
    assert (
        "app.agents.adapters.memorial_validator"
        not in source
    )


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/agents/adapters/memorial_validator.py",
        "app/agents/engines/memorial_validator.py",
    ],
)
def test_adapter_and_engine_have_no_reader(
    relative_path: str,
) -> None:
    tree = ast.parse(_source(relative_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert (
                    "reader"
                    not in alias.name.casefold()
                )
        elif isinstance(node, ast.ImportFrom):
            assert (
                "reader"
                not in (node.module or "").casefold()
            )
        elif isinstance(node, ast.Name):
            assert "reader" not in node.id.casefold()
        elif isinstance(node, ast.Attribute):
            assert "reader" not in node.attr.casefold()


def test_adapter_is_async() -> None:
    assert inspect.iscoroutinefunction(
        execute_memorial_validator_mission
    )


def test_engine_functions_are_synchronous() -> None:
    assert not inspect.iscoroutinefunction(
        construir_payload_memorial
    )
    assert not inspect.iscoroutinefunction(
        derivar_alertas_memorial
    )
    assert not inspect.iscoroutinefunction(
        validate_memorial_validator_payload_against_context
    )


def test_canonical_collections_are_immutable() -> None:
    assert isinstance(
        ORDEM_ALERTAS_MEMORIAL,
        tuple,
    )
    assert isinstance(
        INDICE_ALERTA_MEMORIAL,
        MappingProxyType,
    )
    assert isinstance(
        ALERTAS_MEMORIAL_CANONICOS,
        MappingProxyType,
    )

    with pytest.raises(TypeError):
        operator.setitem(
            ALERTAS_MEMORIAL_CANONICOS,
            "NOVO",
            ("alto", "x"),
        )


def test_no_init_py_altered_by_b14_3e() -> None:
    for init_path in (
        "app/agents/contracts/__init__.py",
        "app/agents/engines/__init__.py",
        "app/agents/adapters/__init__.py",
    ):
        source = _source(init_path)

        assert "memorial_validator" not in source, (
            f"{init_path} referencia B14.3E"
        )