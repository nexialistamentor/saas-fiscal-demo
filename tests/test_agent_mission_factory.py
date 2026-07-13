"""
Testes da MissionFactory soberana — ADR-008 B14.0/B14.1.

Prova o caminho operacional obrigatório de criação de AgentMission:
escopo, sanitização, autoridade de fontes, BudgetPolicy, hashes,
idempotência, UUIDs, correlação e temporalidade.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

import app.agents.mission_factory as mission_factory_module
from app.agents.contracts.canonical import (
    build_context_hash,
    build_mission_idempotency_key,
)
from app.agents.contracts.mission import AgentMission
from app.agents.contracts.shared import BudgetPolicy, SourceRef
from app.agents.mission_factory import create_agent_mission
from app.schemas.source_authority_schema import SourceAuthorityResult


UTC_NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def _kwargs_base(**overrides: object) -> dict:
    kwargs: dict = {
        "mission_type": "auditar_documento",
        "target_agent": "auditor_fiscal",
        "context": {"evento": "teste", "valor": 10},
        "context_schema": "AgentAuditContext",
        "output_schema": "AgentAuditResult",
        "scope": "global",
        "requested_by": "system",
        "authority_level": "leitura",
        "execution_mode": "dry_run",
        "source_request_id": "request-001",
        "created_at": UTC_NOW,
    }
    kwargs.update(overrides)
    return kwargs


def _resultado_fonte(
    *,
    fonte_id: str,
    uso_pretendido: str,
    permitido: bool,
    motivo: str = "resultado controlado",
) -> SourceAuthorityResult:
    return SourceAuthorityResult(
        permitido=permitido,
        fonte_id=fonte_id,
        uso_pretendido=uso_pretendido,
        motivo=motivo,
    )


# ---------------------------------------------------------------------------
# Criação base
# ---------------------------------------------------------------------------

def test_factory_devolve_agent_mission_validada() -> None:
    mission = create_agent_mission(**_kwargs_base())

    assert isinstance(mission, AgentMission)
    assert mission.contract_version == "1.0"
    assert mission.mission_type == "auditar_documento"
    assert mission.target_agent == "auditor_fiscal"
    assert mission.created_at == UTC_NOW


def test_factory_gera_mission_id_uuid4() -> None:
    mission = create_agent_mission(**_kwargs_base())

    assert isinstance(mission.mission_id, UUID)
    assert mission.mission_id.version == 4


def test_factory_gera_correlation_id_uuid4_por_omissao() -> None:
    mission = create_agent_mission(**_kwargs_base())

    assert isinstance(mission.correlation_id, UUID)
    assert mission.correlation_id.version == 4


def test_factory_propaga_correlation_id_fornecido() -> None:
    correlation_id = uuid4()

    mission = create_agent_mission(
        **_kwargs_base(correlation_id=correlation_id)
    )

    assert mission.correlation_id == correlation_id


def test_factory_gera_ids_novos_em_criacoes_distintas() -> None:
    first = create_agent_mission(**_kwargs_base())
    second = create_agent_mission(**_kwargs_base())

    assert first.mission_id != second.mission_id
    assert first.correlation_id != second.correlation_id


def test_factory_usa_created_at_utc_actual_quando_omitido() -> None:
    kwargs = _kwargs_base()
    kwargs.pop("created_at")

    before = datetime.now(timezone.utc)
    mission = create_agent_mission(**kwargs)
    after = datetime.now(timezone.utc)

    assert before <= mission.created_at <= after
    assert mission.created_at.utcoffset() == timedelta(0)


def test_factory_propaga_campos_opcionais() -> None:
    parent_mission_id = uuid4()
    reference_at = UTC_NOW + timedelta(hours=1)
    deadline = UTC_NOW + timedelta(hours=2)

    mission = create_agent_mission(
        **_kwargs_base(
            context_version="2.0",
            output_version="3.0",
            actor_id="user-001",
            parent_mission_id=parent_mission_id,
            agent_version_required="4.5.6",
            priority="alta",
            deadline=deadline,
            reference_at=reference_at,
        )
    )

    assert mission.context_version == "2.0"
    assert mission.output_version == "3.0"
    assert mission.actor_id == "user-001"
    assert mission.parent_mission_id == parent_mission_id
    assert mission.agent_version_required == "4.5.6"
    assert mission.priority == "alta"
    assert mission.deadline == deadline
    assert mission.reference_at == reference_at


# ---------------------------------------------------------------------------
# Escopo
# ---------------------------------------------------------------------------

def test_factory_scope_global_rejeita_tenant() -> None:
    with pytest.raises(ValueError):
        create_agent_mission(
            **_kwargs_base(tenant_id=10)
        )


def test_factory_scope_tenant_exige_tenant_id() -> None:
    with pytest.raises(ValueError):
        create_agent_mission(
            **_kwargs_base(scope="tenant")
        )


def test_factory_scope_tenant_aceita_tenant_id() -> None:
    mission = create_agent_mission(
        **_kwargs_base(scope="tenant", tenant_id=10)
    )

    assert mission.scope == "tenant"
    assert mission.tenant_id == 10


@pytest.mark.parametrize(
    "missing_field",
    ["tenant_id", "entity_type", "entity_id"],
)
def test_factory_scope_documento_exige_campos(
    missing_field: str,
) -> None:
    values = {
        "scope": "documento",
        "tenant_id": 10,
        "entity_type": "nfe",
        "entity_id": "doc-001",
    }
    values[missing_field] = None

    with pytest.raises(ValueError):
        create_agent_mission(
            **_kwargs_base(**values)
        )


def test_factory_scope_documento_aceita_campos_completos() -> None:
    mission = create_agent_mission(
        **_kwargs_base(
            scope="documento",
            tenant_id=10,
            entity_type="nfe",
            entity_id="doc-001",
        )
    )

    assert mission.scope == "documento"
    assert mission.entity_type == "nfe"
    assert mission.entity_id == "doc-001"


def test_factory_scope_utilizador_exige_actor_id() -> None:
    with pytest.raises(ValueError):
        create_agent_mission(
            **_kwargs_base(scope="utilizador")
        )


def test_factory_scope_utilizador_aceita_actor_id() -> None:
    mission = create_agent_mission(
        **_kwargs_base(
            scope="utilizador",
            actor_id="user-001",
        )
    )

    assert mission.actor_id == "user-001"


def test_factory_rejeita_scope_desconhecido() -> None:
    with pytest.raises(ValueError):
        create_agent_mission(
            **_kwargs_base(scope="desconhecido")
        )


# ---------------------------------------------------------------------------
# Sanitização de contexto
# ---------------------------------------------------------------------------

def test_factory_bloqueia_email_no_contexto() -> None:
    with pytest.raises(ValueError, match="SanitizationGuard"):
        create_agent_mission(
            **_kwargs_base(
                context={"contacto": "pessoa@example.com"}
            )
        )


def test_factory_bloqueia_token_em_campo_aninhado() -> None:
    with pytest.raises(ValueError, match="SanitizationGuard"):
        create_agent_mission(
            **_kwargs_base(
                context={
                    "nested": {
                        "authorization": "Bearer abcdefghijklmnop",
                    }
                }
            )
        )


def test_factory_bloqueia_contexto_raiz_nao_dict() -> None:
    with pytest.raises(ValueError):
        create_agent_mission(
            **_kwargs_base(context=["nao", "dict"])
        )


def test_factory_aceita_contexto_limpo() -> None:
    context = {
        "regra_id": "REGRA-001",
        "valor": Decimal("10.50"),
    }

    mission = create_agent_mission(
        **_kwargs_base(context=context)
    )

    assert mission.context == context


# ---------------------------------------------------------------------------
# Hash e idempotência
# ---------------------------------------------------------------------------

def test_factory_calcula_context_hash() -> None:
    context = {"a": 1, "nested": {"b": "texto"}}

    mission = create_agent_mission(
        **_kwargs_base(context=context)
    )

    assert mission.context_hash == build_context_hash(context)


def test_factory_calcula_idempotency_key() -> None:
    kwargs = _kwargs_base(
        scope="tenant",
        tenant_id=10,
    )

    mission = create_agent_mission(**kwargs)

    expected = build_mission_idempotency_key(
        mission_type=kwargs["mission_type"],
        target_agent=kwargs["target_agent"],
        scope=kwargs["scope"],
        tenant_id=kwargs["tenant_id"],
        entity_type=None,
        entity_id=None,
        source_event_id=None,
        schedule_slot=None,
        source_request_id=kwargs["source_request_id"],
        idempotency_reference_at=None,
        contract_version="1.0",
    )
    assert mission.idempotency_key == expected


def test_factory_mesma_missao_estavel_produz_mesma_idempotencia() -> None:
    first = create_agent_mission(**_kwargs_base())
    second = create_agent_mission(**_kwargs_base())

    assert first.mission_id != second.mission_id
    assert first.idempotency_key == second.idempotency_key


def test_factory_reference_at_nao_altera_idempotencia() -> None:
    first = create_agent_mission(**_kwargs_base())
    second = create_agent_mission(
        **_kwargs_base(
            reference_at=UTC_NOW + timedelta(days=1)
        )
    )

    assert first.idempotency_key == second.idempotency_key


def test_factory_idempotency_reference_at_altera_chave() -> None:
    first = create_agent_mission(**_kwargs_base())
    second = create_agent_mission(
        **_kwargs_base(
            idempotency_reference_at=(
                UTC_NOW + timedelta(days=1)
            )
        )
    )

    assert first.idempotency_key != second.idempotency_key


def test_factory_normaliza_origem_textual_na_idempotencia() -> None:
    first = create_agent_mission(
        **_kwargs_base(source_request_id="request-001")
    )
    second = create_agent_mission(
        **_kwargs_base(source_request_id="  request-001  ")
    )

    assert second.source_request_id == "request-001"
    assert first.idempotency_key == second.idempotency_key


# ---------------------------------------------------------------------------
# Origem única
# ---------------------------------------------------------------------------

def test_factory_exige_exactamente_uma_origem() -> None:
    with pytest.raises(ValueError):
        create_agent_mission(
            **_kwargs_base(source_request_id=None)
        )


def test_factory_rejeita_multiplas_origens() -> None:
    with pytest.raises(ValueError):
        create_agent_mission(
            **_kwargs_base(source_event_id=uuid4())
        )


def test_factory_aceita_source_event_id_uuid4() -> None:
    source_event_id = uuid4()

    mission = create_agent_mission(
        **_kwargs_base(
            source_request_id=None,
            source_event_id=source_event_id,
        )
    )

    assert mission.source_event_id == source_event_id


def test_factory_aceita_schedule_slot() -> None:
    mission = create_agent_mission(
        **_kwargs_base(
            source_request_id=None,
            schedule_slot="2026-07-13T12:00Z",
        )
    )

    assert mission.schedule_slot == "2026-07-13T12:00Z"


# ---------------------------------------------------------------------------
# Fontes e SourceAuthorityGuard
# ---------------------------------------------------------------------------

def test_factory_valida_cada_fonte_no_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[tuple[str, str]] = []

    def fake_verificar(request):
        chamadas.append(
            (request.fonte_id, request.uso_pretendido)
        )
        return _resultado_fonte(
            fonte_id=request.fonte_id,
            uso_pretendido=request.uso_pretendido,
            permitido=True,
        )

    monkeypatch.setattr(
        mission_factory_module,
        "verificar_fonte",
        fake_verificar,
    )

    sources = [
        SourceRef(
            fonte_id="fonte-001",
            uso_pretendido="contexto_llm",
        ),
        {
            "fonte_id": "fonte-002",
            "uso_pretendido": "apoiar_explicacao_ux",
        },
    ]

    mission = create_agent_mission(
        **_kwargs_base(sources=sources)
    )

    assert chamadas == [
        ("fonte-001", "contexto_llm"),
        ("fonte-002", "apoiar_explicacao_ux"),
    ]
    assert [source.fonte_id for source in mission.sources] == [
        "fonte-001",
        "fonte-002",
    ]


def test_factory_bloqueia_fonte_nao_permitida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_verificar(request):
        return _resultado_fonte(
            fonte_id=request.fonte_id,
            uso_pretendido=request.uso_pretendido,
            permitido=False,
            motivo="fonte bloqueada para este uso",
        )

    monkeypatch.setattr(
        mission_factory_module,
        "verificar_fonte",
        fake_verificar,
    )

    with pytest.raises(
        ValueError,
        match="SourceAuthorityGuard bloqueou",
    ):
        create_agent_mission(
            **_kwargs_base(
                sources=[
                    {
                        "fonte_id": "fonte-bloqueada",
                        "uso_pretendido": "fundamentar_decisao",
                    }
                ]
            )
        )


def test_factory_sem_fontes_nao_chama_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def falhar_se_chamado(request):
        raise AssertionError("guard não deveria ser chamado")

    monkeypatch.setattr(
        mission_factory_module,
        "verificar_fonte",
        falhar_se_chamado,
    )

    mission = create_agent_mission(
        **_kwargs_base(sources=None)
    )

    assert mission.sources == []


def test_factory_rejeita_source_ref_invalida() -> None:
    with pytest.raises(ValidationError):
        create_agent_mission(
            **_kwargs_base(
                sources=[
                    {
                        "fonte_id": "fonte-001",
                        "uso_pretendido": "uso_invalido",
                    }
                ]
            )
        )


# ---------------------------------------------------------------------------
# BudgetPolicy
# ---------------------------------------------------------------------------

def test_factory_aplica_budget_policy_default() -> None:
    mission = create_agent_mission(**_kwargs_base())

    assert mission.budget_policy == BudgetPolicy()


def test_factory_aceita_budget_policy_modelo() -> None:
    policy = BudgetPolicy(
        allow_llm=True,
        allowed_providers=["local_model"],
        max_calls=1,
        max_input_chars=1000,
        max_output_tokens=100,
        max_cost=Decimal("0.50"),
    )

    mission = create_agent_mission(
        **_kwargs_base(budget_policy=policy)
    )

    assert mission.budget_policy == policy


def test_factory_normaliza_budget_policy_dict() -> None:
    mission = create_agent_mission(
        **_kwargs_base(
            budget_policy={
                "allow_llm": True,
                "allowed_providers": ["local_model"],
                "max_calls": 2,
                "max_input_chars": 2000,
                "max_output_tokens": 200,
                "max_cost": "1.25",
            }
        )
    )

    assert mission.budget_policy.allow_llm is True
    assert mission.budget_policy.max_cost == Decimal("1.25")


def test_factory_rejeita_budget_policy_incoerente() -> None:
    with pytest.raises(ValidationError):
        create_agent_mission(
            **_kwargs_base(
                budget_policy={
                    "allow_llm": False,
                    "max_calls": 1,
                }
            )
        )


def test_factory_rejeita_float_em_max_cost() -> None:
    with pytest.raises(ValidationError):
        create_agent_mission(
            **_kwargs_base(
                budget_policy={
                    "allow_llm": True,
                    "allowed_providers": ["local_model"],
                    "max_calls": 1,
                    "max_input_chars": 1000,
                    "max_output_tokens": 100,
                    "max_cost": 0.5,
                }
            )
        )


# ---------------------------------------------------------------------------
# Autoridade e temporalidade
# ---------------------------------------------------------------------------

def test_factory_elevada_activa_exige_ratificacao() -> None:
    with pytest.raises(ValidationError):
        create_agent_mission(
            **_kwargs_base(
                authority_level="elevada",
                execution_mode="activo",
            )
        )


def test_factory_elevada_activa_aceita_ratificacao_completa() -> None:
    mission = create_agent_mission(
        **_kwargs_base(
            authority_level="elevada",
            execution_mode="activo",
            ratification_id="rat-001",
            authorized_by="admin-001",
            authorization_role="autoridade_final",
        )
    )

    assert mission.ratification_id == "rat-001"
    assert mission.authorized_by == "admin-001"
    assert mission.authorization_role == "autoridade_final"


def test_factory_elevada_dry_run_dispensa_ratificacao() -> None:
    mission = create_agent_mission(
        **_kwargs_base(
            authority_level="elevada",
            execution_mode="dry_run",
        )
    )

    assert mission.ratification_id is None


def test_factory_rejeita_created_at_nao_utc() -> None:
    non_utc = datetime(
        2026,
        7,
        13,
        9,
        0,
        tzinfo=timezone(timedelta(hours=-3)),
    )

    with pytest.raises(ValidationError):
        create_agent_mission(
            **_kwargs_base(created_at=non_utc)
        )


def test_factory_rejeita_deadline_anterior() -> None:
    with pytest.raises(ValidationError):
        create_agent_mission(
            **_kwargs_base(
                deadline=UTC_NOW - timedelta(seconds=1)
            )
        )
