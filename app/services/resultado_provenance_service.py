"""Proveniência estrutural e integridade de resultados persistidos.

V1 deliberadamente NÃO concede autoridade MEI canônica.
O fingerprint SHA-256 comprova integridade do payload persistido, não autoria.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import string
from typing import Any


PROVENANCE_KEY = "_resultado_provenance"
SCHEMA_VERSION = "RESULTADO_PROVENANCE_V1"
INTEGRITY_PROFILE = "SHA256_FINGERPRINT_V1"
_MEI_AUTHORITY_NONE = "NONE"


class ResultadoProvenanceError(ValueError):
    """Resultado persistido não possui proveniência/integridade publicável."""


def _producer_id_valido(producer_id: str) -> bool:
    return (
        isinstance(producer_id, str)
        and producer_id == producer_id.strip()
        and producer_id.startswith("app.")
        and len(producer_id) > len("app.")
    )


def fingerprint_resultado_json(resultado: dict[str, Any]) -> str:
    """SHA-256 determinístico do JSON persistido; integridade, não autoridade."""
    if not isinstance(resultado, dict):
        raise ResultadoProvenanceError("resultado_json deve ser dict")
    encoded = json.dumps(
        resultado,
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def selar_resultado_nao_mei(
    resultado: dict[str, Any],
    *,
    producer_id: str,
) -> dict[str, Any]:
    """Sela resultado V1 explicitamente SEM autoridade MEI canônica."""
    if not isinstance(resultado, dict):
        raise ResultadoProvenanceError("resultado deve ser dict")
    if PROVENANCE_KEY in resultado:
        raise ResultadoProvenanceError("chave de proveniência reservada")
    if not _producer_id_valido(producer_id):
        raise ResultadoProvenanceError("producer_id inválido")

    sealed = copy.deepcopy(resultado)
    sealed[PROVENANCE_KEY] = {
        "schema_version": SCHEMA_VERSION,
        "producer_id": producer_id,
        "mei_authority": _MEI_AUTHORITY_NONE,
        "integrity_profile": INTEGRITY_PROFILE,
    }
    return sealed


def _fingerprint_formato_valido(fingerprint: object) -> bool:
    return (
        isinstance(fingerprint, str)
        and len(fingerprint) == 64
        and fingerprint == fingerprint.lower()
        and all(char in string.hexdigits.lower() for char in fingerprint)
    )


def verificar_resultado_persistido(relatorio: object) -> dict[str, Any]:
    """Verifica envelope + fingerprint e devolve somente o payload de negócio."""
    resultado = getattr(relatorio, "resultado_json", None)
    fingerprint = getattr(relatorio, "fingerprint", None)

    if resultado is None:
        if fingerprint not in (None, ""):
            raise ResultadoProvenanceError(
                "fingerprint presente sem resultado_json"
            )
        return {}

    if not isinstance(resultado, dict):
        raise ResultadoProvenanceError("resultado_json persistido não é dict")

    if not _fingerprint_formato_valido(fingerprint):
        raise ResultadoProvenanceError("fingerprint ausente ou inválido")

    expected = fingerprint_resultado_json(resultado)
    if not hmac.compare_digest(fingerprint, expected):
        raise ResultadoProvenanceError("fingerprint divergente")

    provenance = resultado.get(PROVENANCE_KEY)
    if not isinstance(provenance, dict):
        raise ResultadoProvenanceError("proveniência ausente")

    expected_keys = {
        "schema_version",
        "producer_id",
        "mei_authority",
        "integrity_profile",
    }
    if set(provenance) != expected_keys:
        raise ResultadoProvenanceError("envelope de proveniência inválido")
    if provenance.get("schema_version") != SCHEMA_VERSION:
        raise ResultadoProvenanceError("schema de proveniência desconhecido")
    if provenance.get("integrity_profile") != INTEGRITY_PROFILE:
        raise ResultadoProvenanceError("perfil de integridade desconhecido")
    if not _producer_id_valido(provenance.get("producer_id")):
        raise ResultadoProvenanceError("producer_id persistido inválido")

    # V1 nunca aceita autodeclaração de autoridade MEI.
    if provenance.get("mei_authority") != _MEI_AUTHORITY_NONE:
        raise ResultadoProvenanceError("autoridade MEI não comprovada")

    payload = copy.deepcopy(resultado)
    payload.pop(PROVENANCE_KEY, None)
    return payload
