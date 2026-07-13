"""
Contratos soberanos L3 dos agentes — ADR-008 B14.0.

Este pacote é puro: não importa agentes, ORM, BD, HTTP,
serviços operacionais ou providers LLM.
"""
from app.agents.contracts.canonical import (
    build_context_hash,
    build_mission_idempotency_key,
    canonical_json,
    canonical_sha256,
)
from app.agents.contracts.sanitization import (
    SanitizationResult,
    assert_context_sanitized,
    assert_result_sanitized,
)

__all__ = [
    "SanitizationResult",
    "assert_context_sanitized",
    "assert_result_sanitized",
    "build_context_hash",
    "build_mission_idempotency_key",
    "canonical_json",
    "canonical_sha256",
]
