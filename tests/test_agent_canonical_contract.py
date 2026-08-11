"""
tests/test_agent_canonical_contract.py — ADR-008 B14.0 Commit 2
"""
from __future__ import annotations

import hashlib
import inspect
import json
import unicodedata
import uuid as _uuid_mod
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

import app.agents.contracts.canonical as canonical_contract

from app.agents.contracts.canonical import (
    build_context_hash,
    build_mission_idempotency_key,
    canonical_json,
    canonical_sha256,
)


# ---------------------------------------------------------------------------
# canonical_json
# ---------------------------------------------------------------------------

class TestCanonicalJson:
    def test_chaves_ordenadas(self):
        assert canonical_json({"z": 1, "a": 2, "m": 3}) == '{"a":2,"m":3,"z":1}'

    def test_sem_espacos(self):
        assert " " not in canonical_json({"x": 1})

    def test_determinismo_ordem_diferente(self):
        d1 = {"scope": "tenant", "tenant_id": 42, "type": "M"}
        d2 = {"type": "M", "tenant_id": 42, "scope": "tenant"}
        assert canonical_json(d1) == canonical_json(d2)

    def test_unicode_nao_escapado(self):
        result = canonical_json({"nome": "São Paulo — Brasília"})
        assert "São Paulo" in result
        assert r"\u" not in result

    def test_unicode_nfc_composto_e_decomposto_mesmo_json(self):
        composto   = unicodedata.normalize("NFC", "café")
        decomposto = unicodedata.normalize("NFD", "café")
        assert canonical_json({"v": composto}) == canonical_json({"v": decomposto})

    def test_unicode_nfc_composto_e_decomposto_mesmo_hash(self):
        composto   = unicodedata.normalize("NFC", "café")
        decomposto = unicodedata.normalize("NFD", "café")
        assert canonical_sha256({"v": composto}) == canonical_sha256({"v": decomposto})

    def test_colisao_de_chaves_apos_nfc_bloqueada(self):
        chave_nfc = unicodedata.normalize("NFC", "café")
        chave_nfd = unicodedata.normalize("NFD", "café")
        with pytest.raises(ValueError, match="Colisão"):
            canonical_json({chave_nfc: 1, chave_nfd: 2})

    def test_nan_bloqueado(self):
        with pytest.raises((ValueError, TypeError)):
            canonical_json({"v": float("nan")})

    def test_infinity_bloqueado(self):
        with pytest.raises((ValueError, TypeError)):
            canonical_json({"v": float("inf")})

    def test_minus_infinity_bloqueado(self):
        with pytest.raises((ValueError, TypeError)):
            canonical_json({"v": float("-inf")})

    def test_decimal_nan_bloqueado(self):
        with pytest.raises(ValueError, match="finito"):
            canonical_json({"v": Decimal("NaN")})

    def test_decimal_infinity_bloqueado(self):
        with pytest.raises(ValueError, match="finito"):
            canonical_json({"v": Decimal("Infinity")})

    def test_decimal_minus_infinity_bloqueado(self):
        with pytest.raises(ValueError, match="finito"):
            canonical_json({"v": Decimal("-Infinity")})

    def test_datetime_com_tz_utc_serializado(self):
        dt = datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc)
        assert "2026-07-13T10:00:00+00:00" in canonical_json({"ts": dt})

    def test_datetime_sem_tz_bloqueado(self):
        with pytest.raises(ValueError, match="timezone"):
            canonical_json({"ts": datetime(2026, 7, 13, 10, 0, 0)})

    def test_datetime_offset_equivalente_mesmo_resultado(self):
        dt_utc    = datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc)
        dt_offset = datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone(timedelta(0)))
        assert canonical_json({"ts": dt_utc}) == canonical_json({"ts": dt_offset})

    def test_datetime_normalizado_para_utc(self):
        tz_plus3 = timezone(timedelta(hours=3))
        dt_plus3 = datetime(2026, 7, 13, 13, 0, 0, tzinfo=tz_plus3)
        dt_utc   = datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc)
        assert canonical_json({"ts": dt_plus3}) == canonical_json({"ts": dt_utc})

    def test_date_serializado(self):
        assert "2026-07-13" in canonical_json({"d": date(2026, 7, 13)})

    def test_uuid_v4_serializado(self):
        uid = UUID("12345678-1234-4234-b234-123456789012")
        assert "12345678-1234-4234-b234-123456789012" in canonical_json({"id": uid})

    def test_uuid_v1_bloqueado_no_canonical_json(self):
        uid_v1 = _uuid_mod.uuid1()
        with pytest.raises(ValueError, match="versão 4"):
            canonical_json({"id": uid_v1})

    def test_decimal_serializado_como_str(self):
        assert '"0.50"' in canonical_json({"c": Decimal("0.50")})

    def test_chave_nao_string_bloqueada(self):
        with pytest.raises(TypeError, match="Chave de dicionário não textual"):
            canonical_json({1: "valor"})

    def test_chave_nao_string_aninhada_bloqueada(self):
        with pytest.raises(TypeError, match="Chave de dicionário não textual"):
            canonical_json({"outer": {True: "val"}})

    def test_tipo_nao_suportado_levanta_type_error(self):
        with pytest.raises(TypeError, match="Tipo não serializável"):
            canonical_json({"obj": object()})

    def test_modelo_pydantic_com_datetime_igual_ao_dict_directo(self):
        from pydantic import BaseModel

        class Ev(BaseModel):
            ts: datetime

        dt = datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc)
        assert canonical_json(Ev(ts=dt)) == canonical_json({"ts": dt})

    def test_modelo_pydantic_chaves_validas(self):
        from pydantic import BaseModel

        class Mini(BaseModel):
            x: int

        assert '"x":99' in canonical_json({"m": Mini(x=99)})

    def test_modelo_pydantic_chave_nao_string_bloqueada(self):
        from pydantic import BaseModel

        class Mini(BaseModel):
            payload: dict[Any, str]

        with pytest.raises(TypeError, match="Chave de dicionário não textual"):
            canonical_json(Mini(payload={1: "valor"}))

    def test_estrutura_ciclica_bloqueada(self):
        data: dict = {}
        data["self"] = data
        with pytest.raises(ValueError, match="cíclica"):
            canonical_json(data)

    def test_estrutura_ciclica_em_lista_bloqueada(self):
        lst: list = []
        lst.append(lst)
        with pytest.raises(ValueError, match="cíclica"):
            canonical_json({"v": lst})


# ---------------------------------------------------------------------------
# canonical_sha256
# ---------------------------------------------------------------------------

class TestCanonicalSha256:
    def test_formato_64_hex(self):
        h = canonical_sha256({"a": 1})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_determinismo(self):
        data = {"mission_type": "M", "scope": "global"}
        assert canonical_sha256(data) == canonical_sha256(data)

    def test_dados_diferentes_hash_diferente(self):
        assert canonical_sha256({"a": 1}) != canonical_sha256({"a": 2})

    def test_compativel_com_hashlib(self):
        data = {"x": 1}
        raw = json.dumps(
            {"x": 1}, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        esperado = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert canonical_sha256(data) == esperado


# ---------------------------------------------------------------------------
# build_mission_idempotency_key
# ---------------------------------------------------------------------------

_EVT_ID = uuid4()

_BASE = dict(
    mission_type="MONITORAR_ERROS",
    target_agent="agent_erro_operacional",
    scope="tenant",
    tenant_id=42,
    entity_type=None,
    entity_id=None,
    source_event_id=_EVT_ID,
    schedule_slot=None,
    source_request_id=None,
    idempotency_reference_at=None,
    contract_version="1.0",
)


class TestBuildMissionIdempotencyKey:
    def test_formato_64_hex(self):
        k = build_mission_idempotency_key(**_BASE)
        assert len(k) == 64 and all(c in "0123456789abcdef" for c in k)

    def test_determinismo(self):
        assert build_mission_idempotency_key(**_BASE) == build_mission_idempotency_key(**_BASE)

    def test_source_event_id_uuid_diferente_chave_diferente(self):
        k1 = build_mission_idempotency_key(**_BASE)
        k2 = build_mission_idempotency_key(**{**_BASE, "source_event_id": uuid4()})
        assert k1 != k2

    def test_source_event_id_string_bloqueado(self):
        with pytest.raises(TypeError, match="UUID"):
            build_mission_idempotency_key(**{**_BASE, "source_event_id": "not-a-uuid"})

    def test_source_event_id_uuid_v1_bloqueado(self):
        with pytest.raises(ValueError, match="UUID v4"):
            build_mission_idempotency_key(**{**_BASE, "source_event_id": _uuid_mod.uuid1()})

    def test_schedule_slot_tipo_errado_bloqueado(self):
        with pytest.raises(TypeError, match="schedule_slot deve ser str"):
            build_mission_idempotency_key(**{**_BASE, "source_event_id": None, "schedule_slot": 123})

    def test_source_request_id_tipo_errado_bloqueado(self):
        with pytest.raises(TypeError, match="source_request_id deve ser str"):
            build_mission_idempotency_key(**{**_BASE, "source_event_id": None, "source_request_id": 123})

    def test_idempotency_reference_at_string_bloqueado(self):
        with pytest.raises(TypeError, match="idempotency_reference_at deve ser datetime"):
            build_mission_idempotency_key(**{**_BASE, "idempotency_reference_at": "2026-07-01"})

    def test_schedule_slot_diferente_chave_diferente(self):
        args = {**_BASE, "source_event_id": None, "schedule_slot": "2026-W28"}
        k1 = build_mission_idempotency_key(**args)
        k2 = build_mission_idempotency_key(**{**args, "schedule_slot": "2026-W29"})
        assert k1 != k2

    def test_schedule_slot_vazio_conta_como_ausente(self):
        for v in ["", "   "]:
            with pytest.raises(ValueError, match="exactamente uma origem"):
                build_mission_idempotency_key(**{**_BASE, "source_event_id": None, "schedule_slot": v})

    def test_source_request_id_remove_espacos_externos(self):
        base = {**_BASE, "source_event_id": None}
        k1 = build_mission_idempotency_key(**{**base, "source_request_id": "req-1"})
        k2 = build_mission_idempotency_key(**{**base, "source_request_id": "  req-1  "})
        assert k1 == k2

    def test_schedule_slot_remove_espacos_externos(self):
        base = {**_BASE, "source_event_id": None}
        k1 = build_mission_idempotency_key(**{**base, "schedule_slot": "2026-W28"})
        k2 = build_mission_idempotency_key(**{**base, "schedule_slot": "  2026-W28  "})
        assert k1 == k2

    def test_source_request_id_whitespace_conta_como_ausente(self):
        with pytest.raises(ValueError, match="exactamente uma origem"):
            build_mission_idempotency_key(**{**_BASE, "source_event_id": None, "source_request_id": "   "})

    def test_target_agent_diferente_chave_diferente(self):
        k1 = build_mission_idempotency_key(**_BASE)
        k2 = build_mission_idempotency_key(**{**_BASE, "target_agent": "auditor_fiscal_agent"})
        assert k1 != k2

    def test_tenant_id_diferente_chave_diferente(self):
        k1 = build_mission_idempotency_key(**_BASE)
        k2 = build_mission_idempotency_key(**{**_BASE, "tenant_id": 99})
        assert k1 != k2

    def test_entity_id_int_str_equivalentes(self):
        k1 = build_mission_idempotency_key(**{**_BASE, "entity_id": 1})
        k2 = build_mission_idempotency_key(**{**_BASE, "entity_id": "1"})
        assert k1 == k2

    def test_idempotency_reference_at_datetime_utc(self):
        dt = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
        k = build_mission_idempotency_key(**{**_BASE, "idempotency_reference_at": dt})
        assert len(k) == 64

    def test_idempotency_reference_at_sem_tz_bloqueado(self):
        with pytest.raises(ValueError, match="timezone"):
            build_mission_idempotency_key(**{**_BASE, "idempotency_reference_at": datetime(2026, 7, 1)})

    def test_idempotency_reference_at_diferente_chave_diferente(self):
        dt1 = datetime(2026, 7, 1, tzinfo=timezone.utc)
        dt2 = datetime(2026, 8, 1, tzinfo=timezone.utc)
        k1 = build_mission_idempotency_key(**{**_BASE, "idempotency_reference_at": dt1})
        k2 = build_mission_idempotency_key(**{**_BASE, "idempotency_reference_at": dt2})
        assert k1 != k2

    def test_reference_at_normativo_nao_e_parametro(self):
        sig = inspect.signature(build_mission_idempotency_key)
        assert "reference_at" not in sig.parameters

    def test_nenhuma_origem(self):
        with pytest.raises(ValueError, match="exactamente uma origem"):
            build_mission_idempotency_key(**{**_BASE, "source_event_id": None})

    def test_duas_origens(self):
        with pytest.raises(ValueError, match="exactamente uma origem"):
            build_mission_idempotency_key(**{**_BASE, "schedule_slot": "2026-W28"})

    def test_tres_origens(self):
        with pytest.raises(ValueError, match="exactamente uma origem"):
            build_mission_idempotency_key(**{**_BASE, "schedule_slot": "2026-W28", "source_request_id": "req-1"})

    def test_exactamente_uma_origem_valida(self):
        for extra in [
            {"source_event_id": uuid4(), "schedule_slot": None, "source_request_id": None},
            {"source_event_id": None, "schedule_slot": "2026-W28", "source_request_id": None},
            {"source_event_id": None, "schedule_slot": None, "source_request_id": "req-1"},
        ]:
            k = build_mission_idempotency_key(**{**_BASE, **extra})
            assert len(k) == 64



# ---------------------------------------------------------------------------
# build_effect_idempotency_key
# ---------------------------------------------------------------------------

_EFFECT_BASE = dict(
    mission_idempotency_key="a" * 64,
    effect_type="alert",
    agent_id="normative_watchdog",
    effect_payload={
        "code": "TESTE_PATRULHA",
        "severity": "baixo",
        "message": "alerta sintetico de patrulhamento",
        "evidence_refs": [],
    },
    contract_version="1.0",
)


class TestBuildEffectIdempotencyKey:
    def _builder(self):
        builder = getattr(
            canonical_contract,
            "build_effect_idempotency_key",
            None,
        )
        assert callable(builder), (
            "canonical.py ainda nao expoe "
            "build_effect_idempotency_key"
        )
        return builder

    def test_formato_64_hex(self):
        key = self._builder()(**_EFFECT_BASE)
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_determinismo(self):
        builder = self._builder()
        assert builder(**_EFFECT_BASE) == builder(**_EFFECT_BASE)

    def test_ordem_do_payload_nao_altera_chave(self):
        builder = self._builder()
        payload_reordenado = {
            "message": "alerta sintetico de patrulhamento",
            "evidence_refs": [],
            "severity": "baixo",
            "code": "TESTE_PATRULHA",
        }
        assert builder(**_EFFECT_BASE) == builder(
            **{**_EFFECT_BASE, "effect_payload": payload_reordenado}
        )

    def test_missao_logica_diferente_altera_chave(self):
        builder = self._builder()
        outra = builder(
            **{
                **_EFFECT_BASE,
                "mission_idempotency_key": "b" * 64,
            }
        )
        assert builder(**_EFFECT_BASE) != outra

    def test_payload_diferente_altera_chave(self):
        builder = self._builder()
        outro_payload = {
            **_EFFECT_BASE["effect_payload"],
            "message": "outro alerta",
        }
        assert builder(**_EFFECT_BASE) != builder(
            **{**_EFFECT_BASE, "effect_payload": outro_payload}
        )

    def test_agent_diferente_altera_chave(self):
        builder = self._builder()
        assert builder(**_EFFECT_BASE) != builder(
            **{**_EFFECT_BASE, "agent_id": "outro_agente"}
        )

    def test_tipo_de_efeito_diferente_altera_chave(self):
        builder = self._builder()
        assert builder(**_EFFECT_BASE) != builder(
            **{**_EFFECT_BASE, "effect_type": "action"}
        )

    def test_contract_version_diferente_altera_chave(self):
        builder = self._builder()
        assert builder(**_EFFECT_BASE) != builder(
            **{**_EFFECT_BASE, "contract_version": "2.0"}
        )

    def test_mission_idempotency_key_invalida_e_bloqueada(self):
        builder = self._builder()
        with pytest.raises(ValueError):
            builder(
                **{
                    **_EFFECT_BASE,
                    "mission_idempotency_key": "invalida",
                }
            )

    @pytest.mark.parametrize("campo", ["effect_type", "agent_id"])
    def test_identidade_textual_vazia_e_bloqueada(self, campo):
        builder = self._builder()
        with pytest.raises(ValueError):
            builder(**{**_EFFECT_BASE, campo: "   "})

    def test_effect_payload_exige_dict(self):
        builder = self._builder()
        with pytest.raises(TypeError):
            builder(**{**_EFFECT_BASE, "effect_payload": ["invalido"]})



# ---------------------------------------------------------------------------
# build_context_hash
# ---------------------------------------------------------------------------

class TestBuildContextHash:
    def test_formato_64_hex(self):
        h = build_context_hash({"ano": 2026})
        assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)

    def test_determinismo(self):
        ctx = {"scope": "tenant", "tenant_id": 1}
        assert build_context_hash(ctx) == build_context_hash(ctx)

    def test_diferente_hash_diferente(self):
        assert build_context_hash({"a": 1}) != build_context_hash({"a": 2})

    def test_suporta_datetime_com_tz(self):
        assert len(build_context_hash({"ts": datetime(2026, 7, 13, tzinfo=timezone.utc)})) == 64

    def test_datetime_sem_tz_bloqueado(self):
        with pytest.raises(ValueError, match="timezone"):
            build_context_hash({"ts": datetime(2026, 7, 13)})

    def test_uuid_v1_bloqueado(self):
        with pytest.raises(ValueError, match="versão 4"):
            build_context_hash({"id": _uuid_mod.uuid1()})

    def test_suporta_uuid_v4(self):
        assert len(build_context_hash({"id": uuid4()})) == 64

    def test_suporta_decimal(self):
        assert len(build_context_hash({"v": Decimal("123.45")})) == 64

    def test_contexto_vazio_estavel(self):
        assert build_context_hash({}) == build_context_hash({})

    def test_build_context_hash_exige_dict(self):
        with pytest.raises(TypeError, match="context deve ser dict"):
            build_context_hash(["invalido"])

    def test_build_context_hash_exige_dict_tuple(self):
        with pytest.raises(TypeError, match="context deve ser dict"):
            build_context_hash(("a", "b"))
