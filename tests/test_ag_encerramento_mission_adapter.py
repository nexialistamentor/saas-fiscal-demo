"""
tests/test_ag_encerramento_mission_adapter.py - ADR-010 B14.3B.

Provas contratuais do canario MEI:

- MissionFactory e fronteira do adapter;
- bloqueios, erros e caminho nominal;
- motor, contratos e validacao payload-snapshot;
- reader SQLAlchemy read-only;
- integridade do legado e isolamento estrutural.
"""

from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from tests.canonical_source_hash import canonical_source_sha256

from app.agents.adapters.ag_encerramento import (
    execute_ag_encerramento_mission,
)
from app.agents.contracts.ag_encerramento import (
    ALERTAS_ENCERRAMENTO_CANONICOS,
    AVISOS_LEGAIS_ENCERRAMENTO,
    BASE_REVIEW_REASONS_ENCERRAMENTO,
    CHECKLIST_ENCERRAMENTO_CANONICO,
    TEMPORAL_REVIEW_REASONS_ENCERRAMENTO,
    AgEncerramentoAlertaPlataforma,
    AgEncerramentoCommercialDisclosure,
    AgEncerramentoContext,
    AgEncerramentoPayload,
    AgEncerramentoPreExecutionError,
    AgEncerramentoResultSafetyError,
    AgEncerramentoResultValidationError,
    EncerramentoAccessDeniedError,
    EncerramentoDataUnavailableError,
    EncerramentoPendenciaSnapshot,
)
from app.agents.contracts.shared import BudgetPolicy, SourceRef
from app.agents.engines.ag_encerramento import (
    construir_orientacao_encerramento,
    derivar_alertas_encerramento,
    renderizar_resposta_encerramento,
    validate_ag_encerramento_payload_against_snapshot,
)
from app.agents.mission_factory import create_agent_mission
from app.agents.readers.ag_encerramento import AgEncerramentoReader
from app.constants import AVISO_ENCERRAMENTO_IRREVERSIVEL


ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc

TENANT_ID = 42
ACTOR_ID = 42
EMPRESA_ID = 7

CREATED_AT = datetime(
    2026,
    7,
    16,
    12,
    0,
    0,
    tzinfo=UTC,
)
REFERENCE_AT = datetime(
    2026,
    7,
    1,
    0,
    0,
    0,
    tzinfo=UTC,
)

LEGACY_SHA256 = (
    "57633CB4DBF5F42B47D3F264DF76198BCA0B02F2625845EF0BA40C9D9E88AF93"
)

ACCESS_MESSAGE = (
    "N\u00e3o foi poss\u00edvel autorizar o acesso "
    "\u00e0 empresa solicitada."
)
DATA_MESSAGE = (
    "N\u00e3o foi poss\u00edvel obter os dados necess\u00e1rios "
    "para esta orienta\u00e7\u00e3o."
)
EXECUTION_MESSAGE = (
    "N\u00e3o foi poss\u00edvel concluir a orienta\u00e7\u00e3o "
    "de encerramento."
)


def _mission(
    *,
    context: dict | None = None,
    execution_mode: str = "sombra",
    agent_version_required: str | None = None,
    source_request_id: str = "req-encerramento-001",
    **overrides: object,
):
    kwargs: dict = {
        "mission_type": "orientar_encerramento_empresa",
        "target_agent": "ag_encerramento",
        "context": (
            context
            if context is not None
            else {
                "empresa_id": EMPRESA_ID,
                "tipo_contribuinte": "mei",
            }
        ),
        "context_schema": "ag_encerramento.context",
        "context_version": "1.0",
        "output_schema": "ag_encerramento.result",
        "output_version": "1.0",
        "scope": "tenant",
        "tenant_id": TENANT_ID,
        "actor_id": ACTOR_ID,
        "requested_by": "user",
        "authority_level": "leitura",
        "execution_mode": execution_mode,
        "source_request_id": source_request_id,
        "created_at": CREATED_AT,
        "reference_at": REFERENCE_AT,
        "agent_version_required": agent_version_required,
        "budget_policy": BudgetPolicy(),
        "sources": [],
    }
    kwargs.update(overrides)
    return create_agent_mission(**kwargs)


def _snapshot(
    *,
    empresa_id: int = EMPRESA_ID,
    reference_at: datetime = REFERENCE_AT,
    total_insights_ativos: int = 0,
    estado_ultimo_relatorio: str = "ausente",
    ultimo_relatorio_em: datetime | None = None,
) -> EncerramentoPendenciaSnapshot:
    return EncerramentoPendenciaSnapshot(
        empresa_id=empresa_id,
        reference_at=reference_at,
        total_insights_ativos=total_insights_ativos,
        estado_ultimo_relatorio=estado_ultimo_relatorio,
        ultimo_relatorio_em=ultimo_relatorio_em,
    )


def _reader_mock(
    snapshot: EncerramentoPendenciaSnapshot | None = None,
    *,
    side_effect: Exception | None = None,
) -> MagicMock:
    reader = MagicMock()

    if side_effect is not None:
        reader.obter_snapshot.side_effect = side_effect
    else:
        reader.obter_snapshot.return_value = (
            snapshot if snapshot is not None else _snapshot()
        )

    return reader


def _assert_common_result(result) -> None:
    assert result.attempt == 1
    assert result.agent_id == "ag_encerramento"
    assert result.agent_version == "1.0"
    assert result.mission_type == "orientar_encerramento_empresa"
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

    assert result.payload_schema == "ag_encerramento.result"
    assert result.payload_version == "1.0"

    assert result.started_at.utcoffset() == timedelta(0)
    assert result.finished_at.utcoffset() == timedelta(0)
    assert result.finished_at >= result.started_at

    assert type(result.duration_ms) is int
    assert result.duration_ms >= 0


def _valid_payload(
    *,
    snapshot: EncerramentoPendenciaSnapshot | None = None,
):
    snap = snapshot if snapshot is not None else _snapshot()

    context = AgEncerramentoContext(
        empresa_id=snap.empresa_id,
        tipo_contribuinte="mei",
    )

    payload = construir_orientacao_encerramento(
        context,
        snap,
    )

    return context, snap, payload


# ---------------------------------------------------------------------------
# MissionFactory e caminho nominal
# ---------------------------------------------------------------------------


def test_mission_helper_uses_factory_contract() -> None:
    mission = _mission()

    assert mission.context_hash
    assert mission.idempotency_key
    assert mission.source_request_id == "req-encerramento-001"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sombra", "dry_run"])
async def test_nominal_modes_succeed(mode: str) -> None:
    mission = _mission(execution_mode=mode)
    reader = _reader_mock(_snapshot())

    result = await execute_ag_encerramento_mission(
        mission,
        reader,
    )

    assert result.status == "sucesso"
    assert result.payload
    assert result.alerts == []
    assert result.error_code is None
    assert result.error_message is None
    assert result.mode == mode
    assert result.mission_id == mission.mission_id
    assert result.correlation_id == mission.correlation_id

    _assert_common_result(result)


@pytest.mark.asyncio
async def test_nominal_reader_receives_exact_identifiers() -> None:
    mission = _mission()
    reader = _reader_mock(_snapshot())

    await execute_ag_encerramento_mission(
        mission,
        reader,
    )

    reader.obter_snapshot.assert_called_once_with(
        tenant_id=TENANT_ID,
        actor_id=ACTOR_ID,
        empresa_id=EMPRESA_ID,
        reference_at=REFERENCE_AT,
    )


@pytest.mark.asyncio
async def test_nominal_payload_contract_is_complete() -> None:
    result = await execute_ag_encerramento_mission(
        _mission(),
        _reader_mock(_snapshot()),
    )

    payload = result.payload

    expected_checklist = tuple(
        item.model_dump(mode="python")
        for item in CHECKLIST_ENCERRAMENTO_CANONICO
    )

    assert payload["analysis_type"] == "encerramento_empresa"
    assert payload["schema_type"] == "HowTo"
    assert payload["versao"] == "1.0"
    assert payload["tipo_contribuinte"] == "mei"
    assert payload["publication_allowed"] is False

    assert payload["checklist"] == expected_checklist
    assert payload["avisos_legais"] == AVISOS_LEGAIS_ENCERRAMENTO
    assert (
        payload["aviso_irreversivel"]
        == AVISO_ENCERRAMENTO_IRREVERSIVEL
    )

    assert (
        payload["commercial_disclosure"]
        == AgEncerramentoCommercialDisclosure().model_dump(
            mode="python"
        )
    )

    assert (
        payload["review_reasons"]
        == BASE_REVIEW_REASONS_ENCERRAMENTO
    )

    assert (
        "Orienta\u00e7\u00e3o Preliminar"
        in payload["resposta"]
    )
    assert "Passo a Passo Oficial" not in payload["resposta"]
    assert str(REFERENCE_AT.year) in payload["resposta"]


@pytest.mark.asyncio
async def test_missing_tipo_defaults_to_mei() -> None:
    mission = _mission(
        context={"empresa_id": EMPRESA_ID}
    )

    result = await execute_ag_encerramento_mission(
        mission,
        _reader_mock(_snapshot()),
    )

    assert result.status == "sucesso"
    assert result.payload["tipo_contribuinte"] == "mei"


# ---------------------------------------------------------------------------
# Fronteira pre-execucao
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("updates", "expected_code"),
    [
        (
            {"target_agent": "ag_outro"},
            "MISSION_TARGET_MISMATCH",
        ),
        (
            {"mission_type": "outra"},
            "MISSION_TYPE_UNSUPPORTED",
        ),
        (
            {"context_schema": "outro.context"},
            "CONTEXT_SCHEMA_UNSUPPORTED",
        ),
        (
            {"context_version": "9.0"},
            "CONTEXT_VERSION_UNSUPPORTED",
        ),
        (
            {"output_schema": "outro.result"},
            "OUTPUT_SCHEMA_UNSUPPORTED",
        ),
        (
            {"output_version": "9.0"},
            "OUTPUT_VERSION_UNSUPPORTED",
        ),
        (
            {"scope": "global"},
            "MISSION_SCOPE_UNSUPPORTED",
        ),
        (
            {"tenant_id": None},
            "MISSION_TENANT_REQUIRED",
        ),
        (
            {"tenant_id": True},
            "MISSION_TENANT_REQUIRED",
        ),
        (
            {"tenant_id": "42"},
            "MISSION_TENANT_REQUIRED",
        ),
        (
            {"tenant_id": 0},
            "MISSION_TENANT_REQUIRED",
        ),
        (
            {"actor_id": None},
            "MISSION_ACTOR_UNSUPPORTED",
        ),
        (
            {"actor_id": True},
            "MISSION_ACTOR_UNSUPPORTED",
        ),
        (
            {"actor_id": "42"},
            "MISSION_ACTOR_UNSUPPORTED",
        ),
        (
            {"actor_id": 0},
            "MISSION_ACTOR_UNSUPPORTED",
        ),
        (
            {"actor_id": 43},
            "MISSION_ACTOR_TENANT_MISMATCH",
        ),
        (
            {"reference_at": None},
            "MISSION_REFERENCE_AT_REQUIRED",
        ),
        (
            {
                "reference_at": datetime(
                    2026,
                    7,
                    1,
                    0,
                    0,
                    0,
                )
            },
            "MISSION_REFERENCE_AT_REQUIRED",
        ),
        (
            {
                "reference_at": datetime(
                    2026,
                    7,
                    1,
                    0,
                    0,
                    0,
                    tzinfo=timezone(
                        timedelta(hours=-3)
                    ),
                )
            },
            "MISSION_REFERENCE_AT_REQUIRED",
        ),
        (
            {
                "reference_at": (
                    CREATED_AT
                    + timedelta(seconds=1)
                )
            },
            "MISSION_REFERENCE_AT_REQUIRED",
        ),
        (
            {"requested_by": "admin"},
            "MISSION_AUTHORITY_UNSUPPORTED",
        ),
        (
            {"authority_level": "proposta"},
            "MISSION_AUTHORITY_UNSUPPORTED",
        ),
        (
            {"source_request_id": None},
            "MISSION_ORIGIN_UNSUPPORTED",
        ),
        (
            {"source_request_id": "   "},
            "MISSION_ORIGIN_UNSUPPORTED",
        ),
        (
            {"source_event_id": uuid4()},
            "MISSION_ORIGIN_UNSUPPORTED",
        ),
        (
            {"schedule_slot": "slot-1"},
            "MISSION_ORIGIN_UNSUPPORTED",
        ),
        (
            {
                "budget_policy": BudgetPolicy(
                    currency="USD"
                )
            },
            "MISSION_BUDGET_UNSUPPORTED",
        ),
        (
            {
                "sources": [
                    SourceRef(
                        fonte_id="fonte-001",
                        uso_pretendido=(
                            "apoiar_explicacao_ux"
                        ),
                    )
                ]
            },
            "MISSION_SOURCES_UNSUPPORTED",
        ),
    ],
)
async def test_pre_execution_boundary_codes(
    updates: dict,
    expected_code: str,
) -> None:
    # model_copy cria deliberadamente um estado de fronteira invalido
    # sem instanciar AgentMission directamente.
    mission = _mission().model_copy(
        update=updates
    )
    reader = _reader_mock()

    with pytest.raises(
        AgEncerramentoPreExecutionError
    ) as exc_info:
        await execute_ag_encerramento_mission(
            mission,
            reader,
        )

    assert exc_info.value.code == expected_code
    assert exc_info.value.__cause__ is None

    reader.obter_snapshot.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw_tipo", "expected_code"),
    [
        (
            None,
            "AG_ENCERRAMENTO_CONTEXT_INVALID",
        ),
        (
            True,
            "AG_ENCERRAMENTO_CONTEXT_INVALID",
        ),
        (
            123,
            "AG_ENCERRAMENTO_CONTEXT_INVALID",
        ),
        (
            "",
            "AG_ENCERRAMENTO_CONTEXT_INVALID",
        ),
        (
            "   ",
            "AG_ENCERRAMENTO_CONTEXT_INVALID",
        ),
        (
            "epp",
            "AG_ENCERRAMENTO_TIPO_UNSUPPORTED",
        ),
        (
            "ltda",
            "AG_ENCERRAMENTO_TIPO_UNSUPPORTED",
        ),
    ],
)
async def test_tipo_pre_validation_exact_codes(
    raw_tipo: object,
    expected_code: str,
) -> None:
    mission = _mission(
        context={
            "empresa_id": EMPRESA_ID,
            "tipo_contribuinte": raw_tipo,
        }
    )
    reader = _reader_mock()

    with pytest.raises(
        AgEncerramentoPreExecutionError
    ) as exc_info:
        await execute_ag_encerramento_mission(
            mission,
            reader,
        )

    assert exc_info.value.code == expected_code
    reader.obter_snapshot.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "empresa_id",
    [
        None,
        True,
        "7",
        0,
        -1,
        7.0,
    ],
)
async def test_invalid_empresa_id_is_context_error(
    empresa_id: object,
) -> None:
    mission = _mission(
        context={
            "empresa_id": empresa_id,
            "tipo_contribuinte": "mei",
        }
    )
    reader = _reader_mock()

    with pytest.raises(
        AgEncerramentoPreExecutionError
    ) as exc_info:
        await execute_ag_encerramento_mission(
            mission,
            reader,
        )

    assert (
        exc_info.value.code
        == "AG_ENCERRAMENTO_CONTEXT_INVALID"
    )
    reader.obter_snapshot.assert_not_called()


@pytest.mark.asyncio
async def test_extra_context_field_is_rejected() -> None:
    mission = _mission(
        context={
            "empresa_id": EMPRESA_ID,
            "tipo_contribuinte": "mei",
            "campo_extra": "proibido",
        }
    )

    with pytest.raises(
        AgEncerramentoPreExecutionError
    ) as exc_info:
        await execute_ag_encerramento_mission(
            mission,
            _reader_mock(),
        )

    assert (
        exc_info.value.code
        == "AG_ENCERRAMENTO_CONTEXT_INVALID"
    )


@pytest.mark.asyncio
async def test_non_dict_context_is_rejected() -> None:
    mission = _mission().model_copy(
        update={"context": ["invalido"]}
    )
    reader = _reader_mock()

    with pytest.raises(
        AgEncerramentoPreExecutionError
    ) as exc_info:
        await execute_ag_encerramento_mission(
            mission,
            reader,
        )

    assert (
        exc_info.value.code
        == "AG_ENCERRAMENTO_CONTEXT_INVALID"
    )
    reader.obter_snapshot.assert_not_called()


# ---------------------------------------------------------------------------
# Bloqueios e erros
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_active_mode_blocked_without_reader() -> None:
    reader = _reader_mock()

    result = await execute_ag_encerramento_mission(
        _mission(execution_mode="activo"),
        reader,
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

    reader.obter_snapshot.assert_not_called()
    _assert_common_result(result)


@pytest.mark.asyncio
async def test_incompatible_version_precedes_mode() -> None:
    reader = _reader_mock()

    result = await execute_ag_encerramento_mission(
        _mission(
            execution_mode="activo",
            agent_version_required="9.9.9",
        ),
        reader,
    )

    assert result.status == "bloqueado"
    assert (
        result.alerts[0].code
        == "AGENT_VERSION_INCOMPATIBLE"
    )

    reader.obter_snapshot.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "required",
    [None, "1.0"],
)
async def test_compatible_version_executes(
    required: str | None,
) -> None:
    reader = _reader_mock(_snapshot())

    result = await execute_ag_encerramento_mission(
        _mission(
            agent_version_required=required
        ),
        reader,
    )

    assert result.status == "sucesso"
    reader.obter_snapshot.assert_called_once()


@pytest.mark.asyncio
async def test_access_denied_non_enumerating_block() -> None:
    result = await execute_ag_encerramento_mission(
        _mission(),
        _reader_mock(
            side_effect=(
                EncerramentoAccessDeniedError()
            )
        ),
    )

    assert result.status == "bloqueado"
    assert result.payload == {}
    assert result.error_code is None
    assert result.error_message is None

    assert len(result.alerts) == 1
    assert (
        result.alerts[0].code
        == "AG_ENCERRAMENTO_ACCESS_DENIED"
    )
    assert result.alerts[0].message == ACCESS_MESSAGE

    _assert_common_result(result)


@pytest.mark.asyncio
async def test_data_unavailable_stable_error() -> None:
    result = await execute_ag_encerramento_mission(
        _mission(),
        _reader_mock(
            side_effect=(
                EncerramentoDataUnavailableError()
            )
        ),
    )

    assert result.status == "erro"
    assert result.payload == {}
    assert result.alerts == []

    assert (
        result.error_code
        == "AG_ENCERRAMENTO_DATA_UNAVAILABLE"
    )
    assert result.error_message == DATA_MESSAGE

    _assert_common_result(result)


@pytest.mark.asyncio
async def test_unexpected_error_does_not_leak() -> None:
    secret = "SQL password=CREDENCIAL_SECRETA"

    result = await execute_ag_encerramento_mission(
        _mission(),
        _reader_mock(
            side_effect=RuntimeError(secret)
        ),
    )

    assert result.status == "erro"
    assert result.payload == {}
    assert result.alerts == []

    assert (
        result.error_code
        == "AG_ENCERRAMENTO_EXECUTION_ERROR"
    )
    assert result.error_message == EXECUTION_MESSAGE

    assert secret not in result.error_message
    assert "RuntimeError" not in result.error_message
    assert "Traceback" not in result.error_message

    _assert_common_result(result)


@pytest.mark.asyncio
async def test_snapshot_empresa_mismatch_is_data_error() -> None:
    result = await execute_ag_encerramento_mission(
        _mission(),
        _reader_mock(
            _snapshot(empresa_id=999)
        ),
    )

    assert result.status == "erro"
    assert (
        result.error_code
        == "AG_ENCERRAMENTO_DATA_UNAVAILABLE"
    )


@pytest.mark.asyncio
async def test_snapshot_reference_mismatch_is_data_error() -> None:
    result = await execute_ag_encerramento_mission(
        _mission(),
        _reader_mock(
            _snapshot(
                reference_at=(
                    REFERENCE_AT
                    - timedelta(seconds=1)
                )
            )
        ),
    )

    assert result.status == "erro"
    assert (
        result.error_code
        == "AG_ENCERRAMENTO_DATA_UNAVAILABLE"
    )


@pytest.mark.asyncio
async def test_payload_validation_failure_is_execution_error() -> None:
    with patch(
        "app.agents.adapters.ag_encerramento."
        "validate_ag_encerramento_payload_against_snapshot",
        side_effect=ValueError("desvio interno"),
    ):
        result = await execute_ag_encerramento_mission(
            _mission(),
            _reader_mock(_snapshot()),
        )

    assert result.status == "erro"
    assert (
        result.error_code
        == "AG_ENCERRAMENTO_EXECUTION_ERROR"
    )
    assert result.error_message == EXECUTION_MESSAGE


@pytest.mark.asyncio
async def test_engine_failure_is_execution_error() -> None:
    with patch(
        "app.agents.adapters.ag_encerramento."
        "construir_orientacao_encerramento",
        side_effect=ValueError("desvio interno"),
    ):
        result = await execute_ag_encerramento_mission(
            _mission(),
            _reader_mock(_snapshot()),
        )

    assert result.status == "erro"
    assert (
        result.error_code
        == "AG_ENCERRAMENTO_EXECUTION_ERROR"
    )


# ---------------------------------------------------------------------------
# Semantica do motor
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    (
        "snapshot",
        "expected_codes",
        "expected_review_reasons",
    ),
    [
        (
            _snapshot(
                estado_ultimo_relatorio="ausente",
            ),
            ("RELATORIO_AUSENTE",),
            BASE_REVIEW_REASONS_ENCERRAMENTO,
        ),
        (
            _snapshot(
                estado_ultimo_relatorio=(
                    "timestamp_ausente"
                ),
            ),
            ("RELATORIO_TIMESTAMP_AUSENTE",),
            TEMPORAL_REVIEW_REASONS_ENCERRAMENTO,
        ),
        (
            _snapshot(
                estado_ultimo_relatorio=(
                    "timestamp_naive"
                ),
            ),
            ("RELATORIO_TIMESTAMP_NAIVE",),
            TEMPORAL_REVIEW_REASONS_ENCERRAMENTO,
        ),
        (
            _snapshot(
                estado_ultimo_relatorio=(
                    "timestamp_aware"
                ),
                ultimo_relatorio_em=(
                    REFERENCE_AT
                    - timedelta(days=119)
                ),
            ),
            (),
            BASE_REVIEW_REASONS_ENCERRAMENTO,
        ),
        (
            _snapshot(
                estado_ultimo_relatorio=(
                    "timestamp_aware"
                ),
                ultimo_relatorio_em=(
                    REFERENCE_AT
                    - timedelta(days=120)
                ),
            ),
            ("RELATORIO_DESACTUALIZADO",),
            BASE_REVIEW_REASONS_ENCERRAMENTO,
        ),
    ],
)
def test_engine_report_state_matrix(
    snapshot: EncerramentoPendenciaSnapshot,
    expected_codes: tuple[str, ...],
    expected_review_reasons: tuple[str, ...],
) -> None:
    context = AgEncerramentoContext(
        empresa_id=EMPRESA_ID,
        tipo_contribuinte="mei",
    )

    payload = construir_orientacao_encerramento(
        context,
        snapshot,
    )

    assert tuple(
        alert.code
        for alert in payload.alertas_plataforma
    ) == expected_codes

    assert (
        payload.review_reasons
        == expected_review_reasons
    )


def test_engine_alert_order_and_quantity() -> None:
    snapshot = _snapshot(
        total_insights_ativos=3,
        estado_ultimo_relatorio="ausente",
    )

    alerts = derivar_alertas_encerramento(
        snapshot
    )

    assert tuple(
        alert.code for alert in alerts
    ) == (
        "INSIGHTS_ATIVOS",
        "RELATORIO_AUSENTE",
    )

    assert alerts[0].quantidade == 3
    assert alerts[1].quantidade is None


def test_engine_response_is_deterministic() -> None:
    context, snapshot, payload = _valid_payload()

    expected = renderizar_resposta_encerramento(
        ano=snapshot.reference_at.year,
        checklist=CHECKLIST_ENCERRAMENTO_CANONICO,
        alertas=payload.alertas_plataforma,
        aviso_irreversivel=(
            AVISO_ENCERRAMENTO_IRREVERSIVEL
        ),
        avisos_legais=(
            AVISOS_LEGAIS_ENCERRAMENTO
        ),
    )

    assert payload.resposta == expected

    validate_ag_encerramento_payload_against_snapshot(
        context=context,
        snapshot=snapshot,
        payload=payload,
    )


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        (
            "resposta",
            "resposta adulterada",
        ),
        (
            "analysis_type",
            "outro",
        ),
        (
            "schema_type",
            "Outro",
        ),
        (
            "versao",
            "9.0",
        ),
        (
            "tipo_contribuinte",
            "epp",
        ),
        (
            "checklist",
            (),
        ),
        (
            "avisos_legais",
            (),
        ),
        (
            "aviso_irreversivel",
            "adulterado",
        ),
        (
            "commercial_disclosure",
            AgEncerramentoCommercialDisclosure().model_copy(
                update={
                    "pricing_status": "adulterado"
                }
            ),
        ),
        (
            "alertas_plataforma",
            (),
        ),
        (
            "review_reasons",
            TEMPORAL_REVIEW_REASONS_ENCERRAMENTO,
        ),
        (
            "publication_allowed",
            True,
        ),
    ],
)
def test_payload_validation_detects_tampering(
    field_name: str,
    bad_value: object,
) -> None:
    context, snapshot, payload = _valid_payload()

    altered = payload.model_copy(
        update={field_name: bad_value}
    )

    with pytest.raises(ValueError):
        validate_ag_encerramento_payload_against_snapshot(
            context=context,
            snapshot=snapshot,
            payload=altered,
        )


# ---------------------------------------------------------------------------
# Invariantes dos contratos
# ---------------------------------------------------------------------------


def test_canonical_collections_are_immutable() -> None:
    assert isinstance(
        CHECKLIST_ENCERRAMENTO_CANONICO,
        tuple,
    )
    assert isinstance(
        ALERTAS_ENCERRAMENTO_CANONICOS,
        MappingProxyType,
    )

    with pytest.raises(TypeError):
        ALERTAS_ENCERRAMENTO_CANONICOS[
            "NOVO"
        ] = ("alto", "texto")  # type: ignore[index]


@pytest.mark.parametrize(
    "payload",
    [
        {
            "empresa_id": True,
            "reference_at": REFERENCE_AT,
            "total_insights_ativos": 0,
            "estado_ultimo_relatorio": "ausente",
            "ultimo_relatorio_em": None,
        },
        {
            "empresa_id": EMPRESA_ID,
            "reference_at": datetime(
                2026,
                7,
                1,
            ),
            "total_insights_ativos": 0,
            "estado_ultimo_relatorio": "ausente",
            "ultimo_relatorio_em": None,
        },
        {
            "empresa_id": EMPRESA_ID,
            "reference_at": REFERENCE_AT,
            "total_insights_ativos": -1,
            "estado_ultimo_relatorio": "ausente",
            "ultimo_relatorio_em": None,
        },
        {
            "empresa_id": EMPRESA_ID,
            "reference_at": REFERENCE_AT,
            "total_insights_ativos": 0,
            "estado_ultimo_relatorio": (
                "timestamp_aware"
            ),
            "ultimo_relatorio_em": None,
        },
        {
            "empresa_id": EMPRESA_ID,
            "reference_at": REFERENCE_AT,
            "total_insights_ativos": 0,
            "estado_ultimo_relatorio": (
                "timestamp_naive"
            ),
            "ultimo_relatorio_em": REFERENCE_AT,
        },
        {
            "empresa_id": EMPRESA_ID,
            "reference_at": REFERENCE_AT,
            "total_insights_ativos": 0,
            "estado_ultimo_relatorio": (
                "timestamp_aware"
            ),
            "ultimo_relatorio_em": (
                REFERENCE_AT
                + timedelta(seconds=1)
            ),
        },
    ],
)
def test_snapshot_rejects_invalid_combinations(
    payload: dict,
) -> None:
    with pytest.raises(ValidationError):
        EncerramentoPendenciaSnapshot.model_validate(
            payload
        )


def test_snapshot_is_frozen() -> None:
    snapshot = _snapshot()

    with pytest.raises(ValidationError):
        snapshot.empresa_id = 99  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "code": "RELATORIO_AUSENTE",
            "severidade": "alto",
            "descricao_publica": (
                ALERTAS_ENCERRAMENTO_CANONICOS[
                    "RELATORIO_AUSENTE"
                ][1]
            ),
        },
        {
            "code": "RELATORIO_AUSENTE",
            "severidade": "medio",
            "descricao_publica": "texto adulterado",
        },
        {
            "code": "INSIGHTS_ATIVOS",
            "severidade": "alto",
            "descricao_publica": (
                ALERTAS_ENCERRAMENTO_CANONICOS[
                    "INSIGHTS_ATIVOS"
                ][1]
            ),
            "quantidade": True,
        },
        {
            "code": "INSIGHTS_ATIVOS",
            "severidade": "alto",
            "descricao_publica": (
                ALERTAS_ENCERRAMENTO_CANONICOS[
                    "INSIGHTS_ATIVOS"
                ][1]
            ),
            "quantidade": 0,
        },
        {
            "code": "RELATORIO_AUSENTE",
            "severidade": "medio",
            "descricao_publica": (
                ALERTAS_ENCERRAMENTO_CANONICOS[
                    "RELATORIO_AUSENTE"
                ][1]
            ),
            "quantidade": 1,
        },
    ],
)
def test_alert_contract_rejects_invalid_values(
    kwargs: dict,
) -> None:
    with pytest.raises(ValidationError):
        AgEncerramentoAlertaPlataforma(
            **kwargs
        )


def test_payload_rejects_duplicate_and_wrong_order_alerts() -> None:
    snapshot = _snapshot(
        total_insights_ativos=2,
        estado_ultimo_relatorio="ausente",
    )

    context, _, payload = _valid_payload(
        snapshot=snapshot
    )

    data = payload.model_dump(mode="python")

    duplicated = dict(data)
    duplicated["alertas_plataforma"] = (
        payload.alertas_plataforma[0],
        payload.alertas_plataforma[0],
    )

    with pytest.raises(ValidationError):
        AgEncerramentoPayload.model_validate(
            duplicated
        )

    reversed_order = dict(data)
    reversed_order["alertas_plataforma"] = tuple(
        reversed(
            payload.alertas_plataforma
        )
    )

    with pytest.raises(ValidationError):
        AgEncerramentoPayload.model_validate(
            reversed_order
        )

    validate_ag_encerramento_payload_against_snapshot(
        context=context,
        snapshot=snapshot,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Reader concreto
# ---------------------------------------------------------------------------


def _db_mock(
    *,
    authorized: bool = True,
    insights: int = 0,
    total_reports: int = 0,
    last_created_at: datetime | None = None,
    reconfirmed: bool = True,
) -> MagicMock:
    db = MagicMock()

    db.no_autoflush.__enter__.return_value = None
    db.no_autoflush.__exit__.return_value = False

    q_auth = MagicMock()
    q_auth.filter.return_value.first.return_value = (
        (EMPRESA_ID,)
        if authorized
        else None
    )

    q_exists = MagicMock()
    q_exists.filter.return_value.exists.return_value = (
        object()
    )

    q_insights = MagicMock()
    q_insights.filter.return_value.scalar.return_value = (
        insights
    )

    q_reports = MagicMock()
    q_reports.filter.return_value.one.return_value = (
        total_reports,
        last_created_at,
    )

    q_reconfirm = MagicMock()
    q_reconfirm.filter.return_value.first.return_value = (
        (EMPRESA_ID,)
        if reconfirmed
        else None
    )

    db.query.side_effect = [
        q_auth,
        q_exists,
        q_insights,
        q_reports,
        q_reconfirm,
    ]

    return db


def test_reader_nominal_no_autoflush_and_no_writes() -> None:
    db = _db_mock(insights=2)
    reader = AgEncerramentoReader(db)

    snapshot = reader.obter_snapshot(
        tenant_id=TENANT_ID,
        actor_id=ACTOR_ID,
        empresa_id=EMPRESA_ID,
        reference_at=REFERENCE_AT,
    )

    assert snapshot.total_insights_ativos == 2
    assert (
        snapshot.estado_ultimo_relatorio
        == "ausente"
    )

    assert db.query.call_count == 5
    db.no_autoflush.__enter__.assert_called_once()

    for method_name in (
        "add",
        "add_all",
        "delete",
        "flush",
        "commit",
        "bulk_save_objects",
        "bulk_insert_mappings",
        "bulk_update_mappings",
    ):
        getattr(
            db,
            method_name,
        ).assert_not_called()


def test_reader_denies_actor_mismatch_before_query() -> None:
    db = _db_mock()
    reader = AgEncerramentoReader(db)

    with pytest.raises(
        EncerramentoAccessDeniedError
    ):
        reader.obter_snapshot(
            tenant_id=TENANT_ID,
            actor_id=TENANT_ID + 1,
            empresa_id=EMPRESA_ID,
            reference_at=REFERENCE_AT,
        )

    db.query.assert_not_called()


def test_reader_non_enumerates_missing_company() -> None:
    db = _db_mock(authorized=False)
    reader = AgEncerramentoReader(db)

    with pytest.raises(
        EncerramentoAccessDeniedError
    ):
        reader.obter_snapshot(
            tenant_id=TENANT_ID,
            actor_id=ACTOR_ID,
            empresa_id=EMPRESA_ID,
            reference_at=REFERENCE_AT,
        )


def test_reader_reconfirmation_discards_snapshot() -> None:
    db = _db_mock(reconfirmed=False)
    reader = AgEncerramentoReader(db)

    with pytest.raises(
        EncerramentoAccessDeniedError
    ):
        reader.obter_snapshot(
            tenant_id=TENANT_ID,
            actor_id=ACTOR_ID,
            empresa_id=EMPRESA_ID,
            reference_at=REFERENCE_AT,
        )


@pytest.mark.parametrize(
    (
        "last_created_at",
        "expected_state",
        "expected_timestamp",
    ),
    [
        (
            None,
            "timestamp_ausente",
            None,
        ),
        (
            datetime(
                2026,
                6,
                1,
                0,
                0,
                0,
            ),
            "timestamp_naive",
            None,
        ),
        (
            datetime(
                2026,
                6,
                1,
                0,
                0,
                0,
                tzinfo=timezone(
                    timedelta(hours=-3)
                ),
            ),
            "timestamp_aware",
            datetime(
                2026,
                6,
                1,
                3,
                0,
                0,
                tzinfo=UTC,
            ),
        ),
    ],
)
def test_reader_temporal_states(
    last_created_at: datetime | None,
    expected_state: str,
    expected_timestamp: datetime | None,
) -> None:
    db = _db_mock(
        total_reports=1,
        last_created_at=last_created_at,
    )

    snapshot = AgEncerramentoReader(
        db
    ).obter_snapshot(
        tenant_id=TENANT_ID,
        actor_id=ACTOR_ID,
        empresa_id=EMPRESA_ID,
        reference_at=REFERENCE_AT,
    )

    assert (
        snapshot.estado_ultimo_relatorio
        == expected_state
    )
    assert (
        snapshot.ultimo_relatorio_em
        == expected_timestamp
    )


def test_reader_future_timestamp_data_unavailable() -> None:
    db = _db_mock(
        total_reports=1,
        last_created_at=(
            REFERENCE_AT
            + timedelta(seconds=1)
        ),
    )

    with pytest.raises(
        EncerramentoDataUnavailableError
    ):
        AgEncerramentoReader(
            db
        ).obter_snapshot(
            tenant_id=TENANT_ID,
            actor_id=ACTOR_ID,
            empresa_id=EMPRESA_ID,
            reference_at=REFERENCE_AT,
        )


def test_reader_wraps_technical_error_without_message() -> None:
    db = MagicMock()

    db.no_autoflush.__enter__.return_value = None
    db.no_autoflush.__exit__.return_value = False

    q_auth = MagicMock()
    q_auth.filter.return_value.first.side_effect = (
        RuntimeError("segredo interno")
    )

    db.query.side_effect = [q_auth]

    with pytest.raises(
        EncerramentoDataUnavailableError
    ) as exc_info:
        AgEncerramentoReader(
            db
        ).obter_snapshot(
            tenant_id=TENANT_ID,
            actor_id=ACTOR_ID,
            empresa_id=EMPRESA_ID,
            reference_at=REFERENCE_AT,
        )

    assert str(exc_info.value) == ""


# ---------------------------------------------------------------------------
# Falhas pos-construcao
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_validation_failure_typed() -> None:
    with patch(
        "app.agents.adapters.ag_encerramento."
        "validate_result_against_mission",
        side_effect=ValueError("interno"),
    ):
        with pytest.raises(
            AgEncerramentoResultValidationError
        ) as exc_info:
            await execute_ag_encerramento_mission(
                _mission(),
                _reader_mock(_snapshot()),
            )

    assert (
        exc_info.value.code
        == "RESULT_MISSION_VALIDATION_FAILED"
    )
    assert exc_info.value.__cause__ is None
    assert (
        exc_info.value.__suppress_context__
        is True
    )


@pytest.mark.asyncio
async def test_sanitization_failure_typed() -> None:
    with patch(
        "app.agents.adapters.ag_encerramento."
        "assert_result_sanitized",
        side_effect=ValueError("interno"),
    ):
        with pytest.raises(
            AgEncerramentoResultSafetyError
        ) as exc_info:
            await execute_ag_encerramento_mission(
                _mission(),
                _reader_mock(_snapshot()),
            )

    assert (
        exc_info.value.code
        == "RESULT_SANITIZATION_FAILED"
    )
    assert exc_info.value.__cause__ is None
    assert (
        exc_info.value.__suppress_context__
        is True
    )


# ---------------------------------------------------------------------------
# Integridade estrutural
# ---------------------------------------------------------------------------


def _source(relative_path: str) -> str:
    return (
        ROOT / relative_path
    ).read_text(encoding="utf-8")


def _imported_modules(
    relative_path: str,
) -> set[str]:
    tree = ast.parse(
        _source(relative_path)
    )

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


@pytest.mark.parametrize(
    ("relative_path", "forbidden"),
    [
        (
            "app/agents/contracts/ag_encerramento.py",
            {
                "sqlalchemy",
                "app.models",
                "httpx",
                "requests",
            },
        ),
        (
            "app/agents/engines/ag_encerramento.py",
            {
                "sqlalchemy",
                "app.models",
                "httpx",
                "requests",
                "app.agents.ag_encerramento_agent",
            },
        ),
        (
            "app/agents/adapters/ag_encerramento.py",
            {
                "sqlalchemy",
                "app.models",
                "httpx",
                "requests",
                "app.agents.ag_encerramento_agent",
            },
        ),
    ],
)
def test_layers_have_no_forbidden_imports(
    relative_path: str,
    forbidden: set[str],
) -> None:
    imported = _imported_modules(
        relative_path
    )

    for module in imported:
        assert not any(
            module == item
            or module.startswith(
                f"{item}."
            )
            for item in forbidden
        ), (
            f"{relative_path} imports "
            f"forbidden dependency {module}"
        )


def test_reader_has_no_write_calls_or_text_sql() -> None:
    tree = ast.parse(
        _source(
            "app/agents/readers/"
            "ag_encerramento.py"
        )
    )

    forbidden_calls = {
        "text",
        "add",
        "add_all",
        "delete",
        "flush",
        "commit",
        "bulk_save_objects",
        "bulk_insert_mappings",
        "bulk_update_mappings",
    }

    used: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            used.add(node.func.id)

        elif isinstance(
            node.func,
            ast.Attribute,
        ):
            used.add(node.func.attr)

    assert used.isdisjoint(
        forbidden_calls
    )


def test_reader_repeats_tenant_predicate() -> None:
    source = _source(
        "app/agents/readers/"
        "ag_encerramento.py"
    )

    # Autorização inicial, construção do EXISTS autorizado e
    # reconfirmação final.
    assert (
        source.count(
            "Empresa.user_id == tenant_id"
        )
        >= 3
    )

    # O mesmo predicado EXISTS autorizado deve participar nas duas
    # consultas fiscais: insights e relatórios.
    assert (
        source.count(
            "empresa_autorizada_exists,"
        )
        >= 2
    )

    assert "with self._db.no_autoflush" in source
    assert "func.max(RelatorioAnalise.created_at)" in source


def test_legacy_hash_and_no_run_mission() -> None:
    path = (
        ROOT
        / "app"
        / "agents"
        / "ag_encerramento_agent.py"
    )

    digest = canonical_source_sha256(path)

    assert digest == LEGACY_SHA256

    tree = ast.parse(
        path.read_text(encoding="utf-8")
    )

    method_names = {
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

    assert (
        "execute_ag_encerramento_mission"
        not in source
    )
    assert (
        "app.agents.adapters.ag_encerramento"
        not in source
    )


def test_adapter_async_reader_sync() -> None:
    assert inspect.iscoroutinefunction(
        execute_ag_encerramento_mission
    )

    assert not inspect.iscoroutinefunction(
        AgEncerramentoReader.obter_snapshot
    )
