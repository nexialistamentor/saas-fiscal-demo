"""
tests/test_data_sanitization_mission_adapter.py — ADR-011 B14.3C.

Provas contratuais do DataSanitizationAgent L3:

- MissionFactory e fronteira soberana do adapter;
- modos sombra/dry_run e bloqueios auditáveis;
- contrato e motor determinístico puro;
- validação independente payload-contexto;
- ausência de BD, LLM, persistência e integração activa;
- preservação byte a byte do agente legado.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.agents.adapters.data_sanitization import (
    execute_data_sanitization_mission,
)
from app.agents.contracts.data_sanitization import (
    ALERTAS_SANITIZACAO_CANONICOS,
    CAMPOS_FISCAIS_CANONICOS,
    DataSanitizacaoPreExecutionError,
    DataSanitizacaoResultSafetyError,
    DataSanitizacaoResultValidationError,
    DataSanitizationAlert,
    DataSanitizationContext,
    DataSanitizationPayload,
)
from app.agents.contracts.shared import BudgetPolicy, SourceRef
from app.agents.engines.data_sanitization import (
    construir_payload_sanitizacao,
    derivar_alertas_sanitizacao,
    validate_data_sanitization_payload_against_context,
)
from app.agents.mission_factory import create_agent_mission


ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc

TENANT_ID = 42
ACTOR_ID = 42
EMPRESA_ID = 7

CREATED_AT = datetime(
    2026,
    7,
    17,
    12,
    0,
    0,
    tzinfo=UTC,
)

LEGACY_SHA256 = (
    "F6BADD4F3F65F159453320AAA13D5ED6B41BF26394E594C76FBE593FA0BEF8EE"
)

EXECUTION_MESSAGE = (
    "Não foi possível concluir a sanitização do contexto fiscal."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mission(
    *,
    context: dict | None = None,
    execution_mode: str = "sombra",
    requested_by: str = "user",
    agent_version_required: str | None = None,
    source_request_id: str = "req-sanitizacao-001",
    reference_at: datetime | None = None,
    **overrides: object,
):
    kwargs: dict = {
        "mission_type": "sanitizar_contexto_fiscal",
        "target_agent": "data_sanitization_agent",
        "context": (
            context
            if context is not None
            else {
                "empresa_id": EMPRESA_ID,
                "faturamento": 1000,
            }
        ),
        "context_schema": "data_sanitization.context",
        "context_version": "1.0",
        "output_schema": "data_sanitization.result",
        "output_version": "1.0",
        "scope": "tenant",
        "tenant_id": TENANT_ID,
        "actor_id": ACTOR_ID,
        "entity_type": "empresa",
        "entity_id": EMPRESA_ID,
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


def _assert_common_result(result) -> None:
    assert result.attempt == 1
    assert result.agent_id == "data_sanitization_agent"
    assert result.agent_version == "1.0"
    assert result.mission_type == "sanitizar_contexto_fiscal"
    assert result.scope == "tenant"
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

    assert result.payload_schema == "data_sanitization.result"
    assert result.payload_version == "1.0"

    assert result.started_at.utcoffset() == timedelta(0)
    assert result.finished_at.utcoffset() == timedelta(0)
    assert result.finished_at >= result.started_at

    assert type(result.duration_ms) is int
    assert result.duration_ms >= 0


# ---------------------------------------------------------------------------
# Caminho nominal e modos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sombra", "dry_run"])
async def test_nominal_modes_execute_without_actions(mode: str) -> None:
    result = await execute_data_sanitization_mission(
        _mission(execution_mode=mode)
    )

    assert result.status == "sucesso"
    assert result.mode == mode
    assert result.error_code is None
    assert result.error_message is None
    assert result.alerts == []

    assert result.payload["empresa_id"] == EMPRESA_ID
    assert result.payload["contexto_valido"] is True
    assert result.payload["total_alertas"] == 0
    assert not result.payload["alertas"]
    assert result.payload["publication_allowed"] is False

    _assert_common_result(result)


@pytest.mark.asyncio
async def test_requested_by_user_and_system_are_accepted() -> None:
    for requested_by in ("user", "system"):
        result = await execute_data_sanitization_mission(
            _mission(requested_by=requested_by)
        )
        assert result.status == "sucesso"


@pytest.mark.asyncio
async def test_reference_at_is_optional() -> None:
    result = await execute_data_sanitization_mission(
        _mission(reference_at=None)
    )

    assert result.status == "sucesso"


@pytest.mark.asyncio
async def test_active_mode_is_blocked() -> None:
    result = await execute_data_sanitization_mission(
        _mission(execution_mode="activo")
    )

    assert result.status == "bloqueado"
    assert result.payload == {}
    assert result.error_code is None
    assert result.error_message is None
    assert len(result.alerts) == 1
    assert result.alerts[0].code == "EXECUTION_MODE_NOT_AUTHORIZED"
    assert result.actions_executed == []

    _assert_common_result(result)


@pytest.mark.asyncio
async def test_version_is_checked_before_active_mode() -> None:
    result = await execute_data_sanitization_mission(
        _mission(
            execution_mode="activo",
            agent_version_required="9.0",
        )
    )

    assert result.status == "bloqueado"
    assert len(result.alerts) == 1
    assert result.alerts[0].code == "AGENT_VERSION_INCOMPATIBLE"


# ---------------------------------------------------------------------------
# Fronteira da missão
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field_name", "bad_value", "expected_code"),
    [
        ("target_agent", "outro", "MISSION_TARGET_MISMATCH"),
        ("mission_type", "outra", "MISSION_TYPE_UNSUPPORTED"),
        ("context_schema", "outro", "CONTEXT_SCHEMA_UNSUPPORTED"),
        ("context_version", "9.0", "CONTEXT_VERSION_UNSUPPORTED"),
        ("output_schema", "outro", "OUTPUT_SCHEMA_UNSUPPORTED"),
        ("output_version", "9.0", "OUTPUT_VERSION_UNSUPPORTED"),
        ("scope", "global", "MISSION_SCOPE_UNSUPPORTED"),
        ("tenant_id", None, "MISSION_TENANT_REQUIRED"),
        ("tenant_id", True, "MISSION_TENANT_UNSUPPORTED"),
        ("tenant_id", 0, "MISSION_TENANT_UNSUPPORTED"),
        ("actor_id", True, "MISSION_ACTOR_UNSUPPORTED"),
        ("actor_id", 0, "MISSION_ACTOR_UNSUPPORTED"),
        (
            "actor_id",
            TENANT_ID + 1,
            "MISSION_ACTOR_TENANT_MISMATCH",
        ),
        ("entity_type", "documento", "MISSION_ENTITY_UNSUPPORTED"),
        ("entity_id", True, "MISSION_ENTITY_UNSUPPORTED"),
        ("entity_id", 0, "MISSION_ENTITY_UNSUPPORTED"),
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
        ("source_request_id", " ", "MISSION_ORIGIN_UNSUPPORTED"),
    ],
)
async def test_mission_boundary_rejects_invalid_values(
    field_name: str,
    bad_value: object,
    expected_code: str,
) -> None:
    mission = _mission().model_copy(
        update={field_name: bad_value}
    )

    with pytest.raises(
        DataSanitizacaoPreExecutionError
    ) as exc_info:
        await execute_data_sanitization_mission(mission)

    assert exc_info.value.code == expected_code
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


@pytest.mark.asyncio
async def test_entity_id_must_match_context_empresa_id() -> None:
    mission = _mission().model_copy(
        update={"entity_id": EMPRESA_ID + 1}
    )

    with pytest.raises(
        DataSanitizacaoPreExecutionError
    ) as exc_info:
        await execute_data_sanitization_mission(mission)

    assert exc_info.value.code == "MISSION_ENTITY_UNSUPPORTED"


@pytest.mark.asyncio
async def test_origin_rejects_event_and_schedule() -> None:
    for update in (
        {"source_event_id": _mission().mission_id},
        {"schedule_slot": "2026-07-17T12:00:00Z"},
    ):
        mission = _mission().model_copy(update=update)

        with pytest.raises(
            DataSanitizacaoPreExecutionError
        ) as exc_info:
            await execute_data_sanitization_mission(mission)

        assert exc_info.value.code == "MISSION_ORIGIN_UNSUPPORTED"


@pytest.mark.asyncio
async def test_budget_must_be_exactly_deterministic_default() -> None:
    mission = _mission().model_copy(
        update={"budget_policy": BudgetPolicy(currency="USD")}
    )

    with pytest.raises(
        DataSanitizacaoPreExecutionError
    ) as exc_info:
        await execute_data_sanitization_mission(mission)

    assert exc_info.value.code == "MISSION_BUDGET_UNSUPPORTED"


@pytest.mark.asyncio
async def test_sources_must_be_empty() -> None:
    mission = _mission().model_copy(
        update={
            "sources": [
                SourceRef(
                    fonte_id="fonte-1",
                    uso_pretendido="validar_fato_operacional",
                )
            ]
        }
    )

    with pytest.raises(
        DataSanitizacaoPreExecutionError
    ) as exc_info:
        await execute_data_sanitization_mission(mission)

    assert exc_info.value.code == "MISSION_SOURCES_UNSUPPORTED"


@pytest.mark.asyncio
async def test_context_validation_is_typed_and_non_enumerating() -> None:
    invalid_contexts = (
        {"empresa_id": True, "faturamento": 1},
        {"empresa_id": 0, "faturamento": 1},
        {"empresa_id": EMPRESA_ID, "campo_extra": 1},
    )

    for context in invalid_contexts:
        mission = _mission(context=context)

        with pytest.raises(
            DataSanitizacaoPreExecutionError
        ) as exc_info:
            await execute_data_sanitization_mission(mission)

        assert (
            exc_info.value.code
            == "AG_DATA_SANITIZATION_CONTEXT_INVALID"
        )


# ---------------------------------------------------------------------------
# Contrato do contexto
# ---------------------------------------------------------------------------


def test_context_is_frozen_and_forbids_extra_fields() -> None:
    context = DataSanitizationContext(
        empresa_id=EMPRESA_ID,
        faturamento=1,
    )

    with pytest.raises(ValidationError):
        context.empresa_id = 99  # type: ignore[misc]

    with pytest.raises(ValidationError):
        DataSanitizationContext.model_validate(
            {
                "empresa_id": EMPRESA_ID,
                "faturamento": 1,
                "extra": 1,
            }
        )


@pytest.mark.parametrize(
    "empresa_id",
    [True, False, "7", 7.0, 0, -1],
)
def test_context_rejects_invalid_empresa_id(empresa_id: object) -> None:
    with pytest.raises(ValidationError):
        DataSanitizationContext.model_validate(
            {
                "empresa_id": empresa_id,
                "faturamento": 1,
            }
        )


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_context_rejects_non_finite_numbers(value: float) -> None:
    with pytest.raises(ValidationError):
        DataSanitizationContext(
            empresa_id=EMPRESA_ID,
            faturamento=value,
        )


def test_context_distinguishes_absent_field_from_null() -> None:
    absent = DataSanitizationContext(
        empresa_id=EMPRESA_ID
    )
    explicit_null = DataSanitizationContext(
        empresa_id=EMPRESA_ID,
        faturamento=None,
    )

    assert "faturamento" not in absent.model_fields_set
    assert "faturamento" in explicit_null.model_fields_set


# ---------------------------------------------------------------------------
# Semântica do motor
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("context", "expected_codes", "expected_valid"),
    [
        (
            DataSanitizationContext(empresa_id=EMPRESA_ID),
            ("CONTEXTO_SEM_CAMPOS_FISCAIS",),
            False,
        ),
        (
            DataSanitizationContext(
                empresa_id=EMPRESA_ID,
                faturamento=None,
            ),
            ("CAMPO_NAO_NUMERICO",),
            False,
        ),
        (
            DataSanitizationContext(
                empresa_id=EMPRESA_ID,
                faturamento="1000",
            ),
            ("CAMPO_NAO_NUMERICO",),
            False,
        ),
        (
            DataSanitizationContext(
                empresa_id=EMPRESA_ID,
                faturamento=True,
            ),
            ("CAMPO_NAO_NUMERICO",),
            False,
        ),
        (
            DataSanitizationContext(
                empresa_id=EMPRESA_ID,
                custos=-1,
            ),
            ("CAMPO_NEGATIVO",),
            False,
        ),
        (
            DataSanitizationContext(
                empresa_id=EMPRESA_ID,
                faturamento=1_000_000_000,
            ),
            (),
            True,
        ),
        (
            DataSanitizationContext(
                empresa_id=EMPRESA_ID,
                faturamento=1_000_000_001,
            ),
            ("FATURAMENTO_ACIMA_LIMITE",),
            False,
        ),
        (
            DataSanitizationContext(
                empresa_id=EMPRESA_ID,
                faturamento=0,
                custos=0.0,
            ),
            (),
            True,
        ),
    ],
)
def test_engine_matrix(
    context: DataSanitizationContext,
    expected_codes: tuple[str, ...],
    expected_valid: bool,
) -> None:
    payload = construir_payload_sanitizacao(context)

    assert tuple(
        alert.codigo for alert in payload.alertas
    ) == expected_codes
    assert payload.contexto_valido is expected_valid
    assert payload.total_alertas == len(expected_codes)

    validate_data_sanitization_payload_against_context(
        context=context,
        payload=payload,
    )


def test_engine_preserves_large_integers_without_float_conversion() -> None:
    context = DataSanitizationContext(
        empresa_id=EMPRESA_ID,
        custos=10**1000,
    )

    payload = construir_payload_sanitizacao(context)

    assert payload.contexto_valido is True
    assert payload.alertas == ()


def test_engine_alert_order_is_canonical() -> None:
    context = DataSanitizationContext(
        empresa_id=EMPRESA_ID,
        faturamento=None,
        custos=-1,
        lucro_contabil="invalido",
    )

    alerts = derivar_alertas_sanitizacao(context)

    assert tuple(
        (alert.campo, alert.codigo)
        for alert in alerts
    ) == (
        ("faturamento", "CAMPO_NAO_NUMERICO"),
        ("custos", "CAMPO_NEGATIVO"),
        ("lucro_contabil", "CAMPO_NAO_NUMERICO"),
    )


def test_payload_does_not_expose_raw_financial_values() -> None:
    secret_value = -987_654_321
    context = DataSanitizationContext(
        empresa_id=EMPRESA_ID,
        custos=secret_value,
    )

    payload = construir_payload_sanitizacao(context)
    rendered = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
    )

    assert str(secret_value) not in rendered
    assert payload.alertas[0].campo == "custos"


# ---------------------------------------------------------------------------
# Invariantes dos contratos
# ---------------------------------------------------------------------------


def test_canonical_collections_are_immutable() -> None:
    assert isinstance(CAMPOS_FISCAIS_CANONICOS, tuple)
    assert isinstance(
        ALERTAS_SANITIZACAO_CANONICOS,
        MappingProxyType,
    )

    with pytest.raises(TypeError):
        ALERTAS_SANITIZACAO_CANONICOS[
            "NOVO"
        ] = ("alto", "texto")  # type: ignore[index]


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "codigo": "CAMPO_NEGATIVO",
            "severidade": "critico",
            "campo": "custos",
            "mensagem": (
                ALERTAS_SANITIZACAO_CANONICOS[
                    "CAMPO_NEGATIVO"
                ][1]
            ),
        },
        {
            "codigo": "CAMPO_NEGATIVO",
            "severidade": "alto",
            "campo": "custos",
            "mensagem": "texto adulterado",
        },
        {
            "codigo": "FATURAMENTO_ACIMA_LIMITE",
            "severidade": "alto",
            "campo": "custos",
            "mensagem": (
                ALERTAS_SANITIZACAO_CANONICOS[
                    "FATURAMENTO_ACIMA_LIMITE"
                ][1]
            ),
        },
        {
            "codigo": "CONTEXTO_SEM_CAMPOS_FISCAIS",
            "severidade": "critico",
            "campo": "faturamento",
            "mensagem": (
                ALERTAS_SANITIZACAO_CANONICOS[
                    "CONTEXTO_SEM_CAMPOS_FISCAIS"
                ][1]
            ),
        },
    ],
)
def test_alert_contract_rejects_invalid_combinations(
    kwargs: dict,
) -> None:
    with pytest.raises(ValidationError):
        DataSanitizationAlert(**kwargs)


def test_payload_rejects_duplicate_wrong_order_and_negative_total() -> None:
    context = DataSanitizationContext(
        empresa_id=EMPRESA_ID,
        faturamento=None,
        custos=-1,
    )
    payload = construir_payload_sanitizacao(context)
    data = payload.model_dump(mode="python")

    duplicated = dict(data)
    duplicated["alertas"] = (
        payload.alertas[0],
        payload.alertas[0],
    )
    duplicated["total_alertas"] = 2

    with pytest.raises(ValidationError):
        DataSanitizationPayload.model_validate(duplicated)

    wrong_order = dict(data)
    wrong_order["alertas"] = tuple(reversed(payload.alertas))

    with pytest.raises(ValidationError):
        DataSanitizationPayload.model_validate(wrong_order)

    negative_total = dict(data)
    negative_total["total_alertas"] = -1

    with pytest.raises(ValidationError):
        DataSanitizationPayload.model_validate(negative_total)


def test_payload_rejects_non_strict_boolean_and_count() -> None:
    base = {
        "analysis_type": "sanitizacao_contexto_fiscal",
        "schema_type": "DataSanitizationPayload",
        "versao": "1.0",
        "empresa_id": EMPRESA_ID,
        "contexto_valido": True,
        "total_alertas": 0,
        "alertas": (),
        "publication_allowed": False,
    }

    invalid_bool = dict(base)
    invalid_bool["contexto_valido"] = 1

    with pytest.raises(ValidationError):
        DataSanitizationPayload.model_validate(invalid_bool)

    invalid_count = dict(base)
    invalid_count["total_alertas"] = True

    with pytest.raises(ValidationError):
        DataSanitizationPayload.model_validate(invalid_count)


def test_payload_rejects_wrong_code_order_inside_same_field() -> None:
    not_numeric = DataSanitizationAlert(
        codigo="CAMPO_NAO_NUMERICO",
        severidade="critico",
        campo="faturamento",
        mensagem=ALERTAS_SANITIZACAO_CANONICOS[
            "CAMPO_NAO_NUMERICO"
        ][1],
    )
    negative = DataSanitizationAlert(
        codigo="CAMPO_NEGATIVO",
        severidade="alto",
        campo="faturamento",
        mensagem=ALERTAS_SANITIZACAO_CANONICOS[
            "CAMPO_NEGATIVO"
        ][1],
    )

    with pytest.raises(ValidationError):
        DataSanitizationPayload(
            empresa_id=EMPRESA_ID,
            contexto_valido=False,
            total_alertas=2,
            alertas=(negative, not_numeric),
        )


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("analysis_type", "outro"),
        ("schema_type", "Outro"),
        ("versao", "9.0"),
        ("empresa_id", EMPRESA_ID + 1),
        ("contexto_valido", False),
        ("total_alertas", 1),
        (
            "alertas",
            (
                DataSanitizationAlert(
                    codigo="CONTEXTO_SEM_CAMPOS_FISCAIS",
                    severidade="critico",
                    campo=None,
                    mensagem=(
                        ALERTAS_SANITIZACAO_CANONICOS[
                            "CONTEXTO_SEM_CAMPOS_FISCAIS"
                        ][1]
                    ),
                ),
            ),
        ),
        ("publication_allowed", True),
    ],
)
def test_payload_validation_detects_tampering(
    field_name: str,
    bad_value: object,
) -> None:
    context = DataSanitizationContext(
        empresa_id=EMPRESA_ID,
        faturamento=100,
    )
    payload = construir_payload_sanitizacao(context)
    altered = payload.model_copy(
        update={field_name: bad_value}
    )

    with pytest.raises(ValueError):
        validate_data_sanitization_payload_against_context(
            context=context,
            payload=altered,
        )


# ---------------------------------------------------------------------------
# Falhas de execução e pós-construção
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_failure_returns_stable_public_error() -> None:
    secret = "segredo-interno-987"

    with patch(
        "app.agents.adapters.data_sanitization."
        "construir_payload_sanitizacao",
        side_effect=RuntimeError(secret),
    ):
        result = await execute_data_sanitization_mission(
            _mission()
        )

    assert result.status == "erro"
    assert (
        result.error_code
        == "AG_DATA_SANITIZATION_EXECUTION_ERROR"
    )
    assert result.error_message == EXECUTION_MESSAGE
    assert secret not in result.error_message
    assert "RuntimeError" not in result.error_message
    assert "Traceback" not in result.error_message
    assert result.payload == {}

    _assert_common_result(result)


@pytest.mark.asyncio
async def test_payload_validation_failure_is_execution_error() -> None:
    with patch(
        "app.agents.adapters.data_sanitization."
        "validate_data_sanitization_payload_against_context",
        side_effect=ValueError("interno"),
    ):
        result = await execute_data_sanitization_mission(
            _mission()
        )

    assert result.status == "erro"
    assert (
        result.error_code
        == "AG_DATA_SANITIZATION_EXECUTION_ERROR"
    )
    assert result.error_message == EXECUTION_MESSAGE


@pytest.mark.asyncio
async def test_cross_validation_failure_is_typed() -> None:
    with patch(
        "app.agents.adapters.data_sanitization."
        "validate_result_against_mission",
        side_effect=ValueError("interno"),
    ):
        with pytest.raises(
            DataSanitizacaoResultValidationError
        ) as exc_info:
            await execute_data_sanitization_mission(
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
        "app.agents.adapters.data_sanitization."
        "assert_result_sanitized",
        side_effect=ValueError("interno"),
    ):
        with pytest.raises(
            DataSanitizacaoResultSafetyError
        ) as exc_info:
            await execute_data_sanitization_mission(
                _mission()
            )

    assert exc_info.value.code == "RESULT_SANITIZATION_FAILED"
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


# ---------------------------------------------------------------------------
# Integridade estrutural
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


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/agents/contracts/data_sanitization.py",
        "app/agents/engines/data_sanitization.py",
        "app/agents/adapters/data_sanitization.py",
    ],
)
def test_layers_have_no_forbidden_imports(relative_path: str) -> None:
    forbidden = {
        "sqlalchemy",
        "app.database",
        "app.models",
        "httpx",
        "requests",
        "os",
        "pathlib",
        "subprocess",
        "app.agents.data_sanitization_agent",
        "app.agents.agent_executor",
        "app.agents.agent_scheduler",
    }

    imported = _imported_modules(relative_path)

    for module in imported:
        assert not any(
            module == item
            or module.startswith(f"{item}.")
            for item in forbidden
        ), (
            f"{relative_path} imports forbidden dependency "
            f"{module}"
        )


def test_layers_have_no_persistence_or_file_write_calls() -> None:
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

    for relative_path in (
        "app/agents/engines/data_sanitization.py",
        "app/agents/adapters/data_sanitization.py",
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

        assert used.isdisjoint(forbidden_calls)


def test_legacy_hash_and_no_run_mission() -> None:
    path = ROOT / "app" / "agents" / "data_sanitization_agent.py"

    digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    assert digest == LEGACY_SHA256

    tree = ast.parse(path.read_text(encoding="utf-8"))
    method_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
    }

    assert "run_mission" not in method_names


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/agents/agent_registry.py",
        "app/agents/agent_executor.py",
        "app/agents/agent_scheduler.py",
    ],
)
def test_runtime_components_do_not_reference_adapter(
    relative_path: str,
) -> None:
    source = _source(relative_path)

    assert "execute_data_sanitization_mission" not in source
    assert "app.agents.adapters.data_sanitization" not in source


def test_adapter_is_async_and_has_no_reader() -> None:
    assert inspect.iscoroutinefunction(
        execute_data_sanitization_mission
    )

    adapter_source = _source(
        "app/agents/adapters/data_sanitization.py"
    )
    assert "Reader" not in adapter_source
    assert "reader" not in adapter_source.casefold()
