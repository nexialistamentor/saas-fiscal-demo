"""
app/agents/contracts/canonical.py — ADR-008 B14.0

Regras:
- canonical_json() é a única fonte canónica. Normaliza NFC recursivamente,
  detecta ciclos, colisões de chave após NFC, rejeita UUID não-v4,
  datetime sem timezone, Decimal não-finito, NaN/Infinity float,
  chaves não-string, tipos não suportados.
- canonical_sha256() = SHA256(canonical_json(data).encode("utf-8")).
- Nunca importa agentes, serviços, ORM, BD, HTTP ou providers.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# ---------------------------------------------------------------------------
# Normalização recursiva NFC com detecção de ciclos
# ---------------------------------------------------------------------------

def _normalizar_canonico(
    data: Any,
    _ativos: set[int] | None = None,
) -> Any:
    if _ativos is None:
        _ativos = set()

    if isinstance(data, str):
        return _nfc(data)

    if isinstance(data, (dict, list, tuple)):
        object_id = id(data)
        if object_id in _ativos:
            raise ValueError("Estrutura cíclica não permitida em canonical")
        _ativos.add(object_id)
        try:
            if isinstance(data, dict):
                normalizado: dict[str, Any] = {}
                for chave, valor in data.items():
                    if not isinstance(chave, str):
                        raise TypeError(
                            f"Chave de dicionário não textual em canonical: "
                            f"chave={chave!r} (tipo {type(chave).__name__})"
                        )
                    chave_nfc = _nfc(chave)
                    if chave_nfc in normalizado:
                        raise ValueError(
                            f"Colisão de chave após normalização NFC: {chave_nfc!r}"
                        )
                    normalizado[chave_nfc] = _normalizar_canonico(valor, _ativos)
                return normalizado
            # list ou tuple
            return [_normalizar_canonico(item, _ativos) for item in data]
        finally:
            _ativos.remove(object_id)

    return data


# ---------------------------------------------------------------------------
# Validação recursiva de chaves (defesa em profundidade, pós-normalização)
# ---------------------------------------------------------------------------

def _validar_chaves(data: Any, caminho: str = "") -> None:
    if isinstance(data, dict):
        for k, v in data.items():
            if not isinstance(k, str):
                raise TypeError(
                    f"Chave de dicionário não textual em canonical: "
                    f"chave={k!r} (tipo {type(k).__name__}) no caminho '{caminho}'"
                )
            _validar_chaves(v, caminho=f"{caminho}.{k}" if caminho else k)
    elif isinstance(data, (list, tuple)):
        for i, item in enumerate(data):
            _validar_chaves(item, caminho=f"{caminho}[{i}]")


# ---------------------------------------------------------------------------
# Serializador canónico
# ---------------------------------------------------------------------------

def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        if obj.utcoffset() is None:
            raise ValueError(
                f"datetime canónico deve possuir timezone — recebido: {obj!r}"
            )
        return obj.astimezone(timezone.utc).isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, UUID):
        if obj.version != 4:
            raise ValueError(
                f"UUID canónico deve ser versão 4 — recebido: versão {obj.version}"
            )
        return str(obj)
    if isinstance(obj, Decimal):
        if not obj.is_finite():
            raise ValueError(
                f"Decimal canónico deve ser finito — recebido: {obj!r}"
            )
        return str(obj)
    if hasattr(obj, "model_dump"):
        dumped = obj.model_dump(mode="python")
        return _normalizar_canonico(dumped)
    raise TypeError(f"Tipo não serializável em canonical: {type(obj)!r}")


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def canonical_json(data: Any) -> str:
    """
    Serializa data para JSON canónico.
    Garante: NFC recursivo, detecção de ciclos, colisões de chave após NFC,
    chaves string, ordenadas, sem espaços, ensure_ascii=False, allow_nan=False,
    datetime com tz (UTC), UUID v4, Decimal finito, Pydantic via mode=python.
    """
    data_norm = _normalizar_canonico(data)
    _validar_chaves(data_norm)
    return json.dumps(
        data_norm,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_json_default,
    )


def canonical_sha256(data: Any) -> str:
    """SHA256(canonical_json(data).encode('utf-8')) — 64 hex chars."""
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def build_mission_idempotency_key(
    *,
    mission_type: str,
    target_agent: str,
    scope: str,
    tenant_id: int | None,
    entity_type: str | None,
    entity_id: str | int | None,
    source_event_id: UUID | None,
    schedule_slot: str | None,
    source_request_id: str | None,
    idempotency_reference_at: datetime | None,
    contract_version: str = "1.0",
) -> str:
    """SHA256 canónico de idempotência de missão. Valida tipos e origens."""
    if source_event_id is not None:
        if not isinstance(source_event_id, UUID):
            raise TypeError(
                f"source_event_id deve ser UUID, não {type(source_event_id).__name__!r}"
            )
        if source_event_id.version != 4:
            raise ValueError(
                f"source_event_id deve ser UUID v4 — versão recebida: {source_event_id.version}"
            )
    if schedule_slot is not None and not isinstance(schedule_slot, str):
        raise TypeError("schedule_slot deve ser str ou None")
    if source_request_id is not None and not isinstance(source_request_id, str):
        raise TypeError("source_request_id deve ser str ou None")
    if idempotency_reference_at is not None and not isinstance(idempotency_reference_at, datetime):
        raise TypeError("idempotency_reference_at deve ser datetime ou None")

    schedule_slot_norm = (schedule_slot.strip() if schedule_slot is not None else None) or None
    source_request_id_norm = (source_request_id.strip() if source_request_id is not None else None) or None

    origens = [source_event_id, schedule_slot_norm, source_request_id_norm]
    presentes = [o for o in origens if o is not None]
    if len(presentes) != 1:
        raise ValueError(
            f"build_mission_idempotency_key exige exactamente uma origem não-vazia "
            f"(source_event_id UUID v4, schedule_slot ou source_request_id) — "
            f"{len(presentes)} fornecida(s)"
        )

    ref_at_iso: str | None = None
    if idempotency_reference_at is not None:
        if idempotency_reference_at.utcoffset() is None:
            raise ValueError("idempotency_reference_at deve possuir timezone")
        ref_at_iso = idempotency_reference_at.astimezone(timezone.utc).isoformat()

    payload: dict[str, Any] = {
        "mission_type": mission_type,
        "target_agent": target_agent,
        "scope": scope,
        "tenant_id": tenant_id,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id is not None else None,
        "source_event_id": str(source_event_id) if source_event_id is not None else None,
        "schedule_slot": schedule_slot_norm,
        "source_request_id": source_request_id_norm,
        "idempotency_reference_at": ref_at_iso,
        "contract_version": contract_version,
    }
    return canonical_sha256(payload)


def build_context_hash(context: dict) -> str:
    """SHA256 canónico do contexto da AgentMission. Exige dict."""
    if not isinstance(context, dict):
        raise TypeError("context deve ser dict")
    return canonical_sha256(context)
